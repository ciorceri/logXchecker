# Active Context

## Current Work Focus
Implementing YR20RRO Diploma contest scoring rules and cross-check verification for 88 Cabrillo test logs.

## Recent Changes (May 2026)

### Scoring System Implementation
- Added `[scoring]` section to rules_rro.config with `qso_points=5`, `special_qso_points=10`, `special_callsign=YR20RRO`
- Added 3 new properties to `Rules` base class (`rules.py`): `contest_qso_points`, `contest_special_qso_points`, `contest_special_callsign`
- Modified `crosscheck_logs_filter()` to initialize and pass a `confirmed_pairs` set across bands
- Modified `crosscheck_logs()` to accept `confirmed_pairs` and implement contest-specific scoring:
  - YR20RRO QSOs → 10 points per band (per-band dedup)
  - Regular stations → 5 points once per mode across all bands (global dedup)
  - Default behavior preserved for contests without `[scoring]` section

### Cabrillo Mode Normalization
- Added `'PH': 'SSB'` to `CABRILLO_MODE_ALIASES` dictionary for Romanian contest logs that use "PH" as mode identifier

## Active Decisions & Considerations

### Scoring Logic Placement
- Points are calculated inside `crosscheck_logs()` at confirmation time, not as a post-processing step
- This ensures dedup happens at the moment of confirmation, preventing duplicate scoring

### Global vs Per-Band Dedup
- Regular stations: global `confirmed_pairs` set across all bands (per contest rules: "once per mode regardless of band")
- YR20RRO: per-band dedup via existing `_had_qso_with` mechanism (per rules: "each new band = additional 10 points")
- Decision: the special station check (`callsign2 == special_callsign`) bypasses the global set, preserving YR20RRO's per-band scoring
- Consideration: QSOs with YR20RRO that are duplicate on same band get 0 points via `_had_qso_with` check before reaching the scoring logic

### Default Behavior Preservation
- When `[scoring]` section is absent from rules file, all properties return default values (qso_points=1, special_qso_points=0, special_callsign=None)
- The scoring logic uses `qso_points_normal != 1` as the trigger for the new scoring path — this is fragile
- **Potential improvement**: check for the presence of the `[scoring]` section in the config instead

## Next Steps
1. ~~Run full cross-check with all 88 logs to verify scoring correctness~~ *(confirmed ~84.8% match rate)*
2. ~~Verify that `YO4LHR` with low score (30 pts / 6 QSOs) calculates correctly as 5×6=30~~ *(confirmed)*
3. ~~Verify that existing HF contest rules (`rules_hf.config`) still work with default scoring (1 pt/QSO)~~ *(confirmed)*
4. Consider improving the scoring path detection from `qso_points_normal != 1` to checking for section existence
5. Write unit tests for the new scoring system in `crosscheck_logs()`
6. Write unit tests for `formats/cabrillo.py` (no Cabrillo-specific tests yet)
7. Add test file for `rules_rro.config` scoring rules

## Important Patterns & Preferences
- **INI config is the source of truth** for all contest parameters
- **Backward compatibility** is maintained: all changes default to old behavior
- **Per-format modules** have consistent interfaces (same class/method names)
- **Error handling**: uses tuple-based error format `(line_nr, line_text, error_message)` everywhere

## Learnings
- Cabrillo V2 uses whitespace-separated QSO lines; V3 uses semicolons
- Romanian contest logs may use "PH" instead of "SSB" for phone mode
- The Cabrillo QSO line includes a county exchange field that's parsed but not used in cross-check comparison
- Points are tracked per-QSO but per-band aggregates are re-summed after cross-check
