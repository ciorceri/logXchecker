# 04 — EDI Format Spec

Source: `formats/edi.py`. (Root-level `edi.py` is a backward-compat shim that re-exports this module — don't duplicate logic there.)

## EDI-001: Header field extraction
`Log.get_field(field)` (`formats/edi.py:273-286`) scans every raw line, case-insensitively matching `"{FIELD}="` as a prefix, and collects **all** matches (not just the first) plus the 1-based line number of the last match. A field present more than once is a validation error at the call site, not inside `get_field` itself.

## EDI-002: Required header fields and validation order
Validated in this order inside `validate_header()` (`formats/edi.py:114-266`), each independently gated on presence → single-occurrence → generic validity → rules-based validity (only if `rules` is set):

| Field | EDI key | Generic validator | Rules-based override |
|---|---|---|---|
| Callsign | `PCall` | `validate_callsign`: regex `^\s*(\w+[0-9]+\w+/?\w*)\s*$` | if rules has `callregexp` in `[extra]`, callsign must additionally match `^\s*({callregexp}).*` (case-insensitive) |
| Grid locator | `PWWLo` | `validate_qth_locator`: Maidenhead `^\s*([a-rA-R]{2}\d{2}[a-xA-X]{2})\s*$` | none |
| Band | `PBand` | `validate_band` (generic pattern table, EDI-003) — **only checked when no rules given** | `rules_based_validate_band` against `rules.contest_band(n)['regexp']` for every band 1..N |
| Category/section | `PSect` | `validate_category` (generic single/multi/checklog patterns) — **only checked when no rules given** | `rules_based_validate_category` against every `[categoryN]` regexp; on match, `self.category` is set to the rule's `name`, not the raw value |
| Contest date | `TDate` | `validate_date`: value must be `"{begin};{end}"`, both parsing as `%Y%m%d` | `rules_based_validate_date`: `begin >= rules.contest_begin_date and end <= rules.contest_end_date` (string comparison, not date-aware — relies on `YYYYMMDD` lexical ordering) |

`valid_header` becomes `True` only if callsign, locator, band, category, and date **all** resolved (`formats/edi.py:216-217`) — checked *before* the `[extra]` fields below are validated, so `valid_header` can be flipped back to `False` afterward.

## EDI-003: Generic band/category patterns (used only without rules)
- `_BAND_PATTERNS` (`formats/edi.py:30-34`): `144 → ['144.*','145.*']`, `432 → ['430.*','432.*','435.*']`, `1296 → ['1296.*','1[.,][23].*']`.
- `validate_category` categories (`formats/edi.py:387-391`): `single → ['.*SOSB.*','.*SOMB.*','.*Single.*','^SO$']`, `multi → ['.*MOSB.*','.*MOMB.*','.*Multi.*','^MO$']`, `checklog → ['check','checklog','check log']`.

## EDI-004: `[extra]` fields — email/address/name (`formats/edi.py:219-265`)
Only checked if the field name is in `rules.contest_extra_fields` (RULES-006). For each of `email` (`RHBBS`), `address` (`PAdr1`), `name` (`RName`): missing/duplicate → header error; present but invalid → header error and `valid_header = False` even if it was previously `True`. Validators:
- `validate_email(value)` → delegates to the `validate_email` package (`formats/edi.py:432-435`).
- `validate_address(value)` → `len(value) >= 10` **and** contains at least one of space/comma/period (`formats/edi.py:437-452`).
- name: inline check `len(name[0]) < 8` → invalid (no dedicated method, `formats/edi.py:259`).

## EDI-005: QSO line extraction
`get_qsos()` (`formats/edi.py:288-311`) treats everything between a line starting with `[QSORECORDS` and one starting with `[END` (case-insensitive) as QSO lines, uppercased and stripped. One `LogQso` per line, in file order.

## EDI-006: QSO line format
`REGEX_MINIMAL_QSO_CHECK` (`formats/edi.py:471-474`) is a loose 15-field semicolon-delimited pattern: `date;hour;call;mode;rst_sent;nr_sent;rst_recv;nr_recv;exchange_recv;wwl;points;new_exchange;new_wwl;new_dxcc;duplicate_qso`. A line under 40 chars, or not matching this pattern, is rejected outright (`'Qso line is too short'` / `'Incorrect Qso line format...'`). If it matches the minimal pattern but not the stricter `REGEX_MEDIUM_QSO_CHECK`, the validator walks field-by-field to produce a specific `'Qso field <{name}> has an invalid value ({value})'` message (`formats/edi.py:540-562`).

## EDI-007: Generic per-field QSO validation (`generic_qso_validator`, `formats/edi.py:564-637`)
Independent checks (all run; multiple errors can accumulate on one QSO):
- `date`: `%y%m%d`. `hour`: `%H%M`.
- `call`: `^\w+/?\w+$`.
- `mode`: single digit `^[0-9]$` (raw digit — see RULES-008 for the documented 0-9 meaning, unenforced here).
- `rst_sent`/`rst_recv`: `^[1-5][1-9][1-9]?[aAsS]?$`.
- `nr_sent`/`nr_recv`: `^\d{1,4}$`.
- `exchange_recv`: `^\w{0,6}$`.
- `wwl`: same Maidenhead regex as the header locator.
- `duplicate_qso`: exact value `'D'` (case-insensitive) → invalid with message `'Qso marked as duplicate'`. **⚠ This check is unreachable dead code — see GAP-018.**

## EDI-008: Rules-based QSO validation (`rules_based_qso_validator`, `formats/edi.py:639-699`)
Only runs if `self.rules` is set. In order:
1. If rules has `[extra] callregexp`, the QSO's `call` must match `^\s*{callregexp}` (case-insensitive) or it's rejected — same mechanism as national-contest callsign filtering at the header level.
2. `date` must be within `[contest_begin_date[2:], contest_end_date[2:]]` (2-digit-year sliced comparison, string-lexical).
3. `hour` must be `>= contest_begin_hour` if `date == contest_begin_date[2:]`, and `<= contest_end_hour` if `date == contest_end_date[2:]`.
4. Must fall inside at least one configured period — see EDI-009.
5. `mode` (as `int`) must be in `rules.contest_qso_modes`.

## EDI-009: Period containment algorithm (`qso_inside_period`, `formats/edi.py:701-728`)
For each period 1..N, first cheaply filters by `period.begindate[2:] <= qso.date <= period.enddate[2:]`, then:
- **Same-day period** (`enddate == begindate`): QSO matches iff `beginhour <= qso.hour <= endhour`.
- **Multi-day period**: QSO matches if *any* of: (a) it's on the period's first day and `hour >= beginhour`, (b) it's on the period's last day and `hour <= endhour`, (c) it's strictly between the first and last day (any hour). Returns `(True, period_number)` on first match, `(False, None)` if no period matches. **No rules** → always `(True, None)`.

## EDI-010: Maidenhead distance (fully implemented for EDI)
`qth_distance(qth1, qth2)` (`formats/edi.py:987-1027`): same locator → `1`. Otherwise converts both to lat/long via `conv_maidenhead_to_latlong` (`formats/edi.py:978-984`, using `delta_ord` to map letters/digits to 0-based ordinals) and computes great-circle distance with Earth radius `6373` km, **rounded to the nearest int, and clamped to a minimum of `1`** if the rounded arc distance would be `0`.

## EDI-011: Cross-check entry point
`run_crosscheck(log_class, rules, logs_folder, checklogs_folder)` (`formats/edi.py:1033-1050`) — see `07-crosscheck-spec.md` for the shared pipeline and EDI-specific `crosscheck_band`/`compare_qso` behavior (this module implements the pipeline this way; Cabrillo's is structurally similar but not identical — divergence is called out there).
