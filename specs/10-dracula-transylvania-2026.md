# 10 — DRACULA-Transilvania Contest Rules Alignment (2026)

Source of truth: `Concursul Dracula - Transilvania.docx` (Romanian, at project
root — read via raw XML text extraction, no pandoc/soffice available in this
environment). This file reconciles that authoritative rules document against
the current implementation (`formats/cabrillo/scoring.py`, `scoring.py`,
`common/dxcc.py`) and specifies exactly what must change. Design decisions
below were confirmed with the maintainer directly (not guessed) where the
source document was ambiguous or the fix had cross-cutting scope.

**Already correct, no change needed** (verified against the docx): contest
dates/hours (`20261031 1200` → `20261101 1159`), bands (3.5/7/14/21/28 MHz),
modes (CW, SSB), all 7 categories (A1–C, names and regexes), exchange scheme
(foreign: RST+serial from 001; special stations: RST+`DRC`; YO stations:
RST+county abbreviation), log format (Cabrillo only), and the hardcoded
`YO_COUNTIES` table in `common/dxcc.py` (every county in the docx's two lists —
Transylvania counties and the rest of Romania's counties — matches the
existing table exactly, per-district).

## DRACULA-001: Transylvania county whitelist (new)

The docx explicitly separates Transylvania-region counties from the rest of
Romania's counties — this distinction doesn't exist anywhere in the current
code, but is required for DRACULA-003/006 below. Add to `common/dxcc.py`,
alongside `YO_COUNTIES`:

```python
TRANSYLVANIA_COUNTIES = {'HD', 'AB', 'BN', 'CJ', 'SJ', 'BV', 'CV', 'HR', 'MS', 'SB'}

def is_transylvania_county(exchange):
    """Check if an exchange value is a Transylvania-region county abbreviation."""
    if not exchange:
        return False
    return exchange.upper().strip() in TRANSYLVANIA_COUNTIES
```

Note this is a **subset cutting across `YO_COUNTIES` districts**, not a
district-level split: `YO2` splits into Transylvania `HD` vs. rest `AR, CS, TM`;
`YO5` splits into Transylvania `AB, BN, CJ, SJ` vs. rest `BH, SM, MM`; `YO6` is
**entirely** Transylvania (`BV, CV, HR, MS, SB`); `YO3`, `YO4`, `YO7`, `YO8`,
`YO9` have **no** Transylvania counties at all. Don't derive this from
`YO_COUNTIES` district membership — it must be its own flat whitelist.

## DRACULA-002: `yo_to_yo_points` was never actually wired up — fix while touching this code

Before this change, `_dracula_scoring` (`formats/cabrillo/scoring.py`)
hardcoded `qso1.points = 0` literally for a YO-caller-to-YO-partner contact —
there was no `contest_yo_to_yo_points` property in `ScoringMixin` at all, so
any `yo_to_yo_points=` value in a rules file's `[scoring]` section (e.g.
`README.md`'s Dracula example shows `yo_to_yo_points=0`) was pure decoration,
never read by anything. The official rules set YO-to-YO (non-Transylvania) at
**1 point**, not 0. Fix: add the `contest_yo_to_yo_points` property (RULES-007,
default `1`) to `ScoringMixin`, and make `_dracula_scoring` read it instead of
hardcoding. Update `test_logs/rules_hf_dracula.config` and `README.md`'s
Dracula example to `yo_to_yo_points=1`.

## DRACULA-003: New Transylvania scoring tier (both directions)

Per the docx (sections 6–7), contacting a Transylvania-region station scores
**8 points**, for *both* foreign and YO callers — a tier that sits between the
special-station tier (10) and the generic YO/foreign tier. This tier does not
exist in the current code at all. New `ScoringMixin` properties (RULES-007):
`contest_non_yo_to_transylvania_points` (default `8`) and
`contest_yo_to_transylvania_points` (default `8`) — kept as separate
per-direction fields (confirmed with maintainer) to match every other
direction-pair in `ScoringMixin`, even though both currently default to the
same value.

**Full corrected `_dracula_scoring` decision table** (replaces the current
function body in `formats/cabrillo/scoring.py`):

```
partner_exchange = qso1.qso_fields.get(rules.contest_multiplier_exchange_field, '').strip().upper()

if partner (callsign2) is a DRACULA special station:
    points = contest_non_yo_to_special_points      # unchanged — already correct, same value both directions today
elif caller (callsign1) is YO:
    if partner is YO:
        if is_transylvania_county(partner_exchange): points = contest_yo_to_transylvania_points   # NEW
        else:                                          points = contest_yo_to_yo_points             # was hardcoded 0, now 1 (DRACULA-002)
    else:
        points = contest_yo_to_nonyo_points             # unchanged
else:  # caller is non-YO (foreign)
    if partner is YO:
        if is_transylvania_county(partner_exchange): points = contest_non_yo_to_transylvania_points  # NEW
        else:                                          points = contest_non_yo_to_yo_points           # unchanged
    else:
        if same DXCC as caller: points = contest_non_yo_same_country_points  # unchanged
        else:                    points = contest_non_yo_dxcc_points          # unchanged
```

