"""
Cabrillo (HF) synthetic contest log fixture generator.

Owned by: format-specialist's Cabrillo-fixture-generation agent.
Sibling to edi_fixture_generator.py -- do not merge EDI-specific logic into
this file; see generate_dummy_logs.py's dispatcher, which picks this module
whenever rules.contest_log_format == 'CABRILLO'.

This module builds a deterministic (seeded) set of Cabrillo log files
exercising the cross-check pipeline described in:
  specs/05-format-cabrillo-spec.md
  specs/06-scoring-spec.md
  specs/07-crosscheck-spec.md
  specs/09-known-gaps-and-deviations.md

Design principle (matches edi_fixture_generator.py): every "genuine"
confirmable QSO pair is built by construction (one side generated, the other
derived as its exact mirror) -- never as two independently-random lines
hoped to match. GAP-005b matters here specifically: Cabrillo's compare_qso
compares nr_sent/nr_recv as raw strings (not int()-cast like EDI), so mirrored
exchange values must be copied as identical strings, not merely numerically
equal ('001' != '1' for Cabrillo).

Written first against test_logs/rules_hf_dracula.config (DRACULA custom
scoring: special-station/YO-YO/YO-nonYO/non-YO-same-DXCC/non-YO-diff-DXCC
branches, per-band multiplier). Built generically against the live rules
object (rules.contest_band/_category/_special_callsign/...), so re-running
against a different Cabrillo rules file should mostly work -- extend the
scenario functions below as new contests/edge cases are requested.
"""
import os
import random
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Low-level Cabrillo rendering helpers
# ---------------------------------------------------------------------------

def qso_line(freq: str, mode: str, date: str, hour: str, call1: str, rst1: str, exch1: str,
             call2: str, rst2: str, exch2: str) -> str:
    """Render one Cabrillo QSO line (11-field standard shape, CAB-005).

    `exch1`/`exch2` may themselves contain an embedded space (13-field
    serial+county variant, CAB-005) -- the line is still well-formed since
    the regex splits on whitespace generically.
    """
    return 'QSO: {} {} {} {} {} {} {} {} {} {}'.format(
        freq, mode, date, hour, call1, rst1, exch1, call2, rst2, exch2)


def render_header(fields: Dict[str, Optional[str]], contest_name: str) -> List[str]:
    """Render a Cabrillo header block. Any field key with value None is
    omitted entirely (simulates a genuinely missing mandatory field, CAB-003).
    """
    lines = ['START-OF-LOG: 3.0', 'CONTEST: {}'.format(contest_name)]

    def emit(key):
        if key in fields and fields[key] is not None:
            lines.append('{}: {}'.format(key, fields[key]))

    emit('CALLSIGN')
    emit('CATEGORY-OPERATOR')
    emit('CATEGORY-BAND')
    lines.append('CATEGORY-MODE: {}'.format(fields.get('CATEGORY-MODE') or 'MIXED'))
    lines.append('EMAIL: {}'.format(fields.get('EMAIL') or 'test@example.com'))
    lines.append('NAME: {}'.format(fields.get('NAME') or 'Test Operator'))
    lines.append('CREATED-BY: generate_dummy_logs.py (cabrillo_fixture_generator)')
    return lines


class LogFile(object):
    """Accumulates header fields + QSO lines for one Cabrillo log file, and
    records manifest-worthy metadata about the file itself (not its QSOs --
    those are recorded separately by add_qso)."""

    def __init__(self, callsign_label: str, header_fields: Dict[str, Optional[str]],
                 contest_name: str, checklog: bool = False,
                 note: str = '', valid_expected: bool = True, gap_ref: str = ''):
        self.callsign_label = callsign_label
        self.header_fields = header_fields
        self.contest_name = contest_name
        self.checklog = checklog
        self.note = note
        self.valid_expected = valid_expected
        self.gap_ref = gap_ref
        self.band = None   # band token string, e.g. '40M' or 'ALL'
        self.callsign = header_fields.get('CALLSIGN')
        self.qso_lines: List[str] = []
        self.qso_manifest: List[Dict[str, Any]] = []

    def add_qso(self, raw_line: str, scenario: str, expected_outcome: str,
                partner_callsign: Optional[str] = None,
                partner_ref: Optional[Dict[str, Any]] = None,
                note: str = ''):
        self.qso_lines.append(raw_line)
        self.qso_manifest.append({
            'raw_line': raw_line,
            'scenario': scenario,
            'expected_outcome': expected_outcome,
            'partner_callsign': partner_callsign,
            'partner_ref': partner_ref,
            'note': note,
        })

    def render(self) -> str:
        lines = render_header(self.header_fields, self.contest_name)
        lines.append('')
        lines.extend(self.qso_lines)
        lines.append('END-OF-LOG:')
        return '\n'.join(lines) + '\n'

    def write(self, path: str):
        with open(path, 'w') as f:
            f.write(self.render())


# ---------------------------------------------------------------------------
# Fixture construction
# ---------------------------------------------------------------------------

