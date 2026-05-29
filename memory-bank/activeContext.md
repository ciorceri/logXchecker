# Active Context

## Current Work Focus
Completed a major modularization refactor of the codebase. The monolith `formats/cabrillo.py` (1804 lines) has been split into a package with 6 submodules. Shared utilities extracted to a `common/` package. Scoring properties extracted from `rules.py` into a `ScoringMixin`. CLI output builders extracted from `logXchecker.py`.

## Recent Changes (May 2026)

### Codebase Modularization
- **`common/` package created**: `dxcc.py` (DXCC database + DRACULA helpers), `serialization.py` (dict_to_json/dict_to_xml), `crosscheck.py` (shared pipeline functions), `operator.py` (base operator class)
- **`formats/cabrillo/` split into package**: `constants.py`, `operator.py`, `log.py`, `qso.py`, `scoring.py`, `crosscheck.py`, `__init__.py`
- **`scoring.py` (root)**: `ScoringMixin` extracted from `rules.py` — all 15 scoring properties now live in a dedicated mixin
- **`logXchecker.py`**: `main()` split into `_build_output_single_log()`, `_build_output_multi_log()`, `_build_output_crosscheck()`
- **~400 lines of duplication eliminated** between `formats/edi.py` and `formats/cabrillo.py`

### Backward Compatibility
All existing imports preserved via re-exports in `__init__.py` files. No test changes required.

## Next Steps
- Implement ADIF format support
- Wire up currently-unused Cabrillo validation methods (`validate_band`, `validate_date`, `validate_email`)
- Implement Maidenhead distance for HF

## Active Decisions
- DXCC database lives in `common/dxcc.py` — imported by `logXchecker.py` and format modules
- DRACULA helpers (`is_dracula_contest`, `is_yo_county`, etc.) live in `common/dxcc.py` alongside DXCC lookups
- Scoring mixin keeps backward-compatible property access (e.g. `rules.contest_qso_points` still works)
- Cabrillo package `__init__.py` re-exports everything so `import formats.cabrillo as cabrillo` continues to work
