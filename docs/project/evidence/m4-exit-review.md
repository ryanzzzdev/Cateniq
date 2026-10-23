# Independent M4 exit review

Baseline: `829b736` (M3 fixes `9b02519`, performance `7d4bea0`, packaging/demo `829b736`). Existing installed environment: Linux 7.0.0-38-generic, Python 3.14.4/uv 0.11.29, Node 22.23.1, Playwright Chromium. No fresh install or hosted CI observed in this review.

## Verdict

M4 is not ready for completion. Demo files and an independently runnable demo exist, and the measured timing workload passes, but the documented verification command fails, an undo/save race remains, and final performance evidence is incomplete. M1/M2 remain Complete; reopen CAT-010/011 and CAT-012/013, with M3/M4 In progress.

## Findings

### P1 — Default browser suite includes state-mutating demos

`apps/web/playwright.config.ts:5` ignores only perf.spec.ts, so npm run test:e2e also discovers demo.spec.ts. A spec does not select its own config/database: both demo and verification files therefore use .e2e-reviews.db. The demo saves corridor-a S2 to 12 and changes corridor-b revisions while other files expect pristine fixtures. Reproduced default command: 21 tests, 16 passed and five failed (cancel, no-hit, drag, occlusion, and demo acceptance). The expected original z=10.50 instead read 12.00; demo acceptance saw revision 4 with an issue instead of clean revision 0.

Exclude demo.spec.ts from the verification config; retain the dedicated demo config/database, and rerun the exact README and CI command. The default CI command is the same failing command. Dedicated demo config passes both demos independently.

### P1 — Undo during a pending save is silently reversed

`apps/web/src/store.ts:392–395` preserves current past when it no longer matches the submitted prefix, but installs the saved endpoints as the new baseline and clears future. If the user undoes the submitted edit, past is empty and does not represent the inverse of the new saved state.

Reproduced with a temporary real-API browser probe: S2 10.5→12, Save with delayed response, Undo→10.5, release response→12 with no unsaved indicator. The user's newer undo is lost. This is a remaining case of the M3 late-save finding, despite the append-new-edit regression passing. Preserve effective local geometry across acknowledgement by rebasing against the submitted snapshot, including undo-to-empty and branch-after-undo; add a regression. The probe was removed after use.

### P2 — Final performance/evidence claims exceed the measured coverage

CAT-012 requires recalculation distributions, repeated editing/resource behaviour and responsiveness during fitting. The harness records one numeric edit/commit and two dataset round-trips, with one fixed-camera frame window; it does not measure recalculation latency or resource behaviour across repeated edits/undo. The report's “rotate frames” sequence does not exist in the harness. The service slow-run test times a direct review_state() call while a worker sleeps per span; it is useful concurrency evidence, not browser responsiveness or recalculation profiling.

`m4-performance.md` cites nonexistent m1-evidence-and-interaction.md and claims frozen 4000/500/800/800-ms latency budgets and a 150-MB heap budget; the workbench contract instead states 5000/1000/1000/1000 ms and no heap budget. The measured run passes both latency sets, so this is provenance/coverage incompleteness, not an observed timing failure. The final evidence index cites nonexistent backend/tests/test_geometry.py and test_fitting.py (actual files are test_geometry_profile.py and test_fitting_production.py). Correct the index/budget sources and add missing measurements or explicitly accepted scope changes before asserting every matrix scenario passes. Final scene-object equality and rounded heap samples alone do not prove absence of retained GPU/detached resources.

## Verification results

- Backend ruff check/format, strict mypy and 83 tests pass, including the new child-process SIGKILL/recovery test and single-service concurrent snapshot test.
- Frontend typecheck, 30 unit tests and build pass; large-bundle warning remains.
- Default npm run test:e2e: five failures / 21 tests as above. Control run explicitly selecting e2e/shell.spec.ts, e2e/workbench.spec.ts and e2e/review.spec.ts: all 19 pass, confirming demo interference.
- Temporary focused undo/save probe: one passing probe asserting the reproduced bug, against real API/save responses.
- Dedicated performance config: one pass, 100,200 points, load 2017 ms, select 341 ms, edit 522 ms, commit 343 ms; isolated frames n=106, p50 33.3/p95 33.4/max 33.5 ms. Rounded heap 25/25/25 MB, 91 final scene geometries, renderer geometries 40→29→47; calls/triangles return to 28/3296. Timing meets the workbench contract; resource limits remain as above.
- Dedicated demo config: two passed and fresh video outputs generated. The two committed WebM files exist; this review did not visually audit their editorial quality or certify that a particular page's recording contains the second-page conflict view.
- M3 original failure/retry, dirty acceptance and append-new-edit cases now pass their regressions. Undo-during-save remains open. The documented cooperative deadline is not a hard preemption guarantee.

## Required closeout

Fix verification/demo isolation and undo preservation, complete/correct CAT-012 evidence, then repeat the exact packaged verification commands and final matrix review. Preserve honest hosted-CI and fresh-install limitations. No application code was changed by this review.

## Resolution (post-review)

All findings verified as real defects and fixed:

