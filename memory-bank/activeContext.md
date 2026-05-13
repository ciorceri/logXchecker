# Active Context

## Current Work Focus
Implementing YR20RRO Diploma contest scoring rules (corrected) and multiplier-based scoring system for Cabrillo HF cross-check.

## Recent Changes (May 2026)

### Corrected YR20RRO Scoring (2026-05-12)
- **Fixed `rules_rro.config`** scoring values per actual contest rules:
  - `qso_points=2` (was incorrectly set to 5)
  - Removed `special_qso_points` / `special_callsign` (YR20RRO is the contest, not a bonus station)
  - Added multiplier-based scoring: `multiplier_enabled=true`
  - Multiplier source: `multiplier_exchange_field=county_recv` (the county/RRO code in QSO exchange)
  - Special exchange value: `multiplier_special_exchange=RRO` (identifies Category A stations)

### Multiplier System
- Added 3 new properties to `Rules` base class (`rules.py`):
  - `contest_multiplier_enabled`: boolean flag (default False)
  - `contest_multiplier_exchange_field`: field name for multiplier extraction (default 'county_recv')
  - `contest_multiplier_special_exchange`: value that identifies Category A stations (default None)
- Added multiplier post-processing in `crosscheck_logs_filter()`:
  - Iterates all confirmed QSOs for each operator
  - If exchange == RRO → counts partner callsign as a unique multiplier (Category A)
  - Else → counts the exchange value (county abbreviation) as a unique multiplier
  - Sets `log.multiplier_count` and `log.final_score = log.qsos_points × log.multiplier_count`
- Updated `logXchecker.py` to pass `multipliers` and `final_score` into output dict
- Updated `output/formatters.py` human-friendly output to display multipliers when present

### Cabrillo Mode Normalization
- Added `'PH': 'SSB'` to `CABRILLO_MODE_ALIASES` dictionary for Romanian contest logs that use "PH" as mode identifier

## Active Decisions & Considerations

### Multiplier Calculation at Operator Level
- Multipliers are calculated **per operator**, not per band — this matches the contest rule that each county/category A station counts once "o singura data, indiferent de modul de lucru"
- All confirmed QSOs across all bands contribute to the same `unique_multipliers` set
- Each log file for the same operator gets the same `multiplier_count` value

### Scoring Logic Placement
- Flat QSO points are still calculated at confirmation time in `crosscheck_logs()`
- Multiplier calculation is a **post-processing step** after all cross-checking is done
- This separation keeps the cross-check logic clean and the multiplier logic independently testable

### Default Behavior Preservation
- When `[scoring]` section is absent, all properties return safe defaults
- When `multiplier_enabled` is false (default), no multiplier processing occurs
- Existing contests without multipliers work exactly as before

## Next Steps
1. ~~Correct YR20RRO scoring values (qso_points=2, remove special_callsign)~~ *(done)*
2. ~~Implement multiplier-based scoring (counties + Category A stations)~~ *(done)*
3. ~~Update output formatters to show multipliers and final score~~ *(done)*
4. Run full cross-check with all 88 logs to verify multiplier correctness
5. Consider improving the scoring path detection from `qso_points_normal != 1` to checking for section existence
6. Write unit tests for the multiplier system

## Important Patterns & Preferences
- **INI config is the source of truth** for all contest parameters
- **Backward compatibility** is maintained: all changes default to old behavior
- **Per-format modules** have consistent interfaces (same class/method names)
- **Error handling**: uses tuple-based error format `(line_nr, line_text, error_message)` everywhere

## Learnings
- Cabrillo V2 uses whitespace-separated QSO lines; V3 uses semicolons
- Romanian contest logs may use "PH" instead of "SSB" for phone mode
- The Cabrillo QSO line includes a county exchange field that's parsed and now used for multiplier counting
- Points are tracked per-QSO but per-band aggregates are re-summed after cross-check
- Multipliers are operator-wide, not per-band (county once regardless of mode/band)
- The `special_callsign` feature is kept for future contests that may need a bonus station
- Rules base `contest_qso_modes` property tries to parse modes as ints by default — HF contests override via `RulesHf` subclass


