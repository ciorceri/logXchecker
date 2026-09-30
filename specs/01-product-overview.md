# 01 — Product Overview

## PROD-001: Mission
logXchecker is a CLI tool that validates and cross-checks ham radio contest logs.
It supports two mature log formats today and one planned:

| Format | Contest type | Status | Module |
|---|---|---|---|
| EDI | VHF/UHF/SHF | Implemented | `formats/edi.py` |
| Cabrillo V2.0/V3.0 | HF | Implemented | `formats/cabrillo/` |
| ADIF | — | Planned, not implemented | referenced only (`constants.py:37`, `FORMAT_MODULE_MAP['ADIF'] = 'adif'`) |

## PROD-002: Target users
- Ham radio contest participants submitting a log for validation.
- Contest managers/organizers validating a batch of logs and producing cross-checked, scored results.
- National contest organizers who need callsign filtering (e.g. Romanian YO contests via `callregexp`).

## PROD-003: Core capabilities
1. **Single/multi log validation** — generic syntax validation, or rules-based validation against a contest-specific INI file.
2. **Cross-check** — compare QSOs between all submitted operator logs to confirm mutual contacts, with optional checklogs.
3. **Scoring** — points per confirmed QSO via one of: legacy distance-based (EDI), standard configurable, or a named custom engine (`DRACULA`, `YODX`).
4. **Multi-format output** — human-friendly (default), JSON, XML, CSV (CSV only for cross-check mode — see CLI-006).

## PROD-004: Non-goals (current)
- No web UI or API — CLI only (`logXchecker.py`), confirmed by `memory-bank/projectbrief.md` and absence of any server code in the repo.
- No persistence/database — every run is stateless, reads log/rules files from disk and prints to stdout.
- No network calls — DXCC lookups are from a local flat file (`country.dat`), not a live service.

## PROD-005: Versioning
Current version string is `2.0` (`version.py:2`). No semantic versioning policy is enforced in code; treat this as informational only.