# CATEGORY-BAND header tokens that actually match this rules file's
# per-band regexps (see RULES-003 / band1..5's `regexp` values, which use a
# doubled backslash -- 'N\\.?|Xm' -- so only the trailing "Xm"-style
# alternative ever matches; the leading numeric-frequency alternative never
# does). Verified directly against RulesHf.contest_band(n)['regexp'] rather
# than assumed. If pointed at a different rules file, `_band_tokens()` below
# recomputes this mapping live instead of hard-coding it.
_FALLBACK_BAND_TOKENS = {1: '80M', 2: '40M', 3: '20M', 4: '15M', 5: '10M'}
_FALLBACK_BAND_FREQ = {'80M': '3700', '40M': '7040', '20M': '14040', '15M': '21040', '10M': '28040'}

MODE_RST = {'CW': '599', 'SSB': '59', 'PH': '59'}


def _band_tokens(rules_obj) -> Dict[int, str]:
    """Find, for each configured band number, a header token that actually
    satisfies that band's `regexp` via re.match (as Operator.logs_by_band_regexp
    uses it) -- rather than assuming any particular label. Falls back to the
    band's own `band` value (e.g. '80m'->'80M') if no candidate matches, so a
    differently-shaped rules file doesn't silently produce unmatchable logs.
    """
    import re
    tokens: Dict[int, str] = {}
    candidates = ['80M', '40M', '20M', '15M', '10M', '160M', '6M', '2M']
    for n in range(1, rules_obj.contest_bands_nr + 1):
        regexp = rules_obj.contest_band(n)['regexp']
        chosen = None
        for cand in candidates:
            if re.match(regexp, cand, re.IGNORECASE):
                chosen = cand
                break
        if chosen is None:
            # last resort: try the raw 'band' value itself and a couple of shapes
            raw = rules_obj.contest_band(n)['band']
            for cand in (raw, raw + 'M', raw.upper()):
                if re.match(regexp, cand, re.IGNORECASE):
                    chosen = cand
                    break
        tokens[n] = chosen or _FALLBACK_BAND_TOKENS.get(n, 'ALL')
    return tokens


class FixtureBuilder(object):
    """Builds the full DRACULA-style Cabrillo fixture set against a live
    RulesHf instance (so band tokens / periods / special-callsign list /
    custom-scoring type always match whatever rules file was actually
    handed to the generator)."""

    def __init__(self, rules_obj, rng: random.Random):
        self.rules = rules_obj
        self.rng = rng
        self.contest_name = rules_obj.config['contest'].get('name', 'Generated Contest')
        self.band_tokens = _band_tokens(rules_obj)  # {band_nr: 'HEADER TOKEN'}
        self.band_freq = {tok: _FALLBACK_BAND_FREQ.get(tok, '7040') for tok in self.band_tokens.values()}
        self.period = rules_obj.contest_period(1)
        self.qso_date1 = rules_obj.contest_begin_date  # 'YYYYMMDD'
        self.qso_date2 = rules_obj.contest_end_date
        self.special_callsigns = rules_obj.contest_special_callsign

        self.serial_counters: Dict[str, int] = {}
        self.logs: List[LogFile] = []

        # deterministic time cursor, kept strictly inside the contest window
        from datetime import datetime, timedelta
        self._dt = datetime
        self._td = timedelta
        self._begin_dt = datetime.strptime(rules_obj.contest_begin_date + rules_obj.contest_begin_hour,
                                            '%Y%m%d%H%M')
        self._end_dt = datetime.strptime(rules_obj.contest_end_date + rules_obj.contest_end_hour,
                                          '%Y%m%d%H%M')
        self._cursor = self._begin_dt + timedelta(minutes=30)

    # -- helpers ------------------------------------------------------

    def next_serial(self, callsign: str) -> str:
        n = self.serial_counters.get(callsign, 0) + 1
        self.serial_counters[callsign] = n
        return '{:03d}'.format(n)

    def next_dt(self, step_minutes: int = 17):
        dt = self._cursor
        self._cursor += self._td(minutes=step_minutes)
        if self._cursor >= self._end_dt:
            self._cursor = self._begin_dt + self._td(minutes=45)
        return dt

    def fmt_date_hour(self, dt) -> Tuple[str, str]:
        return dt.strftime('%Y-%m-%d'), dt.strftime('%H%M')

    def band_token(self, band_nr: int) -> str:
        return self.band_tokens[band_nr]

    def freq_for(self, band_token: str) -> str:
        return self.band_freq.get(band_token, '7040')

    # -- log creation ---------------------------------------------------

    def new_valid_log(self, callsign: str, band_nr_or_token, category: str = 'C',
                       checklog: bool = False) -> LogFile:
        band_token = band_nr_or_token if isinstance(band_nr_or_token, str) else self.band_token(band_nr_or_token)
        fields = {
            'CALLSIGN': callsign,
            'CATEGORY-OPERATOR': category,
            'CATEGORY-BAND': band_token,
            'CATEGORY-MODE': 'MIXED',
        }
        log = LogFile(callsign, fields, self.contest_name, checklog=checklog, valid_expected=True)
        log.band = band_token
        log.callsign = callsign
        self.logs.append(log)
        return log

    def new_invalid_log(self, label: str, fields: Dict[str, Optional[str]],
                         note: str, gap_ref: str = '') -> LogFile:
        log = LogFile(label, fields, self.contest_name, checklog=False,
                      valid_expected=False, note=note, gap_ref=gap_ref)
        log.band = fields.get('CATEGORY-BAND')
        log.callsign = fields.get('CALLSIGN')
        self.logs.append(log)
        return log

    # -- genuine pair construction --------------------------------------

    def add_genuine_pair(self, log_a: LogFile, log_b: LogFile, mode: str,
                          dt=None, scenario: str = 'genuine', note: str = '',
                          exch_a: Optional[str] = None, exch_b: Optional[str] = None):
        """Build one genuine, correctly-reciprocal QSO pair by construction:
        generate A's line, then derive B's as its EXACT STRING mirror
        (GAP-005b: Cabrillo compares nr_sent/nr_recv as raw strings, so this
        must not merely be numerically-equal)."""
        dt = dt or self.next_dt()
        date_s, hour_s = self.fmt_date_hour(dt)
        call_a, call_b = log_a.callsign, log_b.callsign
        rst = MODE_RST[mode]
        freq = self.freq_for(log_a.band if log_a.band != 'ALL' else log_b.band)

        exch_a_sent = exch_a if exch_a is not None else self.next_serial(call_a)
        exch_b_sent = exch_b if exch_b is not None else self.next_serial(call_b)

        line_a = qso_line(freq, mode, date_s, hour_s, call_a, rst, exch_a_sent, call_b, rst, exch_b_sent)
        line_b = qso_line(freq, mode, date_s, hour_s, call_b, rst, exch_b_sent, call_a, rst, exch_a_sent)

        ref_a = {'callsign': call_a, 'band': log_a.band, 'raw_line': line_a}
        ref_b = {'callsign': call_b, 'band': log_b.band, 'raw_line': line_b}

        log_a.add_qso(line_a, scenario, 'confirmed', partner_callsign=call_b, partner_ref=ref_b, note=note)
        log_b.add_qso(line_b, scenario, 'confirmed', partner_callsign=call_a, partner_ref=ref_a, note=note)
        return line_a, line_b


