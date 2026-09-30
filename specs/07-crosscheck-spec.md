# 07 — Cross-Check Spec

Source: `common/crosscheck.py` (shared pipeline), `formats/edi.py` (EDI-specific band logic), `formats/cabrillo/crosscheck.py` (Cabrillo-specific band logic).

## XC-001: Shared pipeline stages (`common/crosscheck.py`)
Both formats' `run_crosscheck()` follow the same skeleton, calling into these shared functions:
1. **`load_log_files(log_class, rules, logs_folder, checklogs_folder)`** (`crosscheck.py:21-42`): errors (prints + returns `None`) if `logs_folder` isn't a directory, or if `checklogs_folder` is given but isn't a directory. Every file in `logs_folder` is loaded as a normal log (`checklog=False`); every file in `checklogs_folder` (if given) is loaded with `checklog=True`. **No filename/extension filtering** — a stray non-log file in the folder is loaded and will simply fail header validation.
2. **`group_logs_by_operator(logs_instances, Operator)`** (`crosscheck.py:45-56`): any log with `valid_header is False` is flagged `ignore_this_log = True` and excluded from grouping entirely (it never gets an `Operator` bucket). Remaining logs are grouped by `callsign.upper()` into one `Operator` per callsign, which may hold several logs (e.g. one per band).
3. **`mark_older_duplicates(operator_instances, rules)`** (`crosscheck.py:59-64`): for every band, for every operator, if that operator submitted more than one log matching that band's regexp, only the log with the **latest filesystem mtime** (`os.path.getmtime`) is kept active — all others get `ignore_this_log = True` via `mark_older_logs` (`crosscheck.py:81-92`). **This is a filesystem-timestamp dependency, not a log-content dependency** — copying/extracting log files in a way that changes mtimes (e.g. from a zip, or a fresh git checkout) changes which submission cross-check treats as authoritative. See GAP-007.
4. **`aggregate_qso_points(operator_instances)`** (`crosscheck.py:67-78`): for every log, sums `qso.points` over QSOs where `points and points > 0` into `log.qsos_points`, and counts them into `log.qsos_confirmed`. A QSO confirmed with exactly `0` points (e.g. standard-scoring dedup, or zeroed by the 10-minute rule) **does not** count toward `qsos_confirmed`.

## XC-002: Format-specific `run_crosscheck` sequencing
- **EDI** (`formats/edi.py:1033-1050`): `load → group → mark_older_duplicates → for each band: crosscheck_band → aggregate_qso_points`. No multiplier or 10-minute-rule stage (EDI has neither concept).
- **Cabrillo** (`formats/cabrillo/crosscheck.py:27-52`): `load → group → mark_older_duplicates → (shared confirmed_pairs set) for each band: crosscheck_band → _apply_10_minute_rule → aggregate_qso_points → (if multiplier_enabled) _compute_multipliers`. Order matters: the 10-minute rule runs on already-scored QSOs but *before* aggregation, so zeroed points are excluded from both `qsos_confirmed` and multiplier counting.

