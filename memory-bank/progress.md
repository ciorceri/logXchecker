# Progress

## What Works

### Core Infrastructure
- CLI argument parsing with all operation modes (single check, multi check, cross-check)
- INI-based rules file parsing with validation
- Output formatting: human-friendly, JSON, XML, CSV
- Lazy module loading for format-specific modules

### EDI Format (VHF/UHF/SHF)
- Header validation (callsign, locator, band, category, date)
- QSO parsing and validation
- Cross-check with distance-based scoring
- Maidenhead locator distance calculation
- Log classification (checklog support)

### Cabrillo Format (HF)
- V2.0 and V3.0 format detection and parsing
- Header validation (callsign, band, category, email, name, address, grid locator)
- QSO parsing with county exchange field
- Cross-check with QSO comparison (date/time, mode, RST, serial)
- Mode normalization (PH→SSB, LSB→SSB, USB→SSB, various DIGI→DIGI)
- Scoring system:
  - Default: 1 point per confirmed QSO (legacy)
  - Configurable: regular QSO points, special station bonus points
  - YR20RRO rules: 2 pts per confirmed QSO, multiplier-based scoring (counties + Category A stations)
  - Multiplier system: `multiplier_enabled`, `multiplier_exchange_field`, `multiplier_special_exchange`
- **DRACULA contest support** (added May 2026):
  - Custom scoring engine with `is_dracula_contest()` flag-based dispatch
  - 6-way point determination: special/10pts, YO→non-YO/5pts, non-YO→YO/5pts, non-YO→DXCC/2pts, non-YO→same/1pt, YO→YO/0pts
  - Per-band multipliers with three types: DXCC entities, YO_COUNTY codes, DRC special stations
  - Alphanumeric exchange validation (county codes/DRC instead of serial numbers)
  - Serial number comparison skipped for DRACULA QSO matching
  - YO callsign detection, county abbreviation recognition, DRC special station detection

### Rules Engine
- Generic and contest-specific validation for dates, hours, modes, bands
- Per-period and per-category validation
- Extra field validation (email, address, name, callsign regex)
- Multi-band, multi-period contest support
- **Custom scoring flag** (`custom_scoring=DRACULA` in `[scoring]`) to switch scoring engines
- **6 DRACULA-specific scoring properties** in Rules base class with safe defaults
- **Per-band multiplier mode** (`multiplier_per_band=true`) for DRACULA-style contests

## What's Left to Build

### ADIF Format
- ADIF log parser module is referenced in code but not implemented
- No Log, LogQso, or cross-check functions for ADIF

### Missing Features
- `validate_email()` in Cabrillo Log class calls `validate_email` library but is never invoked (dead code/TODO)
- `validate_band()` and `rules_based_validate_band()` in Cabrillo Log class are never called (dead code/TODO)
- `validate_date()` and `rules_based_validate_date()` in Cabrillo Log class are never called (dead code/TODO)
- No Maidenhead distance calculation for HF (always returns 1 km)
- No heuristics for logs missing `START-OF-LOG:` header
- Category list for Cabrillo is hardcoded to match EDI-style categories

### Tests
- Existing tests cover EDI format primarily
- No unit tests for Cabrillo format specifically
- No tests for the new scoring system
- `test_formatters.py` added with 19 tests covering all output formatter functions

## Current Status
The project is actively developed with a focus on supporting the **YR20RRO Diploma** contest (Romanian 20th anniversary contest, April 27 - May 12, 2024). The Cabrillo parser and cross-check are functional and have been verified with 88 real contest logs with a confirmation rate of ~84.8%. Scoring system is implemented with configurable regular QSO points (2), multiplier-based scoring (counties + Category A RRO stations), and post-processing for final score calculation.

## Known Issues
1. Scoring path detection uses `qso_points_normal != 1` which is fragile — should check for `[scoring]` section existence instead
>>>>>>>

2. Cabrillo `validate_band()` and `validate_date()` methods are implemented but never called
3. Cabrillo regex expects county exchange field — may break for logs without county data
4. Category regex patterns in Cabrillo are hardcoded to match EDI-like values (SINGLE, MULTI, CHECKLOG)
5. `qth_distance()` always returns 1 for Cabrillo — should be documented as intentional for HF contests where distance doesn't matter
6. `validate_email()` in Cabrillo imports `validate_email` library but the function is never called

## Evolution of Project Decisions
- **2025**: Original project supported only EDI format for VHF contests
- **2026 Q1**: Added Cabrillo V2/V3 parser for HF contests
- **2026 Q2 (April)**: Added PH→SSB mode alias for Romanian contest logs
- **2026 Q2 (May)**: Added configurable scoring system for YR20RRO Diploma contest; added test_formatters.py with 19 tests
- **2026 Q2 (May)**: Unified Cabrillo V2 & V3 parser; added 88 YR20RRO test logs; full cross-check verified with ~84.8% confirmation rate
- **2026 Q2 (May)**: Added DRACULA contest support (Oct 2026 rules) with custom scoring engine, per-band multipliers, YO station detection, alphanumeric exchange validation, and 6-way point determination system
