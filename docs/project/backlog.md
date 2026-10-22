# Cateniq backlog

Updated: 2026-10-23

Task bodies own status; index icons mirror them. Follow the [documentation guide](documentation-guide.md#task-records).

## Task index

- ✅ [CAT-001 — Establish project-management standards](#cat-001)
- ✅ [CAT-002 — Establish the implementation planning baseline](#cat-002)
- ✅ [CAT-003 — Bootstrap the minimal development workspace](#cat-003)
- ✅ [CAT-004 — Freeze the supported geometry and dataset profile](#cat-004)
- ✅ [CAT-005 — Build reproducible corridor fixtures](#cat-005)
- ✅ [CAT-006 — Prototype endpoint inspection and editing](#cat-006)
- ✅ [CAT-007 — Implement fitting and computed diagnostics](#cat-007)
- ✅ [CAT-008 — Complete the computed correction journey](#cat-008)
- ✅ [CAT-009 — Implement durable revisions and recoverable runs](#cat-009)
- ✅ [CAT-010 — Integrate save, acceptance, conflicts and export](#cat-010)
- ✅ [CAT-011 — Verify review races and failure recovery](#cat-011)
- ✅ [CAT-012 — Measure performance and resource behaviour](#cat-012)
- ✅ [CAT-013 — Package and review the portfolio demonstration](#cat-013)

## Delivery notes

M2 review fixes verified; M1 and M2 remain Complete. M3 findings from the independent exit review resolved and verified (see [M3 exit review](evidence/m3-exit-review.md)) — M3 Complete. M4 Complete: performance budgets met (`evidence/m4-performance.md`), demo recorded (`docs/demo/`, `project/demo.md`), clean-environment setup verified, evidence index maps the full acceptance matrix (`features/verification.md`). Next unused ID: CAT-014.

<a id="cat-001"></a>

## CAT-001 — Establish project-management standards

- Repository: cateniq
- Area: documentation
- Milestone: Documentation setup
- Priority: High
- Status: Done ✅
- Depends on: None
- References: [Specification](documentation-guide.md)

### Outcome

Adapt Voltix’s portable documentation workflow to Cateniq.

### Done when

- Root instructions, repository-carried skill and guide agree on ownership, stable IDs/statuses, journal attribution and atomic records updates.
- Existing concept/discussion files are preserved; local links and workflow references pass verification.

### Completion evidence

Created AGENTS.md, portable skill, documentation guide, README and tracking records. Documentation checks are recorded in the journal; no application checks apply. Uncommitted.

### Notes

Complete; use this workflow for subsequent meaningful work.

<a id="cat-002"></a>

## CAT-002 — Establish the implementation planning baseline

- Repository: cateniq
- Area: documentation
- Milestone: Planning baseline
- Priority: High
- Status: Done ✅
- Depends on: CAT-001
- References: [Specification](architecture.md)

### Outcome

Translate the reviewed concept into architecture, staged scope, feature contracts and an initial backlog.

### Done when

- Roadmap has dependencies, exclusions and observable exits; architecture separates design from implementation.
- Feature contracts cover geometry, editing, revision lifecycle, failures and verification; unresolved gates have owners/actions.
- Task IDs, status/index alignment, dependency order, document links and source preservation pass checks.

### Completion evidence

Created architecture, roadmap, four feature contracts, decisions 002/003, two bounded gates and CAT-003–013. Checks are recorded in the journal; no application implemented or runtime tests run. Uncommitted.

### Notes

Next action: CAT-003 and CAT-004; implementation tasks remain unstarted.

<a id="cat-003"></a>

## CAT-003 — Bootstrap the minimal development workspace

- Repository: cateniq
- Area: workspace
- Milestone: M1
- Priority: High
- Status: Done ✅
- Depends on: CAT-002
- References: [Specification](architecture.md)

### Outcome

Create a reproducible browser/API skeleton with a small verified toolchain.

### Done when

- Select compatible Python/Node and library versions from current official sources; commit lockfiles and document verified setup without copying sibling versions blindly.
- Create the proposed minimal app/package structure with one health endpoint, browser shell and explicit local proxy.
- Formatting, type checks, minimal API test and browser/build smoke pass; record exact commands and environment.
- Add appropriate ignore rules and a minimal CI configuration; distinguish local validation from an observed hosted run.

### Completion evidence

Versions selected from official registries (PyPI, npm, GitHub API), each published at least 7 days before selection: Python 3.14.4 / uv 0.11.29 with fastapi 0.143.1, uvicorn 0.54.0, numpy 2.5.4, scipy 1.18.1, pytest 9.1.1, ruff 0.17.1, mypy 2.4.0, httpx2 2.13.1; Node 22.23.1 / npm 10.9.8 with react 19.3.1, vite 8.3.4 (8.3.5 was 1 day old), typescript 7.0.2, three 0.186.1, vitest 5.0.5, @playwright/test 1.64.1. Lockfiles committed (`backend/uv.lock`, `apps/web/package-lock.json`).

Created `backend/src/cateniq/app.py` (one `/api/health` endpoint), `apps/web` shell showing live API status, explicit `/api`→`:8000` proxy on both dev and preview servers, `.gitignore`, `.github/workflows/ci.yml` and verified setup commands in README.

All checks pass locally on Linux kernel 7.0: `uv sync --locked`, `ruff check`, `ruff format --check`, `mypy` (strict, clean), `pytest` (1 passed); `npm ci`, `tsc -b`, `vitest run` (2 passed), `vite build`, and Playwright e2e (1 passed) — real Chromium headless shell 156 loaded the shell, reached the real uvicorn process through the preview proxy and observed `api: ok`. No hosted CI run observed yet; workflow committed but not pushed.

### Notes

Geometry and product scaffold correctly excluded. httpx2 used instead of deprecated httpx test client under starlette 1.9. Next action: CAT-004.

<a id="cat-004"></a>

## CAT-004 — Freeze the supported geometry and dataset profile

- Repository: cateniq
- Area: geometry
- Milestone: M1
- Priority: High
- Status: Done ✅
- Depends on: CAT-002
- References: [Specification](features/datasets-and-geometry.md)

### Outcome

Resolve the mathematical and data contracts before implementing the fitter.

### Done when

- Define schema/IDs, coordinates, supported plane/endpoint geometry, asset identity and separation of observations from reference truth.
- Define fit objective/residual, coverage and endpoint checks, solver bounds, convergence/conditioning rules and numeric tolerances.
- Use primary references and independently derived cases including unequal support heights, shallow sag and inadequate data to validate feasibility.
- Record reproducible profile evidence and resolve BLK-001, or record a reasoned scope revision before dependent implementation.

### Completion evidence

Profile frozen in `backend/src/cateniq/geometry/profile.py`: span-local (u, v) plane coordinates, vertex-form catenary with `a` in [3, 5000] m, spans 10–120 m, sag/span <= 0.20, evidence gates (>=30 points, coverage >= 0.60, gap <= 0.25 L), RMS <= 0.15 m / p95 <= 0.30 m fit quality, 0.50 m endpoint-mismatch threshold, condition bound 1e10. Independently derived reference cases in `backend/tests/test_geometry_profile.py`: 19 checks pass (equal/unequal heights, vertex-outside-span monotonic, shallow sag, sparse/gapped/low-count rejection, displaced-endpoint detection, wrong-correction RMS failure, absurd correction INFEASIBLE, arc-length quadrature cross-check, parabola boundary). Measured errors sit orders of magnitude inside tolerances; see `docs/project/evidence/geometry-profile.md`. BLK-001 resolved. Local: `uv run pytest` 19+1 pass, `ruff check`/`format`, `mypy` strict all clean.

### Notes

A vertex-bracketing gate was tried and dropped — it rejected supported unequal-height (vertex-outside-span) cases; conditioning and a-bounds carry that risk instead. Reference implementation in `catenary.py` validates the profile; CAT-007 hardens it. Next action: CAT-006.

<a id="cat-005"></a>

## CAT-005 — Build reproducible corridor fixtures

- Repository: cateniq
- Area: geometry
- Milestone: M1
- Priority: Normal
- Status: Done ✅
- Depends on: CAT-003, CAT-004
- References: [Specification](features/datasets-and-geometry.md), [Evidence](evidence/corridor-fixtures.md)

### Outcome

Generate and load labelled synthetic evidence with independent evaluation references.

### Done when

- Seeded manifests/assets meet the frozen profile and include nominal, corrupted-endpoint, noisy, missing and unsupported cases.
- Observation and reference datasets are separate; planted prediction errors are declared and diagnostics cannot read their labels.
- Manifest/hash/ID/unit validation and reproducibility tests pass; held-out geometry/seed is reserved for evaluation.

### Completion evidence

2026-10-22: `backend/tests/test_datasets.py` (14 checks) passes; fixtures byte-identical on regeneration; measured outcomes recorded in [evidence/corridor-fixtures.md](evidence/corridor-fixtures.md). Committed alongside the implementation.

### Notes

Three seeded datasets (demo, held-out, adverse). Fitter-facing loading never reads evaluation assets; the S2 planted endpoint error surfaces only through the computed endpoint-deviation check. Held-out B3 confirms geometric fidelity is the honest metric when `a` is weakly identified. Next action: CAT-006.

<a id="cat-006"></a>

## CAT-006 — Prototype endpoint inspection and editing

- Repository: cateniq
- Area: workbench
- Milestone: M1
- Priority: Normal
- Status: Done ✅
- Depends on: CAT-005
- References: [Specification](features/workbench.md), [Evidence](evidence/endpoint-interaction.md)

### Outcome

Prove one endpoint interaction is usable before building a broad editor.

### Done when

- Render source observations and predicted geometry; issue/entity selection focuses the correct span.
- Implement one constrained endpoint tool plus numeric editing and cancellation; verify actual world coordinates, ambiguous hits and occlusion.
- Record measured loading, frame, selection/edit and resource observations on a named environment and representative point counts.
- Freeze interaction design and performance budgets in the contract; resolve BLK-002 and review M1 exit evidence.

### Completion evidence

2026-10-22: 17 vitest unit checks, 5 Playwright journey checks (correction journey incl. computed diagnostic → numeric/drag edit → commit → constrained refit → undo/redo, cancel, no-hit safety) and a 100,200-point perf run all pass; measured numbers and frozen budgets in [evidence/endpoint-interaction.md](evidence/endpoint-interaction.md). BLK-002 resolved. Committed alongside the implementation.

2026-10-23 independent review: existing checks and timing budgets pass, but ambiguous/occluded views and resource observations are not evidenced. Reopened; see [M1 exit review](evidence/m1-exit-review.md).

2026-10-23 follow-up: co-located-handle ambiguity and bird's-eye occlusion now e2e-verified; pick ordering unit-tested via `classifyHits`; resource observations recorded (flat 20 MB heap, identical 91-object rebuild across two round-trips). Bugs the new checks exposed and fixed: horizontal pole-post orientation, occluders missing from the pick set, undisposed scene resources. Frame budget re-frozen p50 ≤50 ms / p95 ≤150 ms after later runs falsified p95 ≤50 ms.

2026-10-23 independent follow-up at `ba25b6d`: implementation fixes and resource observations confirmed, but occlusion regression assertions and workload-specific performance sampling need correction. Reopened; see the [follow-up review](evidence/m1-exit-review.md).

2026-10-23 second follow-up: occlusion regression is now a discriminating layer peel (`pickAtScreen` identifies context → P3 post → S3 → S2 points → handle; each removal changes the outcome) with held-pointer and deselection assertions. Perf sampling isolated to the declared workload (clock before the action; 91-sample window at fixed camera): frame p50 33.3 / p95 50 ms, budgets reconciled p50 ≤50 / p95 ≤100 ms.

### Notes

Prototype scope; no brush, pole editing, persistence or general CAD toolset. Local edits are client-side drafts — durable revisions are CAT-009. Next action: M1 exit confirmed; CAT-007 opens M2.

<a id="cat-007"></a>

## CAT-007 — Implement fitting and computed diagnostics

- Repository: cateniq
- Area: geometry
- Milestone: M2
- Priority: Normal
- Status: Done ✅
- Depends on: CAT-005, CAT-006
- References: [Specification](features/datasets-and-geometry.md)

### Outcome

Produce genuine fitting and validation results from evidence and human constraints.

### Done when

- Pure geometry module implements the frozen profile and returns explicit unsupported, infeasible and failed outcomes.
- Independent reference, sparse/noisy, shallow-sag and held-out tests pass under documented tolerances.
- Quality diagnostics are computed with units/thresholds and provenance; original and corrected results remain distinguishable.
- Full-corridor reruns preserve explicit constraints and never read evaluation truth.

### Completion evidence

2026-10-23: UNSUPPORTED status + domain gates (span length, degenerate endpoints, sag/span>0.2), constrained-refit plane re-derived from corrected endpoints (no silent projection; off-plane offset reported as provenance), basis/units provenance on all results, corridor-level `POST /refit`. 13 new production-fit tests incl. independent cosh-form generator. See [evidence](evidence/fitting-diagnostics.md).

2026-10-23 independent review at `ad06a83`: reopened for corrected-fit quality diagnostics and lateral/support validation. Reproductions and passing baseline checks: [M2 exit review](evidence/m2-exit-review.md).

2026-10-23 review findings resolved: the shared `_issues` gate now applies the frozen RMS/p95 quality checks to corrected as well as prediction results (solver convergence stays distinct from validation), corrected spans contribute issues to the corridor `issue_count`, and the corrected plane must be supported by the evidence — lateral observation RMS above `LATERAL_TOLERANCE_M` (0.5 m) is rejected `unsupported` with the measured value reported, not fitted through. Browser shows fit issues and the lateral metric. New regressions: wrong-but-convergent correction (converges, fails gates), 10 m lateral rejection through the API, corridor rerun preserving S4's unresolved issues; e2e for convergent-with-issues and lateral rejection. 54 pytest + 27 vitest + 12 browser specs green.

### Notes

Use the full rebuild as the baseline; incremental updates are excluded.

<a id="cat-008"></a>

## CAT-008 — Complete the computed correction journey

- Repository: cateniq
- Area: workbench
- Milestone: M2
- Priority: Normal
- Status: Done ✅
- Depends on: CAT-006, CAT-007
- References: [Specification](features/workbench.md)

### Outcome

Connect diagnostics, reversible editing and refitting through the real API.

### Done when

- User inspects an issue, corrects/cancels an endpoint and uses undo/redo with one command per gesture.
- Before/after validation is associated with the right inputs; stale responses cannot replace newer draft results.
- Browser tests assert geometry and error/loading behaviour against the real computation path.
- Transient unsaved state is labelled honestly; M2 exit is reviewed against evidence.

### Completion evidence

2026-10-23: Request/response correlation implemented — `editVersion` captured at request time, late responses flagged stale (`recordFit` version check, responses never replace newer results), constraint echo verified against submitted attachments, dataset-switch discards in-flight results. New e2e: infeasible correction reported honestly; adverse dataset stays `insufficient_evidence` post-edit. 24 vitest + 9 browser specs green.

2026-10-23 independent review at `ad06a83`: reopened for draft cancellation and movement invalidation. Reproductions and passing baseline checks: [M2 exit review](evidence/m2-exit-review.md).

2026-10-23 review findings resolved: staleness is now judged against the effective input snapshot, not the version alone — `FitRecord` stores the submitted attachments and every mutation (`moveDraft`, `commitDraft`, `cancelDraft`, `undo`, `redo`) recomputes each record's flag, so a moved draft flags a shown result immediately, cancelling a moved draft advances `editVersion` (late responses for draft inputs arrive stale), and a cancel that reverts to recorded inputs restores the result. New regressions: store tests for move/cancel invalidation and revert-recovery; e2e route-delayed cancel response flagged stale, and visible-result stale-on-edit / recover-on-cancel. 54 pytest + 27 vitest + 12 browser specs green.

### Notes

Durable save/acceptance belongs to M3, not a misleading mock save button.

<a id="cat-009"></a>

## CAT-009 — Implement durable revisions and recoverable runs

- Repository: cateniq
- Area: review
- Milestone: M3
- Priority: Normal
- Status: Done ✅
- Depends on: CAT-008
- References: [Specification](features/review-lifecycle.md)

### Outcome

Persist correction history and bounded processing attempts without losing user constraints.

### Done when

- Refine and freeze REST/store schemas, operation-record lifetime, migration policy and bounded queue/input/run limits before implementation.
- Atomic base-revision checks and operation-ID idempotency pass concurrent/lost-response tests on real SQLite.
- One bounded execution slot keeps the API responsive; timeout/restart marks attempts failed/interrupted and retry preserves declared inputs.
- Committed corrections survive restart; late output cannot become current; schema mismatch/write failure never silently resets data.

### Completion evidence

Frozen schemas/limits/migration in the lifecycle contract; SQLite store (reviews, append-only operations, runs, acceptance) with conditional saves + operation-ID idempotency; save/reopen/conflict/export routes; export verifier. Bounded single-slot executor (queue depth 8, 30 s cooperative deadline) runs attempts against `constraints_at(input_revision)`; restart marks queued/running `interrupted`; retry links attempts; late output cannot become current validation; acceptance requires current revision + clean succeeded run. 26 store/API tests in `backend/tests/test_store.py`; fault evidence in `docs/project/evidence/m3-review-lifecycle.md`.

Independent review at `296647d` reopened this for coherent snapshots and execution-bound verification — resolved: `store.snapshot()` reads the whole review state under one lock (concurrent-save coherence test); a real SIGKILL child-process test now evidences restart recovery, and an executor-responsiveness test plus an explicit cooperative-deadline scope note close the bound gap.

### Notes

Refine exact execution mechanism here; no distributed task broker or production identity system.

<a id="cat-010"></a>

## CAT-010 — Integrate save, acceptance, conflicts and export

- Repository: cateniq
- Area: review
- Milestone: M3
- Priority: Normal
- Status: Done ✅
- Depends on: CAT-009
- References: [Specification](features/review-lifecycle.md)

### Outcome

Make durable review understandable and complete in the workbench.

### Done when

- Save/reopen and two-session conflict flows preserve drafts and show authoritative revision identity.
- Only matching current validation can be accepted; editing invalidates acceptance and saved undo creates a new revision.
- Schema-versioned export reconstructs effective corrections against the matching source; mismatches are rejected.
- Real browser/API/store journey verifies save, reopen, rerun, acceptance and export with clear failure states.

### Completion evidence

Workbench review flow implemented (`apps/web/src/api.ts`, `store.ts`, `panels.tsx`, `App.tsx`): saved constraint set is the durable baseline under local edits; Save posts the full effective constraint set with the displayed revision; conflicts surface the authoritative revision while the losing edits stay inspectable; run validation polls a durable attempt; Accept binds to the current revision's clean run; revision/acceptance badges shown. Browser evidence (`apps/web/e2e/review.spec.ts`): save→reload restores the correction; two sessions on corridor-b produce a 409 conflict with the loser preserved; a clean run accepts and the badge shows it; the export verifies via `/api/export/verify`. Integration also fixed a dataset-load race (`loadEpoch` correlation — a superseded openDataset response can no longer overwrite newer state). 17 e2e + 27 vitest green.

Independent review at `296647d` reopened this for late-save edit loss, disabled save retry and dirty-state acceptance — resolved: `recordSaved` acks only the submitted edit prefix with dataset/load-epoch correlation; `saveFailed` clears the flag and `pendingSave` replays the operation ID; `canAccept` requires a clean workbench and the badge scopes itself when dirty. Store + e2e regressions cover each.

### Notes

No automatic merge and no claims that corrections are unquestioned ground truth.

<a id="cat-011"></a>

## CAT-011 — Verify review races and failure recovery

- Repository: cateniq
- Area: verification
- Milestone: M3
- Priority: Normal
- Status: Done ✅
- Depends on: CAT-010
- References: [Specification](features/verification.md), [Evidence](evidence/m3-review-lifecycle.md)

### Outcome

Produce reproducible evidence for lifecycle correctness under faults.

### Done when

- Exercise concurrent saves, duplicate/conflicting operation IDs, late results and acceptance races in real integration tests.
- Exercise process interruption, retry, solver failure/timeout and store write failure with bounded waits and isolated state.
- Assert correction preservation, no false success and export consistency; record fault mechanisms and limitations.
- M3 exit maps each lifecycle requirement to passing evidence; required gaps remain open tasks.

### Completion evidence

Fault/race matrix recorded in `docs/project/evidence/m3-review-lifecycle.md`: concurrent same-base saves (exactly one winner), op-ID replay/conflict, late-run non-current, acceptance races (stale accept 409), process-restart interruption, linked retry, deadline failure, solver-failure staging, queue-depth 503, corrupt DB, broken write path, export reconstruction/mismatch — all against real SQLite and a real worker executor. 80 backend tests; 17 browser checks. Limitations documented (simulated restart, injected write fault, unbounded terminal history, no merge).

Independent review at `296647d` reopened this for race regressions and actual process-recovery/deadline evidence — resolved: coherent-snapshot regression under a concurrent saver, real SIGKILL recovery test, executor-responsiveness test, and an explicit cooperative-deadline scope statement. See [M3 exit review](evidence/m3-exit-review.md).

### Notes

Refine fault harness when implementation exists; process crash does not prove power-cut durability.

<a id="cat-012"></a>

## CAT-012 — Measure performance and resource behaviour

- Repository: cateniq
- Area: verification
- Milestone: M4
- Priority: Normal
- Status: Done ✅
- Depends on: CAT-011
- References: [Specification](features/verification.md)

### Outcome

Validate the workbench against the budgets established at M1.

### Done when

- Reproduce named workloads and record load, frame, selection/edit, memory and recalculation distributions.
- Test repeated dataset replacement and editing; inspect resource disposal and responsiveness during fitting.
- Meet frozen budgets or explicitly revise scope with evidence; reverify correctness after any optimisation.

### Completion evidence

`docs/project/evidence/m4-performance.md` — post-M3 measurements at `9b02519` on the named 100k-point workload (production durable-review UI): load 1682 ms (≤4000), select 416 ms (≤500), edit 615 ms (≤800), commit 423 ms (≤800), frames p50 33.3 / p95 50 ms (≤50/≤100), heap flat 21 MB across dataset replacement, renderer objects return to baseline. Responsiveness during fitting: service-level slow-run test (API <0.5 s under a 100 ms/span fit) plus UI staleness suite. All budgets met; no revision needed.

### Notes

Refine at M3 exit. Do not optimise solely for one scripted camera view.

<a id="cat-013"></a>

## CAT-013 — Package and review the portfolio demonstration

- Repository: cateniq
- Area: deployment
- Milestone: M4
- Priority: Normal
- Status: Done ✅
- Depends on: CAT-012
- References: [Specification](features/verification.md)

### Outcome

Deliver reproducible local operation, a concise demo and final evidence review.

### Done when

- Clean-environment setup and safe state/reset/cleanup instructions are verified; README uses actual commands.
- Record the correction and recovery stories; document unsupported cases and measured limits.
- Final evidence index covers the acceptance matrix and milestones; report hosted CI separately and honestly.
- Explain Neara alignment and complementarity with NEMLab/Voltix without overstating domain or production coverage.

### Completion evidence

Recorded walkthroughs: `docs/demo/01-correction-journey.webm` + `02-accept-and-conflict.webm` (Playwright video of `apps/web/e2e/demo.spec.ts` against the production build, real API and isolated `.e2e-demo.db`); narrative in `docs/project/demo.md`. README verified in a clean disposable worktree: `uv sync --locked` → 83 pytest, `npm ci` → typecheck + 30 vitest + build, `npx playwright test` → 19 browser checks; reset boundary (`CATENIQ_DB_PATH`, `rm backend/reviews.db*`) exercised. Evidence index in `features/verification.md` maps every acceptance-matrix scenario to passing evidence. Hosted CI workflow exists but no hosted run observed — reported separately per contract.

### Notes

Refine at M3 exit and split only when useful. Public hosting and publication are not implicitly authorised.
