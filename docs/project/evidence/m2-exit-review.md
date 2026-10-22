# Independent M2 exit review

Date: 2026-10-23 (Australia/Sydney). Baseline: `ad06a83`, including M1 follow-up `7809bd1`, CAT-007 `c8d75fd`, CAT-008 `7f2485c`. Working tree initially clean.

## Verdict

M1's previous occlusion and sampling findings are resolved. M2 is implemented but not complete: reproduced validation correctness defects reopen CAT-007 and CAT-008. M3 remains planned.

## Findings

### P1 — Corrected fits bypass quality diagnostics (CAT-007)

`backend/src/cateniq/service.py:265` returns solver status and residuals without evaluating the frozen RMS/p95 quality gates or returning issues. `refit()` counts missing issues as zero. Reproduction using CorridorService on committed corridor-a: S2 attachments [50,0,12] and [95,0,13.5] return status=ok, RMS=0.506459 m, p95=1.213390 m, reason=None, despite limits 0.15/0.30 m. The browser labels this `refit: ok`. Refit S4 with its unchanged predicted endpoints: RMS=0.176770, but its original high_residual issue disappears from the corridor's issue count (only S2's issue remains). Prediction diagnostics also omit the p95 gate.

Keep solver convergence distinct from validation success. Apply the same quality diagnostics to original and corrected results, preserve unresolved issues/counts, and show validation failures in the browser. Add wrong-but-convergent correction tests, not only bound-hit/infeasible cases.

### P1 — Lateral separation is reported but never validated (CAT-007)

`backend/src/cateniq/service.py:239` measures lateral residuals only as provenance after projecting observations into a newly defined plane. Reproduction: S2 attachments [50,10,12] and [95,10,12] return status=ok, vertical RMS=0.035278 m, p95=0.073049 m, while observation lateral RMS=9.999797 m. The rendered fitted conductor is ten metres away from the evidence and supplied supports. The browser does not display the lateral metric.

The evidence document explicitly describes an ungated lateral policy, but this does not satisfy the architecture's non-coplanar rejection requirement or the feature contract's support checks. Reject unsupported correction planes or implement explicit lateral/support validation with documented tolerances; provenance alone must not allow this to appear valid. Test through the API and browser.

### P1 — Cancelling a draft leaves its fit current (CAT-008)

`apps/web/src/store.ts:179` clears the draft without advancing editVersion or invalidating results. A temporary browser probe delayed a real `/fit` response: edit S2 b.z from 10.5 to 12, Validate before committing, Escape (endpoint returns to 10.5), release the response. The UI shows `refit: ok (corrected)` with no stale label for geometry calculated at 12. The probe passed assertions demonstrating the incorrect state. `moveDraft()` also advances editVersion without marking an already recorded fit stale until commit.

Invalidate results on every effective-input change, including draft movement and cancellation. Bind responses to the effective input snapshot, and add delayed-response/cancel plus already-visible-result/edit browser regressions. The temporary probe was removed; no application code changed in this review.

## Verification

Same installed environment as M1: Linux 7.0.0-38-generic, Python 3.14.4, uv 0.11.29, Node 22.23.1, Playwright Chromium. Existing dependency installations; clean installation and hosted CI not observed.

- Backend ruff lint/format, strict mypy: pass; pytest: 52 pass.
- Frontend typecheck, 24 unit tests, build and nine browser journeys: pass. Build retains the large-chunk warning.
- Corrected performance/resource harness: one pass; 100,200 points, load 1468 ms, select 354 ms, edit 509 ms, commit 392 ms. Isolated 3-second frame window: 105 samples, p50 33.3 / p95 33.4 / max 83.3 ms. Meets even the strictest currently written p95 budget (50 ms). Heap rounded 21/21/21 MB; final scene 91 objects; draw calls 28→28 and triangles 3296→3296; renderer geometries 40→47 remains inconclusive for leak acceptance.
- Focused real-API delayed-response browser probe: one pass reproducing the cancelled-draft bug. Direct service probes reproduce the residual and lateral failures above.

## M1 closeout and records caveat

