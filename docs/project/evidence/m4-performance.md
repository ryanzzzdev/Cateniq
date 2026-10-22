# Evidence — performance and resource behaviour (CAT-012)

Date: 2026-10-25
Environment: Linux kernel 7.0, Intel Core Ultra 5 225H (14 threads), 30 GB RAM; Node 22.23.1, Chromium headless shell 156 via Playwright 1.64.1; Python 3.14.4.
Procedure: `cd apps/web && npx playwright test -c playwright.perf.config.ts` against the named `corridor-perf` fixture (100 200 points). Backend suite `cd backend && uv run pytest` provides the service-level run-responsiveness check. Code revision: `9b02519` (post-M3, durable-review UI included — measurements therefore cover the production UI, not a prototype shell).
Budgets: frozen in [M1 evidence](m1-evidence-and-interaction.md) / `features/workbench.md` and `decisions/003-correction-lifecycle.md` after M1 profiling.

## Measured results vs frozen budgets

| Check | Budget | Measured | Verdict |
| --- | --- | --- | --- |
| Load 100k-point corridor | ≤ 4000 ms | 1682 ms | Pass |
| Click-to-highlight selection | ≤ 500 ms | 416 ms | Pass |
| Numeric edit latency | ≤ 800 ms | 615 ms | Pass |
| Commit (constraint apply) | ≤ 800 ms | 423 ms | Pass |
| Frame time p50 / p95 | ≤ 50 / ≤ 100 ms | 33.3 / 50 ms | Pass |
| Heap delta across dataset replacement | ≤ 150 MB | 0 MB (21 → 21 → 21 over two switches) | Pass |
| Renderer objects across replacement | no unbounded growth | geometries 40 → 29 → 47, calls ~28, triangles 3296 stable | Pass |

`GEOPROBE` confirms 91 live geometries render against the 100 200-point cloud — instanced rendering, not per-point objects.

## Responsiveness during fitting

- **Service level**: `backend/tests/test_store.py::test_api_stays_responsive_during_a_slow_run` — a 100 ms/span fit occupying the single executor slot leaves `review_state` responding in < 0.5 s, and the run completes through the worker.
- **UI level**: the staleness suite (`apps/web/e2e/review.spec.ts`, `store.test.ts`) exercises edits committed while a fit/run request is in flight; in-flight responses land as stale, never as current, and the draft stays live — the workbench remains usable rather than blocking on the solver.
- Synthetic fit durations are sub-second by construction; there is no browser-level long-running solve to profile. The single-slot executor bounds solver concurrency by contract (`features/review-lifecycle.md`).

## Resource and repeated-replacement observations

- Three sequential dataset loads (A → perf → A → perf) in one session: heap flat at 21 MB, renderer allocations return to baseline (29–47 geometries live; disposal works — no texture leak, 0 textures allocated throughout).
- Repeated edit/undo cycles are exercised by the vitest and e2e suites with no retention of superseded fit records beyond the last-per-span map; `future` clears on new commits by design.

## Scope notes and limitations

- Numbers are one run on one named machine; they are evidence the budgets hold on the declared environment, not a general hardware guarantee. The config is `workers: 1`, headless; interactive headed numbers may differ.
- The perf spec measures a scripted sequence, not an operator's session; per CAT-012 it is not optimised to a single camera view (load → select → edit → commit → rotate frames).
- Chunk size >500 kB warning at build time (Three.js bundle) is a load-size note, not a runtime budget failure; splitting is future work.

## Verdict

All frozen budgets met on the declared environment with the post-M3 production UI; resource behaviour under repeated loads is measured and flat. No budget revision needed.
