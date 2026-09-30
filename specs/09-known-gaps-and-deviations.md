# 09 — Known Gaps, Bugs, and Doc/Code Deviations

This file exists because SDD only works if drift between spec, docs, and code is
tracked explicitly rather than smoothed over. Everything here was found by reading
the actual source while writing specs `01`-`08`, not carried over from
`memory-bank/` unless marked "confirmed from memory-bank".

## GAP-001 (bug): Cabrillo `RTTY` mode alias is silently overwritten
`formats/cabrillo/constants.py` defines `CABRILLO_MODE_ALIASES` as a dict literal
containing `'RTTY': 'RTTY'` and, later in the same literal, `'RTTY': 'DIGI'`
(`RTTYM` block). Python keeps the last duplicate key, so
`normalize_cabrillo_mode('RTTY')` returns `'DIGI'`, not `'RTTY'`, despite `RTTY`
also being a plain top-level entry in `CABRILLO_MODE_ALIASES` and appearing as a
documented standalone mode in `README.md`'s mode list (`CW, SSB, DIGI, FM, AM, RTTY`).
**Impact**: a contest whose rules allow `RTTY` but not `DIGI` will reject every
real RTTY QSO as an invalid mode. Fix belongs to `format-specialist` (remove the
duplicate key); needs a regression test in `test_cabrillo.py` asserting
`normalize_cabrillo_mode('RTTY') == 'RTTY'`.

## GAP-002: CSV output is cross-check-only (scope limit, not a bug)
`output/formatters.py:print_csv_output` raises `NotImplementedError` for
single-log/multi-log modes. This looks intentional (`README.md`'s examples never
show `-o csv` for `-slc`/`-mlc`) — treat extending it as a feature request, not a
fix, and get explicit sign-off before doing so since the CSV schema
(`Callsign, Country, Continent, ITU, CQ, ValidLog, Band, Category, ConfirmedQso, Points`)
is cross-check-shaped and would need a different schema for per-log validation errors.

## GAP-003: `[extra]` header-field rules are EDI-only
`Rules.contest_extra_fields` (RULES-006) is consulted by `formats/edi.py`'s
`validate_header` for `email`/`address`/`name`, and by **EDI's QSO validator only**
(`formats/edi.py:650-656`) for `callregexp`-based callsign filtering.
**Cabrillo's `Log.validate_header` never reads `contest_extra_fields` at all** —
`EMAIL`/`NAME`/`ADDRESS` are extracted but never required or format-checked —
**and `formats/cabrillo/qso.py` has no reference to `callregexp`/`contest_extra_fields`
either**, so Cabrillo QSOs are never filtered by it. If a national HF contest
needs the same callsign-filtering or mandatory-contact-info behavior EDI has,
it does not currently exist for Cabrillo — this is a feature gap, not a subtle
bug, and should be scoped explicitly before implementing (does `callregexp`
filtering make sense for an international HF contest cross-check the same way
it does for a national VHF one?).

## GAP-004: Cabrillo has defined-but-dead header validators
`Log.validate_band`, `rules_based_validate_band`, `validate_date`,
`rules_based_validate_date`, `validate_email` all exist in
`formats/cabrillo/log.py` but are never invoked from `validate_header()`.
Confirmed consistent with `memory-bank/progress.md`'s "Known Issues" list.
Practical effect: `CATEGORY-BAND` is accepted verbatim with no format check even
when rules are supplied — a malformed band value (e.g. `CATEGORY-BAND: banana`)
passes header validation and will simply fail to match any `[bandN]` regexp
later, producing a confusing "no active log for this band" cross-check error
instead of a clear header error. Wiring these in is a `format-specialist` task;
needs new tests before being enabled, since existing fixtures may currently rely
on lenient band acceptance.

