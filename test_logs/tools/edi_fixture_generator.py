"""
EDI (VHF/UHF/SHF) synthetic contest log fixture generator.

Owned by: format-specialist's fixture-generation agent.
Do not merge Cabrillo-specific logic into this file — see
generate_dummy_logs.py's dispatcher and keep Cabrillo generation in its own
sibling module to avoid collisions with the agent generating Cabrillo fixtures.

This module builds a deterministic (seeded) set of EDI log files exercising
the cross-check pipeline described in:
  specs/04-format-edi-spec.md
  specs/07-crosscheck-spec.md
  specs/09-known-gaps-and-deviations.md

Design principle: every "genuine" confirmable QSO pair is built by
construction (one side generated, the other derived as its exact mirror) —
never as two independently-random lines hoped to match. Every QSO written
is recorded in the returned manifest with its intended cross-check outcome,
so a consumer can diff the real app's -cc -o json output against ground
truth rather than against a human's memory of intent.
"""
import os
import random
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Low-level EDI rendering helpers
# ---------------------------------------------------------------------------

QSO_FIELD_ORDER = (
    'date', 'hour', 'call', 'mode', 'rst_sent', 'nr_sent', 'rst_recv',
    'nr_recv', 'exchange_recv', 'wwl', 'points', 'new_exchange', 'new_wwl',
    'new_dxcc', 'duplicate_qso',
)


def qso_line(date, hour, call, mode, rst_sent, nr_sent, rst_recv, nr_recv,
             wwl, exchange_recv='', points='', new_exchange='', new_wwl='',
             new_dxcc='', duplicate_qso=''):
    """Render one EDI QSO record line (14 ';'-delimited fields, 15 columns)."""
    values = {
        'date': date, 'hour': hour, 'call': call, 'mode': mode,
        'rst_sent': rst_sent, 'nr_sent': nr_sent, 'rst_recv': rst_recv,
        'nr_recv': nr_recv, 'exchange_recv': exchange_recv, 'wwl': wwl,
        'points': points, 'new_exchange': new_exchange, 'new_wwl': new_wwl,
        'new_dxcc': new_dxcc, 'duplicate_qso': duplicate_qso,
    }
    return ';'.join(str(values[f]) for f in QSO_FIELD_ORDER)


def render_header(fields: Dict[str, Optional[str]], contest_name: str) -> List[str]:
    """Render an EDI header block. Any field key omitted from `fields` (value
    None) results in the corresponding "Key=" line being *omitted entirely*
    from the file — used to simulate a genuinely missing mandatory field.
    Value '' (empty string) still emits "Key=" (present, but empty).
    """
    lines = ['[REG1TEST;1]']
    lines.append('TName={}'.format(contest_name))

    def emit(key, present_key=None):
        present_key = present_key or key
        if present_key in fields and fields[present_key] is not None:
            lines.append('{}={}'.format(key, fields[present_key]))

    emit('TDate')
    emit('PCall')
    emit('PWWLo')
    lines.append('PExch=')
    lines.append('PAdr1=')
    lines.append('PAdr2=')
    emit('PSect')
    emit('PBand')
    lines.append('PClub=')
    lines.append('RName=Generated Operator')
    lines.append('RCall=')
    lines.append('Radr1=')
    lines.append('Radr2=')
    lines.append('RPoCo=')
    lines.append('RCity=')
    lines.append('RCoun=Romania')
    lines.append('RPhon=')
    lines.append('RHBBS=')
    lines.append('MOpe1=')
    lines.append('MOpe2=')
    lines.append('STXEq=')
    lines.append('SPowe=100W')
    lines.append('SRXEq=')
    lines.append('SAnte=')
    lines.append('SAntH=')
    lines.append('CQSOs=')
    lines.append('CQSOP=')
    lines.append('CWWLs=')
    lines.append('CWWLB=')
    lines.append('CExcs=')
    lines.append('CExcB=')
    lines.append('CDXCs=')
    lines.append('CDXCB=')
    lines.append('CToSc=')
    lines.append('CODXC=')
    lines.append('[Remarks]')
    return lines


class LogFile(object):
    """Accumulates header fields + QSO lines for one EDI log file, and
    records manifest-worthy metadata about the file itself (not its QSOs --
    those are recorded separately by the scenario-building code)."""

    def __init__(self, callsign_label: str, header_fields: Dict[str, Optional[str]],
                 contest_name: str, checklog: bool = False,
                 note: str = '', valid_expected: bool = True, gap_ref: str = ''):
        self.callsign_label = callsign_label  # human label, may differ from PCall (e.g. missing-call case)
        self.header_fields = header_fields
        self.contest_name = contest_name
        self.checklog = checklog
        self.note = note
        self.valid_expected = valid_expected
        self.gap_ref = gap_ref
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
        lines.append('[QSORecords;{}]'.format(len(self.qso_lines)))
        lines.extend(self.qso_lines)
        lines.append('[END OF LOG]')
        return '\n'.join(lines) + '\n'

    def write(self, path: str):
        with open(path, 'w') as f:
            f.write(self.render())


