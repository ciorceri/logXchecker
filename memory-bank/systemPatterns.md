# System Patterns & Architecture

## Overall Architecture

```
┌─────────────────────────────────────────────┐
│                logXchecker.py               │
│        (CLI entry point / orchestration)    │
├─────────────────────────────────────────────┤
│                                             │
│   ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│   │  Rules   │  │  Formats │  │  Output  │  │
│   │  rules.py│  │ *.py     │  │formatters│  │
│   │  rules_* │  │          │  │  .py     │  │
│   └──────────┘  └──────────┘  └──────────┘  │
│                                             │
└─────────────────────────────────────────────┘
```

## Key Design Patterns

### 1. Modular Format Architecture
Each log format (EDI, Cabrillo) lives in its own Python module under `formats/` with a consistent interface:
- `Log` class: validate headers, parse QSOs
- `LogQso` class: single QSO validation
- `crosscheck_logs_filter()`: orchestrates cross-check
- `crosscheck_logs()`: per-band cross-check logic
- `compare_qso()`: compare two QSOs for a match
- `dict_to_json()` / `dict_to_xml()`: serialization helpers

### 2. Rules Class Hierarchy
```
Rules (base - rules.py)
├── RulesVhf (rules_vhf.py) - integer modes for EDI
└── RulesHf (rules_hf.py) - string modes for Cabrillo
```
- Base class handles all INI parsing, validation, and shared properties
- Sub-classes only override `contest_qso_modes` to change type
- Config-driven: all contest parameters come from INI files

### 3. Lazy Module Loading
- `logXchecker.py` loads format modules on demand via `FORMAT_MODULE_MAP` (constants.py)
- Rules class is resolved dynamically via `FORMAT_RULES_MAP` based on the log format in the INI file
- No hard imports of optional format modules

### 4. Cross-Check Algorithm
1. **Load/Warm-up phase**: Parse all logs, group by operator callsign, mark older logs
2. **Per-band loop**: For each band defined in rules:
   - For each operator's QSO, find the partner operator
   - Compare QSO pairs (date/time within 5 min, mode match, RST match, serial match)
   - If match found, award points based on scoring rules
3. **Post-processing**: Sum points per operator per band

### 5. Scoring System for HF contests (based on an YO contest)
Points calculation logic in `crosscheck_logs()`:
```
if partner == special_callsign → special_qso_points (e.g. 10)
elif qso_points != 1 AND (mode, call1, call2) not seen before → qso_points (e.g. 5)
else → distance * multiplier (default 1 point per QSO, legacy)
```
- Deduplication via global `confirmed_pairs` set across all bands
- YR20RRO special station gets separate per-band dedup via `_had_qso_with`

#### Scoring Configuration (rules INI `[scoring]` section)
| Field                         | Type    | Default         | Description                                      |
|-------------------------------|---------|-----------------|--------------------------------------------------|
| `qso_points`                  | int     | 1               | Points for a regular confirmed QSO               |
| `special_qso_points`          | int     | 0               | Points for QSO with the special station          |
| `special_callsign`            | str     | None            | Callsign of the special/bonus station            |
| `multiplier_enabled`          | bool    | false           | Enable multiplier-based scoring (score = pts × mults) |
| `multiplier_exchange_field`   | str     | 'county_recv'   | QSO field name containing the exchange value     |
| `multiplier_special_exchange` | str     | None            | Exchange value indicating Category A station     |

Scoring properties are defined in `Rules` base class (`rules.py`) with `@property` decorators that read from `self.config['scoring']` and return safe defaults on `KeyError`/`ValueError`.

### 6. Version Selection
The module auto-detects Cabrillo version (2.0 vs 3.0) from `START-OF-LOG:` header line, and parses QSO lines accordingly.

## Critical Implementation Paths

### Log Validation Flow
```
Log.__init__()
├── validate_header()
│   ├── Read file content
│   ├── HF only : Detect Cabrillo version
│   ├── Parse header fields (callsign, band, category, grid locator)
│   └── Validate against rules if provided
└── get_qsos()
    └── For each QSO line:
        └── LogQso.__init__()
            ├── validate_qso_format() - regex match
            ├── parse_qso_fields() - extract fields
            ├── generic_qso_validator() - date/hour/RST/serial
            └── rules_based_qso_validator() - mode/period
```

### Cross-Check Flow
```
crosscheck_logs_filter()
├── Parse all logs, group by operator
├── Mark older log files per band
├── confirmed_pairs = set()
├── For each band: crosscheck_logs(..., confirmed_pairs)
│   ├── For each operator's QSO:
│   │   ├── Skip invalid or already confirmed
│   │   ├── Find partner operator
│   │   ├── Find matching QSO in partner's log via compare_qso()
│   │   ├── Award points (distance/special/normal/default)
│   │   └── Mark as confirmed
│   └── Mark unmatched QSOs
└── Sum points per operator per band
```
