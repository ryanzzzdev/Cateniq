# Review, processing and provenance contract

Date: 2026-10-22

Status: Frozen implementation profile (CAT-009): REST/store schemas, operation-record lifetime, migration policy and bounded limits below are the contract. Initial accepted design direction text above remains the rationale.

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

## Frozen implementation profile (CAT-009)

### REST schemas

All review routes are under `/api/datasets/{dataset_id}/review`. A review belongs to one dataset identity (manifest hash is recorded at creation; a changed manifest produces an explicit error, not a silent reset).

- `GET /review` → `{dataset_id, manifest_hash, revision, accepted: {revision, run_id, at} | null, constraints: {span_id: {attach_a, attach_b}}}` — constraints are the effective saved constraint set (corrected spans only; absent span = predicted attachments).
- `POST /review/operations` body `{operation_id, base_revision, edits: {span_id: {attach_a, attach_b}}}` → 200 `{revision, operation_id, replayed: bool}`; identical operation-ID + payload replays the stored outcome (`replayed: true`, no revision advance); same ID + different payload → 409; `base_revision` ≠ current → 409 `{detail, current_revision}`; invalid payload → 422. `edits` holds the full effective constraint set, not a delta.
- `POST /review/runs` body `{operation_id}` → `{attempt_id, state}`; a repeated operation ID returns the existing attempt (no duplicate work).
- `GET /review/runs/{attempt_id}` → `{attempt_id, operation_id, input_revision, algorithm, state, stage, retry_of, result | null, created_at, started_at, finished_at}`.
- `GET /review/runs/current` → the latest `succeeded` run whose `input_revision` equals the current revision, or `null`. Runs against older revisions are retained as history and can never satisfy this.
- `POST /review/accept` body `{revision, run_id}` → 200 `{accepted: {...}}`; 409 when the revision is not current, the run did not succeed for that revision, or any span carries issues.
- `GET /review/export` → schema-versioned snapshot (below).
- `POST /export/verify` body `{export}` → `{ok, dataset_id, revision, constraints}`; rejects wrong dataset identity, unknown span references, unsupported export schema, or a reconstructed constraint set that differs from the declared one.

### Store schema (SQLite, schema_version 1)

```sql
meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);              -- schema_version=1
reviews(dataset_id TEXT PRIMARY KEY, manifest_hash TEXT NOT NULL,
        current_revision INTEGER NOT NULL, created_at TEXT NOT NULL);
operations(review TEXT NOT NULL, seq INTEGER NOT NULL,
           operation_id TEXT NOT NULL, base_revision INTEGER NOT NULL,
           result_revision INTEGER NOT NULL, payload TEXT NOT NULL,
           created_at TEXT NOT NULL,
           PRIMARY KEY (review, seq), UNIQUE (review, operation_id));
runs(attempt_id INTEGER PRIMARY KEY, review TEXT NOT NULL,
     operation_id TEXT NOT NULL, input_revision INTEGER NOT NULL,
     algorithm TEXT NOT NULL, state TEXT NOT NULL, stage TEXT NOT NULL,
     result TEXT, retry_of INTEGER,
     created_at TEXT NOT NULL, started_at TEXT, finished_at TEXT,
     UNIQUE (review, operation_id));
acceptance(review TEXT NOT NULL, revision INTEGER NOT NULL,
           run_id INTEGER NOT NULL, accepted_at TEXT NOT NULL,
           PRIMARY KEY (review, revision));
```

Saves execute `BEGIN IMMEDIATE` — base-revision check, operation-ID check, insert, revision advance in one transaction; two same-base writers serialise and exactly one succeeds. `runs.state` ∈ `queued|running|succeeded|failed|interrupted`; `stage` ∈ `input_validation|fit|output_validation`.

### Operation-record lifetime and migration

Operation records persist for the lifetime of the store file; there is no TTL and no replay against a newer base. Deleting the store file is the only reset and is explicit. Migration policy: `meta.schema_version` must equal 1; any other value is an explicit open error — no automatic migration exists in v1.

### Bounded limits

- One run executor slot (FIFO); queue depth 8 — a ninth admitted run is rejected 503 with a retry hint.
- Run deadline 30 s, enforced cooperatively between per-span stages (a timed-out run is `failed`, never half-published). The deadline is a cooperative bound on work *between* solver calls — it does not preempt a single stuck or runaway solve within one span. Accepted scope: per-span solves are treated as bounded work in this profile; a preemptive kill of an in-progress solve is not claimed. API responsiveness while the slot is occupied is verified separately.
- Operation payload: ≤128 edited endpoints, `operation_id` 8–64 chars, coordinates finite numbers.
- Algorithm identity `vertex-catenary-1.0` + frozen profile constants recorded on every attempt.
