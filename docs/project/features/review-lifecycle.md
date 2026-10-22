# Review, processing and provenance contract

Date: 2026-10-22

Status: Initial accepted design direction, not implemented. Exact API schemas and execution limits are refined before CAT-009/CAT-010.

## Revision model

A review belongs to one immutable dataset identity and original prediction. Its monotonically increasing revision captures the current endpoint-constraint set. Keep original predictions, correction history and derived results separate. Geometry output is not itself a human instruction.

Save requests carry base revision, stable operation ID and a validated correction payload. In one transaction, validate the expected revision, append the correction record and advance the revision. Concurrent requests from the same base allow at most one successful change. Conflicting or invalid requests do not partially update state.

An identical retry of a completed operation returns its original outcome without advancing the revision again, even if later changes exist. Reuse of that operation ID with different content is an error. Do not automatically replay a stale edit against a new base revision. Document the supported operation-record lifetime with the store schema.

Saved corrections survive process restarts and algorithm reruns. Local undo/redo is a client concern until saved; server history is append-only for review changes. Restoring an earlier correction set creates a new revision. No automatic merge or reviewer identity/permission system is claimed.

## Processing attempts

Each attempt records dataset hash, review revision, algorithm version/parameters and immutable effective constraints. Logical stages are input validation, fit and output validation. States are queued, running, succeeded, failed and interrupted; a succeeded computation may still contain unresolved quality issues.

Keep admission, queue size, input sizes and execution duration bounded. The specific limits and timeout mechanism are a CAT-009 acceptance deliverable. Repeated requests with the same run operation ID must not create duplicate work. The API remains responsive while fitting runs.

On application restart, queued/running attempts from the prior process become interrupted. Retry creates a new linked attempt from a declared revision; it can recompute the whole corridor. This is recovery from durable inputs, not checkpoint resume of solver memory. Show a failed stage and a concrete recovery action.

Run output remains tied to its input revision. A run finishing after a later edit may be retained as history but cannot become current validation. Publish a result only after its complete result metadata is committed; failed publication must not report success to the client.

## Validation and acceptance

Distinguish three facts: an edit was saved, the current revision passed configured geometric checks, and a reviewer accepted that exact result. Acceptance requires a successful validation run for the same current dataset/review revision with no blocking issues. A concurrent edit causes acceptance conflict. Any later correction leaves the new revision unaccepted.

A human correction is not automatically ground truth. Exports retain validation/acceptance status and any limitations. No model is described as physically safe because this workflow accepted it.

## Export contract

Export includes schema version, dataset manifest/hash and coordinate convention, original prediction identity, algorithm version and parameters, stable entity/point references as relevant, before/after endpoint constraints, correction and base revision, run identity and metrics, timestamps and review acceptance status. Do not invent reviewer identity in a local demo.

A historical export is a consistent snapshot of its chosen revision. Importing/reading the export in a verifier must resolve every referenced entity and reconstruct the effective correction set against the matching source dataset. A mismatched dataset or unsupported schema is rejected. The export is training/evaluation provenance capture; it does not demonstrate model training or active selection of samples.

## Acceptance and failure cases

- Two independent clients saving the same base revision cannot silently overwrite each other.
- Lost-response retry is idempotent; conflicting operation-ID reuse is rejected.
- Restart after a committed save preserves the revision and corrections; interrupted runs remain visible and retryable.
- A correction remains effective after rerun, or the run explicitly reports that it cannot satisfy it.
- Late results and acceptance races cannot validate or accept the wrong revision.
- Database busy/write failure and invalid schema produce explicit errors, no false saved state and no silent reset.
- Export reconstruction matches the saved correction and validation identities.

Tasks: [CAT-009](../backlog.md#cat-009), [CAT-010](../backlog.md#cat-010), [CAT-011](../backlog.md#cat-011).
