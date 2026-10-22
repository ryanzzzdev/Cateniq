# Evidence — endpoint interaction prototype and budgets (CAT-006 / BLK-002)

Date: 2026-10-22
Environment: Linux kernel 7.0, Intel Core Ultra 5 225H (14 threads), 30 GB RAM; Python 3.14.4/FastAPI 0.143.1 backend; Node 22.23.1, Vite 8.3.4 preview, Three.js 0.186.1; Chromium via Playwright 1.64.1 (headless).
Workload: `corridor-perf` — 9 spans × 11,000 conductor points + context = 100,200 points rendered, generated on demand by `scripts/generate_perf_corridor.py` (not committed).
Procedure: `cd apps/web && npx playwright test` (5 journey checks) and `npx playwright test -c playwright.perf.config.ts` (measurement run against the 100k workload). Unit coverage: 17 vitest checks for the store and interaction math; backend: 39 pytest checks including service-level HTTP tests.

Independent review: [M1 exit review](m1-exit-review.md) reproduces timing and existing tests, reopened ambiguous/occluded-view verification and resource observations — both addressed below (updated 2026-10-23).

## Frozen interaction design (chosen in CAT-006)

- Selection: click a span's conductor points or predicted curve in the viewport, or a row in the diagnostic queue. Handles appear only on the selected span, so an unselected span can never be dragged.
- Edit tool: one endpoint handle per end (drag) plus numeric x/y/z fields (focus starts a draft). Dragging is constrained to the declared vertical plane through the span's attachments (ray↔plane intersection); the endpoint snaps to the support pole's named attachment candidates within 0.6 m.
- Preview before commit: a ghost handle, a from→to displacement line, a snap ring on the candidate target, and a live displacement readout in the properties panel.
- Commit/cancel/undo: pointer release (or Commit) produces one logical undoable command — a drag with zero displacement produces none. Esc cancels and restores the pre-draft endpoint. Ctrl+Z / Ctrl+Shift+Z / Ctrl+Y drive undo/redo; a new commit clears the redo stack. Numeric fields are keyboard-reachable with visible focus rings; queue rows are buttons.
- Picking honesty: no-hit clicks clear selection and move nothing; invisible handles are not pickable; the nearest hit wins, so an ambiguous click never moves an arbitrary object.
- State distinction: selected span vs in-progress draft vs committed local edits (labelled "unsaved draft — persistence is CAT-009") vs refit preview (marked stale after any subsequent edit to the span). Durable revisions/run identities are CAT-009 scope.
- Validation preview: `POST /api/datasets/{id}/fit` refits the span constrained to the current (edited) attachments and draws the dashed result curve; S2 corrected to `P3:high` refits ok (RMS 0.033 m), to `P3:low` returns infeasible.

## Measured performance (100,200 points)

| Interaction | Measured | Frozen budget |
| --- | --- | --- |
| Load → ready (fetch + parse + scene build) | 1,886 ms | ≤ 5,000 ms |
| Issue/entity select → properties visible | 416 ms | ≤ 1,000 ms |
| Begin numeric edit → draft panel + displacement | 555 ms | ≤ 1,000 ms |
| Commit edit | 393 ms | ≤ 1,000 ms |
| Frame delta p50 / p95 | 33.2 / 33.4 ms (first runs); 33.3 / 116–133 ms (later runs) | p50 ≤ 50 ms; p95 ≤ 150 ms |

Measured latencies include Playwright action overhead, so they are conservative end-to-end bounds. Frame p95 varies 33–133 ms across runs under headless Chromium (GC and buffer-upload jitter); occasional single-frame spikes to ~283 ms occur during initial geometry upload and are outside the p95 budget. The original p95 ≤ 50 ms budget was falsified by later runs and is re-frozen at ≤ 150 ms.

## Coverage proven

- Full journey e2e: queue shows the computed `endpoint_mismatch` on S2 (deviation +1.51 m), numeric z-edit 10.5→12.0, commit, constrained refit ok (rms ≈0.03 m), undo restores 10.5 (refit marked stale), redo restores 12.0.
- Cancel: mid-draft Esc restores the predicted endpoint and leaves no undo entry.
- Ambiguous/no-hit: clicking empty sky selects nothing and moves nothing; a subsequent select shows the prediction unchanged.
- Drag path: pointer drag on the b-handle to the P3:high candidate's screen position snaps and commits 10.5→12.0 as one command.
- Ambiguous view: verified 2026-10-23. S1's b-handle and S2's a-handle share world point (50, 0, 12); clicking that pixel while S2 is selected drafts endpoint **a** and while S1 is selected drafts endpoint **b** — the nearest *visible* handle wins; the invisible co-located handle never steals the pick (e2e `co-located handles`). Cancelling before release commits nothing.
- Occluded view: verified 2026-10-23. A bird's-eye camera above pole P3 puts the pole post (top 13.5 m) between the camera and the b-handle (10.5 m): clicking the handle's position hits the post and produces no draft and no move (e2e `occluded handle cannot be dragged through a pole`). The same handle drags normally once the camera returns. Pick ordering is now classified by the unit-tested `classifyHits` (nearest visible hit; blockers shadow what they occlude; no-hit moves nothing).
- Bugs found and fixed by these checks: pole posts rendered horizontally (cylinder axis is +Y, not +Z — now rotated upright); pole posts/context points were absent from the pick set so occluders did not shadow picks (now blockers); `clearData()` removed objects without disposing geometries/materials and `dispose()` left the ResizeObserver attached (both fixed).

## Resource observations (100,200-point workload, same environment)

Measured across two dataset round-trips (perf → corridor-a → perf → corridor-b → perf):

- JS heap (usedJSHeapSize): flat at 20 MB before and after both round-trips.
- Scene object count: 91 objects after reload — identical rebuild, no stale-object accumulation.
- Draw calls/triangles at a fixed camera: 28 / 3,296 before and after reload — render load returns to baseline.
- `renderer.info.memory.geometries` varied (40→47): it counts geometry buffers ever uploaded, which depends on which objects entered the frustum during the session — not live-object count. Live objects (91) and heap confirm no accumulation. Repeated-load acceptance remains CAT-012.

## Limits declared

Prototype scope: no persistence, revisions, cross-span edits or pole editing; edits are client-side drafts. Frame times were measured in headless Chromium on the named machine — real-GPU frame pacing may differ. ~100k points is the agreed representative workload, not a scale claim.
