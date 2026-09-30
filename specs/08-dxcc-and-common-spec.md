# 08 — DXCC and Common Package Spec

Source: `common/dxcc.py`, `common/operator.py`, `common/serialization.py`, `common/crosscheck.py` (crosscheck functions are specified in `07-crosscheck-spec.md`).

## DXCC-001: Database loading (`_load_dxcc_database`, `common/dxcc.py:30-110`)
Loaded **once at module import time** into the module-level `DXCC_BY_PREFIX` dict (`common/dxcc.py:259`) — there is no reload/refresh mechanism; changing `country.dat` requires a process restart. File location: `<project_root>/country.dat`, falling back to `<cwd>/country.dat` if not found there; if neither exists, the database is silently empty (`{}`) — no error is raised, so DXCC-dependent features (DRACULA/YODX scoring, `country`/`continent`/`itu`/`cq` CLI output fields) would silently degrade to "unknown" rather than fail loudly.

Format: one line per DXCC entity, `Country-Name: ITU-zone: CQ-zone: CONTINENT: GPS main-prefix: prefix-list;` (colon-separated, semicolon-terminated; lines not ending in `;` are skipped). Each of the entity's prefixes (main + alternates from the prefix-list, alternates starting with `*` excluded) maps to the same entity-info dict (`country`, `main_prefix`, `continent`, `itu`, `cq`, `gps`). **First entity to claim a given prefix wins** on conflict (`common/dxcc.py:106-108`) — later entities sharing a prefix are silently shadowed.

## DXCC-002: Callsign lookup (`lookup_callsign`, `common/dxcc.py:113-180`)
Generates a prioritized list of candidate prefixes to try against `DXCC_BY_PREFIX`, returns the **first candidate that matches** (i.e. the most specific/highest-priority interpretation, not necessarily the longest string match):
- **3-part portable** (`PREFIX/BASE/SUFFIX`, e.g. `DL/YO5PJB/P`): `PREFIX` tried first (highest priority — the portable prefix indicates the *operating* DXCC entity), then the whole `BASE`, then progressively shortened prefixes of `BASE`.
- **2-part portable** (`X/Y`): the whole original string tried first, then each part whole, then progressively shortened prefixes of each part.
- **No slash**: progressively shortened prefixes of the whole callsign, longest first.

Deduplicates the candidate list (first occurrence wins) before checking. Returns `None` if no candidate matches.

## DXCC-003: Derived helpers
- `is_yo_callsign(callsign)`: `lookup_callsign(...)['main_prefix'] == 'YO'`.
- `get_callsign_continent(callsign)`: `lookup_callsign(...)['continent']` or `None`.
- `are_same_dxcc(c1, c2)`: both lookups succeed **and** `main_prefix` matches — two callsigns that both fail lookup are **not** considered "same DXCC" (returns `False`, not an ambiguous match).

## DXCC-004: DRACULA/YODX-specific helpers
- `YO_COUNTIES` (`common/dxcc.py:220-229`): a fixed dict of Romanian call-district (`YO2`..`YO9`) → list of 2-letter county abbreviations. `ALL_YO_COUNTIES` is the flattened set, used by `is_yo_county`. This table is **hardcoded in Python**, separate from `ScoringMixin.contest_dracula_county_list` (RULES-007), which is parsed from the INI `[scoring] dracula_county_list` field. **Neither table is actually consulted by DRACULA scoring**: `contest_dracula_county_list` is defined but never read anywhere in `formats/cabrillo/scoring.py` (confirmed dead), and the DRACULA multiplier branch (`formats/cabrillo/scoring.py:205-209`) accepts **any** non-empty exchange value as a `YO_COUNTY` multiplier key without calling `is_yo_county` at all — that validation call is made only in the **YODX** branch (`scoring.py:193`), not DRACULA. So DRACULA county multipliers are effectively unvalidated free-text, not backed by either table. See GAP-010.
- `is_dracula_contest(rules)` / `is_yodx_contest(rules)`: `rules.contest_custom_scoring == 'DRACULA'` / `'YODX'` (`None`-safe).
- `is_dracula_special(callsign, rules)`: callsign (uppercased/stripped) is in `rules.contest_special_callsign`.
- `is_yo_county(exchange)`: uppercased/stripped value is in `ALL_YO_COUNTIES` — this is the hardcoded table, independent of any INI-configured county list.

## COMMON-001: `common/operator.py` — defined but not actually shared
`common/operator.py` defines a base `Operator` class (callsign, `logs` list, `add_log_by_path`, `add_log_instance`, `logs_by_band_regexp`) intended to be the single shared implementation. **In practice, neither format module imports it**: `formats/edi.py` defines its own near-identical `Operator` class inline (`formats/edi.py:37-60`), and `formats/cabrillo/operator.py` defines its own near-identical `Operator` class (`formats/cabrillo/operator.py:21-43`) rather than subclassing/importing `common.operator.Operator`. This is real, currently-harmless duplication left over from the modularization refactor — see GAP-011. **The three are not actually identical**: `common/operator.py`'s `add_log_by_path` calls `Log(path, rules=rules, checklog=checklog)` but never imports a `Log` symbol into that module at all — calling it would raise `NameError: name 'Log' is not defined`. It's harmless only because nothing currently calls `common.operator.Operator.add_log_by_path` (nothing imports the class at all). Any future format module should actually import `common.operator.Operator` rather than adding a fourth copy — but fix the missing `Log` import first, or the "shared" class remains silently broken for that method.

## COMMON-002: Serialization (`common/serialization.py`)
`dict_to_json(d)` → `json.dumps(d)` (no `default=` handler — a `ValueError` object stored as an error tuple element, as can happen via `qso1.cc_error = e` in `_compare_qso_pair`, `formats/edi.py:877-888`, would raise `TypeError: Object of type ValueError is not JSON serializable` if it ever reached JSON output un-stringified — verify this can't happen before shipping a change that surfaces raw exceptions into `cc_error`). `dict_to_xml(d)` → `dicttoxml.dicttoxml(d)` (returns `bytes`, not `str` — `print()` on it in `logXchecker.py:285` will show the `b'...'` repr; this is existing, unremarked-upon behavior).
