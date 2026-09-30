# 05 — Cabrillo Format Spec

Source: `formats/cabrillo/{constants,log,qso,operator}.py`.

## CAB-001: Version detection
The **first line** must match `^START-OF-LOG:\s*(\d+\.\d+)` (case-insensitive, `formats/cabrillo/log.py:88-96`). Only versions `'2.0'` and `'3.0'` are accepted; anything else (or a missing/malformed first line) is a header error (`'Missing or invalid START-OF-LOG header'` / `'Unsupported Cabrillo version: {v}'`) and parsing stops — **no fallback heuristic** for logs with a missing/misplaced START-OF-LOG line.

## CAB-002: Header field parsing (`_parse_cabrillo_header`, `formats/cabrillo/log.py:142-221`)
Scans lines up to the first `QSO:` or `END-OF-LOG:` line. Each `KEY: value` line (colon-split, key uppercased/stripped) is matched against a fixed set of known keys (`CALLSIGN`, `CATEGORY-OPERATOR`, `CATEGORY-BAND`, `CATEGORY-MODE`, `CATEGORY-POWER`, `EMAIL`, `GRID-LOCATOR`, `NAME`, `ADDRESS`, `OPERATORS`, `CONTEST`, `LOCATION`, `CLUB`, `CREATED-BY`, `CLAIMED-SCORE`, `SOAPBOX`, `CATEGORY-ASSISTED`, `CATEGORY-STATION`, `CATEGORY-TIME`, `CATEGORY-TRANSMITTER`, `CATEGORY-OVERLAY`). **Cabrillo V3 nested form** is also supported: a line literally keyed `CATEGORY:` with a `sub_key: value` payload (e.g. `CATEGORY: operator: SO`) maps into the same internal fields. Unknown keys are silently ignored (not an error).