# ---------------------------------------------------------------------------
# Scenario assembly
# ---------------------------------------------------------------------------

def build_fixture(rules_obj, seed: int, operators_min: int) -> Dict[str, Any]:
    rng = random.Random(seed)
    fb = FixtureBuilder(rules_obj, rng)
    notes: List[str] = [
        "Cabrillo has no locator field (CAB-003) -- the EDI-only 'locator mismatch' taxonomy "
        "category (XC-005 step 7) does not apply here; no QSO exercises it in this fixture set.",
        "This rules file has no [extra] section/callregexp, and per GAP-003 Cabrillo ignores "
        "contest_extra_fields entirely even when present -- 'national callregexp filtering' is N/A here.",
        "Cabrillo logs have no per-log header date field at all (CAB-003) -- 'malformed header date' "
        "is EDI-only (EDI-009); QSO-line date/hour validity is exercised instead (malformed_qso_lines).",
        "GAP-001 (RTTY alias overwritten to DIGI) is not exercised: this rules file's modes=CW,SSB "
        "does not include RTTY, so no RTTY QSO is generated for this contest.",
        "GAP-014 (10-minute multi-op rule keyed off category name == 'MULTI') is not exercised: this "
        "rules file's multi-op category is named 'MO-AB-HP MIXT', not 'Multi', so the rule structurally "
        "cannot fire here -- expected inert behavior, not a bug in this fixture set.",
    ]

    specials = fb.special_callsigns
    special_1 = specials[1] if len(specials) > 1 else specials[0]
    special_2 = specials[0]

    # == DRACULA custom-scoring branches (SCORE-004) =======================
    log_dl2fff = fb.new_valid_log('DL2FFF', 2, category='B2')
    log_special1 = fb.new_valid_log(special_1, 2, category='C')
    fb.add_genuine_pair(log_dl2fff, log_special1, 'CW', scenario='dracula_special_nonyo_caller',
                        note='SCORE-004 special-station branch (non-YO caller); applies regardless '
                             'of caller YO status.')

    log_yo9ddd = fb.new_valid_log('YO9DDD', 2, category='A2')
    log_special2 = fb.new_valid_log(special_2, 2, category='C')
    fb.add_genuine_pair(log_yo9ddd, log_special2, 'CW', scenario='dracula_special_yo_caller',
                        note='SCORE-004 special-station branch (YO caller) -- demonstrates the branch '
                             "applies regardless of caller YO status, despite its 'non_yo_to_special' name.")

    log_yo3bbb = fb.new_valid_log('YO3BBB', 3, category='B1')
    log_yo7ccc = fb.new_valid_log('YO7CCC', 3, category='A1')
    fb.add_genuine_pair(log_yo3bbb, log_yo7ccc, 'SSB', scenario='dracula_yo_yo',
                        note='SCORE-004 YO-YO branch: 0 points both sides.')

    log_yo5aaa = fb.new_valid_log('YO5AAA', 3, category='A1')
    log_f5ggg = fb.new_valid_log('F5GGG', 3, category='B1')
    fb.add_genuine_pair(log_yo5aaa, log_f5ggg, 'SSB', scenario='dracula_yo_nonyo_and_nonyo_yo',
                        note='SCORE-004: yo_to_nonyo_points (YO5AAA side) + non_yo_to_yo_points '
                             '(F5GGG side) from ONE reciprocal pair (each side scored independently).')

    log_dl1eee = fb.new_valid_log('DL1EEE', 2, category='B3')
    fb.add_genuine_pair(log_dl1eee, log_dl2fff, 'CW', scenario='dracula_nonyo_same_dxcc',
                        note='SCORE-004: non_yo_same_country_points (both DL, same DXCC entity).')

    log_py1jjj = fb.new_valid_log('PY1JJJ', 3, category='A2')
    log_ja1iii = fb.new_valid_log('JA1III', 3, category='A2')
    fb.add_genuine_pair(log_py1jjj, log_ja1iii, 'CW', scenario='dracula_nonyo_diff_dxcc',
                        note='SCORE-004: non_yo_dxcc_points (different DXCC entities, PY vs JA).')

    # == Filler genuine pairs: more DXCC/continent diversity + padding =====
    log_vk2kkk = fb.new_valid_log('VK2KKK', 4, category='A1')
    log_zs5lll = fb.new_valid_log('ZS5LLL', 4, category='B1')
    fb.add_genuine_pair(log_vk2kkk, log_zs5lll, 'SSB', scenario='filler_diff_dxcc')

    log_g4mmm = fb.new_valid_log('G4MMM', 4, category='A2')
    log_i4nnn = fb.new_valid_log('I4NNN', 4, category='B2')
    fb.add_genuine_pair(log_g4mmm, log_i4nnn, 'CW', scenario='filler_diff_dxcc')

    log_w1ooo = fb.new_valid_log('W1OOO', 5, category='A3')
    log_ve3ppp = fb.new_valid_log('VE3PPP', 5, category='B3')
    fb.add_genuine_pair(log_w1ooo, log_ve3ppp, 'CW', scenario='filler_diff_dxcc')

    log_ha5rrr = fb.new_valid_log('HA5RRR', 5, category='B1')
    log_ok1sss = fb.new_valid_log('OK1SSS', 5, category='A1')
    fb.add_genuine_pair(log_ha5rrr, log_ok1sss, 'SSB', scenario='filler_diff_dxcc')

    log_ok1two = fb.new_valid_log('OK1TWO', 5, category='A2')
    log_ve3zzz = fb.new_valid_log('VE3ZZZ', 5, category='B2')
    fb.add_genuine_pair(log_ok1two, log_ve3zzz, 'CW', scenario='filler_diff_dxcc',
                        note='OK1TWO genuinely has an active 5th-band log so the separate '
                             'one_sided_qso scenario below can prove "has a log on this band, just '
                             'not this contact" rather than "no log at all".')

    # == CAB-005: 13-field exchange (serial+county) alongside 11-field =====
    log_yo4county = fb.new_valid_log('YO4COUNTY', 4, category='A2')
    log_dl3county = fb.new_valid_log('DL3COUNTY', 4, category='B2')
    fb.add_genuine_pair(log_yo4county, log_dl3county, 'CW', scenario='cab005_13field',
                        exch_a='001 MS', exch_b='010 QC',
                        note='CAB-005 13-field QSO line (serial+county combined exchange, embedded '
                             'space in nr_sent/nr_recv); mirrored as an exact string per GAP-005b.')

    # == GAP-016: CATEGORY-BAND: ALL fallback ===============================
    log_allb1 = fb.new_valid_log('YO6ALLB', 'ALL', category='A3')
    log_dl4real40 = fb.new_valid_log('DL4REAL40', 2, category='B2')
    fb.add_genuine_pair(log_allb1, log_dl4real40, 'CW', scenario='gap016_all_band_clean',
                        note='CATEGORY-BAND: ALL log; confirms correctly since the partner only has '
                             'one real-band log (40M), so "wrong" band passes simply find no active '
                             'partner log and this QSO is naturally retried until the right pass.')

    log_dl5allb = fb.new_valid_log('DL5ALLB', 'ALL', category='B3')
    real_band_token = fb.band_token(3)  # 20M -- the QSO's true band
    real_freq = fb.freq_for(real_band_token)
    dt_amb = fb.next_dt()
    date_s, hour_s = fb.fmt_date_hour(dt_amb)
    exch_allb1 = fb.next_serial('YO6ALLB')
    exch_dl5allb = fb.next_serial('DL5ALLB')
    line_allb1 = qso_line(real_freq, 'SSB', date_s, hour_s, 'YO6ALLB', '59', exch_allb1, 'DL5ALLB', '59', exch_dl5allb)
    line_dl5allb = qso_line(real_freq, 'SSB', date_s, hour_s, 'DL5ALLB', '59', exch_dl5allb, 'YO6ALLB', '59', exch_allb1)
    gap016_note = (
        "GAP-016: both operators are ALL-band-only, so this QSO (real freq {} / {}) is expected to be "
        "matched/confirmed during band_nr=1 (the {} pass) of the outer cross-check loop -- the FIRST "
        "band pass tried -- rather than a pass corresponding to its actual band, since neither side's "
        "single ALL log is ever filtered by its own QSOs' real frequency (formats/cabrillo/crosscheck.py"
        ":62-66,116-124). Still a legitimately-confirming pair per compare_qso; the gap is about which "
        "band pass processes it, not about correctness of the match itself."
    ).format(real_freq, real_band_token, fb.band_token(1))
    log_allb1.add_qso(line_allb1, 'gap016_all_band_ambiguous', 'confirmed',
                      partner_callsign='DL5ALLB', note=gap016_note)
    log_dl5allb.add_qso(line_dl5allb, 'gap016_all_band_ambiguous', 'confirmed',
                        partner_callsign='YO6ALLB', note=gap016_note)

    # == One dedicated pair per distinct compare_qso ValueError (XC-005) ===
    log_ha5ooo = fb.new_valid_log('HA5OOO', 2, category='A1')
    log_sp2ppp = fb.new_valid_log('SP2PPP', 2, category='B1')
    dt = fb.next_dt()
    date_s, hour_s = fb.fmt_date_hour(dt)
    freq2 = fb.freq_for(log_ha5ooo.band)
    line_a = qso_line(freq2, 'SSB', date_s, hour_s, 'HA5OOO', '59', '101', 'SP2PPP', '59', '201')
    line_b = qso_line(freq2, 'SSB', date_s, hour_s, 'SP2PPP', '57', '201', 'HA5OOO', '59', '101')  # rst_sent differs
    log_ha5ooo.add_qso(line_a, 'rst_mismatch', 'not_confirmed:Rst mismatch', partner_callsign='SP2PPP')
    log_sp2ppp.add_qso(line_b, 'rst_mismatch', 'not_confirmed:Rst mismatch (other ham)', partner_callsign='HA5OOO')

    log_i4qqq = fb.new_valid_log('I4QQQ', 2, category='A2')
    log_on4rrr = fb.new_valid_log('ON4RRR', 2, category='B2')
    dt = fb.next_dt()
    date_s, hour_s = fb.fmt_date_hour(dt)
    line_a = qso_line(freq2, 'SSB', date_s, hour_s, 'I4QQQ', '59', '005', 'ON4RRR', '59', '040')
    line_b = qso_line(freq2, 'SSB', date_s, hour_s, 'ON4RRR', '59', '040', 'I4QQQ', '59', '5')  # '5' != '005'
    gap005b_note = ("GAP-005b: I4QQQ sent '005', ON4RRR logged receiving '5' -- Cabrillo string-compares "
                    "nr_sent/nr_recv as unequal (EDI would int()-cast both to 5 and treat them as equal).")
    log_i4qqq.add_qso(line_a, 'serial_mismatch_gap005b', 'not_confirmed:Serial number mismatch (other ham)',
                      partner_callsign='ON4RRR', note=gap005b_note)
    log_on4rrr.add_qso(line_b, 'serial_mismatch_gap005b', 'not_confirmed:Serial number mismatch',
                       partner_callsign='I4QQQ', note=gap005b_note)

    log_oz1sss = fb.new_valid_log('OZ1SSS', 3, category='A3')
    log_pa3ttt = fb.new_valid_log('PA3TTT', 3, category='B3')
    dt_a = fb.next_dt()
    dt_b = dt_a + fb._td(minutes=8)
    freq3 = fb.freq_for(log_oz1sss.band)
    da, ha = fb.fmt_date_hour(dt_a)
    db, hb = fb.fmt_date_hour(dt_b)
    line_a = qso_line(freq3, 'CW', da, ha, 'OZ1SSS', '599', '301', 'PA3TTT', '599', '401')
    line_b = qso_line(freq3, 'CW', db, hb, 'PA3TTT', '599', '401', 'OZ1SSS', '599', '301')
    time_note = 'OZ1SSS and PA3TTT log 8 minutes apart for the "same" contact -- over the 5-minute cutoff.'
    log_oz1sss.add_qso(line_a, 'time_mismatch', "not_confirmed:Different date/time between qso's",
                       partner_callsign='PA3TTT', note=time_note)
    log_pa3ttt.add_qso(line_b, 'time_mismatch', "not_confirmed:Different date/time between qso's",
                       partner_callsign='OZ1SSS', note=time_note)

    log_oe3uuu = fb.new_valid_log('OE3UUU', 3, category='A1')
    log_hb9vvv = fb.new_valid_log('HB9VVV', 3, category='B1')
    dt = fb.next_dt()
    date_s, hour_s = fb.fmt_date_hour(dt)
    line_a = qso_line(freq3, 'CW', date_s, hour_s, 'OE3UUU', '599', '501', 'HB9VVV', '599', '601')
    line_b = qso_line(freq3, 'SSB', date_s, hour_s, 'HB9VVV', '59', '601', 'OE3UUU', '59', '501')
    mode_note = "OE3UUU logs CW, HB9VVV logs SSB for the 'same' contact -- both individually valid modes, but compare_qso's normalized-mode equality check fails."
    log_oe3uuu.add_qso(line_a, 'mode_mismatch', 'not_confirmed:Mode mismatch', partner_callsign='HB9VVV', note=mode_note)
    log_hb9vvv.add_qso(line_b, 'mode_mismatch', 'not_confirmed:Mode mismatch', partner_callsign='OE3UUU', note=mode_note)

    # == Duplicate-in-period: same pair confirmed twice in the one period ==
    log_s51xxx = fb.new_valid_log('S51XXX', 4, category='A2')
    log_ve3yyy = fb.new_valid_log('VE3YYY', 4, category='B2')
    for n in range(2):
        dt = fb.next_dt()
        date_s, hour_s = fb.fmt_date_hour(dt)
        exch_a = '{:03d}'.format(700 + n)
        exch_b = '{:03d}'.format(800 + n)
        freq4 = fb.freq_for(log_s51xxx.band)
        line_a = qso_line(freq4, 'SSB', date_s, hour_s, 'S51XXX', '59', exch_a, 'VE3YYY', '59', exch_b)
        line_b = qso_line(freq4, 'SSB', date_s, hour_s, 'VE3YYY', '59', exch_b, 'S51XXX', '59', exch_a)
        if n == 0:
            log_s51xxx.add_qso(line_a, 'duplicate_in_period_first', 'confirmed', partner_callsign='VE3YYY')
            log_ve3yyy.add_qso(line_b, 'duplicate_in_period_first', 'confirmed', partner_callsign='S51XXX')
        else:
            dup_note = ('Second genuinely-matching contact between the same pair in the same (only) '
                        'period; rejected purely by the _had_qso_with duplicate guard, before candidate '
                        'search even happens -- not by content mismatch.')
            log_s51xxx.add_qso(line_a, 'duplicate_in_period_second', 'not_confirmed:Qso already confirmed',
                               partner_callsign='VE3YYY', note=dup_note)
            log_ve3yyy.add_qso(line_b, 'duplicate_in_period_second', 'not_confirmed:Qso already confirmed',
                               partner_callsign='S51XXX', note=dup_note)

    # == One-sided QSO: G4ONE logs OK1TWO, OK1TWO never logs it back =======
    log_g4one = fb.new_valid_log('G4ONE', 5, category='A2')
    dt = fb.next_dt()
    date_s, hour_s = fb.fmt_date_hour(dt)
    freq5 = fb.freq_for(log_g4one.band)
    line = qso_line(freq5, 'CW', date_s, hour_s, 'G4ONE', '599', '901', 'OK1TWO', '599', '902')
    log_g4one.add_qso(line, 'one_sided_qso', 'not_confirmed:No qso found on OK1TWO log',
                      partner_callsign='OK1TWO',
                      note='OK1TWO has a valid, active 5th-band log (see filler_diff_dxcc pair with '
                           'VE3ZZZ) but never logged this specific contact back.')

    # == No log from partner at all (piggyback on YO3BBB's log) ============
    dt = fb.next_dt()
    date_s, hour_s = fb.fmt_date_hour(dt)
    freq_yo3 = fb.freq_for(log_yo3bbb.band)
    line = qso_line(freq_yo3, 'SSB', date_s, hour_s, 'YO3BBB', '59', '111', 'SP2GHOST', '59', '222')
    log_yo3bbb.add_qso(line, 'no_log_from_partner', 'not_confirmed:No log from SP2GHOST',
                       partner_callsign='SP2GHOST',
                       note='SP2GHOST never appears as an operator anywhere in logs/ or checklogs/.')

    # == Partner has a valid log, but not on this band (piggyback on YO7CCC) ==
    dt = fb.next_dt()
    date_s, hour_s = fb.fmt_date_hour(dt)
    freq_yo7 = fb.freq_for(log_yo7ccc.band)
    line = qso_line(freq_yo7, 'CW', date_s, hour_s, 'YO7CCC', '599', '112', 'OK1SSS', '599', '223')
    log_yo7ccc.add_qso(line, 'no_log_for_band', 'not_confirmed:No valid log for this band from OK1SSS',
                       partner_callsign='OK1SSS',
                       note='OK1SSS has a valid Cabrillo log, but only on the 5th band (see '
                            'filler_diff_dxcc pair with HA5RRR); YO7CCC logs on the 3rd band.')

    # == Checklog-only submitter -- GAP-005a (Cabrillo excludes checklogs on
    #    BOTH sides unconditionally, unlike EDI's partner-side exception) ===
    log_n2check = fb.new_valid_log('N2CHECK', 2, category='C', checklog=True)
    dt = fb.next_dt()
    date_s, hour_s = fb.fmt_date_hour(dt)
    freq_ha5 = fb.freq_for(log_ha5ooo.band)
    line_check = qso_line(freq_ha5, 'CW', date_s, hour_s, 'N2CHECK', '599', '501', 'HA5OOO', '599', '101')
    line_ha5 = qso_line(freq_ha5, 'CW', date_s, hour_s, 'HA5OOO', '599', '101', 'N2CHECK', '599', '501')
    log_n2check.add_qso(line_check, 'checklog_only_gap005a', 'not_evaluated:cc_confirmed stays None',
                        partner_callsign='HA5OOO',
                        note="This log is only ever loaded as a checklog. Cabrillo's _find_active_log "
                             "excludes checklogs unconditionally on BOTH sides (no exclude_checklog "
                             "parameter, contrast EDI's XC-003) -- N2CHECK is never selected as log1, "
                             "so this QSO is never reached by the per-band loop body: cc_confirmed stays "
                             "None, not True/False (XC-006). Contrast with EDI, where a checklog CAN "
                             "confirm a partner's QSO (GAP-005 item 1).")
    log_ha5ooo.add_qso(line_ha5, 'checklog_only_gap005a', 'not_confirmed:No valid log for this band from N2CHECK',
                       partner_callsign='N2CHECK',
                       note='GAP-005a: content would otherwise match N2CHECK\'s checklog line exactly, '
                            'but Cabrillo excludes checklogs on the partner side too, unlike EDI.')

    # == Malformed QSO lines (single-log/multi-log validation, not just -cc) ==
    log_yo8bad = fb.new_valid_log('YO8BADQSO', 2, category='B1')
    log_dl6good = fb.new_valid_log('DL6GOOD', 2, category='A2')
    dt = fb.next_dt()
    date_s, hour_s = fb.fmt_date_hour(dt)
    freq_bad = fb.freq_for(log_yo8bad.band)
    good_a = qso_line(freq_bad, 'CW', date_s, hour_s, 'YO8BADQSO', '599', '001', 'DL6GOOD', '599', '051')
    good_b = qso_line(freq_bad, 'CW', date_s, hour_s, 'DL6GOOD', '599', '051', 'YO8BADQSO', '599', '001')
    log_yo8bad.add_qso(good_a, 'malformed_qso_lines', 'confirmed', partner_callsign='DL6GOOD',
                       note='One genuine QSO alongside six malformed lines below, so the log/operator '
                            "isn't *entirely* broken -- realistic mix.")
    log_dl6good.add_qso(good_b, 'malformed_qso_lines', 'confirmed', partner_callsign='YO8BADQSO')

    dt2 = fb.next_dt()
    d2, h2 = fb.fmt_date_hour(dt2)
    too_short = 'QSO: {} CW {} {} YO8BADQSO 599 002'.format(freq_bad, d2, h2)
    log_yo8bad.add_qso(too_short, 'malformed_too_short', 'invalid:Incorrect QSO line format',
                       note='Missing call2/rst2/exch2 -- fails both the 11- and 13-field regexes entirely.')

    dt3 = fb.next_dt()
    d3, h3 = fb.fmt_date_hour(dt3)
    bad_rst = qso_line(freq_bad, 'CW', d3, h3, 'YO8BADQSO', '99', '003', 'DL6GOOD', '599', '052')
    log_yo8bad.add_qso(bad_rst, 'malformed_bad_rst', 'invalid:Rst is invalid: 99',
                       note="RST '99' fails ^[1-5][1-9][1-9]?[aAsS]?$ (leading digit must be 1-5).")

    dt4 = fb.next_dt()
    d4, h4 = fb.fmt_date_hour(dt4)
    bad_exch = qso_line(freq_bad, 'CW', d4, h4, 'YO8BADQSO', '599', '1234567', 'DL6GOOD', '599', '053')
    log_yo8bad.add_qso(bad_exch, 'malformed_bad_exchange', 'invalid:Sent exchange is invalid: 1234567',
                       note="'1234567' is 7 chars, exceeds \\w{1,6} and isn't a two-token exchange either.")

    bad_date = 'QSO: {} CW 2026-13-45 1200 YO8BADQSO 599 004 DL6GOOD 599 054'.format(freq_bad)
    log_yo8bad.add_qso(bad_date, 'malformed_bad_date', 'invalid:Qso date is invalid',
                       note="'2026-13-45' matches the line regex shape but isn't a real calendar date.")

    bad_hour = 'QSO: {} CW 2026-10-31 2560 YO8BADQSO 599 005 DL6GOOD 599 055'.format(freq_bad)
    log_yo8bad.add_qso(bad_hour, 'malformed_bad_hour', 'invalid:Qso hour is invalid',
                       note="'2560' matches \\d{4} but hour 25 doesn't exist.")

    before_start = 'QSO: {} CW 2026-10-30 1000 YO8BADQSO 599 006 DL6GOOD 599 056'.format(freq_bad)
    log_yo8bad.add_qso(before_start, 'malformed_date_before_contest', 'invalid:Qso date is invalid: before contest starts',
                       note='2026-10-30 is one full day before begindate=20261031 (rules_based_qso_validator).')

    # == Whole-log header validation failures (contribute zero QSOs) =======
    fb.new_invalid_log('NOCALL', {
        'CATEGORY-OPERATOR': 'C', 'CATEGORY-BAND': '40M',
    }, note="CALLSIGN field entirely absent -> 'CALLSIGN field is not present' (CAB-003).")

    fb.new_invalid_log('NOBAND', {
        'CALLSIGN': 'NOBAND1', 'CATEGORY-OPERATOR': 'C',
    }, note="CATEGORY-BAND field entirely absent -> 'CATEGORY-BAND field is not present' (CAB-003).")

    fb.new_invalid_log('BADCALLSIGN', {
        'CALLSIGN': 'NOCALLSIGN', 'CATEGORY-OPERATOR': 'C', 'CATEGORY-BAND': '40M',
    }, note="CALLSIGN='NOCALLSIGN' has no digit at all, fails validate_callsign's "
            "^\\s*(\\w+/)?(\\w+[0-9]+)\\w+(/?)\\w*\\s*$ (CAB-003).")

    fb.new_invalid_log('BADCATEGORY', {
        'CALLSIGN': 'BADCAT1', 'CATEGORY-OPERATOR': 'X9-UNKNOWN', 'CATEGORY-BAND': '40M',
    }, note="CATEGORY-OPERATOR='X9-UNKNOWN' matches none of this rules file's [categoryN] regexps "
            "(A1/A2/A3/B1/B2/B3/C). Per CAB-012 this is a KNOWN GAP: validate_header records NO "
            "ERR_HEADER line for this case -- the log is silently dropped from cross-check with no "
            "diagnostic error at all, not 'rejected with an error message'.",
        gap_ref='CAB-012')

    # -- Optional padding to satisfy a higher --operators floor ------------
    existing_ops = {log.callsign for log in fb.logs if log.valid_expected}
    prefixes = ['DL', 'F', 'G', 'I', 'HA', 'OK', 'SP', 'OE', 'HB9', 'PA', 'ON', 'OZ',
                'PY', 'JA', 'VK', 'ZS', 'VE', 'W', 'YO']
    band_nrs = list(range(1, rules_obj.contest_bands_nr + 1))
    pad_idx = 0
    while len(existing_ops) < operators_min:
        pad_idx += 1
        p1 = rng.choice(prefixes)
        p2 = rng.choice(prefixes)
        s1 = ''.join(rng.choice('ABCDEFGHJKLMNPQRSTUVWXYZ') for _ in range(3))
        s2 = ''.join(rng.choice('ABCDEFGHJKLMNPQRSTUVWXYZ') for _ in range(3))
        call_a = '{}{}{}'.format(p1, rng.randint(1, 9), s1)
        call_b = '{}{}{}'.format(p2, rng.randint(1, 9), s2)
        if call_a in existing_ops or call_b in existing_ops or call_a == call_b:
            continue
        band_nr = rng.choice(band_nrs)
        mode = rng.choice(['CW', 'SSB'])
        pad_log_a = fb.new_valid_log(call_a, band_nr, category=rng.choice(['A1', 'A2', 'A3', 'B1', 'B2', 'B3', 'C']))
        pad_log_b = fb.new_valid_log(call_b, band_nr, category=rng.choice(['A1', 'A2', 'A3', 'B1', 'B2', 'B3', 'C']))
        fb.add_genuine_pair(pad_log_a, pad_log_b, mode, scenario='genuine_padding_for_operator_floor')
        existing_ops.add(call_a)
        existing_ops.add(call_b)

    return _finalize_manifest(fb, notes)


