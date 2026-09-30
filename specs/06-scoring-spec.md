# 06 — Scoring Spec

Source: `formats/cabrillo/scoring.py` (Cabrillo/HF only — EDI has no equivalent module; EDI scoring is the single legacy line in `crosscheck_band`, see XC-003). `ScoringMixin` defaults are in `03-rules-engine-spec.md#RULES-007`.

## SCORE-001: Scoring dispatch (`apply_custom_scoring`, `scoring.py:235-248`)
```
custom_type = rules.contest_custom_scoring if rules else None
  'DRACULA' → _dracula_scoring(callsign1, callsign2, rules, qso1)
  'YODX'    → _yodx_scoring(callsign1, callsign2, rules, qso1)
  None      → _standard_scoring(callsign1, callsign2, rules, qso1, confirmed_pairs,
                                 band_nr, qso_points_normal, qso_points_special,
                                 special_callsign_list, distance)
  anything else → raise NotImplementedError('Custom scoring type "{type}" is not implemented')
```
`callsign1` is the log owner being scored ("caller"), `callsign2` is the confirmed QSO partner. All three scoring functions return `(True, [])` — the boolean/list pair is assigned to `qso1.cc_confirmed`/`qso1.cc_error`, meaning **a reached scoring function always marks the QSO confirmed with no error**; confirmation failure is decided earlier in `crosscheck_band` (before scoring is ever called).

## SCORE-002: Standard scoring (`_standard_scoring`, `scoring.py:313-327`)
```
if callsign2.upper() in special_callsign_list:
    points = qso_points_special                      # e.g. bonus for a special event station
elif qso_points_normal != 1:
    # a [scoring] qso_points value other than the default 1 is present
    pair_key = (mode, min(callsign1, callsign2), max(callsign1, callsign2))
    if pair_key not seen before (per band, via confirmed_pairs set):
        points = qso_points_normal
    else:
        points = 0                                    # per-mode, per-callsign-pair dedup
else:
    points = distance * band_multiplier                # legacy path — distance always 1 for Cabrillo (CAB-010)
```
`confirmed_pairs` is created once per `run_crosscheck()` call and threaded through every band's `crosscheck_band()` (`formats/cabrillo/crosscheck.py:42-44`), so the per-mode/per-pair dedup is **global across all bands**, not per-band — a station confirming the same partner on the same mode on two different bands only scores the standard points once, the second band's QSO scores `0`.

**⚠ The dedup key is symmetric and shared by *both* operators in the pair** (`min(callsign1, callsign2), max(callsign1, callsign2)` — same tuple regardless of which one is being scored as "caller", `scoring.py:319`). Since `crosscheck_band` iterates operators and scores each one's own confirmed QSO independently, whichever operator's QSO is processed *first* claims the `qso_points_normal` points via `_standard_scoring`, and the other operator's matching QSO for the same contact scores `0` when it's processed afterward — not because it's a duplicate contact, but because it's the *same* contact seen from the other side. This means, for any rules file with a non-default `qso_points` (e.g. `test_logs/rules_hf_rro_2024.config`'s `qso_points=2`), **only one side of each confirmed QSO pair ever scores points**, and which side depends on iteration order over `operator_instances` (a dict — insertion order in current CPython, i.e. roughly the OS's directory-listing order from `load_log_files`). This is not documented anywhere as intentional and is flagged as a new gap — see GAP-013.

## SCORE-003: ⚠ Fragile scoring-path selector
The `qso_points_normal != 1` check is how the code distinguishes "a `[scoring]` section configured real points" from "no scoring configured, use legacy distance*multiplier" — but `contest_qso_points` (`ScoringMixin`) *defaults to* `1` when `[scoring]` is entirely absent, and a contest author could legitimately set `qso_points=1` explicitly, which would be silently treated as "no scoring configured" and fall into the legacy branch. See GAP-006 — flag any touch to this logic rather than patching around it.

## SCORE-004: DRACULA scoring (`_dracula_scoring`, `formats/cabrillo/scoring.py`)
Rewritten per `specs/10-dracula-transylvania-2026.md` DRACULA-002/003 to add
the previously-missing Transylvania-region scoring tier (8 points, both
directions) and to make YO-YO scoring read a real config property
(`contest_yo_to_yo_points`, default `1`) instead of hardcoding `0`.
```
partner_exchange = qso1.qso_fields.get(rules.contest_multiplier_exchange_field, '').strip().upper()
                    # same field _compute_multiplier_for_qso reads (SCORE-006) — no separate config

if callsign2 is a DRACULA special station (is_dracula_special): points = non_yo_to_special_points   # despite the name, applies regardless of caller's YO status
elif callsign1 is YO:
    if callsign2 is YO:
        if is_transylvania_county(partner_exchange): points = yo_to_transylvania_points   # NEW, default 8
        else:                                          points = yo_to_yo_points             # default 1 (was hardcoded 0)
    else:
        points = yo_to_nonyo_points
else:  # callsign1 is non-YO
    if callsign2 is YO:
        if is_transylvania_county(partner_exchange): points = non_yo_to_transylvania_points  # NEW, default 8
        else:                                          points = non_yo_to_yo_points
    elif same DXCC entity:   points = non_yo_same_country_points
    else:                    points = non_yo_dxcc_points
```
Note the special-station branch uses `contest_non_yo_to_special_points` for the point value even when the *caller* is YO — there is no separate `yo_to_special_points` branch reached in this function despite `ScoringMixin` defining `contest_yo_to_special_points` (RULES-007); that property is defined but effectively dead for DRACULA scoring as currently written.

