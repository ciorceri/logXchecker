# Active Context

## Current Work Focus
Added 10-minute rule enforcement for multi-operator stations in DRACULA contest cross-check.

## Recent Changes
### formats/cabrillo.py
- **`run_crosscheck()`**: Added call to `_apply_10_minute_rule()` between the per-band cross-check loop and `_aggregate_qso_points()`
- **`_get_band_from_frequency()`**: New helper that parses a frequency string (from the raw QSO line) and determines which contest band (1..N) it belongs to, using ±5% tolerance around the band's nominal frequency
- **`_parse_qso_datetime()`**: New helper that converts a QSO's date+hour fields into a `datetime` object for chronological sorting
- **`_classify_qso_multiplier()`**: New helper that wraps `_compute_multiplier_for_qso()` to determine the multiplier key for a QSO's partner station
- **`_apply_10_minute_rule()`**: New function that implements the CQWW-style 10-minute rule:
  - Only applies to operators with `category == 'multi'`
  - Collects all confirmed QSOs chronologically across all logs
  - Tracks band sessions (first QSO time per band)
  - Band changes before 10 full minutes have elapsed get the QSO penalized to 0 points
  - Exception: working a new multiplier (DXCC, YO county, or DRC) allows early band change
  - Uses the existing `_compute_multiplier_for_qso()` infrastructure for new-multiplier detection

## Next Steps
- (none currently)

## Active Decisions
- The 10-minute rule is applied unconditionally but only has effect for `category == 'multi'` operators
- Frequency-to-band mapping uses ±5% tolerance around the nominal band frequency, covering standard HF band edges
- Multiplier exception detection reuses the existing `_compute_multiplier_for_qso()` logic, ensuring consistent treatment with the scoring system
- The `_aggregate_qso_points()` function naturally handles zero-point QSOs (it only counts `points > 0` as confirmed), so violating QSOs are properly excluded
