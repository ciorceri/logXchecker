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

## Test Files
| File                  | Purpose                                             |
|-----------------------|-----------------------------------------------------|
| `test_parser.py`      | Format parser tests (EDI)                           |
| `test_rules.py`       | Rules validation tests                              |
| `test_edi.py`         | EDI-specific tests (1637 lines, most comprehensive) |
| `test_logXchecker.py` | Main application tests (placeholder, 15 lines)      |
| `test_formatters.py`  | Output formatter tests (19 tests, added May 2026)   |

## Test Log Directories
| Directory                        | Contents                             |
|----------------------------------|--------------------------------------|
| `test_logs/cabrillo/logs/`       | 88 Cabrillo logs for YR20RRO contest |
| `test_logs/cabrillo/logs_clean/` | Processed YR20RRO logs               |
| `test_logs/cabrillo/logs_raw/`   | Original YR20RRO logs                |
| `test_logs/edi/`                 | EDI format test logs                 |
| `test_logs/adif/`                | ADIF test files                      |

## Rules Config Files
| File                         | Type        | Purpose                                                         |
|------------------------------|-------------|-----------------------------------------------------------------|
| `test_logs/rules_hf.config`  | HF/Cabrillo | Generic HF contest rules                                        |
| `test_logs/rules_vhf.config` | VHF/EDI     | VHF contest rules                                               |
| `test_logs/rules_rro.config` | HF/Cabrillo | YR20RRO Diploma contest rules with `[scoring]` section          |
|                                            | (qso_points=5, special_qso_points=10, special_callsign=YR20RRO) |

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
