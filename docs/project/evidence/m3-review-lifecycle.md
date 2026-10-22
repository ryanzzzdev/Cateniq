# Evidence — durable review lifecycle and fault verification (CAT-009 / CAT-010 / CAT-011)

Date: 2026-10-25
Environment: Linux kernel 7.0, Intel Core Ultra 5 225H (14 threads), 30 GB RAM; Python 3.14.4/FastAPI, SQLite (WAL); Node 22, Chromium via Playwright (headless).
Procedure: `cd backend && uv run pytest` (80 checks), `cd apps/web && npx playwright test` (17 browser checks incl. `e2e/review.spec.ts`), `npx vitest run` (27). Fault tests run on real SQLite files under `tmp_path`, a real worker-thread executor (disabled only where a test drives `execute_next` deterministically), and a real FastAPI `TestClient`.

## Frozen limits (contract: `features/review-lifecycle.md`)

- Single executor slot, FIFO queue depth 8 — the ninth admitted run is refused (503 `run queue is full; retry later`).
- Run deadline 30 s, enforced cooperatively between per-span stages — a timed-out run is `failed`, never half-published.
- Operation IDs 12–64 chars; run operation IDs dedupe to the existing attempt (`replayed: true`).
- Run states `queued|running|succeeded|failed|interrupted`; stages `input_validation|fit|output_validation`; result and terminal state publish in one write.

## Fault and race evidence

| Mechanism | Test | Outcome |
| --- | --- | --- |
| Two same-base saves race on real SQLite | `test_concurrent_same_base_saves_allow_exactly_one_winner` | `BEGIN IMMEDIATE` serialises them; exactly one wins, the loser gets `ConflictError` with the current revision |
| Lost response retried with same operation ID | `test_identical_retry_replays_without_advancing` | Replay returns the original result; revision does not advance |
| Same operation ID, different content | `test_same_id_different_content_is_an_error` | `OperationConflictError` — never a silent overwrite |
| Stale base revision | `test_stale_base_is_rejected_and_state_untouched` | Rejected; state untouched |
| Two-browser-session conflict | `e2e/review.spec.ts` stale-save test | Losing session sees the authoritative revision; its local edit stays inspectable |
| Manifest hash drift | `test_manifest_hash_mismatch_is_an_explicit_error` | Store refuses to bind a review to a different dataset identity |
| Wrong store schema version | `test_wrong_schema_version_is_rejected` | `SchemaError` — no in-place reset or silent migration |
| Corrupt database file | `test_corrupt_db_fails_explicitly` | `sqlite3.DatabaseError` at open — an explicit error, not a reinitialised store |
| Broken write path mid-session | `test_write_failure_surfaces_and_prior_state_survives` | Write raises explicitly; reopening shows the committed revision intact |
| Ninth active run admitted | `test_queue_bound_rejects_ninth_active_run`, `test_queue_overflow_is_rejected_503` | Store raises `StoreError`; API returns 503 |
| Run exceeds deadline | `test_deadline_failure_never_reports_success` | `failed` at the cooperative check; never reports success |
| Solver throws mid-run | `test_solver_failure_marks_run_failed_with_stage` | `failed` with `stage=fit` and the error recorded; `runs/current` stays empty — a failed attempt never validates |
| Process restart with queued/running work | `test_restart_marks_active_attempts_interrupted` | Prior-process attempts become `interrupted` on store open |
| Interrupted attempt retried | `test_interrupted_run_retries_as_linked_attempt` | New linked attempt (`retry_of`) at the declared revision; recomputes from durable inputs |
| Run output landing after a newer save | `test_late_result_cannot_become_current_validation`, `test_late_run_output_cannot_validate_the_wrong_revision` | The attempt runs against `constraints_at(input_revision)` and its result can never become current validation for a newer revision |
| Acceptance without a matching clean run | `test_acceptance_requires_matching_clean_run`, `test_issues_block_acceptance` | Rejected — acceptance needs the current revision plus a succeeded run for that exact revision with zero issues |
| Acceptance racing a later save | `test_acceptance_round_trip_and_race` | Accepting the stale revision/run is a 409; the new revision is unaccepted |
| Dataset-load response race | `loadEpoch` in `apps/web/src/App.tsx`; `review.spec.ts` reload flow | A superseded `openDataset` response is discarded — `datasetId` and loaded data can no longer mismatch |
| Export replayed against the verifier | `test_export_reconstructs_and_rejects_mismatch`, `review.spec.ts` export test | Operation chain reconstructs the declared constraints; tampered constraints, broken chains, unknown spans and foreign dataset identities are rejected 422 |

## Honest limitations

- **Process-restart simulation** uses a second `ReviewStore`/`CorridorService` over the same file — it exercises durable-state recovery, not an OS-level kill mid-write. SQLite's own atomicity covers torn writes; no power-cut durability is claimed.
- **Write-failure injection** closes the connection in-session (deterministic). An earlier read-only-file variant was dropped as flaky: the failed constructor leaked a connection and WAL sidecars made the outcome filesystem-dependent. The injected fault still proves the contract: failures surface as errors and committed state survives.
- **Queue-depth bound** counts active (queued/running) attempts; terminal attempts are free. The bound protects the executor slot, not total attempt volume — a caller can still accumulate finished run history unboundedly (intended: history is the audit trail).
- **Local undo/redo** remains a client concern until saved; restoring an earlier correction set is a normal save producing a new revision — there is no dedicated "undo saved revision" UI.
- **No merge**: a conflicted save is rejected, not merged — by contract.
- Acceptance is workflow bookkeeping, not an electrical-safety certification.
