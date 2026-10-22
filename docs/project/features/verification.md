# Verification and demonstration plan

Date: 2026-10-22

Status: M1 application checks have run and were independently reproduced; see [M1 exit review](../evidence/m1-exit-review.md) for results and outstanding interaction/resource evidence. Later milestone acceptance remains planned.

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

## Numerical and interaction gates

CAT-004 sets numerical tolerances from known-geometry fixtures before production fitting is accepted. CAT-006 sets performance budgets on a named environment before performance acceptance. If measured feasibility requires a scope/budget change, record the decision and rerun the relevant checks; never silently relax a failing gate.

Use deterministic failure control where practical. Tests should assert state/geometry and user-visible outcomes, not implementation details. Browser fixture tests complement a real API integration test; they cannot substitute for it. A process-kill test proves only the tested process-crash recovery, not power-loss durability.

## Demonstration deliverables

A short walkthrough should show the labelled synthetic dataset, computed issue, evidence inspection, correction and undo, revalidation, saved/reopened result and provenance. A second brief sequence shows a conflicting edit or interrupted run and recovery. Provide a repeatable local demo and a readable recording; public hosting is optional future scope requiring a separate access decision.

Final documentation explains local requirements, storage/reset behaviour, known unsupported geometry, measurement limits and the portfolio/Neara relationship. Hosted CI should run suitable automated checks when configured; its result remains unverified until an actual run is observed.

Tasks: [CAT-011](../backlog.md#cat-011), [CAT-012](../backlog.md#cat-012), [CAT-013](../backlog.md#cat-013).
