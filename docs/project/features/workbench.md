# Spatial review workbench contract

Date: 2026-10-22

Status: Endpoint interaction prototyped and budgets frozen (CAT-006, [evidence](../evidence/endpoint-interaction.md)); persistence and rerun plumbing remain M2+.

## Main journey

The screen presents a diagnostic queue, a 3D evidence viewport and selected-span properties/validation results. Selecting an issue focuses the relevant geometry without hiding which dataset and revision are open. Users can toggle observations and model geometry and inspect a textual measurement alongside the visual cue; colour alone must not convey status.

The first editor changes one conductor endpoint. Frozen design (CAT-006): per-endpoint handles appear only on the selected span; the drag is constrained to the declared vertical plane through the span's attachments and snaps to the support pole's named attachment candidates within 0.6 m. Numeric x/y/z editing is the precise alternative (field focus begins a draft). A ghost handle, displacement line, candidate snap ring and live displacement readout preview the edit before commit. Picking and snapping are derived from visible source geometry only — invisible handles are unpickable, no-hit clicks move nothing, and pole/context objects act as occluders: the nearest visible hit wins, so an occluded handle cannot be dragged through a pole.

A drag produces one logical undoable command rather than a command per pointer event. Cancel restores the previous local state. Undo/redo covers local endpoint edits; a new edit clears redo. Camera movement is not a model correction. Immutable source points are not modified.

## State and asynchronous behaviour

Distinguish selected object, local draft, saved review revision, pending run, validated result and reviewer acceptance. Show unsaved changes and warn before discarding them through navigation or dataset replacement. A save failure preserves the draft. An unsaved draft is not promised durable across browser crashes.

Slow or out-of-order responses cannot overwrite newer drafts or make old validation appear current. Late results retain their revision identity and are labelled stale where appropriate. Error messages explain whether the user should correct input, retry or reload a conflicting server revision.

After a conflict, preserve the local draft and offer inspection/reload or deliberate reapplication against the latest revision. Do not silently merge overlapping edits. Undoing a saved edit produces a new draft and, when saved, a new revision; it does not roll back the server history.

## Usability and performance

Provide visible tool state, keyboard undo/redo, keyboard-accessible issue selection and numerical editing, focus indication, readable error messages and recoverable loading states. The target is a desktop engineering workbench; phone editing and full accessibility certification are not initial claims.

Measure loading, frame times, selection, editing and memory at stated point counts and hardware/browser settings. Frozen reference environment (CAT-006): Linux kernel 7.0, Intel Core Ultra 5 225H, 30 GB RAM, headless Chromium via Playwright 1.64.1, Vite preview + uvicorn. Workload: `corridor-perf`, 100,200 rendered points, generated on demand. Budgets (measured → frozen): load→ready ≤5 s, select ≤1 s, edit feedback ≤1 s, commit ≤1 s, frame p95 ≤50 ms. The count is a test workload, not proof of large-scale capability. Test switching datasets and repeated edits for stale objects/resource growth.

## Acceptance

- A new user can inspect, select, correct, undo, redo and cancel one endpoint without editing code.
- Correct endpoint selection and coordinate changes are asserted independently of screenshot appearance.
- Ambiguous/no-hit selection does not move an arbitrary object.
- Failed saves and stale responses preserve user intent and show the right result revision.
- Interaction evidence includes performance measurements and explicit limitations.

Tasks: [CAT-006](../backlog.md#cat-006), [CAT-008](../backlog.md#cat-008), [CAT-010](../backlog.md#cat-010).