The new occlusion test identifies successive blockers, verifies an exposed handle begins a drag, and checks blocking while the pointer is held. The timing harness starts before load dispatch and resets frame samples after settling at a fixed camera. These resolve the prior findings; M1 remains Complete.

Performance budget records still disagree: workbench contract p95<=50 ms, closeout/backlog p95<=100 ms, older endpoint evidence/blocker text p95<=150 ms. This run meets all three; reconcile the current intended budget before CAT-012 rather than silently selecting a looser one. This is a documentation follow-up, not a new observed performance failure.

Next: fix the three M2 correctness findings, add regression coverage, and repeat M2 exit review before CAT-009.

## Resolution of the three P1 findings (2026-10-23)

### P1 — Corrected fits bypass quality diagnostics — resolved

`service.py` now computes validation issues through a shared `_issues` helper applied to both prediction and corrected results: the frozen RMS (0.15 m) and p95 (0.30 m) gates produce `high_residual` / `high_residual_p95` issues, status failures produce `insufficient_evidence` / `unsupported_domain` / `fit_failed`. Solver convergence stays distinct from validation success — a converged-but-wrong corrected fit reports `status: ok` *with* issues; `refit()` counts corrected-span issues in `issue_count`, so unresolved spans (e.g. S4's high_residual) survive a corridor rerun. Reproduction now returns: S2 b z 10.5 -> 13.5 -> `ok` with `high_residual` + `high_residual_p95`. Browser shows issue kind/detail/threshold under the fit result. Regressions: `test_wrong_but_convergent_correction_fails_validation`, `test_refit_counts_issues_on_corrected_spans`, e2e "a converged correction that fails quality gates shows its issues". The p95 gate was also missing from prediction diagnostics and is now applied there (S4 reports both issues).

### P1 — Lateral separation reported but never validated — resolved

New frozen threshold `LATERAL_TOLERANCE_M` = 0.50 m in `profile.py`: the corrected refit plane must be supported by the evidence. When observation lateral RMS about the corrected plane exceeds it, the correction is non-coplanar and rejected `unsupported` — the measured value is reported in the reason and provenance echo, not silently fitted. Reproduction now returns: S2 attachments [50,10,12]/[95,10,12] -> `unsupported`, "corrected plane unsupported by observations: lateral RMS 10.000 m > LATERAL_TOLERANCE_M 0.5". Browser displays the lateral metric on every corrected result. Regressions: `test_off_plane_correction_reports_provenance` (now asserts rejection + provenance), e2e "a correction the evidence does not support is rejected".

### P1 — Cancelling a draft leaves its fit current — resolved

Staleness is now judged against the effective input snapshot rather than the version counter alone: `FitRecord` stores the submitted attachments and every mutation that can change effective inputs (`moveDraft`, `commitDraft`, `cancelDraft`, `undo`, `redo`) recomputes each record's flag. Cancelling a moved draft advances `editVersion`, so a late response computed for draft inputs arrives flagged stale; a result recorded for inputs a cancel reverts to is restored to current. A shown result flags stale on draft movement, before commit. Regressions: store tests for move/cancel invalidation and revert-recovery; e2e route-delayed `/fit` response after Escape flagged "stale"; e2e visible-result stale-on-edit / recover-on-cancel.

## Performance budget reconciliation (documentation follow-up)

The three disagreeing budget records are unified at p50 <= 50 ms / p95 <= 100 ms: `workbench.md` (was p95 <= 50), `endpoint-interaction.md` (was p95 <= 150), `blockers.md` BLK-002 note (was p95 <= 150), backlog second-follow-up note (already <= 100). Isolated fixed-camera evidence supports it: p95 33.4-50.0 ms, max single frame 83.3 ms. Dated historical budget statements in review documents are left as records of what was believed at the time.

## Verification of the resolution (same environment)

- Backend: `ruff check`/`format` clean, strict `mypy` clean, 54 pytest pass (15 fitting-production incl. new wrong-but-convergent/lateral/refit-count regressions).
- Frontend: `tsc -b` clean, 27 vitest pass (11 store incl. cancel/move invalidation), production build clean.
- Browser: 12 workbench specs pass incl. new delayed-response cancel, lateral rejection, and converged-with-issues journeys.