def _finalize_manifest(fb: FixtureBuilder, notes: List[str]) -> Dict[str, Any]:
    total_qsos = 0
    confirmed_qsos = 0
    logs_manifest = []
    for log in fb.logs:
        n = len(log.qso_manifest)
        total_qsos += n
        confirmed_qsos += sum(1 for q in log.qso_manifest if q['expected_outcome'] == 'confirmed')
        logs_manifest.append({
            'callsign_label': log.callsign_label,
            'callsign': getattr(log, 'callsign', None),
            'band': getattr(log, 'band', None),
            'checklog': log.checklog,
            'valid_header_expected': log.valid_expected,
            'note': log.note,
            'gap_ref': log.gap_ref,
            'header_fields': log.header_fields,
            'qsos': log.qso_manifest,
        })

    return {
        'fixture': fb,  # internal use by the writer; stripped before json.dump
        'logs': logs_manifest,
        'summary': {
            'total_logs': len(fb.logs),
            'total_qsos': total_qsos,
            'confirmed_qsos': confirmed_qsos,
            'confirmed_ratio': (confirmed_qsos / total_qsos) if total_qsos else 0.0,
        },
        'notes': notes,
    }


def write_fixture(manifest: Dict[str, Any], outdir: str) -> None:
    fb: FixtureBuilder = manifest['fixture']
    logs_dir = os.path.join(outdir, 'logs')
    checklogs_dir = os.path.join(outdir, 'checklogs')
    os.makedirs(logs_dir, exist_ok=True)
    os.makedirs(checklogs_dir, exist_ok=True)

    for log_manifest, log in zip(manifest['logs'], fb.logs):
        target_dir = checklogs_dir if log.checklog else logs_dir
        filename = '{}.log'.format(log.callsign_label)
        path = os.path.join(target_dir, filename)
        log.write(path)
        log_manifest['path'] = path
