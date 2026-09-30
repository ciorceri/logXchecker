# logXchecker Specifications (SDD)

This directory is the source of truth for **spec-driven development** on logXchecker.
It was produced by reverse-engineering the existing implementation (as of commit
`91b48f8`, branch `refactor`) plus the `memory-bank/` docs. Every requirement below
is traceable to actual code — file:line citations are given so the spec can be
verified against the source, not just trusted.

## How to use these specs

- **Before changing behavior**: find the relevant `REQ-xxx` here, update the spec
  first (with the reasoning), then change the code and tests to match.
- **Before adding a feature**: add new requirements in the right file (or a new
  file, following the numbering convention) before writing code.
- **Reviewing a PR**: the `code-reviewer` subagent (`.claude/agents/code-reviewer.md`)
  should check the diff against the relevant spec file, not just style.
- **A spec and the code disagree**: that is a bug in one of the two. Don't silently
  "fix" the code to match a stale spec, or the spec to match a buggy
  implementation — flag it (see `09-known-gaps-and-deviations.md` for a list of
  gaps already identified this way).

## File map

| File | Covers |
|---|---|
| `01-product-overview.md` | Mission, users, supported/planned formats, high-level scope |
| `02-cli-and-output-spec.md` | `logXchecker.py` argument parsing, dispatch, output formats |
| `03-rules-engine-spec.md` | INI rules schema, `Rules`/`RulesHf`/`RulesVhf`, validation |
| `04-format-edi-spec.md` | EDI header/QSO parsing & validation (`formats/edi.py`) |
| `05-format-cabrillo-spec.md` | Cabrillo header/QSO parsing & validation (`formats/cabrillo/`) |
| `06-scoring-spec.md` | `ScoringMixin`, standard/DRACULA/YODX scoring, multipliers, 10-minute rule |
| `07-crosscheck-spec.md` | Cross-check pipeline shared by both formats, EDI vs Cabrillo divergence |
| `08-dxcc-and-common-spec.md` | DXCC database, callsign lookup, `common/` shared code |
| `09-known-gaps-and-deviations.md` | Confirmed bugs, dead code, undocumented behavior, doc/code drift |
| `10-dracula-transylvania-2026.md` | DRACULA-Transilvania contest rules alignment: reconciles the authoritative rules document against the implementation, with confirmed design decisions for each gap |

## Requirement ID convention

`<AREA>-<NNN>`, areas: `PROD`, `CLI`, `RULES`, `EDI`, `CAB`, `SCORE`, `XC`, `DXCC`, `GAP`.
IDs are stable — once assigned, don't renumber; superseded requirements are marked
`(superseded by REQ-xxx)` rather than deleted, so history stays legible.

## Model provenance

Authored by Claude Sonnet 5.5 by reading the actual source modules directly
(not solely the `memory-bank/` summaries, which were found to be stale in places
— see `09-known-gaps-and-deviations.md`, item GAP-009). An independent review
pass by Opus 5.5 is expected to follow, focused on `06-scoring-spec.md` and
`07-crosscheck-spec.md` (the highest-risk, most easily misdescribed logic).