The exchange value used to detect "is this partner a Transylvania station" is
the **same field** `_compute_multiplier_for_qso` already reads
(`rules.contest_multiplier_exchange_field`, default `nr_recv`) — don't
introduce a second, separately-configured field for this.

## DRACULA-004: Multiplier rule must not give YO callers a county multiplier

Per the docx (section 8): foreign stations' multipliers = DXCC entities + YO
counties + DRC (once per band, any mode); **YO stations' multipliers = DXCC
entities + DRC only — no county multiplier**. `_compute_multiplier_for_qso`
(`formats/cabrillo/scoring.py`) currently returns `('YO_COUNTY', value)` for
*any* caller contacting a YO partner, regardless of the caller's own YO
status — this is wrong for a YO caller per the rules (and was previously
untested either way, since no caller-awareness existed in this function at
all).

Fix: thread the **caller's own callsign** into `_compute_multiplier_for_qso`
(new parameter; both call sites — `_compute_multipliers`'s per-log loop and
`_classify_qso_multiplier`/`_apply_10_minute_rule`'s per-QSO loop — already
have the owning `log`/`log.callsign` in scope, so this doesn't require any
new data plumbing beyond the signature change). In the DRACULA branch: if the
caller is YO and the partner is YO (non-special), return `None` (no
multiplier at all for a same-country DRACULA contact) instead of
`('YO_COUNTY', ...)`. If the caller is non-YO (foreign), keep the existing
`('YO_COUNTY', value)` behavior unchanged.

**Also close GAP-010 while touching this code**: validate `exchange_val`
against `common.dxcc.is_yo_county` before returning a `YO_COUNTY` multiplier
tuple (currently any non-empty string is accepted unvalidated). This applies
regardless of the Transylvania tier — `is_yo_county` checks the full
`YO_COUNTIES` set, `is_transylvania_county` (DRACULA-001) is a separate,
narrower check used only for scoring-tier selection (DRACULA-003), not for
multiplier validation.

## DRACULA-005: Witness-confirmation rule (new feature, generic opt-in)

The docx states: *"O legătură cu o stație care nu a trimis log se punctează
dacă stația respectivă apare în minim 5 loguri valide"* — a contact with a
station that never submitted its own log is still scored if that callsign
appears in at least 5 other valid logs. This mechanism does not exist at all
today; cross-check currently requires both sides to have a submitted log
(`'No log from {callsign2}'` otherwise, unconfirmed). Confirmed design
(interview with maintainer):

- **Scope**: contest-wide, not per-band. "Appears in ≥N valid logs" counts
  **distinct witnessing operators** (by callsign), not distinct log files —
  an operator who submitted logs for 3 different bands and claims the same
  phantom callsign on all 3 counts as **one** witness, not three.
- **Feature gating**: generic, opt-in via the new `contest_witness_confirmation_min_logs`
  property (RULES-007, default `0` = disabled) — not hardcoded to DRACULA.
  Any Cabrillo contest's rules file can set `witness_confirmation_min_logs=N`
  in `[scoring]` to enable it with threshold `N`.
- **Trusted data**: once the threshold is met, trust each witnessing caller's
  own submitted RST/exchange for their own scoring — there is no partner log
  to cross-verify against, and the maintainer explicitly chose not to require
  inter-witness exchange consensus.
- **Checklogs count** toward the witness tally (checklogs exist specifically
  to help confirm others' contacts without competing, which is exactly this
  use case).
