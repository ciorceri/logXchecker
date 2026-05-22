# System Patterns & Architecture

## Overall Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                     logXchecker.py                          │
│              (CLI entry point / orchestration)              │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────┐  ┌──────────────┐  ┌──────────┐  ┌──────────┐ │
│  │  Rules   │  │   Formats    │  │  Output  │  │  Common  │ │
│  │ rules.py │  │ formats/     │  │ output/  │  │ common/  │ │
│  │ rules_hf │  │  edi.py      │  │formatters│  │  dxcc.py │ │
│  │ rules_vhf│  │  cabrillo/   │  │  .py     │  │  serial- │ │
│  │ scoring  │  │    log.py    │  │          │  │  ization │ │
│  │  .py     │  │    qso.py    │  │          │  │ crossck  │ │
│  │          │  │    operator  │  │          │  │ operator │ │
│  │          │  │    scoring   │  │          │  └──────────┘ │
│  │          │  │    crossck   │  │          │               │
│  └──────────┘  │    constants │  └──────────┘               │
│                └──────────────┘                              │
└──────────────────────────────────────────────────────────────┘
```

## Key Design Patterns

### 1. Modular Format Architecture
Each log format lives under `formats/` with a consistent interface:

**`formats/edi.py`** (single file):
- `Log`, `LogQso`, `Operator` classes
- `run_crosscheck()`, `crosscheck_band()`, `compare_qso()`
- Maidenhead distance calculation (`qth_distance`, `conv_maidenhead_to_latlong`)

**`formats/cabrillo/`** (package):
| Submodule | Responsibility |
|-----------|---------------|
| `constants.py` | Mode aliases, QSO regex patterns, header fields |
| `operator.py` | Operator class |
| `log.py` | Log header validation, QSO parsing |
| `qso.py` | LogQso validation, field assignment, period checks |
| `scoring.py` | DRACULA + standard scoring, multipliers, 10-minute rule |
| `crosscheck.py` | Cross-check orchestration, `compare_qso`, `_find_active_log` |

Both formats import shared utilities from `common/`.

### 2. Common Package (`common/`)
| Module | Purpose |
|--------|---------|
| `common/dxcc.py` | DXCC database loading, `lookup_callsign`, `is_yo_callsign`, `are_same_dxcc`, DRACULA helpers, `YO_COUNTIES` |
| `common/serialization.py` | `dict_to_json()`, `dict_to_xml()` |
| `common/crosscheck.py` | `load_log_files`, `group_logs_by_operator`, `mark_older_duplicates`, `aggregate_qso_points`, `mark_older_logs` |
| `common/operator.py` | Base `Operator` class |

### 3. Rules Class Hierarchy
```
ScoringMixin (scoring.py) — all INI [scoring] section properties
    │
Rules (rules.py) — INI parsing, validation
├── RulesVhf (rules_vhf.py) — integer modes for EDI
└── RulesHf (rules_hf.py) — string modes for Cabrillo
```
- `Rules` inherits from `ScoringMixin`, keeping scoring properties separated
- Sub-classes only override `contest_qso_modes`
- Config-driven: all contest parameters come from INI files

### 4. Lazy Module Loading
- `logXchecker.py` loads format modules on demand via `FORMAT_MODULE_MAP` (constants.py)
- Rules class resolved dynamically via `FORMAT_RULES_MAP` based on log format in INI
- No hard imports of optional format modules

### 5. Cross-Check Algorithm
1. **Load/Warm-up phase**: Parse all logs, group by operator callsign, mark older logs
2. **Per-band loop**: For each band in rules:
   - Find each operator's active log on the band
   - Compare QSO pairs (date/time within 5 min, mode match, RST match, serial match)
   - Award points via `apply_custom_scoring()` dispatcher
3. **10-minute rule** (Cabrillo only): Penalize multi-op band violations
4. **Post-processing**: Aggregate points, compute multipliers

### 6. Scoring System for HF contests

#### Scoring Dispatcher (`apply_custom_scoring`)
```
if custom_scoring == 'DRACULA' → _dracula_scoring()
elif custom_scoring is None    → _standard_scoring()
else                           → NotImplementedError
```

#### Standard (RRO-style) Scoring
```
if partner == special_callsign → special_qso_points (e.g. 10)
elif qso_points != 1 AND (mode, call1, call2) not seen → qso_points (e.g. 5)
else → distance * multiplier (default 1 point per QSO, legacy)
```

#### DRACULA Custom Scoring
```
if partner is DRC special → 10 pts
elif caller is YO:
    if partner is YO → 0 pts
    else → 5 pts
else (non-YO):
    if partner is YO → 5 pts
    elif same DXCC → 1 pt
    else → 2 pts
```

## Critical Implementation Paths

### Log Validation Flow
```
Log.__init__()
├── validate_header()
│   ├── Read file content
│   ├── HF: Detect Cabrillo version from START-OF-LOG
│   ├── Parse header fields (callsign, band, category, grid locator)
│   └── Validate against rules if provided
└── get_qsos()
    └── For each QSO line:
        └── LogQso.__init__()
            ├── validate_qso_format() — regex match
            ├── parse_qso_fields() — extract fields
            ├── generic_qso_validator() — date/hour/RST/serial
            └── rules_based_qso_validator() — mode/period
```

### Cross-Check Flow
```
run_crosscheck()
├── load_log_files()          # common/crosscheck.py
├── group_logs_by_operator()  # common/crosscheck.py
├── mark_older_duplicates()   # common/crosscheck.py
├── For each band: crosscheck_band()
│   ├── For each operator's QSO:
│   │   ├── Skip invalid/confirmed
│   │   ├── Find partner operator
│   │   ├── Find matching QSO via compare_qso()
│   │   └── Award points via apply_custom_scoring()
├── _apply_10_minute_rule()   # Cabrillo only
├── aggregate_qso_points()    # common/crosscheck.py
└── _compute_multipliers()    # if enabled
```
