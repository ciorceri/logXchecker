# 03 — Rules Engine Spec

Source: `rules.py`, `rules_hf.py`, `rules_vhf.py`, `scoring.py`.

## RULES-001: Class hierarchy
```
ScoringMixin (scoring.py)         — all [scoring]-section properties
    └── Rules (rules.py)          — INI parsing, generic validation
          ├── RulesVhf (rules_vhf.py)  — contest_qso_modes: List[int]  (EDI)
          └── RulesHf  (rules_hf.py)   — contest_qso_modes: List[str]  (Cabrillo)
```
`Rules.__init__(path)` (`rules.py:42-49`) raises `FileNotFoundError` if `path` doesn't exist, parses the INI with stdlib `configparser`, then immediately runs `validate_rules()` — **an invalid rules file fails at construction time**, not lazily.

## RULES-002: `[contest]` section — required fields
| Field | Type | Required | Notes |
|---|---|---|---|
| `begindate`, `enddate` | `YYYYMMDD` string | yes | validated with `datetime.strptime(..., '%Y%m%d')` (`rules.py:106-108`) |
| `beginhour`, `endhour` | `HHMM` string | yes | validated with `%H%M` (`rules.py:114-117`) |
| `bands` | int ≥ 1 | yes | `contest_bands_nr`; `KeyError`/`ValueError` on missing/non-int (`rules.py:172-179`) |
| `periods` | int ≥ 1 | yes | `contest_periods_nr` (`rules.py:184-191`) |
| `categories` | int ≥ 1 | yes | `contest_categories_nr` (`rules.py:199-206`) |
| `modes` | comma list | yes | int list (VHF) or upper-string list (HF); `KeyError`/`ValueError` on missing/malformed (`rules.py:158-170`, `rules_hf.py:29-37`, `rules_vhf.py:30-38`) |
| `custom_scoring` | string, optional | no | uppercased/stripped; drives scoring dispatch (`scoring.py:47-51`) — known values: absent/`None`, `DRACULA`, `YODX` |

## RULES-003: `[bandN]` sections (N = 1..bands)
Required keys per band: `band` (label used in reports), `regexp` (matched against the log's raw band/frequency value), `multiplier` (int, used in legacy distance-based scoring — `rules.py:181-182`). Missing any of the three on any band 1..N → `ValueError('Rules file has invalid settings for band {N}')` (`rules.py:70-77`).

## RULES-004: `[periodN]` sections (N = 1..periods)
Required keys: `begindate`, `enddate`, `beginhour`, `endhour`, `bands` (comma list of `bandN` section names). Every entry in `bands` must name an existing `[bandN]` section or `ValueError('Rules file has invalid band settings ({band}) for period {N}')` (`rules.py:126-131`). Dates/hours validated the same way as `[contest]` (`rules.py:109-122`).

## RULES-005: `[categoryN]` sections (N = 1..categories)
Required keys: `name` (report label), `regexp` (matched against the log's raw category/section value), `bands` (comma list of `bandN` names, same cross-reference validation as periods, `rules.py:133-138`).

## RULES-006: `[extra]` section (optional)
Any key whose value is (case-insensitively) `YES` is added to `contest_extra_fields` and treated as a **mandatory header field to validate** by the format module: `email`, `address`, `name` are the fields the EDI format module actually checks (`formats/edi.py:220-265`). `callregexp`, if present **and non-empty** (`rules.py:229` uses `assert self.config['extra'][field]`, so `callregexp=` with an empty value is excluded), is included in `contest_extra_fields` (`rules.py:222-234`) and is used both to gate log header callsigns and to filter accepted QSO callsigns (national-contest filtering). **Cabrillo does not consult `[extra]` at all** — see GAP-003.

## RULES-007: `[scoring]` section (optional) — `ScoringMixin` properties and defaults
All are `try/except (KeyError, ValueError): return <default>` (`scoring.py`), so any missing/malformed field silently falls back rather than erroring:

| Property | INI key | Default |
|---|---|---|
| `contest_qso_points` | `qso_points` | `1` |
| `contest_special_qso_points` | `special_qso_points` | `0` |
| `contest_special_callsign` | `special_callsign` (comma list) | `[]` |
| `contest_multiplier_enabled` | `multiplier_enabled` (bool) | `False` |
| `contest_multiplier_per_band` | `multiplier_per_band` (bool) | `False` |
| `contest_multiplier_exchange_field` | `multiplier_exchange_field` | `'nr_recv'` |
| `contest_multiplier_special_exchange` | `multiplier_special_exchange` (upper) | `None` |
| `contest_non_yo_to_special_points` | `non_yo_to_special_points` | `10` |
| `contest_non_yo_to_yo_points` | `non_yo_to_yo_points` | `5` |
| `contest_non_yo_dxcc_points` | `non_yo_dxcc_points` | `2` |
| `contest_non_yo_same_country_points` | `non_yo_same_country_points` | `1` |
| `contest_non_yo_same_continent_points` | `non_yo_same_continent_points` | `2` |
| `contest_yo_to_special_points` | `yo_to_special_points` | `10` |
| `contest_yo_to_nonyo_points` | `yo_to_nonyo_points` | `5` |
| `contest_yo_to_nonyo_same_continent_points` | `yo_to_nonyo_same_continent_points` | **= `contest_yo_to_nonyo_points`** (not a fixed literal) |
| `contest_non_yo_to_yo_same_continent_points` | `non_yo_to_yo_same_continent_points` | **= `contest_non_yo_to_yo_points`** |
| `contest_dracula_county_list` | `dracula_county_list` (multiline `DISTRICT: county,county` per line) | `{}` |

Note: `contest_qso_points` default of `1` doubles as a **scoring-path selector** in `_standard_scoring` (see SCORE-003) — this is the fragile check flagged in GAP-006; don't rely on "is `qso_points` set" vs "is it `1`" being semantically distinguishable from outside this code.

## RULES-008: `RulesVhf` vs `RulesHf` mode semantics
- `RulesVhf.contest_qso_modes` (`rules_vhf.py:30-38`): `List[int]`. Per the module docstring, EDI mode codes are `0=None 1=SSB 2=CW 3=SSB+CW 4=CW+SSB 5=AM 6=FM 7=RTTY 8=SSTV 9=ATV` — this mapping is documentation-only; the code itself just parses ints, it does not enforce or use this mapping anywhere.
- `RulesHf.contest_qso_modes` (`rules_hf.py:29-37`): `List[str]`, each `.strip().upper()`'d. Compared against the *normalized* Cabrillo mode string (see CAB-004) — not the raw log mode token.

## RULES-009: Full rules validation sequence (`Rules.validate_rules`, `rules.py:58-138`)
Order matters for error clarity (each stage's error message names the specific missing/invalid piece): (1) required `[contest]` fields present → (2) `bands ≥ 1` and every `[bandN]` has `band`/`regexp`/`multiplier` → (3) `periods ≥ 1` and every `[periodN]` has required keys → (4) `categories ≥ 1` and every `[categoryN]` has required keys → (5) all dates/hours parseable → (6) every period's `bands` list references real `[bandN]` sections → (7) every category's `bands` list references real `[bandN]` sections. There is **no cross-check that `[scoring]` fields are internally consistent** (e.g. `multiplier_exchange_field` naming a QSO field that doesn't exist for the format) — malformed scoring config fails silently at scoring time, not at load time.