- **Scope of applicability**: only for QSOs whose cross-check failure was
  specifically `'No log from {callsign2}'` — i.e. `callsign2` has **zero**
  `Operator` entries in `operator_instances` at all. Do **not** extend this to
  `'No log for this band from {callsign2}'` (that operator *did* submit at
  least one log, just not for this band — a structurally different case, out
  of scope for this rule) or to any RST/serial/time/mode mismatch case (an
  actual conflicting log exists there; that's not "never submitted a log").

**Implementation shape** (a new function, e.g. `_apply_witness_confirmation(operator_instances, rules)`
in `formats/cabrillo/scoring.py`, called from `run_crosscheck`
(`formats/cabrillo/crosscheck.py`) after the normal per-band loop and the
10-minute rule, but before `aggregate_qso_points`/`_compute_multipliers` —
same ordering concern as the 10-minute rule, since this can newly confirm and
score QSOs that must then be included in aggregation and multiplier counting):

1. No-op immediately if `rules.contest_witness_confirmation_min_logs <= 0`.
2. Scan every valid, non-ignored QSO across every operator's every log
   (checklogs included) whose `cc_confirmed is False` and `cc_error ==
   'No qso found on {callsign2} log'`... **correction**: the actual error for
   "partner has zero logs" is `'No log from {callsign2}'` (set directly in
   `crosscheck_band` before any candidate search happens, `formats/cabrillo/crosscheck.py:83-87`)
   — match on that exact string (or, more robustly, re-derive the condition
   directly: `qso.qso_fields['call'].upper() not in operator_instances`, which
   is what actually causes that error and is more resilient to message wording
   changes than string-matching `cc_error`).
3. Group these QSOs by the phantom partner callsign; tally the **set** of
   distinct witnessing operator callsigns per phantom callsign.
4. For phantom callsigns meeting the threshold: for every one of that phantom's
   pending QSOs, mark it confirmed and run it through the existing
   `apply_custom_scoring` dispatch exactly as a normal confirmed QSO would be
   (same function, same `confirmed_pairs` semantics for the standard-scoring
   path — use a set scoped to this witness-confirmation pass, separate from
   the per-band `confirmed_pairs`, since these QSOs were never part of any
   band's normal confirmation pass). Use `distance=1` (matches Cabrillo's
   existing `qth_distance` stub, CAB-010 — no locator data exists for a
   phantom partner anyway).
5. QSOs for phantom callsigns *not* meeting the threshold are left exactly as
   they are (`cc_confirmed=False`, original error) — this pass must not
   change anything about them.

This needs a `band_nr` to pass into `apply_custom_scoring` (used by the
standard-scoring legacy branch, GAP-006). Derive it the same way
`_get_band_from_frequency` does elsewhere in this module, or from which
`[bandN]` regexp matches the owning log's `band` value — whichever the
implementer finds cleaner; document the choice in a comment since there's no
existing precedent for deriving band_nr from a `Log` object outside the
per-band loop itself.

## DRACULA-006: Duplicate-QSO definition must include mode (global Cabrillo fix)

The docx (section 12.h) defines a duplicate as *"contacte realizate cu aceeași
stație în aceeași bandă și în același mod de lucru"* — same station, same
band, **and same mode**. A second contact with the same station on the same
band but a *different* mode is explicitly **not** a duplicate and should
score normally. `crosscheck_band`'s `_had_qso_with` dedup guard
(`formats/cabrillo/crosscheck.py`) currently keys only on
`'{callsign2}-period{period_nr}'` — mode is not part of the key, so a
legitimate second-mode contact on the same band would today be wrongly
rejected as `'Qso already confirmed'`.

**Confirmed scope: fix this globally in `formats/cabrillo/crosscheck.py`**,
for all Cabrillo contests, not just DRACULA — the maintainer agreed this is
the objectively correct definition of "duplicate" for Cabrillo-style contests
generally, not a DRACULA-specific quirk. **EDI's equivalent dedup logic in
`formats/edi.py` is explicitly out of scope for this change** — leave it as-is.

Fix: change both the check and the append to include mode:
```python
dedup_key = '{}-period{}-{}'.format(callsign2, inside_period_nr1, qso1.qso_fields['mode'])
...
_had_qso_with.append('{}-period{}-{}'.format(callsign2, partner_period_nr, qso2.qso_fields['mode']))
```
(`qso1`/`qso2`'s modes are guaranteed equal for a pair that reached this point,
since `compare_qso` already enforces a mode match — using either is fine, but
be consistent about which one for readability.)

This is a **behavior change affecting every existing Cabrillo rules file**,
including the curated fixtures under `test_logs/cabrillo/` and the generated
fixtures under `test_logs/generated/dracula/` — re-run the full suite and the
generated-fixture integration test (`test_generated_fixtures.py`) after this
change; a fixture that has two same-band, same-mode, same-callsign QSOs where
the second was *expected* to be rejected as a duplicate should still behave
identically (the fix only changes behavior for the previously-mishandled
different-mode case), but this must be verified, not assumed.

## DRACULA-007: Out of scope, documented only — not a code change

The docx's ranking/leaderboard requirements (separate "clasamente" by
continent/country for foreign stations, a YO ranking, a Transylvania ranking)
and trophy/diploma eligibility (working ≥5 special callsigns) are **out of
scope**, confirmed with the maintainer. `logXchecker` currently has no
ranking/leaderboard computation at all — it reports per-operator/per-band
confirmed QSOs, points, and multipliers only (`logXchecker.py`'s
`_build_output_crosscheck`, CLI-004). This is a future feature request, not a
correctness gap in existing scoring — do not build it as part of this
alignment work. If picked up later, it would need its own spec file.

## DRACULA-008: Test config and README updates required alongside the code

`test_logs/rules_hf_dracula.config` and `README.md`'s Dracula example
`[scoring]` section must be updated to reflect DRACULA-002/003/005/006:
`yo_to_yo_points=1` (was `0`), add `non_yo_to_transylvania_points=8` and
`yo_to_transylvania_points=8`, and (only if the maintainer wants the witness
rule demonstrated in the canonical example — otherwise leave
`witness_confirmation_min_logs` unset/absent, which defaults to disabled)
optionally `witness_confirmation_min_logs=5`. `README.md`'s `[scoring]`
section field-reference prose (the bullet list describing each field) needs
the three new fields added to it.
