# Progress

## What Works

### Core Infrastructure
- CLI argument parsing with all operation modes (single check, multi check, cross-check)
- INI-based rules file parsing with validation
- Output formatting: human-friendly, JSON, XML, CSV
- Lazy module loading for format-specific modules
- Shared `common/` package for DXCC lookups, serialization, cross-check pipeline

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
- **DRACULA contest support**:
  - Custom scoring engine with `is_dracula_contest()` flag-based dispatch
  - 6-way point determination: special/10pts, YO→non-YO/5pts, non-YO→YO/5pts, non-YO→DXCC/2pts, non-YO→same/1pt, YO→YO/0pts
  - Per-band multipliers with three types: DXCC entities, YO_COUNTY codes, DRC special stations
  - Alphanumeric exchange validation (county codes/DRC instead of serial numbers)
  - YO callsign detection, county abbreviation recognition, DRC special station detection
  - 10-minute rule for multi-operator stations

### Rules Engine
- Generic and contest-specific validation for dates, hours, modes, bands
- Per-period and per-category validation
- Extra field validation (email, address, name, callsign regex)
- Multi-band, multi-period contest support
- Custom scoring flag (`custom_scoring=DRACULA`)
- Per-band multiplier mode (`multiplier_per_band=true`)
- Scoring properties extracted into dedicated `ScoringMixin` (`scoring.py`)

### Code Organization (refactored May 2026)
- `common/dxcc.py`: DXCC database, callsign lookup, DRACULA helpers
- `common/serialization.py`: JSON/XML serialization (no duplication)
- `common/crosscheck.py`: Shared cross-check pipeline (~400 lines of duplication eliminated)
- `formats/cabrillo/`: Split into 6 submodules (was 1804-line monolith)
- `scoring.py`: Scoring mixin extracted from `rules.py`

## What's Left to Build

### ADIF Format
- ADIF log parser module is referenced in code but not implemented
- No Log, LogQso, or cross-check functions for ADIF

### Missing Features
- `validate_email()` in Cabrillo Log class is never invoked (dead code/TODO)
- `validate_band()` and `rules_based_validate_band()` in Cabrillo Log class are never called
- `validate_date()` and `rules_based_validate_date()` in Cabrillo Log class are never called
- No Maidenhead distance calculation for HF (always returns 1 km)
- No heuristics for logs missing `START-OF-LOG:` header
- Category list for Cabrillo is hardcoded to match EDI-style categories

### Tests
- 140 tests total across 6 test files (297 subtests), all passing
- `test_cabrillo.py`: 46 tests covering Log, LogQso, Operator, helper functions
- `test_formatters.py`: 19 tests covering all output formatter functions
- `test_edi.py`: ~25 tests covering Log, LogQso, Operator, helper functions
- `test_rules.py`: 15 tests covering rules validation and INI parsing

## Current Status
The codebase has been significantly modularized. The Cabrillo format is now a package with clear separation of concerns. Shared utilities live in `common/`. Scoring properties have been extracted from the Rules class. All 140 tests pass with zero changes to test code.

## Known Issues
1. Scoring path detection uses `qso_points_normal != 1` which is fragile — should check for `[scoring]` section existence instead
2. Cabrillo `validate_band()` and `validate_date()` methods are implemented but never called
3. Cabrillo regex expects county exchange field — may break for logs without county data
4. Category regex patterns in Cabrillo are hardcoded to match EDI-like values (SINGLE, MULTI, CHECKLOG)
5. `qth_distance()` always returns 1 for Cabrillo — should be documented as intentional for HF
6. `validate_email()` in Cabrillo imports `validate_email` library but the function is never called

## Evolution of Project Decisions
- **2025**: Original project supported only EDI format for VHF contests
- **2026 Q1**: Added Cabrillo V2/V3 parser for HF contests
- **2026 Q2 (April)**: Added PH→SSB mode alias for Romanian contest logs
- **2026 Q2 (May)**: Added configurable scoring system for YR20RRO Diploma contest; added test_formatters.py with 19 tests
- **2026 Q2 (May)**: Unified Cabrillo V2 & V3 parser; added 88 YR20RRO test logs; full cross-check verified with ~84.8% confirmation rate
- **2026 Q2 (May)**: Added DRACULA contest support (Oct 2026 rules) with custom scoring engine, per-band multipliers, YO station detection, alphanumeric exchange validation, and 6-way point determination system, plus 10-minute rule for multi-op stations
- **2026 Q2 (May)**: Major modularization — split `formats/cabrillo.py` into a 6-module package, created `common/` package (DXCC, serialization, cross-check), extracted `ScoringMixin` from `rules.py`, extracted CLI output builders from `logXchecker.py`. Eliminated ~400 lines of duplication. All 140 tests pass with no test code changes.
