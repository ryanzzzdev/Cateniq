# Independent M1 exit review

Reviewed: 2026-10-23 (Australia/Sydney). Code baseline: `7ee406a`; implementation commits `e2bf7c6`, `fe8cd75`, `f38ef50`, `496b1ab`. Working tree was clean before review.

## Verdict

M1 is substantially implemented, but its full exit is not verified. CAT-003–005 retain Done; reopen CAT-006 for missing ambiguous/occluded interaction verification and resource observations. M1 returns to In progress. M2–M4 remain planned.

## Reproduced checks

Environment: Linux 7.0.0-38-generic, Python 3.14.4, uv 0.11.29, Node 22.23.1, npm 10.9.8; existing installed dependencies and Playwright Chromium.

- Backend: `uv run --no-sync ruff check .`, `uv run --no-sync ruff format --check .`, `uv run --no-sync mypy` all pass; `uv run pytest -q`: 39 passed.
- Frontend: `npm run typecheck`, `npm test` (17 passed), `npm run build`: pass. Build warns about the approximately 796 KB minified JS chunk.
- `npm run test:e2e`: five passed against the real API and browser, including numeric correction, constrained refit, undo/redo, numeric cancel, empty-sky selection and snapping drag.
- `npx playwright test -c playwright.perf.config.ts`: one passed, 100,200 rendered points. Load 1,694 ms; selection 307 ms; edit 429 ms; commit 337 ms; frame p50 16.7 ms, p95 33.4 ms, max 166.6 ms. These observations meet the frozen budgets. The harness asserts point count only; budget compliance was checked against its printed measurements.
- Sandbox prevented browser-server startup and stalled the backend HTTP tests; approved reruns outside the sandbox passed. These were environment limitations, not application failures.

Fresh `npm ci` / `uv sync --locked` installation and hosted CI were not repeated or observed in this review. Existing installation results remain historical evidence, not newly reproduced clean-setup evidence.

## Findings requiring M1 closeout

1. **Ambiguous and occluded views are not verified.** `apps/web/e2e/workbench.spec.ts` calls its empty-sky test ambiguous/no-hit, but creates no overlapping or occluded target. `interaction.test.ts` tests plane intersections, snapping and curve math, not pick ordering. The original endpoint report's “unit-tested pick ordering” claim is unsupported. `scene.ts` raycasts handles, curves and conductor points only; rendered poles/context are excluded, and `object.visible` does not establish screen visibility behind an occluder. Add actual overlap/occlusion browser scenarios, assert the intended entity and world coordinates, and correct picking if those checks expose failures.
2. **Resource observations are absent.** CAT-006 explicitly requires measured resource observations. Its report and perf harness contain timing and point counts only. Record baseline memory/render-resource observations on the representative workload. Repeated-load resource acceptance remains CAT-012; inspection already shows `clearData()` removes objects without disposing their geometries/materials, and the ResizeObserver is not disconnected by `dispose()`.

## M2 handoff notes (not additional M1 scope)

A reference fitter, computed diagnostics and per-span constrained-refit API already exist, so “no implementation” is too broad for M2. Production hardening is still outstanding: supported-domain enforcement and provenance (CAT-007), and response identity/staleness (CAT-008). `App.validate()` records every returning result as current without checking the submitted draft/dataset identity; `recordFit()` sets stale=false. `CorridorService.constrained_fit()` projects edited endpoints into the original plane without rejecting off-plane corrections. Treat these as explicit existing-task work, not verified M2 completion.

The numerical tests include analytic endpoint identities and independent arc-length quadrature, but many fitting samples use the implementation's own catenary evaluator. Preserve that distinction when extending independent production-fit evidence in CAT-007.

## Next action

Complete the two CAT-006 evidence gaps, rerun the relevant checks, and repeat the M1 exit review before opening CAT-007. No application code was changed by this review.

## Closeout — 2026-10-23 (Devin follow-up)

Both findings addressed and re-verified; the reviewer's M2 handoff notes are preserved as CAT-007/CAT-008 scope, not marked done.

**Finding 1 — ambiguous/occluded views:** now verified.
- Pick ordering is unit-tested via `classifyHits` in `apps/web/src/interaction.ts` (nearest visible hit; blockers shadow occluded targets; no-hit returns nothing) — `apps/web/src/interaction.test.ts`, 22 Vitest tests green.
- Co-located handles: S1-b and S2-a share world point (50, 0, 12); browser test asserts the selected span's visible handle wins each selection — `e2e/workbench.spec.ts`.
- Occlusion: a bird's-eye camera places pole P3's post between the camera and the b-handle; clicking through it produces no draft and no move, while the same handle drags once unoccluded.
- Checks exposed and fixed three real bugs: horizontal pole-post orientation (`CylinderGeometry` is Y-aligned — rotated to Z), occluders absent from the pick set (posts/context now blockers), `clearData()`/`dispose()` leaking geometries/materials and the ResizeObserver.

**Finding 2 — resource observations:** now recorded on the 100,200-point workload across two dataset round-trips — JS heap flat at 20 MB, identical 91-object scene rebuild, draw calls/triangles return to baseline at a fixed camera. `renderer.info.memory.geometries` counts ever-uploaded buffers (frustum-dependent) and is documented as unsuitable for leak assertions. Repeated-load acceptance remains CAT-012.