# ---------------------------------------------------------------------------
# Fixture construction
# ---------------------------------------------------------------------------

class FixtureBuilder(object):
    """Builds the full NAPOCA-2016-style EDI fixture set against a live
    RulesVhf instance (so band labels / period bounds / callregexp always
    match whatever rules file was actually handed to the generator)."""

    def __init__(self, rules_obj, rng: random.Random):
        self.rules = rules_obj
        self.rng = rng
        self.contest_name = rules_obj.config['contest'].get('name', 'Generated Contest')
        self.band_label = {1: rules_obj.contest_band(1)['band'], 2: rules_obj.contest_band(2)['band']}
        self.period = rules_obj.contest_period(1)
        self.tdate = '{};{}'.format(self.period['begindate'], self.period['enddate'])
        self.qso_date = self.period['begindate'][2:]  # 2-digit-year EDI date, e.g. '160507'
        self.qso_date_day2 = self.period['enddate'][2:]
        self.callregexp_prefix = (rules_obj.contest_extra_field_value('callregexp') or '').upper()

        self.serial_counters: Dict[str, int] = {}
        self.locators: Dict[str, str] = {}
        self._locator_pool = self._build_locator_pool()
        self._locator_idx = 0

        self.logs: List[LogFile] = []          # every LogFile created (valid or not)
        self.pairs: List[Dict[str, Any]] = []   # manifest-level pair bookkeeping

    # -- helpers ------------------------------------------------------

    def _build_locator_pool(self) -> List[str]:
        # Maidenhead locator = 2 letters (a-r) + 2 digits + 2 letters (a-x).
        # First-pair letter fixed to 'K' (arbitrary but valid, Romania-ish);
        # second first-pair letter and both second-pair letters vary.
        letters1 = 'KLM'          # subset of a-r, arbitrary but valid
        letters2 = 'ABCDEFGHIJKLMNOPQRSTUVWX'  # a-x, valid 2nd pair
        pool = []
        for l1 in letters1:
            for d in range(10, 60):
                for l2 in letters2[:6]:
                    pool.append('K{}{:02d}{}{}'.format(l1, d, l2, self.rng.choice(letters2)))
        self.rng.shuffle(pool)
        return pool

    def next_locator(self, callsign: str) -> str:
        if callsign not in self.locators:
            loc = self._locator_pool[self._locator_idx]
            self._locator_idx += 1
            self.locators[callsign] = loc
        return self.locators[callsign]

    def next_serial(self, callsign: str) -> str:
        n = self.serial_counters.get(callsign, 0) + 1
        self.serial_counters[callsign] = n
        return '{:03d}'.format(n)

    def band_field_value(self, band_nr: int) -> str:
        return '{} MHz'.format(self.band_label[band_nr])

    # -- log creation ---------------------------------------------------

    def new_valid_log(self, callsign: str, band_nr: int, psect: str = 'SINGLE',
                       checklog: bool = False, tdate: Optional[str] = None) -> LogFile:
        fields = {
            'PCall': callsign,
            'PWWLo': self.next_locator(callsign),
            'PBand': self.band_field_value(band_nr),
            'PSect': psect,
            'TDate': tdate or self.tdate,
        }
        log = LogFile(callsign, fields, self.contest_name, checklog=checklog,
                      valid_expected=True)
        log.band_nr = band_nr
        log.callsign = callsign
        self.logs.append(log)
        return log

    def new_invalid_log(self, label: str, fields: Dict[str, Optional[str]],
                         note: str, gap_ref: str = '') -> LogFile:
        log = LogFile(label, fields, self.contest_name, checklog=False,
                      valid_expected=False, note=note, gap_ref=gap_ref)
        log.band_nr = None
        log.callsign = fields.get('PCall')
        self.logs.append(log)
        return log

    # -- genuine pair construction --------------------------------------

    def add_genuine_pair(self, log_a: LogFile, log_b: LogFile, mode: str,
                          rst: str, hour: str = '1300', date: Optional[str] = None,
                          scenario: str = 'genuine', note: str = ''):
        """Build one genuine, correctly-reciprocal QSO pair by construction:
        generate A's line, then derive B's as its exact mirror."""
        date = date or self.qso_date
        call_a, call_b = log_a.callsign, log_b.callsign
        loc_a, loc_b = self.locators[call_a], self.locators[call_b]

        nr_a = self.next_serial(call_a)   # what A sends to B
        nr_b = self.next_serial(call_b)   # what B sends to A

        line_a = qso_line(date, hour, call_b, mode, rst, nr_a, rst, nr_b, loc_b)
        line_b = qso_line(date, hour, call_a, mode, rst, nr_b, rst, nr_a, loc_a)

        ref_a = {'callsign': call_a, 'band': log_a.band_nr, 'raw_line': line_a}
        ref_b = {'callsign': call_b, 'band': log_b.band_nr, 'raw_line': line_b}

        log_a.add_qso(line_a, scenario, 'confirmed', partner_callsign=call_b,
                      partner_ref=ref_b, note=note)
        log_b.add_qso(line_b, scenario, 'confirmed', partner_callsign=call_a,
                      partner_ref=ref_a, note=note)
        return line_a, line_b