## XC-003: EDI per-band cross-check (`crosscheck_band`, `formats/edi.py:735-810`)
For each operator `callsign1`/`ham1`: find their **active, non-checklog** log on this band via `_find_active_log(ham1, rules, band_nr, exclude_checklog=True)` (`formats/edi.py:813-833` — "active" = not `ignore_this_log`, `valid_header is True`, and, when `exclude_checklog=True`, also not `use_as_checklog`). Skip the operator entirely if none found. For each QSO in that log, in file order:
1. Invalid QSO → mark not-confirmed with its first parse error as the reason; skip.
2. Already confirmed (from a prior pass — shouldn't normally recur within one band pass, but the check exists) → skip.
3. Duplicate-within-period guard: if this callsign+period combination was already confirmed earlier in this same band loop (tracked in `_had_qso_with`), mark `'Qso already confirmed'` and skip — **this makes a second, otherwise-valid QSO with the same partner in the same period always fail**, even if it's a legitimately separate contact. **⚠ Cabrillo-only pending change**: per `specs/10-dracula-transylvania-2026.md` DRACULA-006, the Cabrillo version of this guard (XC-004) is being changed to key on mode as well as callsign+period, since a same-band different-mode contact is not actually a duplicate. EDI's guard (described here) is explicitly out of scope for that change and stays as-is.
4. Partner (`callsign2`) must have an `Operator` entry at all → else `'No log from {callsign2}'`.
5. Partner must have *any* log matching this band's regexp → else `'No log for this band from {callsign2}'`. **Correction**: `_has_band_logs` calls `logs_by_band_regexp` (`formats/edi.py:841`), which *does* require `valid_header is True` on each log it returns (`formats/edi.py:55-56`) — and `group_logs_by_operator` never even puts an invalid-header log into an `Operator` in the first place (`common/crosscheck.py:49-51`). So this step's practical distinction from step 6 is not "valid vs. any" but "has a log on this band at all" vs. "that log isn't the one shadowed by `mark_older_logs`" — see next point.
6. Partner must have an **active** (non-`ignore_this_log`) log for this band (`exclude_checklog=False` — i.e. a checklog-only submission from the partner is acceptable here) → else `'No valid log from {callsign2}'`. Because `mark_older_duplicates`/`mark_older_logs` always leaves exactly one log per operator per band un-ignored (XC-001 step 3), this error is effectively unreachable in practice once step 5 has already passed — there's always an active log if there's any valid-header log at all on that band.
7. Search partner's QSOs for a candidate: same callsign as `callsign1`, same period number (via `_find_qso_candidates`, `formats/edi.py:859-874`), then run full `compare_qso` (XC-005) on each candidate **in file order**, stopping at the first one that passes → else `'No qso found on {callsign2} log'`. **Note**: each failed candidate's specific `compare_qso` failure reason (e.g. `'Rst mismatch'`, `'Serial number mismatch'`) is written to `qso1.cc_error` inside the loop (`_compare_qso_pair`, `formats/edi.py:877-888`) but then **unconditionally overwritten** with the generic `'No qso found on {callsign2} log'` if no candidate ultimately passes (`formats/edi.py:800-802`) — EDI never surfaces the specific mismatch reason to the user when every candidate fails, only when a candidate outright doesn't exist. Cabrillo, having no retry loop, has no such overwrite and *does* surface the specific reason from `compare_qso` on its one candidate (see XC-004) — this is a second, previously unlisted facet of the EDI/Cabrillo divergence, see GAP-015.
8. On success: record the had-QSO-with marker, `qso1.points = distance * band_multiplier` (distance from `qth_distance`, EDI-010), `cc_confirmed = True`.

**Note the asymmetry**: `exclude_checklog=True` for the *searching* operator's own log (a checklog-only submitter can never be the one whose QSOs get cross-checked/scored) but `exclude_checklog=False` for the *partner* (a checklog-only submission can still confirm someone else's QSO). This is intentional-looking (checklogs exist to help confirm others without competing) but is **not mirrored in Cabrillo** — see XC-004 and GAP-005.

## XC-004: Cabrillo per-band cross-check (`crosscheck_band`, `formats/cabrillo/crosscheck.py:55-112`)
Two changes landed here per `specs/10-dracula-transylvania-2026.md`:
1. **DRACULA-006 (global Cabrillo fix, all contests, not DRACULA-specific)**:
   the `_had_qso_with` dedup key now includes mode —
   `'{callsign2}-period{period_nr}-{mode}'` — instead of just
   `'{callsign2}-period{period_nr}'`. A duplicate is same station + same band
   + same mode; a second, same-band contact on a *different* mode is a
   legitimate separate QSO and must not be rejected as `'Qso already
   confirmed'`. EDI's equivalent guard (XC-003 step 3) is explicitly out of
   scope and is unchanged.
2. **DRACULA-005 (new, generic opt-in feature)**: a new post-processing step,
   `_apply_witness_confirmation` (`formats/cabrillo/scoring.py`), runs in
   `run_crosscheck` after this function and the 10-minute rule but before
   `aggregate_qso_points`/`_compute_multipliers` (XC-002). It confirms and
   scores QSOs against a partner callsign with zero submitted logs at all,
   once at least `rules.contest_witness_confirmation_min_logs` distinct
   witnessing operators (contest-wide, not per-band; checklogs included,
   since a checklog's own QSOs never run through this function's normal
   per-band loop at all — see the note below) independently logged a contact
   with that same phantom callsign. Disabled by default
   (`witness_confirmation_min_logs=0`); only applies to QSOs whose failure
   here was specifically the `'No log from {callsign2}'` case (`callsign2`
   has zero `Operator` entries at all), not the `'No valid log for this
   band from {callsign2}'` case (a structurally different, out-of-scope
   case — that operator *did* submit a log, just not one active for this
   band) or any `compare_qso` mismatch (a real conflicting log exists there).
   Each witness-confirmed QSO is re-run through the same `apply_custom_scoring`
   dispatch a normally-confirmed QSO would use, with `distance=1` (no
   locator data exists for a phantom partner) and a `confirmed_pairs` set
   scoped to this pass only (separate from the per-band one).

