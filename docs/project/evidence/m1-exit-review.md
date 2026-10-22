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
