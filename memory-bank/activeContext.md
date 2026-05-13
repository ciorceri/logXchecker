# Active Context

## Current Work Focus
Adding DRACULA contest support (October 2026) and generalising the cross-check engine for custom-scoring contests.

## Recent Changes (May 2026)

### DRACULA Contest Support (2026-05-13)
- **Created `test_logs/rules_hf_dracula.config`** — DRACULA contest rules INI file with:
  - 5 bands (3.5, 7, 14, 21, 28 MHz), 2 modes (CW, SSB), 7 categories (A1-A3, B1-B3, C)
  - 1 period (31 Oct 12:00 UTC → 1 Nov 11:59 UTC, 24 hours)
  - Custom scoring: `custom_scoring=DRACULA` flag to enable special logic
  - 6 scoring point values for the various QSO type combinations
  - Multiplier system: per-band, with exchange field handling non-numeric values
  - 9 special DRACULA station callsigns (YP2/YR2/YQ2, YP5/YR5/YQ5, YP6/YR6/YQ6...DRACULA)
- **Added 6 new DRACULA scoring properties to `Rules` base class (`rules.py`)**:
  - `contest_custom_scoring`: string flag identifying the scoring engine ('DRACULA', default None)
  - `contest_non_yo_to_special_points`: 10 pts (any station → special DRACULA)
  - `contest_non_yo_to_yo_points`: 5 pts (non-YO → YO station)
  - `contest_yo_to_nonyo_points`: 5 pts (YO → non-YO station)
  - `contest_non_yo_dxcc_points`: 2 pts (non-YO → different DXCC)
  - `contest_non_yo_same_country_points`: 1 pt (non-YO → same country)
- **Added DRACULA helper functions to `formats/cabrillo.py`**:
  - `YO_COUNTIES` dict and `ALL_YO_COUNTIES` set (Romanian county abbreviations)
  - `is_yo_callsign()`: detect YO/YP/YQ/YR prefix callsigns
  - `is_dracula_special()`: check if callsign is in special station list
  - `is_yo_county()`: check if exchange value is a Romanian county code
  - `is_dracula_contest()`: check if custom_scoring == 'DRACULA'
- **Modified `generic_qso_validator()`**: accepts alphanumeric exchanges (1-6 chars) for DRACULA
- **Modified `compare_qso()`**: skips serial number comparison for DRACULA (exchanges can be county codes/DRC)
- **Modified `crosscheck_logs()`**: DRACULA scoring branch with 6-way point determination based on:
  - Whether caller is YO or non-YO
  - Whether partner is special DRACULA, YO, or non-YO
  - Whether partner is same-country DXCC or different
- **Modified `crosscheck_logs_filter()`**: DRACULA multiplier logic with DXCC/YO_COUNTY/DRC types, supporting per-band multipliers

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