`is_transylvania_county` (`common/dxcc.py`, DRACULA-001) checks a flat
10-county whitelist (`TRANSYLVANIA_COUNTIES`) that cuts across `YO_COUNTIES`
district boundaries — it is a separate, narrower check from `is_yo_county`
(used for multiplier validation, SCORE-006) and is only ever consulted here
for scoring-tier selection, never for multiplier validity.

## SCORE-005: YODX scoring (`_yodx_scoring`, `scoring.py:270-310`)
Continent-aware (uses `get_callsign_continent`, `'EU'` is the only continent treated specially):
```
if callsign1 is YO:
    if callsign2 is YO: points = 0
    elif callsign2's continent == 'EU': points = yo_to_nonyo_same_continent_points
    else:                                points = yo_to_nonyo_points
else:  # callsign1 is non-YO
    if callsign2 is YO: points = non_yo_to_yo_points          # flat — no continent distinction here
    elif same DXCC:      points = non_yo_same_country_points
    elif both continents known and equal: points = non_yo_same_continent_points
    else:                                  points = non_yo_dxcc_points
```
`yo_to_nonyo_same_continent_points` and `non_yo_to_yo_same_continent_points` default to the plain (non-continent) point values if not set in `[scoring]` (RULES-007) — a YODX rules file that doesn't set these explicitly degrades gracefully to non-continent-aware scoring rather than erroring.

**Corrections to the logic above** (verified against `scoring.py:270-310`):
- `'EU'`-is-special treatment applies **only to the YO-caller branch** (`callsign1` is YO, `callsign2` is non-YO, `scoring.py:291`). In the non-YO-caller branch, *any* continent match between caller and partner counts as "same continent" (`continent1 and continent2 and continent1 == continent2`, `scoring.py:306`) — not specifically `'EU'`. So "EU is the only continent treated specially" is true for one branch and false for the other.
- The function's own docstring (`scoring.py:278-280`) describes a continent split for the *non-YO-works-YO* case too, but the actual code for that case (`scoring.py:297-299`) always returns the flat `non_yo_to_yo_points` regardless of continent — the docstring and the implementation disagree; trust the code quoted here, not the docstring, until one of them is fixed.
- `contest_non_yo_to_yo_same_continent_points` (`ScoringMixin`, `scoring.py:138-142`, RULES-007) is defined but **never read** by `_yodx_scoring` or anywhere else — dead code, in the same way `contest_yo_to_special_points` is dead for DRACULA (SCORE-004).

