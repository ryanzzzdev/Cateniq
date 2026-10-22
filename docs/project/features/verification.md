# Verification and demonstration plan

Date: 2026-10-22

Status: all matrix scenarios have verified evidence; see the evidence index below. Independent reviews: [M1](../evidence/m1-exit-review.md), [M2](../evidence/m2-exit-review.md), [M3](../evidence/m3-exit-review.md), [M4](../evidence/m4-exit-review.md). The M4 review's findings (demo/verification-suite isolation, undo-during-save, incomplete performance evidence) are resolved — see its resolution section.

## Evidence standard

For every reported check, name the procedure/command, code and data revision, toolchain, OS/browser/hardware, workload, observed result and limitations. Separate deterministic tests, real-process integration, manual usability observations, performance runs and hosted CI. A screenshot or recording does not replace correctness evidence.

Verification commands are defined and exercised during CAT-003 and subsequent implementation; this document does not invent working commands. A final evidence index will link each required scenario to a reproducible result. Do not create empty evidence reports before checks occur.

## Acceptance matrix

| ID | Scenario | Required observation | Task |
| --- | --- | --- | --- |
| D1 | Dataset identity and malformed input | Hash/unit/schema/ID failures rejected; reference truth separated from fitter inputs | CAT-005 |
| G1 | Independent geometry fixtures | Transform and fitted-curve errors within frozen tolerances, including unequal heights | CAT-004, CAT-007 |
| G2 | Sparse/noisy/infeasible data | Explicit unsupported/failed/quality outcome; no forced green status | CAT-007 |
| U1 | Endpoint correction | Inspect, select, numeric/constrained edit, cancel, undo/redo and accurate coordinates | CAT-006, CAT-008 |
| U2 | Async and save failures | Draft retained, old result never shown as current, clear recovery | CAT-010 |
| R1 | Two-session conflict and lost response | Conditional save permits one winner; identical retry does not duplicate change | CAT-009, CAT-011 |
| R2 | Restart and rerun | Durable corrections preserved; interrupted attempt retryable; API responsive | CAT-009, CAT-011 |
| R3 | Acceptance race | Only current validated revision can be accepted; later edit invalidates acceptance | CAT-010, CAT-011 |
| E1 | Provenance export | Snapshot reconstructed against matching source; mismatches rejected | CAT-010, CAT-011 |
| F1 | Store/solver failure | Bounded failure with no false commit, silent reset or partial published result | CAT-011 |
| P1 | Resource and interaction workload | Declared frame/load/selection/recalculation measurements meet pre-agreed budgets | CAT-006, CAT-012 |
| X1 | Complete user journey | Real browser/API/store/fitter path survives reopen and produces correct export | CAT-010, CAT-013 |
| X2 | Clean setup and demo | Documented setup, reset and cleanup reproduced in a clean disposable environment | CAT-003, CAT-013 |

## Evidence index

| ID | Passing evidence |
| --- | --- |
| D1 | `backend/tests/test_datasets.py` — hash/unit/schema rejections; reference truth stays separate from fitter inputs |
| G1 | `backend/tests/test_geometry_profile.py`, `backend/tests/test_fitting_production.py` — frozen-tolerance checks incl. unequal heights; M1 evidence doc |
| G2 | `backend/tests/test_fitting_production.py`, adverse fixtures — explicit `unsupported`/`failed`/issue outcomes, never forced green; e2e lateral/quality-gate regressions |
| U1 | `apps/web/e2e/workbench.spec.ts`, `apps/web/src/store.test.ts` — select, numeric/constrained edit, cancel, undo/redo, coordinate accuracy |
| U2 | `apps/web/e2e/review.spec.ts` (delayed/aborted saves, undo during pending save), `store.test.ts` — drafts retained, stale results never shown current, retry recovers |
| R1 | `backend/tests/test_store.py` concurrent-save/op-ID tests; `e2e/review.spec.ts` two-session 409 |
| R2 | `backend/tests/test_store.py` — real SIGKILL recovery (`TestRealProcessRecovery`), linked retry, API responsive under a slow run |
| R3 | `backend/tests/test_store.py` acceptance-race tests; `e2e/review.spec.ts` dirty-state acceptance gating |
| E1 | `backend/tests/test_store.py` export reconstruction/mismatch tests; `e2e/review.spec.ts` verifier round-trip |
| F1 | `backend/tests/test_store.py` — corrupt DB, closed-connection write fault, solver failure staging, queue bound |
| P1 | [m4-performance](../evidence/m4-performance.md) — all frozen budgets met at `9b02519`; resource behaviour flat |
| X1 | `apps/web/e2e/review.spec.ts` + `e2e/demo.spec.ts` — full journey survives reopen and verifies export |
| X2 | README setup verified in a clean disposable worktree (CAT-013 journal entry); [demo walkthrough](../demo.md) |

## Numerical and interaction gates

CAT-004 sets numerical tolerances from known-geometry fixtures before production fitting is accepted. CAT-006 sets performance budgets on a named environment before performance acceptance. If measured feasibility requires a scope/budget change, record the decision and rerun the relevant checks; never silently relax a failing gate.

Use deterministic failure control where practical. Tests should assert state/geometry and user-visible outcomes, not implementation details. Browser fixture tests complement a real API integration test; they cannot substitute for it. A process-kill test proves only the tested process-crash recovery, not power-loss durability.

## Demonstration deliverables

A short walkthrough should show the labelled synthetic dataset, computed issue, evidence inspection, correction and undo, revalidation, saved/reopened result and provenance. A second brief sequence shows a conflicting edit or interrupted run and recovery. Provide a repeatable local demo and a readable recording; public hosting is optional future scope requiring a separate access decision.

Final documentation explains local requirements, storage/reset behaviour, known unsupported geometry, measurement limits and the portfolio/Neara relationship. Hosted CI should run suitable automated checks when configured; its result remains unverified until an actual run is observed.

Tasks: [CAT-011](../backlog.md#cat-011), [CAT-012](../backlog.md#cat-012), [CAT-013](../backlog.md#cat-013).

Independent re-review at `4611e39`: baseline suites pass; its remaining undo-plus-different-endpoint save race is resolved (`recordSaved` snapshots the acknowledged endpoint set; store + browser regressions). Final acceptance verified per the evidence index; see [M4 re-review](../evidence/m4-exit-review.md#independent-re-review-at-4611e39).