# ---------------------------------------------------------------------------
# Scenario assembly
# ---------------------------------------------------------------------------

def _ring_pairs(callsigns: List[str]) -> List[Tuple[str, str]]:
    n = len(callsigns)
    return [(callsigns[i], callsigns[(i + 1) % n]) for i in range(n)]


def build_fixture(rules_obj, seed: int, operators_min: int) -> Dict[str, Any]:
    rng = random.Random(seed)
    fb = FixtureBuilder(rules_obj, rng)

    manifest_notes: List[str] = []

    # -- 1. Genuine mesh: band1 (SSB), 8 operators in a ring -----------
    band1_calls = ['YO5AAA', 'YO5BBB', 'YO5CCC', 'YO5DDD', 'YO5EEE', 'YO5FFF', 'YO5GGG', 'YO5HHH']
    band1_logs = {c: fb.new_valid_log(c, 1, psect='SINGLE') for c in band1_calls}
    for a, b in _ring_pairs(band1_calls):
        fb.add_genuine_pair(band1_logs[a], band1_logs[b], mode='1', rst='59',
                             scenario='genuine_mesh_band1')

    # -- 2. Genuine mesh: band2 (CW), 6 operators in a ring -------------
    band2_calls = ['YO2ABC', 'YO2ABD', 'YO2ABE', 'YO3XYZ', 'YO3XYA', 'YO3XYB']
    band2_logs = {c: fb.new_valid_log(c, 2, psect='SINGLE') for c in band2_calls}
    for a, b in _ring_pairs(band2_calls):
        fb.add_genuine_pair(band2_logs[a], band2_logs[b], mode='2', rst='599',
                             scenario='genuine_mesh_band2')

    # -- 3. One-sided QSO: III logs a contact with JJJ, JJJ never logs it back --
    log_iii = fb.new_valid_log('YO5III', 1, psect='SINGLE')
    log_jjj = fb.new_valid_log('YO5JJJ', 1, psect='SINGLE')  # valid, but zero QSOs
    loc_jjj = fb.locators['YO5JJJ']
    nr_iii = fb.next_serial('YO5III')
    line = qso_line(fb.qso_date, '1300', 'YO5JJJ', '1', '59', nr_iii, '59', '001', loc_jjj)
    log_iii.add_qso(line, 'one_sided', "not_confirmed:No qso found on YO5JJJ log",
                    partner_callsign='YO5JJJ',
                    note="JJJ has a valid band1 log but never logged this contact; "
                         "candidate generator yields zero candidates -> generic "
                         "'No qso found on {call} log' (formats/edi.py:800-802).")

    # -- 4. No log from partner at all: KKK claims contact with a ghost call --
    log_kkk = fb.new_valid_log('YO5KKK', 1, psect='SINGLE')
    ghost = 'YO9ZZZ'  # never appears as any log's PCall anywhere in this fixture set
    nr_kkk = fb.next_serial('YO5KKK')
    line = qso_line(fb.qso_date, '1300', ghost, '1', '59', nr_kkk, '59', '001', 'KN10AA')
    log_kkk.add_qso(line, 'no_log_from_partner',
                    'not_confirmed:No log from {}'.format(ghost),
                    partner_callsign=ghost,
                    note='{} never submitted any log/checklog at all.'.format(ghost))

    # -- 5. Partner has no log on this band: LLL (band1) vs MMM (band2 only) --
    log_lll = fb.new_valid_log('YO5LLL', 1, psect='SINGLE')
    log_mmm = fb.new_valid_log('YO2MMM', 2, psect='SINGLE')  # only a band2 log, zero QSOs
    loc_mmm = fb.locators['YO2MMM']
    nr_lll = fb.next_serial('YO5LLL')
    line = qso_line(fb.qso_date, '1300', 'YO2MMM', '1', '59', nr_lll, '59', '001', loc_mmm)
    log_lll.add_qso(line, 'no_log_for_band',
                    'not_confirmed:No log for this band from YO2MMM',
                    partner_callsign='YO2MMM',
                    note='YO2MMM only ever submitted a band2 (432) log; LLL logged '
                         'this contact on band1 (144).')

    # -- 6. RST mismatch (both sides fail, per GAP-015 both get the generic msg) --
    log_nnn = fb.new_valid_log('YO5NNN', 1, psect='SINGLE')
    log_ooo = fb.new_valid_log('YO5OOO', 1, psect='SINGLE')
    loc_nnn, loc_ooo = fb.locators['YO5NNN'], fb.locators['YO5OOO']
    nr_nnn, nr_ooo = fb.next_serial('YO5NNN'), fb.next_serial('YO5OOO')
    # NNN's rst_recv ("57") deliberately does NOT match what OOO actually sent ("59")
    line_nnn = qso_line(fb.qso_date, '1300', 'YO5OOO', '1', '59', nr_nnn, '57', nr_ooo, loc_ooo)
    line_ooo = qso_line(fb.qso_date, '1300', 'YO5NNN', '1', '59', nr_ooo, '59', nr_nnn, loc_nnn)
    gap015_note = ("compare_qso raises 'Rst mismatch' internally, but EDI's single-candidate "
                   "retry loop unconditionally overwrites qso1.cc_error with the generic "
                   "'No qso found on {call} log' once no candidate passes (formats/edi.py:800-802, "
                   "GAP-015) -- the specific RST-mismatch reason never reaches the user.")
    log_nnn.add_qso(line_nnn, 'rst_mismatch', 'not_confirmed:No qso found on YO5OOO log',
                    partner_callsign='YO5OOO', note=gap015_note)
    log_ooo.add_qso(line_ooo, 'rst_mismatch', 'not_confirmed:No qso found on YO5NNN log',
                    partner_callsign='YO5NNN', note=gap015_note)

    # -- 7. Serial/exchange mismatch --
    log_ppp = fb.new_valid_log('YO5PPP', 1, psect='SINGLE')
    log_qqq = fb.new_valid_log('YO5QQQ', 1, psect='SINGLE')
    loc_ppp, loc_qqq = fb.locators['YO5PPP'], fb.locators['YO5QQQ']
    nr_ppp, nr_qqq = fb.next_serial('YO5PPP'), fb.next_serial('YO5QQQ')
    # PPP's nr_recv ("999") does NOT match what QQQ actually sent (nr_qqq)
    line_ppp = qso_line(fb.qso_date, '1300', 'YO5QQQ', '1', '59', nr_ppp, '59', '999', loc_qqq)
    line_qqq = qso_line(fb.qso_date, '1300', 'YO5PPP', '1', '59', nr_qqq, '59', nr_ppp, loc_ppp)
    note = ("compare_qso raises 'Serial number mismatch' internally; overwritten by the same "
            "generic message per GAP-015 (EDI casts nr_sent/nr_recv to int() so this is a real "
            "numeric mismatch, not a string-padding artifact -- contrast with Cabrillo's raw "
            "string comparison, GAP-005 item 2).")
    log_ppp.add_qso(line_ppp, 'serial_mismatch', 'not_confirmed:No qso found on YO5QQQ log',
                    partner_callsign='YO5QQQ', note=note)
    log_qqq.add_qso(line_qqq, 'serial_mismatch', 'not_confirmed:No qso found on YO5PPP log',
                    partner_callsign='YO5PPP', note=note)

    # -- 8. Time >5 minutes apart --
    log_rrr = fb.new_valid_log('YO5RRR', 1, psect='SINGLE')
    log_sss = fb.new_valid_log('YO5SSS', 1, psect='SINGLE')
    loc_rrr, loc_sss = fb.locators['YO5RRR'], fb.locators['YO5SSS']
    nr_rrr, nr_sss = fb.next_serial('YO5RRR'), fb.next_serial('YO5SSS')
    line_rrr = qso_line(fb.qso_date, '1200', 'YO5SSS', '1', '59', nr_rrr, '59', nr_sss, loc_sss)
    line_sss = qso_line(fb.qso_date, '1210', 'YO5RRR', '1', '59', nr_sss, '59', nr_rrr, loc_rrr)  # +10 min
    note = ("10 minutes apart (> compare_qso's 5-minute cutoff) -> 'Different date/time between "
            "qso's' internally, overwritten to the generic 'No qso found' message per GAP-015.")
    log_rrr.add_qso(line_rrr, 'time_mismatch', 'not_confirmed:No qso found on YO5SSS log',
                    partner_callsign='YO5SSS', note=note)
    log_sss.add_qso(line_sss, 'time_mismatch', 'not_confirmed:No qso found on YO5RRR log',
                    partner_callsign='YO5RRR', note=note)

    # -- 9. Mode mismatch (both individually valid modes, but different) --
    log_ttt = fb.new_valid_log('YO5TTT', 1, psect='SINGLE')
    log_uuu = fb.new_valid_log('YO5UUU', 1, psect='SINGLE')
    loc_ttt, loc_uuu = fb.locators['YO5TTT'], fb.locators['YO5UUU']
    nr_ttt, nr_uuu = fb.next_serial('YO5TTT'), fb.next_serial('YO5UUU')
    line_ttt = qso_line(fb.qso_date, '1300', 'YO5UUU', '1', '59', nr_ttt, '59', nr_uuu, loc_uuu)  # SSB
    line_uuu = qso_line(fb.qso_date, '1300', 'YO5TTT', '6', '59', nr_uuu, '59', nr_ttt, loc_ttt)  # FM
    note = ("TTT logs mode=1 (SSB), UUU logs mode=6 (FM) for the 'same' contact -- both modes are "
            "individually valid per rules modes=1,2,6, so the QSO parses fine but compare_qso's "
            "mode equality check fails ('Mode mismatch'), overwritten per GAP-015.")
    log_ttt.add_qso(line_ttt, 'mode_mismatch', 'not_confirmed:No qso found on YO5UUU log',
                    partner_callsign='YO5UUU', note=note)
    log_uuu.add_qso(line_uuu, 'mode_mismatch', 'not_confirmed:No qso found on YO5TTT log',
                    partner_callsign='YO5TTT', note=note)

    # -- 10. Locator (WWL) mismatch -- EDI-only check, no Cabrillo equivalent --
    log_vvv = fb.new_valid_log('YO5VVV', 1, psect='SINGLE')
    log_www = fb.new_valid_log('YO5WWW', 1, psect='SINGLE')
    loc_vvv, loc_www = fb.locators['YO5VVV'], fb.locators['YO5WWW']
    nr_vvv, nr_www = fb.next_serial('YO5VVV'), fb.next_serial('YO5WWW')
    wrong_loc = 'JN12AB'  # structurally valid Maidenhead, but deliberately wrong / unassigned
    # VVV logs the WRONG locator for WWW (should have been loc_www); WWW logs VVV correctly.
    line_vvv = qso_line(fb.qso_date, '1300', 'YO5WWW', '1', '59', nr_vvv, '59', nr_www, wrong_loc)
    line_www = qso_line(fb.qso_date, '1300', 'YO5VVV', '1', '59', nr_www, '59', nr_vvv, loc_vvv)
    note = ("VVV logged WWW's WWL as {} instead of WWW's real header locator {} -- "
            "compare_qso's EDI-only locator cross-match (EDI-010/XC-005 step 7) fails "
            "('Qth locator mismatch'), overwritten per GAP-015. This check has no Cabrillo "
            "equivalent (CAB-003).").format(wrong_loc, loc_www)
    log_vvv.add_qso(line_vvv, 'locator_mismatch', 'not_confirmed:No qso found on YO5WWW log',
                    partner_callsign='YO5WWW', note=note)
    log_www.add_qso(line_www, 'locator_mismatch', 'not_confirmed:No qso found on YO5VVV log',
                    partner_callsign='YO5VVV', note=note)

    # -- 11. Duplicate-in-period: XXA works XXB twice in the same period --
    log_xxa = fb.new_valid_log('YO5XXA', 1, psect='SINGLE')
    log_xxb = fb.new_valid_log('YO5XXB', 1, psect='SINGLE')
    loc_xxa, loc_xxb = fb.locators['YO5XXA'], fb.locators['YO5XXB']
    nr_xxa1 = fb.next_serial('YO5XXA')
    nr_xxb1 = fb.next_serial('YO5XXB')
    line_xxa1 = qso_line(fb.qso_date, '1300', 'YO5XXB', '1', '59', nr_xxa1, '59', nr_xxb1, loc_xxb)
    line_xxb1 = qso_line(fb.qso_date, '1300', 'YO5XXA', '1', '59', nr_xxb1, '59', nr_xxa1, loc_xxa)
    log_xxa.add_qso(line_xxa1, 'duplicate_in_period_first', 'confirmed',
                    partner_callsign='YO5XXB', note='First, genuinely valid contact with XXB.')
    log_xxb.add_qso(line_xxb1, 'duplicate_in_period_first', 'confirmed',
                    partner_callsign='YO5XXA')
    nr_xxa2 = fb.next_serial('YO5XXA')
    line_xxa2 = qso_line(fb.qso_date, '1320', 'YO5XXB', '1', '59', nr_xxa2, '59', '900', loc_xxb)
    log_xxa.add_qso(line_xxa2, 'duplicate_in_period_second',
                    "not_confirmed:Qso already confirmed",
                    partner_callsign='YO5XXB',
                    note=("Second contact with the same callsign in the same period. Rejected by "
                          "the _had_qso_with duplicate guard *before* even looking up XXB's log "
                          "(formats/edi.py:763-768/XC-003 step 3) -- note this fires even though "
                          "this second QSO could otherwise be a legitimate separate contact."))

    # -- 12. Checklog-only submitter demonstrating EDI's checklog asymmetry (GAP-005 item 1) --
    log_cka = fb.new_valid_log('YO5CKA', 1, psect='SINGLE')
    log_ckb = fb.new_valid_log('YO5CKB', 1, psect='CHECK', checklog=True)
    loc_cka, loc_ckb = fb.locators['YO5CKA'], fb.locators['YO5CKB']
    nr_cka, nr_ckb = fb.next_serial('YO5CKA'), fb.next_serial('YO5CKB')
    line_cka = qso_line(fb.qso_date, '1300', 'YO5CKB', '6', '59', nr_cka, '59', nr_ckb, loc_ckb)
    line_ckb = qso_line(fb.qso_date, '1300', 'YO5CKA', '6', '59', nr_ckb, '59', nr_cka, loc_cka)
    log_cka.add_qso(line_cka, 'checklog_confirms_partner', 'confirmed',
                    partner_callsign='YO5CKB',
                    note=("CKB is a checklog-only submission (loaded from checklogs/, "
                          "use_as_checklog=True). EDI's _find_active_log uses "
                          "exclude_checklog=False for the *partner* side (XC-003), so CKB's "
                          "checklog CAN confirm CKA's QSO -- this is the EDI/Cabrillo asymmetry "
                          "documented in GAP-005 item 1 (Cabrillo excludes checklogs "
                          "unconditionally on both sides and could never confirm this)."))
    log_ckb.add_qso(line_ckb, 'checklog_never_scored', 'not_evaluated:cc_confirmed stays None',
                    partner_callsign='YO5CKA',
                    note=("CKB's own log is never chosen as the *searching* log1 because "
                          "exclude_checklog=True on that side (XC-003) -- CKB's copy of this "
                          "QSO is never run through crosscheck_band's loop body at all, so "
                          "cc_confirmed stays None (not True/False) and qso.points stays None. "
                          "In -v -o json output this appears in the 'qso_valid' bucket labelled "
                          "'None : Not confirmed' because formatters.py's `if cc_confirmed is "
                          "False` branch takes the *other* path for None (XC-006)."))

    # -- 13. Malformed QSO lines (format-level) exercising -slc/-mlc paths too --
    log_qln = fb.new_valid_log('YO5QLN', 1, psect='SINGLE')
    log_qlm = fb.new_valid_log('YO5QLM', 1, psect='SINGLE')
    loc_qln, loc_qlm = fb.locators['YO5QLN'], fb.locators['YO5QLM']
    nr_qln, nr_qlm = fb.next_serial('YO5QLN'), fb.next_serial('YO5QLM')
    good_line = qso_line(fb.qso_date, '1300', 'YO5QLM', '1', '59', nr_qln, '59', nr_qlm, loc_qlm)
    log_qln.add_qso(good_line, 'genuine_alongside_malformed', 'confirmed',
                    partner_callsign='YO5QLM')
    log_qlm.add_qso(qso_line(fb.qso_date, '1300', 'YO5QLN', '1', '59', nr_qlm, '59', nr_qln, loc_qln),
                    'genuine_alongside_malformed', 'confirmed', partner_callsign='YO5QLN')

    too_short = '160507;1200;YO5QLM;1;59'
    log_qln.add_qso(too_short, 'malformed_too_short', 'invalid:Qso line is too short',
                    note='Line is under the 40-char minimum (EDI-006).')

    wrong_field_count = '160507;1200;YO5QLM;1;59;001;59;005;{}'.format(loc_qlm)
    log_qln.add_qso(wrong_field_count, 'malformed_wrong_field_count',
                    'invalid:Incorrect Qso line format (incorrect number of fields).',
                    note='Only 9 fields (8 separators) present; REGEX_MINIMAL_QSO_CHECK needs 15.')

    bad_rst = qso_line(fb.qso_date, '1300', 'YO5QLM', '1', 'XYZ', nr_qln, '59', nr_qlm, loc_qlm)
    log_qln.add_qso(bad_rst, 'malformed_bad_rst_regex',
                    "invalid:Qso field <rst sent> has an invalid value (XYZ)",
                    note='Matches the loose 15-field minimal pattern but fails REGEX_MEDIUM_QSO_CHECK '
                         'on the rst_sent field -> field-specific message (EDI-006).')

    bad_nr = qso_line(fb.qso_date, '1300', 'YO5QLM', '1', '59', 'ABCD', '59', nr_qlm, loc_qlm)
    log_qln.add_qso(bad_nr, 'malformed_bad_serial_regex',
                    "invalid:Qso field <rst send nr> has an invalid value (ABCD)",
                    note="nr_sent='ABCD' fails \\d{1,4}; field_names maps this position to "
                         "'rst send nr' (formats/edi.py:547-548).")

    bad_date = qso_line('160532', '1300', 'YO5QLM', '1', '59', nr_qln, '59', nr_qlm, loc_qlm)
    log_qln.add_qso(bad_date, 'malformed_bad_date_semantic', 'invalid:Qso date is invalid',
                    note="'160532' is 6 digits (passes both minimal and medium regexes syntactically) "
                         "but day 32 does not exist -> generic_qso_validator's strptime raises (EDI-007).")

    bad_hour = qso_line(fb.qso_date, '9999', 'YO5QLM', '1', '59', nr_qln, '59', nr_qlm, loc_qlm)
    log_qln.add_qso(bad_hour, 'malformed_bad_hour_semantic', 'invalid:Qso hour is invalid',
                    note="'9999' passes the \\d{4} digit-count regex but is not a valid HHMM time.")

    # NEW FINDING (not in specs/09-known-gaps-and-deviations.md, confirmed by self-verification):
    # LogQso.parse_qso_fields() extracts fields using REGEX_MINIMAL_QSO_CHECK, whose *last*
    # group is `(?P<duplicate_qso>.*?)` with no trailing anchor/literal after it. Because
    # re.match doesn't require full-string consumption and the group is lazy, this group
    # always captures '' regardless of what's actually in the 15th field -- so
    # generic_qso_validator's `if qso_fields['duplicate_qso'].upper() == 'D'` check
    # (formats/edi.py:633-635) can never fire: the field is permanently unreachable dead
    # code. Confirmed directly: re.match(REGEX_MINIMAL_QSO_CHECK, '...;D').group('duplicate_qso')
    # == '' even though the raw line ends in ';D'. Flagged for format-specialist -- NOT worked
    # around in application code here, only reflected in this fixture's expected outcome below
    # (which documents the *actual*, buggy behavior: the trailing ';D' is silently ignored, so
    # this line parses as a perfectly valid QSO, identical in content to the earlier genuine
    # QLN<->QLM contact above -- making it a *second* contact with the same partner in the same
    # period, which the duplicate-in-period guard (XC-003 step 3) then rejects instead).
    dup_marker = qso_line(fb.qso_date, '1300', 'YO5QLM', '1', '59', nr_qln, '59', nr_qlm, loc_qlm,
                          duplicate_qso='D')
    log_qln.add_qso(dup_marker, 'malformed_duplicate_flag_dead_code_bug',
                    'not_confirmed:Qso already confirmed',
                    partner_callsign='YO5QLM',
                    note="INTENDED (per EDI-007 spec) was 'Qso marked as duplicate' (QSO-parse-"
                         "level invalid, since duplicate_qso='D'). ACTUAL/observed: the 'D' is "
                         "never parsed (dead-code bug above), so this QSO is treated as valid and "
                         "identical to the earlier genuine QLN<->QLM contact -> rejected by the "
                         "duplicate-in-period guard as 'Qso already confirmed' instead. This "
                         "fixture intentionally encodes the ACTUAL behavior, not the nominally-"
                         "documented one -- see the NEW FINDING comment just above in the "
                         "generator source.")

    # -- 14. Malformed QSO lines (rules-based) --
    log_qlr = fb.new_valid_log('YO5QLR', 1, psect='SINGLE')
    log_qls = fb.new_valid_log('YO5QLS', 1, psect='SINGLE')
    loc_qlr, loc_qls = fb.locators['YO5QLR'], fb.locators['YO5QLS']
    nr_qlr, nr_qls = fb.next_serial('YO5QLR'), fb.next_serial('YO5QLS')
    good_line2 = qso_line(fb.qso_date, '1300', 'YO5QLS', '1', '59', nr_qlr, '59', nr_qls, loc_qls)
    log_qlr.add_qso(good_line2, 'genuine_alongside_malformed', 'confirmed', partner_callsign='YO5QLS')
    log_qls.add_qso(qso_line(fb.qso_date, '1300', 'YO5QLR', '1', '59', nr_qls, '59', nr_qlr, loc_qlr),
                    'genuine_alongside_malformed', 'confirmed', partner_callsign='YO5QLR')

    before_start = qso_line('160101', '1200', 'YO5QLS', '1', '59', nr_qlr, '59', nr_qls, loc_qls)
    log_qlr.add_qso(before_start, 'malformed_date_before_contest',
                    'invalid:Qso date is invalid: before contest starts',
                    note="Date 20160101 is before rules.contest_begin_date=20160501 "
                         "(rules_based_qso_validator, EDI-008).")

    bad_mode = qso_line(fb.qso_date, '1300', 'YO5QLS', '7', '59', nr_qlr, '59', nr_qls, loc_qls)
    log_qlr.add_qso(bad_mode, 'malformed_mode_not_configured',
                    'invalid:Qso mode is invalid: not in defined modes',
                    note="mode=7 (RTTY) is a syntactically valid single digit but not in "
                         "rules modes=1,2,6 (EDI-008/RULES-008).")

    filtered_call = qso_line(fb.qso_date, '1300', 'DL5ZZZ', '1', '59', nr_qlr, '59', '777', 'JN58TD')
    log_qlr.add_qso(filtered_call, 'malformed_qso_callregexp_filtered',
                    "invalid:Qso callsign is not accepted based on 'callregexp' from rules files",
                    note="Contacted call 'DL5ZZZ' does not match [extra] callregexp=yo at the "
                         "QSO level (rules_based_qso_validator, EDI-008) -- distinct from the "
                         "header-level callsign filter demonstrated by the DL1ABC log below.")

    # -- 15. Whole-log header validation failures (contribute zero cross-checked QSOs) --
    fb.new_invalid_log(
        'no_pcall', {
            'PWWLo': fb.next_locator('HEADER_MISSING_PCALL'),
            'PBand': fb.band_field_value(1), 'PSect': 'SINGLE', 'TDate': fb.tdate,
        }, note="PCall field entirely absent -> 'PCall field is not present'.")

    fb.new_invalid_log(
        'badcall', {
            'PCall': 'YO5', 'PWWLo': fb.next_locator('HEADER_BADCALL'),
            'PBand': fb.band_field_value(1), 'PSect': 'SINGLE', 'TDate': fb.tdate,
        }, note="PCall='YO5' fails the generic callsign regex (no trailing letters after the "
                "digit) -> 'PCall field content is not valid'.")

    fb.new_invalid_log(
        'YO5DTA', {
            'PCall': 'YO5DTA', 'PWWLo': fb.next_locator('YO5DTA'),
            'PBand': fb.band_field_value(1), 'PSect': 'SINGLE',
            'TDate': '2016-05-07;2016-05-08',
        }, note="TDate uses dashes, fails generic '%Y%m%d' parsing -> "
                "'TDate field value is not valid'.")

    fb.new_invalid_log(
        'YO5DTB', {
            'PCall': 'YO5DTB', 'PWWLo': fb.next_locator('YO5DTB'),
            'PBand': fb.band_field_value(1), 'PSect': 'SINGLE',
            'TDate': '20160101;20160102',
        }, note="TDate parses fine but is outside rules.contest_begin_date/end_date "
                "(20160501-20160518) -> rules_based_validate_date fails.")

    fb.new_invalid_log(
        'YO5CAT1', {
            'PCall': 'YO5CAT1', 'PWWLo': fb.next_locator('YO5CAT1'),
            'PBand': fb.band_field_value(1), 'PSect': 'FOOBARBAZ', 'TDate': fb.tdate,
        }, note="PSect='FOOBARBAZ' matches no configured [categoryN] regexp.")

    fb.new_invalid_log(
        'YO5LOC1', {
            'PCall': 'YO5LOC1', 'PWWLo': 'ZZ99ZZ',
            'PBand': fb.band_field_value(1), 'PSect': 'SINGLE', 'TDate': fb.tdate,
        }, note="PWWLo='ZZ99ZZ' -- 'Z' is outside the Maidenhead a-r first-pair range.")

    fb.new_invalid_log(
        'YO5BND1', {
            'PCall': 'YO5BND1', 'PWWLo': fb.next_locator('YO5BND1'),
            'PBand': '50 MHz', 'PSect': 'SINGLE', 'TDate': fb.tdate,
        }, note="PBand='50 MHz' matches neither [band1] (144|145|2m) nor [band2] (430|432|435|70cm).")

    fb.new_invalid_log(
        'DL1ABC', {
            'PCall': 'DL1ABC', 'PWWLo': fb.next_locator('DL1ABC'),
            'PBand': fb.band_field_value(1), 'PSect': 'SINGLE', 'TDate': fb.tdate,
        }, note="Callsign is well-formed but does not match [extra] callregexp=yo -- demonstrates "
                "EDI's national-contest callsign filtering (RULES-006) actually rejecting a log; "
                "Cabrillo has no equivalent filter at all (GAP-003).",
        gap_ref='GAP-003')

    # -- Optional padding to satisfy a higher --operators floor ---------
    existing_ops = {log.callsign for log in fb.logs if log.valid_expected}
    pad_idx = 0
    while len(existing_ops) < operators_min:
        pad_idx += 1
        call = 'YO5PAD{:02d}'.format(pad_idx)
        if call in existing_ops:
            continue
        partner_pool = band1_calls  # pad against the existing band1 mesh
        partner = partner_pool[pad_idx % len(partner_pool)]
        pad_log = fb.new_valid_log(call, 1, psect='SINGLE')
        fb.add_genuine_pair(pad_log, band1_logs[partner], mode='1', rst='59',
                            hour='1305', scenario='genuine_padding_for_operator_floor')
        existing_ops.add(call)

    return _finalize_manifest(fb, manifest_notes)


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
            'band_nr': getattr(log, 'band_nr', None),
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
        filename = '{}.edi'.format(log.callsign_label)
        path = os.path.join(target_dir, filename)
        log.write(path)
        log_manifest['path'] = path
