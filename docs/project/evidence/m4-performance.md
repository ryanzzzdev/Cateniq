# Evidence — performance and resource behaviour (CAT-012)

Date: 2026-10-23
Environment: Linux kernel 7.0, Intel Core Ultra 5 225H (14 threads), 30 GB RAM; Node 22.23.1, Chromium headless shell 156 via Playwright 1.64.1; Python 3.14.4.
Procedure: `cd apps/web && npx playwright test -c playwright.perf.config.ts` against the named `corridor-perf` fixture (100 200 points). Backend suite `cd backend && uv run pytest` provides the service-level run-responsiveness check. Code revision: `9b02519` (post-M3, durable-review UI included — measurements therefore cover the production UI, not a prototype shell).
Budgets: frozen in `features/workbench.md` after M1 profiling (see [endpoint-interaction evidence](endpoint-interaction.md)).

## Measured results vs frozen budgets

| Check | Contract budget (`features/workbench.md`) | Measured | Verdict |
| --- | --- | --- | --- |
| Load → ready, 100k corridor | ≤ 5 s | 1634 ms | Pass |
| Click-to-highlight selection | ≤ 1 s | 431 ms | Pass |
| Edit feedback | ≤ 1 s | 619 ms | Pass |
| Commit | ≤ 1 s | 442 ms | Pass |
| Frame time p50 / p95 (fixed-camera 3 s window) | ≤ 50 / ≤ 100 ms | 33.3 / 50 ms | Pass |
| Recalculation (`POST /fit` click-to-result on edited span) | no frozen budget — observed | 445 ms | Observed |
| Repeated dataset replacement | no stale objects / resource growth per contract | heap flat 22 MB across three loads; renderer geometries 40 → 29 → 47, calls ~28, triangles 3296 | Pass |
| Repeated edit/undo/redo cycles (5×) | no stale objects / resource growth per contract | heap flat 22 MB; renderer 50 geometries / 36 calls during live editing (selected-span curve + handles allocated, not leaked) | Pass |

`GEOPROBE` confirms 91 live geometries render against the 100 200-point cloud — instanced rendering, not per-point objects.

## Responsiveness during fitting

- **Service level**: `backend/tests/test_store.py::test_api_stays_responsive_during_a_slow_run` — a 100 ms/span fit occupying the single executor slot leaves `review_state` responding in < 0.5 s, and the run completes through the worker. This is API-concurrency evidence, not browser responsiveness.
- **Browser level**: recalculation itself is measured above (445 ms round-trip). During in-flight fit/save requests the staleness suite (`e2e/review.spec.ts`, `store.test.ts`) exercises edits and undos; late responses land as stale or are rebased, never silently overwriting newer local work.
- Synthetic fit durations are sub-second by construction; there is no long-running solve to profile. The single-slot executor bounds solver concurrency by contract (`features/review-lifecycle.md`).

## Resource and repeated-replacement observations

- Three sequential dataset loads (A → perf → A → perf and perf → B → perf) in one session: heap flat at 22 MB, renderer allocations return to baseline (~29–47 live geometries; 0 textures allocated throughout).
- Five commit → undo → redo cycles in one selection: heap flat; elevated geometry/call counts during live editing reflect the actively displayed correction curve and handles, not accumulation.
- `future` clears on new commits and fit records retain only the last result per span by design — no unbounded local-history retention.

## Scope notes and limitations

- Numbers are one run on one named machine; they are evidence the budgets hold on the declared environment, not a general hardware guarantee. Headless fixed-camera frames; an interactive headed session may differ. The harness measures a scripted sequence (load → frames → select → edit → commit → recalculate → repeated edits → dataset round-trips), not an operator's session.
- Heap deltas are rounded whole-megabyte samples of JS heap — they do not isolate GPU-resident or detached-DOM resources; renderer-object counts are the proxy for those and return to baseline.
- The independent M4 review noted an earlier version of this document cited outdated budget values and measurements the harness did not perform; the table above now matches `features/workbench.md` and only what `e2e/perf.spec.ts` actually measures.
- Chunk size >500 kB warning at build time (Three.js bundle) is a load-size note, not a runtime budget failure; splitting is future work.

## Verdict

All frozen budgets met on the declared environment with the post-M3 production UI; recalculation latency and repeated-edit/replacement resource behaviour are measured within the harness. No budget revision needed.