## GAP-005: EDI and Cabrillo cross-check diverge in three ways that look unintentional
1. **Checklog asymmetry**: EDI's `_find_active_log` takes `exclude_checklog`,
   used as `True` for the searching operator's log and `False` for the partner's
   — so a checklog-only submission *can* confirm someone else's QSO in EDI.
   Cabrillo's `_find_active_log` has no such parameter and excludes checklogs
   unconditionally on both sides — a checklog-only Cabrillo submission can never
   confirm anyone.
2. **Exchange/serial comparison type**: `compare_qso`'s serial-number cross-match
   casts both sides to `int()` in EDI but compares raw strings in Cabrillo. A
   Cabrillo pair like `'001'` vs `'1'` would mismatch where the equivalent EDI
   pair would match.
3. **Candidate search strategy**: EDI's `_find_qso_candidates` yields every
   textually-matching candidate and the caller tries each through full
   `compare_qso` until one passes; Cabrillo's `_find_matching_qso` returns only
   the *first* textually-matching candidate and never retries. If a partner has
   two QSOs from the same callsign in the same period, EDI can still confirm the
   correct one; Cabrillo may report a spurious RST/serial/time mismatch against
   the wrong candidate instead.

None of these are documented as intentional format differences anywhere. Before
"fixing" any of them, confirm with the maintainer whether Cabrillo's stricter
behavior is deliberate (e.g. checklog semantics may genuinely differ between HF
and VHF contest culture) — this is exactly the kind of decision `rules-scoring-specialist`
and `format-specialist` should flag rather than silently unify.

## GAP-006: Fragile scoring-path selector (confirmed from memory-bank)
`_standard_scoring`'s `qso_points_normal != 1` check (SCORE-003) is a proxy for
"was `[scoring] qso_points` actually configured", but `1` is also the
`ScoringMixin` default when `[scoring]` is absent entirely, *and* a valid
explicit value a contest author could set. Recommended fix (not yet done):
replace with an explicit check for whether `'scoring'` is a section in
`rules.config`, threaded through as an argument rather than inferred from the
point value.

## GAP-007: Cross-check log selection depends on filesystem mtime
`mark_older_logs` (`common/crosscheck.py:81-92`) picks the "active" log per
operator per band by `os.path.getmtime`, not by any field inside the log file
(no revision marker, no "submitted at" timestamp in Cabrillo/EDI headers).
Re-extracting a logs folder from a zip, syncing via a tool that rewrites mtimes,
or a fresh `git clone` can all change which of an operator's duplicate
submissions is treated as authoritative, with no warning. Worth flagging to the
maintainer as a robustness gap even though it's unlikely to be hit in normal
single-extraction contest workflows.

## GAP-008: Silent fallback to base `Rules` class for unmapped formats
`logXchecker.py:_get_rules_class` falls back to the plain `Rules` class (no
`RulesVhf`/`RulesHf` mode-parsing specialization) if the INI's `[log] format`
isn't a key in `FORMAT_RULES_MAP` — instead of raising a clear "unsupported
format" error at rules-load time. This means a rules file with e.g.
`format=adif` today loads "successfully" as a generic `Rules` instance (with
`contest_qso_modes` raising only if `modes` itself is malformed) and only fails
later, confusingly, when `_get_log_format_module('ADIF')` tries to import the
nonexistent `adif` module. When ADIF support is added, `FORMAT_RULES_MAP` must
gain an explicit `'ADIF': 'rules_adif.RulesAdif'` (or similar) entry — don't
rely on the fallback.

## GAP-009 (doc drift, now corrected here): `memory-bank/` docs were stale
Two confirmed discrepancies found while writing these specs:
- `memory-bank/techContext.md:64` reports `test_cabrillo.py: 46 tests`; the file
  on disk currently defines 64 `test_` functions — stale and shouldn't be
  trusted without re-checking.
