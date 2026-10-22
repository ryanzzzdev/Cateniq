# Spatial review workbench contract

Date: 2026-10-22

Status: Initial design; interaction feasibility and performance budgets are an M1 gate.

## Main journey

The screen presents a diagnostic queue, a 3D evidence viewport and selected-span properties/validation results. Selecting an issue focuses the relevant geometry without hiding which dataset and revision are open. Users can toggle observations and model geometry and inspect a textual measurement alongside the visual cue; colour alone must not convey status.

The first editor changes one conductor endpoint. Use a visible handle constrained to an explicit plane or support target, with numerical coordinate editing as a precise alternative. Display the candidate target and displacement before committing the edit. Picking and snapping must be derived from visible/source geometry, never hidden synthetic ground truth. CAT-006 will choose and document the exact interaction after trying ambiguous and occluded views.

A drag produces one logical undoable command rather than a command per pointer event. Cancel restores the previous local state. Undo/redo covers local endpoint edits; a new edit clears redo. Camera movement is not a model correction. Immutable source points are not modified.

## State and asynchronous behaviour

Distinguish selected object, local draft, saved review revision, pending run, validated result and reviewer acceptance. Show unsaved changes and warn before discarding them through navigation or dataset replacement. A save failure preserves the draft. An unsaved draft is not promised durable across browser crashes.

Slow or out-of-order responses cannot overwrite newer drafts or make old validation appear current. Late results retain their revision identity and are labelled stale where appropriate. Error messages explain whether the user should correct input, retry or reload a conflicting server revision.

After a conflict, preserve the local draft and offer inspection/reload or deliberate reapplication against the latest revision. Do not silently merge overlapping edits. Undoing a saved edit produces a new draft and, when saved, a new revision; it does not roll back the server history.

## Usability and performance

Provide visible tool state, keyboard undo/redo, keyboard-accessible issue selection and numerical editing, focus indication, readable error messages and recoverable loading states. The target is a desktop engineering workbench; phone editing and full accessibility certification are not initial claims.

Measure loading, frame times, selection, editing and memory at stated point counts and hardware/browser settings. Start with a small corridor and a roughly 100,000-point representative workload, then determine budgets in CAT-006 before broader optimisation. The count is a test workload, not proof of large-scale capability. Test switching datasets and repeated edits for stale objects/resource growth.

## Acceptance

- A new user can inspect, select, correct, undo, redo and cancel one endpoint without editing code.
- Correct endpoint selection and coordinate changes are asserted independently of screenshot appearance.
- Ambiguous/no-hit selection does not move an arbitrary object.
- Failed saves and stale responses preserve user intent and show the right result revision.
- Interaction evidence includes performance measurements and explicit limitations.

Tasks: [CAT-006](../backlog.md#cat-006), [CAT-008](../backlog.md#cat-008), [CAT-010](../backlog.md#cat-010).