## CAB-003: Required header fields
Only **`CALLSIGN`**, **`CATEGORY-BAND`**, **`CATEGORY-OPERATOR`** are mandatory for `valid_header = True` (`formats/cabrillo/log.py:139`):
- `CALLSIGN` → `validate_callsign`: `^\s*(\w+\/{1})?(\w+[0-9]+)\w+(\/?)\w*\s*$` (allows an optional leading `PREFIX/` and optional trailing `/SUFFIX`).
- `CATEGORY-BAND` → stored **uppercased, unvalidated** as `self.band` (no regex/format check at all — contrast with EDI-002's `PBand` which is always checked against a pattern table even without rules).
- `CATEGORY-OPERATOR` → generic `validate_category` (single/multi/checklog, CAB-006) or rules-based `rules_based_validate_category`, same shape as EDI-002 but with different generic patterns.

`EMAIL`, `NAME`, `ADDRESS`, `GRID-LOCATOR` are extracted if present but **never validated against `[extra]` rules** — see GAP-003. `self.date` is not read from the log at all; it's just set to `rules.contest_begin_date` if rules are provided, else `None` (`formats/cabrillo/log.py:129`) — Cabrillo logs have no log-level date field in this implementation; date validity is entirely a QSO-line concern (CAB-008).

## CAB-004: Mode normalization (`normalize_cabrillo_mode`, `formats/cabrillo/constants.py:118-122`)
Looks up the uppercased mode token in `CABRILLO_MODE_ALIASES` (`constants.py:43-83`), falling back to the raw uppercased token if unmapped. Groups: `SSB` family (`SSB`,`PHONE`,`PH`,`LSB`,`USB` → `SSB`), `DIGI` family (`PSK*`,`JT*`,`FT*`,`FSK*`,`MFSK`,`OLIVIA`,`RTTYM`,`CONTESTI`,`PACKET`,`PAX*`,`THROB`,`WINMOR`,`DOMINO`,`MT63`,`ISCAT`,`QRA64` → `DIGI`), plus `CW`,`FM`,`AM`,`SSTV`,`ATV` map to themselves.

**⚠ See GAP-001**: the dict literal defines `'RTTY': 'RTTY'` and later, in the same literal, `'RTTY': 'DIGI'` — a duplicate key. Python keeps the *last* occurrence, so `CABRILLO_MODE_ALIASES['RTTY']` is actually `'DIGI'`, not `'RTTY'`. Any spec, docstring, or test asserting `normalize_cabrillo_mode('RTTY') == 'RTTY'` is describing the *intended* behavior, not the *actual* one — verify against this file before relying on it.

## CAB-005: QSO line format — two field-count variants
Standard 11-capture-group regex `REGEX_CABRILLO_QSO` (`constants.py:86-99`): `QSO: freq mode date(YYYY-MM-DD) time(HHMM) call1 rst1 exch1 call2 rst2 exch2 [tail]`. A 13-field variant `REGEX_CABRILLO_QSO_13F` (`constants.py:102-115`) is structurally identical except `exch1` and `exch2` each capture **two whitespace-separated tokens** (e.g. serial number + county code). `LogQso.parse_qso_fields` (`formats/cabrillo/qso.py:81-91`) picks the 13-field regex when the line has **≥ 12 whitespace-separated data tokens** after `QSO:`, else the 11-field regex — both `_assign_fields` and `_assign_fields_13f` are currently field-identical implementations (`formats/cabrillo/qso.py:93-137`), so today the two variants only differ in *which raw tokens land in* `nr_sent`/`nr_recv` (single value vs. `"serial county"` combined string), not in downstream field semantics.

`qso_fields['date']` is stored as a 6-digit `YYMMDD` string derived by slicing the `YYYY-MM-DD` capture (`date_raw[2:4]+date_raw[5:7]+date_raw[8:10]`, `qso.py:108`) — same internal representation as EDI, enabling shared comparison logic in cross-check.

## CAB-006: Generic category patterns (`validate_category`, `formats/cabrillo/log.py:275-288`)
`single → ['.*SINGLE.*','.*SO.*']`, `multi → ['.*MULTI.*','.*MO.*','.*MULTI-OP.*']`, `checklog → ['check','checklog','check-log']`. Different from EDI's patterns (EDI-003) — e.g. Cabrillo's `single` pattern (`.*SO.*`) is broader/looser than EDI's `^SO$`.

## CAB-007: Generic per-field QSO validation (`generic_qso_validator`, `formats/cabrillo/qso.py:153-205`)
Same date/hour/call/RST shape as EDI (`%y%m%d`, `%H%M`, `^\w+/?\w+$`, `^[1-5][1-9][1-9]?[aAsS]?$`), but:
- `mode`: valid iff `normalize_cabrillo_mode(...)` produced a non-empty/non-falsy string (no format regex — any non-empty normalized mode passes generic validation; contest-mode membership is a rules-based check, CAB-008).
- `nr_sent`/`nr_recv` (exchange): valid if either a single `\w{1,6}` token **or** two such tokens separated by whitespace (`re_exchange_combined`, `qso.py:190-205`) — accommodates the 13-field serial+county case.

## CAB-008: Rules-based QSO validation (`rules_based_qso_validator`, `formats/cabrillo/qso.py:207-251`)
Order: (1) `qso_fields['mode']` (already normalized) must be in `rules.contest_qso_modes` (`RulesHf`'s uppercased string list) — **not** the raw log token; (2)-(3) date/hour bounds vs contest begin/end, identical shape to EDI-008 steps 2-3; (4) period containment via `qso_inside_period` (CAB-009). **Note**: unlike EDI-008, there is no `callregexp`/`[extra]` filtering step here at all — Cabrillo QSOs are never filtered by national-contest callsign regex (consistent with GAP-003, `[extra]` is EDI-only in practice).

## CAB-009: Period containment algorithm
Byte-for-byte the same algorithm as EDI-009 (`formats/cabrillo/qso.py:253-278` mirrors `formats/edi.py:701-728`) — this is duplicated logic across the two formats rather than shared via `common/`; a bug fix in one must be mirrored in the other until/unless this is refactored.

## CAB-010: Distance is a stub for HF
`formats/cabrillo/constants.py:125-126`: `qth_distance(qth1, qth2)` unconditionally returns `1`. This is intentional per `memory-bank/techContext.md` (HF scoring doesn't use physical distance) — don't "fix" this without a scoring-model discussion; standard scoring's legacy branch (`distance * band multiplier`, SCORE-002) degenerates to just `band multiplier` for Cabrillo as a result.

## CAB-012: Unmatched category records no error
If `CATEGORY-OPERATOR` doesn't match any configured category (generic or rules-based), `validate_category`/`rules_based_validate_category` return `(False, None)` but `validate_header` only reads the second element (`self.category = _cat`, `formats/cabrillo/log.py:123-127`) — it never checks the first (`_res`) and never appends a header error for this case. The log is silently rejected (`valid_header` ends up `False` because `self.category` is `None`) with no line in `errors[ERR_HEADER]` explaining why — a real-world log with a typo'd category value fails cross-check with no diagnostic pointing at the actual cause.

## CAB-011: Dead/unused validation methods (confirmed present, confirmed unused)
`Log.validate_band`, `Log.rules_based_validate_band`, `Log.validate_date`, `Log.rules_based_validate_date`, `Log.validate_email` (`formats/cabrillo/log.py:255-272, 303-328, 313-318`) are all defined but **never called from `validate_header()` or anywhere else** in this module. Practical effect: `CATEGORY-BAND` is accepted verbatim with no regex check even when rules are supplied (contrast CAB-003), and email is captured but never format-checked. See GAP-004.