Broadly similar to XC-003 but **not structurally identical** — there is no separate `_has_band_logs` step (Cabrillo's `_find_active_log` folds "has a log on this band" and "is it active" into one call), and the "no valid log" error message differs from EDI's (`'No valid log for this band from {callsign2}'`, `formats/cabrillo/crosscheck.py:92`, vs. EDI's two-message split in XC-003 steps 5-6). Differences from EDI's algorithm:
- `_find_active_log` (`formats/cabrillo/crosscheck.py:115-130`) has **no `exclude_checklog` parameter** — checklogs are excluded unconditionally on *both* sides (searcher and partner). A checklog-only submitter's log can never confirm anyone else's QSO in Cabrillo, unlike EDI. See GAP-005.
- `_find_active_log` also has an **`ALL`-band fallback**: if the operator has no log matching the specific band's regexp, but has a log whose `band.upper() == 'ALL'` (a single log covering every band, common in some Cabrillo submissions), that log is used instead — EDI's `_find_active_log` has no equivalent fallback. **This fallback does not filter QSOs by actual frequency at all** (`formats/cabrillo/crosscheck.py:62-66,116-124`): an `ALL`-band log is used as-is on *every* band-number pass of the outer `for band in range(1, rules.contest_bands_nr + 1)` loop, and every QSO inside it is checked against that band's partner logs regardless of the QSO's own frequency — a QSO actually made on 14 MHz can be compared against partner logs during the "80m" pass just as much as the "20m" pass, and gets scored/multiplier-tagged with whatever `band_nr` that pass happens to be on. See GAP-016.
- Scoring is delegated to `apply_custom_scoring` (`06-scoring-spec.md`) instead of the fixed `distance * multiplier` formula; the `confirmed_pairs` set is threaded in from the caller and shared **across all bands** for that run (SCORE-002).
- `_find_matching_qso` (`formats/cabrillo/crosscheck.py:133-143`) returns a single match (first candidate matching callsign + period) rather than EDI's "try each candidate through full comparison, fall through on mismatch" generator (`_find_qso_candidates` + loop in EDI). **Practical effect**: if a partner log has two QSOs from the same callsign in the same period where the first candidate fails `compare_qso` (e.g. RST/serial mismatch) but a later one would pass, EDI keeps trying candidates while Cabrillo stops at the first candidate and reports whatever `compare_qso` says about it (rst/serial/time mismatch) rather than continuing to search. See GAP-005.

## XC-005: QSO comparison (`compare_qso`, duplicated in `formats/edi.py:891-958` and `formats/cabrillo/crosscheck.py:156-206`)
Both raise `ValueError` with a specific message on the first failing check (caught by the caller and turned into `cc_error`):
1. `qso1`/`qso2` must both be `valid`.
2. Callsign cross-match: `log1.callsign == qso2.call` and `log2.callsign == qso1.call` (comment in both copies notes this is effectively unreachable given how candidates are pre-filtered by callsign).
3. Absolute datetime built from `date`(`YYMMDD`)+`hour`(`HHMM`) for both QSOs; **must be within 5 minutes** of each other (`timedelta(minutes=5)`) or `'Different date/time between qso's'`.
4. `mode` must match exactly (already-normalized string for Cabrillo, raw digit for EDI).
5. RST cross-match: `qso1.rst_sent == qso2.rst_recv` and `qso1.rst_recv == qso2.rst_sent`.
6. Serial/exchange cross-match: `qso1.nr_sent == qso2.nr_recv` and `qso1.nr_recv == qso2.nr_sent` — **EDI compares as `int()`** (`formats/edi.py:946-948`), **Cabrillo compares as raw strings** (`formats/cabrillo/crosscheck.py:201-204`). This means Cabrillo would treat `'001'` and `'1'` as a mismatch where EDI would treat them as equal — a real behavioral divergence, not just a style difference. See GAP-005.
7. **EDI only**: QTH locator cross-match (`log1.maidenhead_locator == qso2.wwl` and vice versa) — Cabrillo has no locator field to check (CAB-003) so this step doesn't exist there.
8. Return value: EDI returns the real `qth_distance(...)` (EDI-010); Cabrillo always returns `1` (CAB-010, since `compare_qso` in that module doesn't even call `qth_distance` — it just returns the literal `1` at `formats/cabrillo/crosscheck.py:206`).

## XC-006: What "confirmed" means downstream
`qso.cc_confirmed` ∈ `{True, False, None}`. `None` means the cross-check band loop for that QSO's band never ran or never reached this QSO (e.g. the operator had no active log on that band at all, so the whole per-operator loop body was skipped) — callers that branch on `cc_confirmed is False` (e.g. CLI-007's verbose output) should be aware that `None` takes the *other* branch of such a check (the one written for the `True` case), which is not necessarily semantically "confirmed" even though it's grouped with it. CLI-007 shows the concrete effect for the human-readable label this produces.
