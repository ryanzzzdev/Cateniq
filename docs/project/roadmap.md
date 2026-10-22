# Cateniq roadmap

Updated: 2026-10-22

Build a reproducible spatial review workflow, not a full digital-twin platform. Scope: [decision 002](decisions/002-scope-and-stack.md). Task status belongs in the [backlog](backlog.md). No calendar delivery dates are committed; reassess effort at the M1 exit.

| Milestone | Outcome | Status | Depends on |
| --- | --- | --- | --- |
| Documentation setup | Portable Voltix-style project-management workflow | Complete | None |
| Planning baseline | Architecture, feature contracts, initial sequence and acceptance gates | Complete | Documentation setup |
| M1 — Evidence and interaction | Reproducible corridor and usable endpoint correction prototype | Complete | Planning baseline |
| M2 — Computed correction | Real fitting, diagnostics and reversible correction journey | Planned | M1 |
| M3 — Durable review | Versioned save, recovery, conflict handling and provenance | Planned | M2 |
| M4 — Verified portfolio demo | Reproducible delivery, performance/failure evidence and presentation | Planned | M3 |

Setup and planning completion refer to documents: [CAT-001](backlog.md#cat-001), [CAT-002](backlog.md#cat-002). M1 delivered a verified workspace, the frozen numerical profile, reproducible fixtures and a measured endpoint-editing prototype — M2 adds the production fitter and computed correction journey.

## M1 — Evidence and interaction

Outcome: inspect a reproducible synthetic corridor and correct one endpoint in a browser prototype, with a defensible numerical profile ready for implementation.

Scope: pinned minimal development workspace, coordinate/dataset profile, independent reference cases, seeded fixtures, viewport and constrained/numeric editing prototype. Tasks: [CAT-003](backlog.md#cat-003)–[CAT-006](backlog.md#cat-006).

Dependencies: planning baseline; CAT-003 and CAT-004 can proceed independently. CAT-005 requires the profile and workspace; CAT-006 uses its fixtures.

Exit criteria:

- Verified setup starts a browser shell and API and runs minimal checks from locked dependencies.
- Coordinate conventions, supported geometry, residual definitions, solver limits and tolerances are frozen with independent reference evidence.
- Fixture generation is reproducible, with observations and evaluation truth separated and intentional corruption disclosed.
- Endpoint selection/editing is usable in normal and ambiguous views; prototype evidence records actual coordinates and performance.
- Reference environment, workload and performance budgets are documented for later acceptance.

Excluded: durable review, trained classification, real-data ingestion, production deployment. Open gates: [BLK-001](blockers.md#blk-001), [BLK-002](blockers.md#blk-002).

## M2 — Computed correction

Outcome: a computed diagnostic leads to an edit, a genuine refit and before/after validation.

Scope: geometry module, diagnostics, undo/redo and read-only provenance of calculations. Tasks: [CAT-007](backlog.md#cat-007), [CAT-008](backlog.md#cat-008).

Dependencies: M1.

Exit criteria:

- Geometry passes independent and adverse-case fixtures under frozen tolerances.
- Diagnostics are derived from evidence rather than planted issue IDs; good spans and unresolved cases behave correctly.
- The user inspects, edits, cancels, undoes/redoes and revalidates one endpoint through the real API.
- Human constraints are respected or explicitly reported infeasible; late responses cannot replace newer local results.

Excluded: persistence guarantees and reviewer acceptance; the UI must identify transient state until M3. Full-corridor recomputation is sufficient.

## M3 — Durable review

Outcome: saved corrections survive restart and rerun, conflicts are visible and exports reconstruct the reviewed revision.

Scope: SQLite revisions and operation IDs, bounded processing attempts, interrupted-run recovery, client save/reload/conflict flow, validation/acceptance and export. Tasks: [CAT-009](backlog.md#cat-009)–[CAT-011](backlog.md#cat-011).

Dependencies: M2. Persistence/API contracts may be refined earlier, but durable end-to-end acceptance requires the computed workflow.

Exit criteria:

- Conditional writes and lost-response retries preserve revision history without duplicate changes.
- Two browser sessions cannot silently overwrite each other; losing drafts remain inspectable.
- Process restart preserves committed corrections and marks abandoned runs interrupted; retry uses declared inputs and preserves constraints.
- Only matching current validation permits acceptance; edits and late results cannot bypass that rule.
- Export reconstruction and store/solver failure scenarios pass against real processes.

Excluded: user accounts/roles, arbitrary uploads, public service and real-time merging. A local two-session demonstration is not a production collaboration claim.

## M4 — Verified portfolio demo

Outcome: another developer can run and understand a measured, complete correction workflow.

Scope: performance/resource evidence, reproducible local packaging and cleanup, useful CI, concise demo recording, limitations and milestone exit review. Tasks: [CAT-012](backlog.md#cat-012), [CAT-013](backlog.md#cat-013); refine these at M3 exit.

Dependencies: M3.

Exit criteria:

- The [verification matrix](features/verification.md) maps required scenarios to passing evidence or an explicitly accepted scope revision; required checks are not silently skipped.
- Performance meets the budgets frozen after the M1 prototype on the declared environment; repeated loads/edits have measured resource behaviour.
- Clean setup, correction/save/reopen/export and failure recovery are reproduced against the real application.
- README and operating/demo instructions contain tested commands, state/reset boundaries and honest limitations.
- A short recording and written explanation connect demonstrated engineering to Neara and the wider energy portfolio without claiming complete role coverage.

Hosted CI status must be reported separately from local results; no claim of a green hosted run without observing one. Public deployment, real LiDAR validation and additional tools remain future candidates, not hidden exit requirements.
