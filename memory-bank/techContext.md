# Technical Context

## Technologies Used
- **Python 3.10+** (minimum required)
- **configparser** (stdlib) — INI rules file parsing
- **re** (stdlib) — regex-based QSO parsing and validation
- **datetime** (stdlib) — date/time validation
- **json** (stdlib) — JSON output serialization
- **dicttoxml** — XML output serialization
- **argparse** (stdlib) — CLI argument parsing
- **importlib** (stdlib) — lazy module loading

## Development Setup
- **OS**: Tested on Windows and Linux (Ubuntu)
- **Package Manager**: pip
- **Test Runner**: pytest + pytest-cov
- **Packaging**: cx_Freeze (frozen .exe builds)
- **Virtual Environment**: `venv/` (Python 3.14)

## Project Structure
```
logXchecker/
├── logXchecker.py           # CLI entry point + output builders
├── rules.py                 # Rules class (INI parsing + validation)
├── rules_hf.py              # RulesHf (string modes for Cabrillo)
├── rules_vhf.py             # RulesVhf (integer modes for EDI)
├── scoring.py               # ScoringMixin (all [scoring] section properties)
├── constants.py             # Shared constants, FORMAT_MODULE_MAP
├── version.py               # __project__, __version__
├── edi.py                   # Backward-compat shim → formats.edi
│
├── common/
│   ├── __init__.py
│   ├── dxcc.py              # DXCC database, lookup_callsign, YO/DRACULA helpers
│   ├── serialization.py     # dict_to_json, dict_to_xml
│   ├── crosscheck.py        # Shared cross-check pipeline functions
│   └── operator.py          # Base Operator class
│
├── formats/
│   ├── __init__.py
│   ├── edi.py               # EDI format: Log, LogQso, Operator, crosscheck
│   └── cabrillo/
│       ├── __init__.py      # Re-exports everything for backward compat
│       ├── constants.py     # Mode aliases, QSO regex, header fields
│       ├── operator.py      # Operator class
│       ├── log.py           # Log class (header validation, QSO parsing)
│       ├── qso.py           # LogQso class (QSO validation, period checks)
│       ├── scoring.py       # Scoring engines, multipliers, 10-minute rule
│       └── crosscheck.py    # Cross-check orchestration, compare_qso
│
├── output/
│   ├── __init__.py
│   └── formatters.py        # Human-friendly, CSV output formatters
│
└── memory-bank/             # Project documentation
```

## Test Files
| File                  | Purpose                                             |
|-----------------------|-----------------------------------------------------|
| `test_parser.py`      | Format parser tests (EDI)                           |
| `test_rules.py`       | Rules validation tests (15 tests)                   |
| `test_edi.py`         | EDI-specific tests (~25 tests)                      |
| `test_cabrillo.py`    | Cabrillo-specific tests (46 tests)                  |
| `test_logXchecker.py` | Main application tests (placeholder, 3 tests)       |
| `test_formatters.py`  | Output formatter tests (19 tests)                   |

## Test Log Directories
| Directory                        | Contents                             |
|----------------------------------|--------------------------------------|
| `test_logs/cabrillo/logs/`       | 88 Cabrillo logs for YR20RRO contest |
| `test_logs/cabrillo/logs_raw/`   | Original YR20RRO logs                |
| `test_logs/cabrillo/logs_dracula/` | DRACULA contest test logs          |
| `test_logs/edi/`                 | EDI format test logs                 |
| `test_logs/adif/`                | ADIF test files                      |

## Rules Config Files
| File                                   | Type        | Purpose                                     |
|----------------------------------------|-------------|----------------------------------------------|
| `test_logs/rules_hf.config`            | HF/Cabrillo | Generic HF contest rules                     |
| `test_logs/rules_vhf.config`           | VHF/EDI     | VHF contest rules                            |
| `test_logs/rules_rro.config`           | HF/Cabrillo | YR20RRO Diploma contest with `[scoring]`     |
| `test_logs/rules_hf_dracula.config`    | HF/Cabrillo | DRACULA contest with custom scoring + per-band mults |
| `test_logs/rules_vhf_napoca_2016.config` | VHF/EDI | NAPOCA 2016 VHF contest rules                |

## Dependencies (from requirements.txt)
- colorama
- coverage
- dicttoxml
- Pygments
- pytest
- pytest-cov
- validate_email

## Technical Constraints
1. **File format detection**: Cabrillo version detected from `START-OF-LOG:` header; no fallback heuristic for malformed headers
2. **Maidenhead distance**: Not yet implemented for HF (`qth_distance()` always returns 1)
3. **Cabrillo QSO regex**: Assumes specific field order (freq, mode, date, time, call1, rst_sent, nr_sent, county, call2, rst_recv, nr_recv, [exchange])
4. **No ADIF support yet**: Module referenced in `FORMAT_MODULE_MAP` but not implemented

## CLI Usage
```
logXchecker.py [-h] (-f FORMAT | -r RULES) (-slc path | -mlc path | -cc path)
               [-cl path] [-o OUTPUT] [-v]

Modes:
  -f FORMAT    Format only (EDI, CABRILLO) — for single log check without rules
  -r RULES     Rules file path — enables rules-based validation

Operations:
  -slc path    Single log check
  -mlc path    Multiple log check (folder)
  -cc path     Cross-check logs (folder)
  -cl path     Checklogs folder (used with -cc)
  -o FORMAT    Output: human-friendly (default), json, xml, csv
  -v           Verbose output for cross-check details
```

## File Size Limits
- No explicit limits on log file size
- Files are read entirely into memory via `read_file_content()` / `readlines()`
