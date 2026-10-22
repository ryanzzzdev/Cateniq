# 003 — Preserve corrections and bind results to revisions

Date: 2026-10-22

Status: Accepted as a design baseline; not implemented.

## Context

An algorithm rerun can otherwise overwrite human work, and asynchronous fitting can return after a newer edit. Two clients can lose changes if saving means simply replacing the current model.

## Decision

Keep source observations, original predictions, human constraints and derived results separate. Save correction revisions transactionally with expected-base checks and stable operation IDs. Rerun fitting against an immutable input snapshot and effective human constraints. Store results with their input identity; only matching current results are eligible for current validation and reviewer acceptance.

Keep historical corrections. Local undo edits the draft; undo of saved work becomes a new revision. Explicitly distinguish saved, geometrically validated and reviewer-accepted states. Conflicts preserve the proposal rather than silently merging it.

Persist processing attempts, mark abandoned attempts interrupted on restart, and retry from durable inputs. Initially recompute the whole corridor; do not promise arbitrary stage checkpoints. Use one bounded numerical execution slot and keep API/store ownership separate from worker computation.

## Alternatives

Replacing model geometry in place loses provenance. Last-write-wins loses concurrent work. A CRDT or general collaborative editor adds scope not required for stale-write protection. Treating every edit as ground truth hides uncertainty. Incremental processing before a dependency model risks stale neighbours.

## Consequences and follow-up

The API, UI and store must carry revision identity consistently. Idempotency, publication races, restart and export reconstruction require explicit tests. Exact schema, bounds and worker timeout mechanism are refined in CAT-009. Application acceptance is not an electrical safety certification.

## Acceptance source

Selected under the user's delegated planning request on 2026-10-22, implementing the concept's preservation, provenance and revision-safety requirements.

## References

[Lifecycle contract](../features/review-lifecycle.md), [CAT-009](../backlog.md#cat-009), [CAT-011](../backlog.md#cat-011).