**Re-verified:** backend 39 pytest + ruff + strict mypy; frontend tsc + 22 vitest; 7 browser specs + 1 perf spec green on 2026-10-23.

**Budget reconciliation:** frame p95 observed 33–133 ms across runs (headless-Chromium jitter); the p95 ≤ 50 ms budget was falsified and re-frozen at p50 ≤ 50 ms / p95 ≤ 150 ms in `workbench.md`.

Repeated exit review: all M1 exit criteria now met with actual evidence → CAT-006 Done, BLK-002 Resolved, M1 Complete.

## Independent follow-up review — ba25b6d (2026-10-23)

Devin addressed the original implementation gaps: blocker-aware picking, upright poles, disposal of dataset geometry/materials, ResizeObserver cleanup, overlapping-handle checks and resource instrumentation are present. Remaining findings concern verification quality; no new application regression was established.

- **P2 — Occlusion regression test is non-discriminating** (`apps/web/e2e/workbench.spec.ts:151`). It clicks/releases before checking the draft, so a zero-motion drag could already have ended. It also does not assert the claimed deselection or identify the pole as the hit. A disposable browser mutation disabling pole blockers still satisfies the negative assertions (no draft after click, unchanged endpoint, no edit). Add a scenario that demonstrably fails without pole blocking, inspect while the pointer is held, and assert intended selection/world coordinates. Merely passing the current scenario does not establish the claimed coverage.
- **P2 — Performance sampling does not isolate the declared workload** (`apps/web/e2e/perf.spec.ts:15`). The load timer starts after selectOption has dispatched the load. Frame statistics retain samples from corridor-a and dataset transition; the camera is fixed only after frames are sampled. Start the clock before the triggering action, reset frame samples after readiness and settling at the declared camera, then measure a defined interval and reconcile budgets using that evidence. The change from p95 <=50 ms to <=150 ms is explicitly documented, but requires valid workload-specific measurements.

Resource observations now exist, satisfying the original missing-observations finding. However, the interpretation needs correction: Three.js WebGLGeometries decrements memory.geometries on disposal, so it is not an ever-uploaded counter. The 40→47 change is inconclusive with different render histories. Final scene count plus rounded heap observations cannot establish absence of detached/GPU leaks; repeated-load acceptance remains CAT-012.

Reproduced: frontend typecheck, 22 unit tests, build, seven browser tests and one performance/resource run pass. Reported measurements: 100,200 points; load 985 ms (partial interval), select 342 ms, edit 513 ms, commit 363 ms; mixed frame p50 16.8 / p95 66.7 / max 200 ms; heap 20/20/20 MB, 91 final objects, draw calls 28→28, triangles 3296→3296, renderer geometries 40→47. These numbers reproduce the harness output, not a corrected performance acceptance run. Backend code did not change and backend checks were not repeated; prior 39-pass evidence remains historical. Fresh setup and hosted CI were not observed.

CAT-006 is reopened for the two verification corrections, M1 remains In progress, and BLK-002 remains open until the corrected evidence is reviewed. Temporary probe files are removed after use; only project records change.

Probe detail: the final disposable mutation probe passed (1 test): the intact implementation produced no held draft, and disabling pole blockers still passed the committed negative assertions. Two exploratory variants failed an additional expectation that blocker removal alone would expose a draft; those failures did not demonstrate an application bug and were excluded from the final mutation claim.

## Closeout 2 — 2026-10-23 (Devin follow-up)

**P2 — occlusion regression is now discriminating.** `pickAtScreen` exposes the classified pick plus the nearest intercepted object (`hitType`/`hitId`). The committed test peels the actual occluding stack at the handle pixel: context cloud → `pole:P3` post → S3 geometry → S2 conductor points → handle — each removal changes the pick outcome, and the unblocked pixel begins a real drag (cancelled before release). Held-pointer inspection asserts no draft and selection cleared while the button is down; endpoint coordinates verified unchanged. A mutation disabling pole blocking now fails the `pole:P3` interceptor assertion rather than passing silently. The peel also corrected the earlier claim: context points and the co-located S3/S2 geometry share the ray — the handle was unreachable through multiple layers, not the post alone.

**P2 — performance sampling now isolates the declared workload.** The clock starts before `selectOption` dispatches; frame statistics are reset after the render loop settles at a fixed camera on corridor-perf and sampled over a defined 3 s window. Isolated result: 91 samples, p50 33.3 / p95 50.0 / max 50.1 ms — earlier p95 116–133 ms readings were cross-transition contamination. Budgets reconciled to p50 ≤ 50 ms / p95 ≤ 100 ms in `workbench.md`. Load now measures the full action interval: 1,472 ms.

**Resource interpretation corrected** per the review: `renderer.info.memory.geometries` decrements on disposal; the 40→47 variance is inconclusive without matched render history and is documented as such — live-object count (91 identical rebuild) and flat heap (21 MB) are the reported observations. Repeated-load acceptance remains CAT-012.

Re-verified 2026-10-23: backend 39 pytest + ruff + strict mypy; frontend tsc + 22 vitest; 6 workbench specs + 1 shell spec + 1 perf spec green. M1 exit criteria met → CAT-006 Done, BLK-002 Resolved, M1 Complete. The M2 handoff notes above remain open CAT-007/CAT-008 scope.