## SCORE-006: Multiplier classification (`_compute_multiplier_for_qso`, `formats/cabrillo/scoring.py`)
Per `specs/10-dracula-transylvania-2026.md` DRACULA-004, this function now
takes an additional `caller_callsign=None` parameter (threaded in from both
call sites — `_compute_multipliers`'s per-log loop and `_apply_10_minute_rule`/
`_classify_qso_multiplier`'s per-QSO loop, both of which pass `log.callsign`)
and the DRACULA branch is now caller-aware, plus validates the exchange value
against `is_yo_county` (closing GAP-010 — see `specs/09-known-gaps-and-deviations.md`'s
updated GAP-010 entry). Returns a `(category, key)` tuple identifying a
unique multiplier, or `None` if the QSO doesn't count toward a multiplier.
Dispatch mirrors `contest_custom_scoring`:
- **YODX**: partner is YO → `('YO_COUNTY', exchange_value)` if the configured exchange field holds a recognized Romanian county code (`is_yo_county`), else `None`; partner is non-YO → `('DXCC', main_prefix_or_first_two_chars)`. Not caller-aware (unchanged by DRACULA-004 — that fix is DRACULA-specific).
- **DRACULA**: partner is a DRC special station → `('DRC', partner_callsign)`; partner is YO →
  - if `caller_callsign` is also YO: `None` — a YO caller's multipliers are DXCC entities + DRC only, no county multiplier, per the official rules (DRACULA-004);
  - else (non-YO/foreign caller): `('YO_COUNTY', exchange_value)` **only if** the exchange value passes `is_yo_county` (GAP-010 fix — previously any non-empty value was accepted unvalidated), else `None`;

  partner is non-YO → `('DXCC', main_prefix_or_first_two_chars)`.
- **Standard** (no custom scoring): extracts a county code via `_extract_county_from_exchange` — **last token** if the exchange field has 2 whitespace-separated tokens, else the whole (single) token (`scoring.py:226-232`). If that equals `contest_multiplier_special_exchange` → `('CAT_A', partner_callsign)`; else `('COUNTY', county_value)`; empty exchange → `None`.

Note: `is_yo_county` (validates against the full `YO_COUNTIES` set) is a
different, broader check than `is_transylvania_county` (SCORE-004's
Transylvania-tier scoring check, `common/dxcc.py`, DRACULA-001) — the two are
never interchangeable; multiplier validity and scoring-tier selection are
deliberately separate checks.

DXCC fallback: if `lookup_callsign(partner_call)` finds nothing, the multiplier key falls back to the callsign's first two characters (`partner_call[:2]`) rather than `None` — a made-up "DXCC" bucket can appear in results for unrecognized callsigns instead of being excluded.

## SCORE-007: Multiplier aggregation (`_compute_multipliers`, `scoring.py:143-171`)
Only runs if `rules.contest_multiplier_enabled` (checked by the caller, `formats/cabrillo/crosscheck.py:49-50`). Counts **distinct** multiplier tuples among QSOs that are both `cc_confirmed` and have `points > 0` (a confirmed-but-zero-point QSO, e.g. from the standard-scoring dedup in SCORE-002 or zeroed by the 10-minute rule in SCORE-008, does **not** contribute a multiplier).
- `multiplier_per_band = True`: multiplier set is per-log (i.e. per band, since each log is one band); `log.multiplier_count = len(that log's unique multipliers)`.
- `multiplier_per_band = False`: multiplier set is pooled across **all** of the operator's logs; every log gets the same `multiplier_count` (the pooled total).
- Either way: `log.final_score = log.qsos_points * log.multiplier_count` (or `0` if `qsos_points` is falsy).

## SCORE-008: 10-minute multi-op rule (`_apply_10_minute_rule`, `scoring.py:79-140`)
Applies only to operators with **at least one log** whose `category.upper() == 'MULTI'` (checked per-operator, not per-log — if *any* log for that operator is category MULTI, the rule runs across **all** of that operator's confirmed QSOs on every band). Pipeline position: runs *after* all bands are cross-checked (scoring already assigned) but *before* `aggregate_qso_points`/`_compute_multipliers` (`formats/cabrillo/crosscheck.py:42-50`), so it can retroactively zero out points already assigned by `apply_custom_scoring`.

Algorithm: gather every confirmed, valid QSO across all the operator's logs with a parseable datetime, sort chronologically. Determine each QSO's band number from its raw frequency token (`_get_band_from_frequency`, ±5% tolerance against `rules.contest_band(n)['band']` parsed as MHz) — a QSO whose frequency doesn't map to any configured band is skipped entirely (not penalized, just ignored by this rule). Walk the sorted list tracking `current_band_nr` and `session_first_time`:
- Same band as current → no-op (stays in the current "session").
- Different band, and **less than 10 minutes since `session_first_time`**, and this QSO's multiplier key (if any) is not new (not already in `seen_multipliers`) → **this QSO's points are set to `0`** — this is the actual penalty.
- Different band otherwise (≥10 min elapsed, or the QSO introduces a genuinely new multiplier) → the band switch is allowed; `current_band_nr`/`session_first_time` reset to this QSO.
- Any QSO's multiplier key, once seen, is added to `seen_multipliers` regardless of whether the QSO was penalized.

`_get_band_from_frequency` (`scoring.py:31-59`) accepts either a decimal MHz string (`'14.025'`) or an integer that could be Hz or kHz, inferring the unit from magnitude (`≥1,000,000 → Hz`, `≥10,000 → kHz`, else already MHz) before matching against configured band centers with 5% tolerance — this is a heuristic, not an exact-band-plan lookup; a contest with two bands whose center frequencies are within 5% of each other would be ambiguous (first match wins, by band-number iteration order).

**Two additional details, verified against `scoring.py:79-140`:**
- **The `is_multi` check scans *every* log the operator has, including ones marked `ignore_this_log` or with an invalid header** (`scoring.py:84-87` iterates `op_inst.logs` directly, with no filtering) — so a stray/duplicate/invalid log with `category=MULTI` can turn the 10-minute rule on for an operator even if that specific log is otherwise completely ignored everywhere else. The QSO-gathering step *does* filter (`if log.ignore_this_log or not log.valid_header: continue`, `scoring.py:93`) — only the multi-detection step doesn't.
- **The rule keys off `log.category`, which (when rules are supplied) is the rules file's `[categoryN] name` value, not the raw `CATEGORY-OPERATOR` log line** (`formats/cabrillo/log.py:123-124,300`; `_apply_10_minute_rule` checks `log.category.upper() == 'MULTI'`, `scoring.py:85`). This means the rule only fires for a given contest if that contest's rules file happens to name a category exactly `Multi` (case-insensitively) — e.g. `test_logs/rules_hf_yodx.config` does (`name=Multi`), so the rule applies there, but `test_logs/rules_hf_dracula.config` names its multi-op category `MO-AB-HP MIXT` (see `README.md`'s Dracula example, `[category7] name=MO-AB-HP MIXT`), so **the 10-minute rule never fires for the DRACULA contest as currently configured**, regardless of whether that's the intent. See GAP-014.
