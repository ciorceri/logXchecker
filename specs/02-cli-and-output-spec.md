# 02 — CLI and Output Spec

Source: `logXchecker.py`.

## CLI-001: Argument groups
Two **mutually exclusive, required** groups (`logXchecker.py:94-101`):
- Group 1 — format source: `-f/--format` (one of `FORMAT_MODULE_MAP` keys, case-insensitive, `constants.py:35-39`: `EDI`, `ADIF`, `CABRILLO`) **or** `-r/--rules` (path to an INI rules file).
- Group 2 — operation mode: `-slc/--singlelogcheck PATH`, `-mlc/--multilogcheck PATH`, or `-cc/--crosscheck PATH`.

Plus optional flags: `-cl/--checklogs PATH` (checklogs folder, used with `-mlc`/`-cc`), `-o/--output {human-friendly,json,xml,csv}` (default `human-friendly`), `-v/--verbose` (adds per-QSO detail in cross-check mode).

**Validation**: `-f` value must case-insensitively match a `FORMAT_MODULE_MAP` key or `argparse.ArgumentTypeError` is raised (`logXchecker.py:67-78`). `-o` value must match one of the 4 known outputs (case-insensitive) or the same error (`logXchecker.py:80-90`).

## CLI-002: Rules-file resolution (`main()`, `logXchecker.py:236-253`)
When `-r` is given:
1. Read the file; `IOError` → print `Cannot open rules file: {path}` and `sys.exit(1)`.
2. Parse with `configparser`; read `[log][format]`, uppercase it. Missing `[log]` section or `format` key → print `Rules file does not have a [log] section with a format field` and exit(1).
3. Resolve the concrete `Rules` subclass via `FORMAT_RULES_MAP` (`logXchecker.py:43-46`: `EDI → rules_vhf.RulesVhf`, `CABRILLO → rules_hf.RulesHf`). **If the format has no entry in this map, it silently falls back to the base `Rules` class** (`logXchecker.py:49-58`) rather than erroring — see GAP-008.
4. Instantiate `RulesClass(path)` — this runs full INI validation (see `03-rules-engine-spec.md`); any `KeyError`/`ValueError` here propagates as an uncaught exception (not converted to a clean CLI error message).

When `-f` is given instead: `log_format` is just the raw `-f` value; no rules object is created (`rules=None` passed through).

## CLI-003: Format module resolution
`_get_log_format_module()` (`logXchecker.py:121-140`) maps the resolved `log_format` string through `FORMAT_MODULE_MAP` and lazy-imports it via `importlib.import_module`. Unsupported format (not a map key) → `ValueError('Selected log type is unsupported: {format}')`. Import failure (module listed but not installed/implemented — this is the current state of `ADIF`) → re-raised as `ImportError` with a clearer message. Both are caught in `main()` and printed then `sys.exit(1)` (`logXchecker.py:262-266`).

## CLI-004: Mode dispatch
- **`-slc`** → `_build_output_single_log()`: errors if the path isn't a file (`Cannot open file : {path}`, exit 1); otherwise instantiates `log(path, rules=rules_obj)` and merges its `.errors` dict into the output under key `INFO_LOG` (`= 'log'`).
- **`-mlc`** → `_build_output_multi_log()`: errors if the path isn't a directory (`Cannot open logs folder : {path}`, exit 1); iterates every file in the folder (no extension filter), builds one output entry per file under `INFO_LOGS` (`= 'logs'`). If `-cl` is also given and is a valid directory, appends checklogs (each built with `checklog=True`) to the same `INFO_LOGS` list.
- **`-cc`** → `_build_output_crosscheck()`: **requires `rules`** — if `-f` was used instead of `-r`, `main()` prints `No rules were provided` and exits(1) *before* calling this (`logXchecker.py:274-277`). Calls `lfmodule.run_crosscheck(lfmodule.Log, rules=rules, logs_folder=..., checklogs_folder=...)` (see `07-crosscheck-spec.md`), then builds a per-operator, per-band dict enriched with DXCC info (`country`, `continent`, `itu`, `cq` via `common.dxcc.lookup_callsign`) and, if `-v`, per-QSO confirmed/error detail lines.

## CLI-005: Output dict shape (all modes)
Top-level keys are from `constants.py`: `INFO_LOG='log'`, `INFO_MLC='multi_logs_folder'`, `INFO_LOGS='logs'`, `INFO_CC='cross_check_folder'`, `INFO_OPERATORS='operators'`, `INFO_BANDS='band'`, plus per-log error keys `ERR_IO='io'`, `ERR_HEADER='header'`, `ERR_QSO='qso'`. Each `errors` dict always has all three of `io`/`header`/`qso` present (possibly empty lists) — `Log.__init__` initializes all three unconditionally.

## CLI-006: Output formatting
- **human-friendly** (default): `output/formatters.py:print_human_friendly_output()`. Prints a version banner line first *only* for this output mode (`logXchecker.py:230-231`, printed before any parsing/validation happens).
- **json**: `lfmodule.dict_to_json(output)` → `json.dumps` (via `common/serialization.py`, re-exported per-format module).
- **xml**: `lfmodule.dict_to_xml(output)` → `dicttoxml.dicttoxml`.
- **csv**: `output/formatters.py:print_csv_output()`. **Only implemented for cross-check mode** (`INFO_CC` key present) — single-log and multi-log CSV output raises `NotImplementedError('CSV output is only implemented for cross-check mode')` (`output/formatters.py:118-120`). This is intentional current scope, not a bug — flag any change here as a deliberate feature addition.

## CLI-007: Verbose cross-check detail
When `-v` and cross-check mode: for each QSO in each operator/band, if `qso.cc_confirmed is False` it's added to `qso_errors` as `"{qso_line} : {cc_error}"`; otherwise added to `qso_valid` as `"{qso_line} : {points} : {'Confirmed' if qso.cc_confirmed else 'Not confirmed'}"` (`logXchecker.py:220`). Since `None` is falsy, a QSO with `cc_confirmed is None` lands in the `qso_valid` *list* (not the errors list) but is labelled `"Not confirmed"` in the printed line — a slightly confusing combination (right bucket boundary, misleading-looking label) rather than the outright-wrong "always prints Confirmed" behavior an earlier reading of this ternary might suggest.
