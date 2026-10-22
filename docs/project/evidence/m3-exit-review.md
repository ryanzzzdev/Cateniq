# Independent M3 exit review

Reviewed baseline: `296647d`, including M2 fixes `620604f` and M3 commits `493908b`, `d01211c`, `e65ba0a`. Review date: 2026-10-23 Australia/Sydney (system UTC 2026-10-22). Repository code was clean at verification; temporary probes removed after use.

## Verdict

The three prior M2 findings are fixed and regression-tested; M2 remains Complete. M3 requires corrections in CAT-009/010 and additional CAT-011 verification before its exit can be accepted. No production implementation was changed during review.

## Reproduced findings

### P1 — A late save discards newer local edits (CAT-010)

`apps/web/src/App.tsx` save() fetches the latest review and unconditionally calls recordSaved(); `apps/web/src/store.ts` recordSaved() clears the entire past/future history. Editing remains enabled during the request. A real-API browser probe saved S2 b.z=12 with the response delayed, committed a newer b.z=13 edit, then released the response: the displayed endpoint reverted to 12 and the unsaved indicator disappeared. The newer edit was neither saved nor preserved. Save responses also lack dataset/load-epoch correlation, unlike openDataset().

Capture the submitted snapshot and dataset/load generation. Clear only the acknowledged edits and preserve later edits; discard or separately retain responses belonging to another open dataset. Add delayed-save/edit and dataset-switch regressions.

### P2 — Failed saves leave retry permanently disabled (CAT-010)

`apps/web/src/App.tsx:246` calls fitFailed() on non-conflict save errors, which clears fitPending rather than savePending. A browser probe aborted the operations request: an error appeared, the local edit remained, but Save stayed disabled. No transition clears the flag until reload, which loses unsaved work. Clear savePending on every terminal save outcome, preserve the draft, and retain/reuse the operation ID and submitted payload for uncertain-response retries instead of generating a new UUID on each attempt.

### P1 — Unsaved edits do not invalidate the acceptance UI (CAT-010)

`apps/web/src/panels.tsx` canAccept checks the saved revision/run but not local past/draft state; store mutations leave accepted untouched. A real-API browser probe validated clean corridor-b revision 0, changed B1 b.z to 30 and committed locally, then clicked the still-enabled Accept button. The accepted badge appeared beside the unsaved changed geometry. The server correctly accepted saved revision 0, not the changed geometry: the defect is the UI allowing and presenting acceptance without distinguishing the displayed draft. Disable acceptance for dirty state and clearly invalidate or scope prior acceptance when effective geometry changes; cover draft, commit, undo/redo and late acceptance responses.

### P1 — Exports are not coherent snapshots under concurrent saves (CAT-009/011)

`backend/src/cateniq/service.py:485–507` reads review state, operation history and current validation separately. ReviewStore.review() itself reads constraints after releasing its lock. A deterministic interleaving probe inserted a real SQLite save between review_state() and history(): export declared revision 0 but included an operation ending at revision 1; its own verifier rejected it with “operation chain does not reach declared revision”. This simulates a save at an allowed interleaving; it is not a stress-test claim.

Read revision, constraints, history, validation and acceptance under one coherent transaction/snapshot. Apply this to review-state responses as well as exports; test a concurrent saver with a barrier at the read boundary.

## M3 verification gate still incomplete

The lifecycle evidence candidly uses a second store/service instance to simulate restart, and closes a connection to inject a write fault. These do not meet the roadmap's real-process recovery exit without an explicit scope change. The timeout test sets the deadline to zero; it does not exercise a slow or stuck numerical call. The worker checks the deadline only between spans/after fitting, so the documented 30-second cooperative check is not a hard execution bound. Add real process interruption/restart/retry and slow-solver responsiveness/deadline evidence, or record an accepted scope change before claiming the corresponding exit. This review did not run a process-kill test.

## Reproduced checks and limits

Existing installed environment: Python 3.14.4/uv 0.11.29, Node 22.23.1, Linux 7.0.0-38-generic, Playwright Chromium; tests use disposable SQLite files and the dedicated .e2e-reviews.db.

- Backend: ruff lint/format, strict mypy and 80 pytest tests pass.
- Frontend: typecheck, 27 unit tests, production build and 17 browser checks pass (large JS chunk warning remains).
- Three temporary browser probes pass assertions demonstrating the delayed-save loss, disabled retry and dirty-state acceptance defects. They use real API responses except the deliberate aborted save request.
- Temporary-directory service/SQLite interleaving probe reproduces an internally inconsistent export.
- Prior M2 regressions now cover corrected RMS/p95 issues, lateral rejection, cancelled-draft late responses and visible-result staleness/recovery; all pass.
- No fresh dependency installation, hosted CI, perf rerun or actual process-kill recovery was observed in this review.

Next: correct the four defects and close the real-process/deadline evidence gap; rerun focused regressions and M3 exit verification before opening M4.

## Resolution — findings addressed (2026-10-25)

All four findings confirmed by reproduction, fixed, and covered by regressions. The review text above is preserved verbatim.

### P1 — Late save discards newer edits → fixed

`store.recordSaved` now takes the submitted `EditCommand[]` prefix and drops exactly those acknowledged commands; edits committed mid-flight survive as unsaved local edits. `save()` correlates the response to the captured `loadEpoch` + `datasetId` — a response superseded by a dataset switch or newer load is discarded. Regressions: store prefix/diverged-history tests; `e2e/review.spec.ts` delayed-save test commits a newer edit while the operations response is held and asserts it survives unsaved.

### P2 — Failed saves leave retry permanently disabled → fixed

Non-conflict save errors now call `store.saveFailed()` (clears `savePending` — was `fitFailed`, which cleared the wrong flag). `pendingSave` retains the submitted operation; a retry replays the same `operation_id` for an identical payload (server dedupes — the uncertain-response case lands once) and issues a fresh ID for a changed payload. Regression: `review.spec.ts` aborts the first save, asserts Save re-enables with the edit preserved, and the retry succeeds.

### P1 — Unsaved edits do not invalidate the acceptance UI → fixed

`canAccept` additionally requires a clean workbench (`!draft && !past.length`); the accepted badge carries an explicit `unsaved edits differ` qualifier while local edits exist, reverting on undo. Regression: the `review.spec.ts` accept test edits after acceptance, asserts the qualifier + disabled button, undoes and asserts clean again.

### P1 — Exports are not coherent snapshots → fixed

`ReviewStore.snapshot()` reads revision, constraints, operation history, acceptance and current validation under a single lock; `review()` and `export_review()` both go through it. Regression: `test_export_is_coherent_under_concurrent_saves` runs a real saver thread against repeated exports — every export verifies against its declared revision.

### Verification gap → closed

- **Real process interruption**: `test_process_kill_marks_run_interrupted_and_retry_recovers` spawns a real child process that marks a run `running`, SIGKILLs it mid-run, and a fresh process marks it `interrupted`; a linked retry recomputes from the declared revision and `succeeded`s. The simulated-restart test is retained as a cheaper regression.
- **Slow-solver responsiveness**: `test_api_stays_responsive_during_a_slow_run` patches a 100 ms/span fit through the real worker thread — `review_state` answers in <0.5 s while the slot is occupied and the run still completes.
- **Deadline scope**: the contract now states explicitly that the 30 s bound is cooperative between per-span stages and does not preempt a single stuck solve — recorded as accepted scope, not a hard execution bound.

### Verification after fixes

83 pytest, ruff/format, strict mypy, `tsc -b`, production build, 30 vitest, 19 browser specs — all green.