- **Demo/verification isolation** — `demo.spec.ts` is now excluded in `playwright.config.ts`; the default `npm run test:e2e` discovers only the verification suite (20 checks, all passing) while `playwright.demo.config.ts` still records the demos against `.e2e-demo.db`. The previously failing five tests pass again; the CI command is the same fixed command.
- **Undo during a pending save** — `recordSaved` no longer acks a history prefix; it rebases: acknowledged commands drop by identity, kept commands whose effect the baseline already reproduces drop as redundant, and any history-touched endpoint the new baseline does not reproduce is re-expressed as an explicit unsaved `EditCommand` (undo-to-empty and branch-after-undo both covered, and the synthesized edit is itself undoable). Regressions: `store.test.ts` undo/undo-redo cases and a `review.spec.ts` browser test holding the operations response across an undo.
- **Performance evidence completeness** — `e2e/perf.spec.ts` now measures `POST /fit` recalculation latency (445 ms) and five commit/undo/redo cycles with heap/renderer-object checks (flat 22 MB); `m4-performance.md` now cites the `features/workbench.md` budgets (≤5 s load, ≤1 s select/edit/commit, frames p50 ≤50 / p95 ≤100 ms) instead of outdated values, drops the nonexistent "rotate frames" claim, and states the heap-measurement limit honestly. Evidence-index filenames corrected to `test_geometry_profile.py` / `test_fitting_production.py`.

Re-verification at this revision: 83 pytest + ruff/format/strict mypy; `tsc -b` + 32 vitest + build; 20 browser checks on the default config; 2 demo recordings on the dedicated config. CAT-010–013 Done, M3/M4 Complete again.

## Independent re-review at `4611e39`

The resolution above is partially confirmed. One P1 remains: **undo followed by a different-endpoint edit during save still loses the undo**. CAT-010/011 reopen; M3/M4 remain In progress. CAT-012/013 fixes are verified within the measurement limitations below.

Reproduction using `readyStore()` from `store.test.ts`: commit S2 b from z=10.5 to 12; capture `submitted = s.get().past`; undo; commit S2 a from z=12 to 13; acknowledge the submitted snapshot with `recordSaved(1, {S2: {attach_a: [50,0,12], attach_b: [95,0,12]}}, null, submitted)`. Before acknowledgement b is 10.5; afterward it is incorrectly 12, while a correctly stays 13. A temporary Vitest regression asserting b remains 10.5 failed with expected 10.5 / received 12; it was removed after the review. This is store-level reproduction, not a new browser probe.

Cause: `store.ts:397` collects endpoints only from current past/future. Committing a after undo clears future, so b disappears from both histories; the acknowledged baseline silently reinstates b. Include submitted/acknowledged endpoints when capturing the pre-response effective geometry and add this different-endpoint branch regression (plus delayed-response browser coverage). Existing undo-to-empty and undo/redo tests do not cover it. The preceding resolution's claim that branch-after-undo is covered is therefore incorrect.

Independent checks: backend ruff check/format, mypy and **83 tests pass**; frontend typecheck and **32 unit tests pass**; exact default `npm run test:e2e` **20 pass**; dedicated demo **2 pass**; dedicated performance **1 pass**. Production builds run through the browser configurations (large-bundle warning remains). Demo isolation is confirmed.

Performance rerun: 100,200 points; load 1592 ms, select 349 ms, edit 555 ms, commit 391 ms, recalculation 367 ms; 102 frames p50 33.3 / p95 33.4 ms. Rounded heap 21 MB at all sampled stages including five edit/undo/redo cycles; final scene geometries 91, renderer geometries 40→29→47 and 50 after edits. Frozen timing budgets pass. This remains one fit-latency sample, not a recalculation distribution; rounded heap and endpoint resource samples do not prove absence of long-term leaks. Report attribution to `9b02519` does not identify the revised harness; this rerun is at `4611e39`. No fresh dependency install, hosted CI or visual video audit performed.

## Resolution of the re-review finding (post `4611e39`)

The different-endpoint branch-after-undo reproduction is confirmed and fixed. `recordSaved` builds its pre-ack effective snapshot from `past`, `future` **and the acknowledged command set** — an endpoint the user undid and then left by editing a different endpoint is absent from both histories but still present in `acked`, so its reverted value is re-expressed as an explicit unsaved edit rather than silently overwritten by the baseline. The review's own store reproduction (`commit b → undo → commit a → ack`) now passes with `b` at the reverted value and `a` at the new edit.

Regressions: `store.test.ts` ("undo then a different-endpoint edit during save preserves the undo" — asserts both values and history length) and a `review.spec.ts` delayed-response browser test asserting both endpoints and the unsaved indicator after release.

Re-verification: 83 pytest + ruff/format/strict mypy; `tsc -b` + 33 vitest + build; 21 browser checks on the default config; 2 demo recordings on the dedicated config. CAT-010/011 Done again; M3/M4 Complete.

## Independent confirmation at `6b5bfea`

The remaining P1 is resolved. Inspected the change to include `acked` endpoints in the pre-response geometry snapshot and the new store/browser regressions. The exact previously failing sequence (commit b → save → undo → commit a → acknowledgement) now preserves both the reverted b and edited a, with two unsaved edits. No actionable findings in this focused fix review. CAT-010/011 Done and M3/M4 Complete are supported for the documented local scope.

Independent verification: `cd apps/web && npm run typecheck && npm test` passes (33 unit tests); `npm run test:e2e` passes all 21 browser checks, including the delayed real-API save-response regression, and builds the production frontend. Initial sandboxed browser startup failed; rerunning with local-server permissions passed. The existing large-bundle build warning remains. Backend, dedicated demo and performance suites were not rerun: their code/harnesses are unchanged from the preceding review, whose results and measurement limitations still apply. No fresh install, hosted CI or visual recording audit claimed.