- `README.md:258-330` has a "Simple HF rules format (YODX contest example)"
  section (`name=YODX 2024`), but that example config has no
  `custom_scoring=YODX` line, and `README.md:110`'s prose names only `DRACULA`
  as a possible `custom_scoring` value. So the README shows a rules example
  *named* YODX without ever documenting the `custom_scoring=YODX` engine
  (`_yodx_scoring` in `formats/cabrillo/scoring.py`) that actually exists in
  code and has its own dedicated fixture, `test_logs/rules_hf_yodx.config`
  (which *does* set `custom_scoring=YODX`), added per the git history
  (`91b48f8 Added custom scoring for YO DX HF Contest`) after the README's
  custom-scoring prose was last updated. `06-scoring-spec.md` (SCORE-005) is the
  first place the `YODX` engine itself is actually specified.
Treat `memory-bank/` and `README.md` as a helpful starting point for
*architecture and intent*, but always verify specifics (test counts, which
custom-scoring values exist) against the current source before trusting them —
this is why these specs cite file:line rather than repeating that prose.

## GAP-010 (FIXED — see `specs/10-dracula-transylvania-2026.md` DRACULA-004): DRACULA's `YO_COUNTY` multiplier is now validated against `is_yo_county`; `dracula_county_list` remains unused
**Update**: the multiplier-validation half of this gap is now fixed.
`_compute_multiplier_for_qso`'s DRACULA branch (`formats/cabrillo/scoring.py`)
now calls `is_yo_county` on the exchange value before returning a
`('YO_COUNTY', exchange_value)` tuple — exactly like the sibling `YODX`
branch already did — instead of accepting any non-empty string unvalidated.
This also made the function caller-aware: a YO caller now gets no county
multiplier at all for a YO-YO contact (DXCC entities + DRC only, per the
official rules), matching the docx's section 8. See `specs/06-scoring-spec.md`
SCORE-006 and `test_gaps_scoring.py`'s `TestGap010DraculaCountyMultiplierNowValidated`
(the old characterization test asserting the buggy unvalidated behavior was
updated to assert the fix, per that gap test file's own stated convention).

**Still true, not in scope for this fix**: `ScoringMixin.contest_dracula_county_list`
(RULES-007) parses a multiline `[scoring] dracula_county_list` INI field into
`{district: [counties]}`, but no code anywhere reads this property —
confirmed dead code. DRACULA county validation is backed by the hardcoded
`common.dxcc.YO_COUNTIES`/`is_yo_county` table (via the fix above), not by
this INI field. Confirm with the maintainer whether `contest_dracula_county_list`
should be wired up as an alternative/override to the hardcoded table, or
removed from `ScoringMixin` as dead config surface — this part of the
original gap is unchanged.

## GAP-011: `common/operator.py` is unused duplication, and is itself broken if called
`common/operator.py` defines a base `Operator` class specifically so both format
modules could share it (per `memory-bank/systemPatterns.md`'s description of the
`common/` package), but neither `formats/edi.py` nor `formats/cabrillo/operator.py`
actually imports it — both define their own structurally-identical `Operator`
class instead (COMMON-001). Low-risk today because nothing imports
`common.operator.Operator` at all — and that's fortunate, because its
`add_log_by_path` method references a bare `Log` name that is never imported
into `common/operator.py`, so calling it would raise `NameError`. Should be
cleaned up next time either format's copy is touched: fix the missing `Log`
import in `common/operator.py` *before* pointing any new format module at it,
rather than adding a fourth (equally duplicated) copy.

## GAP-013: Standard-scoring pair dedup awards points to only one side of a confirmed QSO
`_standard_scoring`'s dedup key (`(mode, min(callsign1, callsign2), max(callsign1, callsign2))`,
`formats/cabrillo/scoring.py:319`, see SCORE-002) is **symmetric** — identical
regardless of which of the two operators in the contact is currently being
scored. `crosscheck_band` scores each operator's own log independently, so for
any confirmed QSO pair, whichever operator's QSO is processed first (by
dict-iteration order over `operator_instances`, i.e. roughly the OS's log-folder
listing order) claims the `qso_points_normal` points, and the *other* operator's
matching QSO for the exact same contact scores `0` — not because it's an actual
duplicate, but because the pair key was already marked seen. This affects every
contest whose rules set a non-default `qso_points` (e.g.
`test_logs/rules_hf_rro_2024.config`'s `qso_points=2`). Confirm with the
maintainer whether this is intended (e.g. "score is per-contact, assigned once,
by convention to whoever's log was processed first" — unlikely to be desired)
before treating it as correct; this looks like a genuine scoring bug, not a
documented design choice.

## GAP-014: The 10-minute multi-op rule keys off the rules file's category *name*, so it silently never fires for some contests
`_apply_10_minute_rule` (SCORE-008) checks `log.category.upper() == 'MULTI'`,
and `log.category` (when rules are supplied) is set to the matching
`[categoryN] name` value from the rules file (`formats/cabrillo/log.py:123-124,300`),
not the raw `CATEGORY-OPERATOR` log line. `test_logs/rules_hf_yodx.config` names
its multi-op category `Multi`, so the rule applies there — but
`test_logs/rules_hf_dracula.config` names its multi-op category
`MO-AB-HP MIXT` (matching `README.md`'s own Dracula example,
`[category7] name=MO-AB-HP MIXT`), so **the 10-minute rule never fires for the
DRACULA contest as currently configured**. If the maintainer wants the 10-minute
rule to apply to DRACULA multi-op stations, either the rules file's category
name needs to literally be `Multi`, or the check needs to key off something
more structural than an arbitrary display-name string equality.

## GAP-015: EDI discards the specific cross-check mismatch reason when every candidate QSO fails
EDI's candidate-retry loop (`formats/edi.py:793-798`) captures each failed
candidate's specific `compare_qso` error (e.g. `'Rst mismatch'`,
`'Serial number mismatch'`, `'Different date/time between qso's'`) into
`qso1.cc_error` via `_compare_qso_pair` — but if no candidate ultimately passes,
that specific reason is **unconditionally overwritten** with the generic
`'No qso found on {callsign2} log'` (`formats/edi.py:800-802`). So for EDI,
a real near-miss (e.g. the partner logged the wrong RST) and a genuine absence
(the partner never logged this contact at all) produce the *same* user-facing
error message. Cabrillo, having no retry loop (XC-004's single-candidate
behavior), does not have this overwrite and surfaces the specific
`compare_qso` failure reason for its one candidate. Whether EDI should be
changed to preserve the last specific error (closer to Cabrillo's behavior) or
Cabrillo should gain EDI's retry-then-generalize behavior is a design call for
`format-specialist`/the maintainer, not an obvious one-line fix — the two
formats currently give meaningfully different debugging experiences for the
same underlying situation.

## GAP-016: Cabrillo's `ALL`-band log fallback doesn't filter QSOs by actual frequency
When an operator has no log matching a specific band's regexp but has a log
with `CATEGORY-BAND: ALL`, `_find_active_log` falls back to that log for
*every* band-number pass of the cross-check's outer loop
(`formats/cabrillo/crosscheck.py:62-66,116-124`) — and every QSO inside that
`ALL` log is checked against band-specific partner logs regardless of the
QSO's own frequency. A QSO actually made on 14 MHz can be evaluated during the
"80m" band pass just as much as the "20m" pass, and if it happens to match a
partner's QSO during the wrong pass, it gets scored and multiplier-tagged
under that wrong `band_nr`. EDI has no `ALL`-band concept at all, so this is
Cabrillo-only. Needs a decision from `format-specialist`: either filter `ALL`
logs' QSOs by their own parsed frequency (`_get_band_from_frequency`, already
used by the 10-minute rule) before matching them into a given band pass, or
confirm this is acceptably rare/harmless in practice (e.g. if `ALL`-band logs
are uncommon among real submissions) before leaving it as-is.

## GAP-018 (bug, found while generating test fixtures, verified independently): EDI's `;D` duplicate-QSO marker is never detected
`LogQso.REGEX_MINIMAL_QSO_CHECK`'s final capture group is
`(?P<duplicate_qso>.*?)` (`formats/edi.py:474`) — lazy, with no anchor or
literal after it, and used with `re.match` (which does not require consuming
the whole input string). Verified directly:
```
line = '160507;1450;LZ7J;1;59;006;59;019;;KN22HB;362;;N;;D'  # 50 chars, explicit trailing D
m = re.match(LogQso.REGEX_MINIMAL_QSO_CHECK, line)
m.group('duplicate_qso')  # -> '' , not 'D'
m.span()                  # -> (0, 49) — one character short of the full 50-char line
```
The lazy `.*?` group matches the empty string as soon as it possibly can, and
since `re.match` doesn't require reaching the end of the string, the regex
engine never backtracks to actually consume the trailing `D`. **Practical
effect**: `generic_qso_validator`'s `self.qso_fields['duplicate_qso'].upper() == 'D'`
check (`formats/edi.py:633-635`, EDI-007) is permanently unreachable — a QSO
line explicitly marked as a duplicate by the logging software (`;D` in the
15th field) is silently parsed as an ordinary, valid QSO and passed on to
rules-based validation and cross-check like any other contact. The intended
`'Qso marked as duplicate'` header/QSO error never fires for any input.
Suggested fix (not yet done): anchor the regex to the end of the line for this
group (e.g. `(?P<duplicate_qso>.*)$`) or otherwise make the match require
consuming the whole line — needs a new positive-case test in `test_edi.py`
(none currently exercises this field) alongside the fix, since the field is
entirely untested today.

## GAP-019 (found while implementing DRACULA-006, see `specs/10-dracula-transylvania-2026.md`): `_find_matching_qso` isn't mode-aware, so same-period multi-mode contacts may not fully round-trip confirm
DRACULA-006 fixed `crosscheck_band`'s `_had_qso_with` dedup guard to key on
mode as well as callsign+period, so a same-band, different-mode second
contact with the same partner is no longer short-circuited as
`'Qso already confirmed'` before comparison even runs. However,
`_find_matching_qso` (`formats/cabrillo/crosscheck.py`, XC-004) still returns
only the **first** callsign+period match in the partner's log, with no mode
filter and no "already consumed" tracking — the same limitation already
described for GAP-005's point 3 (candidate-retry strategy), just now
concretely reachable via a different-mode path that the GAP-013-style dedup
fix newly unblocks. **Practical effect**: an operator who legitimately worked
the same partner twice in the same period on two different modes may still
see one side spuriously fail with `'Mode mismatch'` (or another
`compare_qso` error) instead of fully confirming, if `_find_matching_qso`
happens to pick the wrong-mode candidate first. This was not in DRACULA-006's
fix scope (the spec's target was specifically the dedup guard) and was left
untouched deliberately — fixing `_find_matching_qso` to filter/retry by mode
(mirroring EDI's candidate-retry generator, GAP-005 point 3) is a natural
follow-up, tracked here rather than done silently as scope creep on the
DRACULA rules-alignment work.

## GAP-017: XML output prints Python `bytes` repr
`common.serialization.dict_to_xml` returns whatever `dicttoxml.dicttoxml()`
returns, which is `bytes`. `logXchecker.py`'s `-o xml` path does
`print(lfmodule.dict_to_xml(output))`, so the actual terminal output is a
`b'<?xml version=...'` byte-string repr, not clean XML text. Whether this is
"working as observed" (some consumer downstream decodes it) or an oversight is
unconfirmed — flag before changing, since any existing downstream consumer might
already be parsing the `b'...'`-wrapped form.
