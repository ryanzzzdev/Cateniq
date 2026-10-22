# Cateniq backlog

Updated: 2026-10-22

Task bodies own status; index icons mirror them. Follow the [documentation guide](documentation-guide.md#task-records).

## Task index

- ✅ [CAT-001 — Establish project-management standards](#cat-001)
- ✅ [CAT-002 — Establish the implementation planning baseline](#cat-002)
- 🟢 [CAT-003 — Bootstrap the minimal development workspace](#cat-003)
- 🟢 [CAT-004 — Freeze the supported geometry and dataset profile](#cat-004)
- 📋 [CAT-005 — Build reproducible corridor fixtures](#cat-005)
- 📋 [CAT-006 — Prototype endpoint inspection and editing](#cat-006)
- 📋 [CAT-007 — Implement fitting and computed diagnostics](#cat-007)
- 📋 [CAT-008 — Complete the computed correction journey](#cat-008)
- 📋 [CAT-009 — Implement durable revisions and recoverable runs](#cat-009)
- 📋 [CAT-010 — Integrate save, acceptance, conflicts and export](#cat-010)
- 📋 [CAT-011 — Verify review races and failure recovery](#cat-011)
- 📋 [CAT-012 — Measure performance and resource behaviour](#cat-012)
- 📋 [CAT-013 — Package and review the portfolio demonstration](#cat-013)

## Delivery notes

Documentation setup and the planning baseline are complete; no application implementation has started. Next: CAT-003 (workspace) and CAT-004 (numerical profile), which can be undertaken independently. Then CAT-005 → CAT-006 closes M1. Later work remains Backlog until dependencies pass and the task is refined for execution. Keep the active set small. Next unused ID: CAT-014.

<a id="cat-001"></a>

## CAT-001 — Establish project-management standards

- Repository: cateniq
- Area: documentation
- Milestone: Documentation setup
- Priority: High
- Status: Done ✅
- Depends on: None
- References: [Specification](documentation-guide.md)

### Outcome

Adapt Voltix’s portable documentation workflow to Cateniq.

### Done when

- Root instructions, repository-carried skill and guide agree on ownership, stable IDs/statuses, journal attribution and atomic records updates.
- Existing concept/discussion files are preserved; local links and workflow references pass verification.

### Completion evidence

Created AGENTS.md, portable skill, documentation guide, README and tracking records. Documentation checks are recorded in the journal; no application checks apply. Uncommitted.

### Notes

Complete; use this workflow for subsequent meaningful work.

<a id="cat-002"></a>

## CAT-002 — Establish the implementation planning baseline

- Repository: cateniq
- Area: documentation
- Milestone: Planning baseline
- Priority: High
- Status: Done ✅
- Depends on: CAT-001
- References: [Specification](architecture.md)

### Outcome

Translate the reviewed concept into architecture, staged scope, feature contracts and an initial backlog.

### Done when

- Roadmap has dependencies, exclusions and observable exits; architecture separates design from implementation.
- Feature contracts cover geometry, editing, revision lifecycle, failures and verification; unresolved gates have owners/actions.
- Task IDs, status/index alignment, dependency order, document links and source preservation pass checks.

### Completion evidence

Created architecture, roadmap, four feature contracts, decisions 002/003, two bounded gates and CAT-003–013. Checks are recorded in the journal; no application implemented or runtime tests run. Uncommitted.

### Notes

Next action: CAT-003 and CAT-004; implementation tasks remain unstarted.

<a id="cat-003"></a>

## CAT-003 — Bootstrap the minimal development workspace

- Repository: cateniq
- Area: workspace
- Milestone: M1
- Priority: High
- Status: Ready 🟢
- Depends on: CAT-002
- References: [Specification](architecture.md)

### Outcome

Create a reproducible browser/API skeleton with a small verified toolchain.

### Done when

- Select compatible Python/Node and library versions from current official sources; commit lockfiles and document verified setup without copying sibling versions blindly.
- Create the proposed minimal app/package structure with one health endpoint, browser shell and explicit local proxy.
- Formatting, type checks, minimal API test and browser/build smoke pass; record exact commands and environment.
- Add appropriate ignore rules and a minimal CI configuration; distinguish local validation from an observed hosted run.

### Completion evidence

Not started; no implementation or verification evidence yet.

### Notes

Start here for implementation. Do not implement geometry or a full product scaffold in this task.

<a id="cat-004"></a>

## CAT-004 — Freeze the supported geometry and dataset profile

- Repository: cateniq
- Area: geometry
- Milestone: M1
- Priority: High
- Status: Ready 🟢
- Depends on: CAT-002
- References: [Specification](features/datasets-and-geometry.md)

### Outcome

Resolve the mathematical and data contracts before implementing the fitter.

### Done when

- Define schema/IDs, coordinates, supported plane/endpoint geometry, asset identity and separation of observations from reference truth.
- Define fit objective/residual, coverage and endpoint checks, solver bounds, convergence/conditioning rules and numeric tolerances.
- Use primary references and independently derived cases including unequal support heights, shallow sag and inadequate data to validate feasibility.
- Record reproducible profile evidence and resolve BLK-001, or record a reasoned scope revision before dependent implementation.

### Completion evidence

Not started; no implementation or verification evidence yet.

### Notes

Can proceed independently of CAT-003. This task owns the numerical gate; no runtime classifier is required.

<a id="cat-005"></a>

## CAT-005 — Build reproducible corridor fixtures

- Repository: cateniq
- Area: geometry
- Milestone: M1
- Priority: Normal
- Status: Backlog 📋
- Depends on: CAT-003, CAT-004
- References: [Specification](features/datasets-and-geometry.md)

### Outcome

Generate and load labelled synthetic evidence with independent evaluation references.

### Done when

- Seeded manifests/assets meet the frozen profile and include nominal, corrupted-endpoint, noisy, missing and unsupported cases.
- Observation and reference datasets are separate; planted prediction errors are declared and diagnostics cannot read their labels.
- Manifest/hash/ID/unit validation and reproducibility tests pass; held-out geometry/seed is reserved for evaluation.

### Completion evidence

Not started; no implementation or verification evidence yet.

### Notes

Promote to Ready when prerequisites pass; keep generated assets small and reproducible.

<a id="cat-006"></a>

## CAT-006 — Prototype endpoint inspection and editing

- Repository: cateniq
- Area: workbench
- Milestone: M1
- Priority: Normal
- Status: Backlog 📋
- Depends on: CAT-005
- References: [Specification](features/workbench.md)

### Outcome

Prove one endpoint interaction is usable before building a broad editor.

### Done when

- Render source observations and predicted geometry; issue/entity selection focuses the correct span.
- Implement one constrained endpoint tool plus numeric editing and cancellation; verify actual world coordinates, ambiguous hits and occlusion.
- Record measured loading, frame, selection/edit and resource observations on a named environment and representative point counts.
- Freeze interaction design and performance budgets in the contract; resolve BLK-002 and review M1 exit evidence.

### Completion evidence

Not started; no implementation or verification evidence yet.

### Notes

Prototype scope; no brush, pole editing, persistence or general CAD toolset.

<a id="cat-007"></a>

## CAT-007 — Implement fitting and computed diagnostics

- Repository: cateniq
- Area: geometry
- Milestone: M2
- Priority: Normal
- Status: Backlog 📋
- Depends on: CAT-005, CAT-006
- References: [Specification](features/datasets-and-geometry.md)

### Outcome

Produce genuine fitting and validation results from evidence and human constraints.

### Done when

- Pure geometry module implements the frozen profile and returns explicit unsupported, infeasible and failed outcomes.
- Independent reference, sparse/noisy, shallow-sag and held-out tests pass under documented tolerances.
- Quality diagnostics are computed with units/thresholds and provenance; original and corrected results remain distinguishable.
- Full-corridor reruns preserve explicit constraints and never read evaluation truth.

### Completion evidence

Not started; no implementation or verification evidence yet.

### Notes

Use the full rebuild as the baseline; incremental updates are excluded.

<a id="cat-008"></a>

## CAT-008 — Complete the computed correction journey

- Repository: cateniq
- Area: workbench
- Milestone: M2
- Priority: Normal
- Status: Backlog 📋
- Depends on: CAT-006, CAT-007
- References: [Specification](features/workbench.md)

### Outcome

Connect diagnostics, reversible editing and refitting through the real API.

### Done when

- User inspects an issue, corrects/cancels an endpoint and uses undo/redo with one command per gesture.
- Before/after validation is associated with the right inputs; stale responses cannot replace newer draft results.
- Browser tests assert geometry and error/loading behaviour against the real computation path.
- Transient unsaved state is labelled honestly; M2 exit is reviewed against evidence.

### Completion evidence

Not started; no implementation or verification evidence yet.

### Notes

Durable save/acceptance belongs to M3, not a misleading mock save button.

<a id="cat-009"></a>

## CAT-009 — Implement durable revisions and recoverable runs

- Repository: cateniq
- Area: review
- Milestone: M3
- Priority: Normal
- Status: Backlog 📋
- Depends on: CAT-008
- References: [Specification](features/review-lifecycle.md)

### Outcome

Persist correction history and bounded processing attempts without losing user constraints.

### Done when

- Refine and freeze REST/store schemas, operation-record lifetime, migration policy and bounded queue/input/run limits before implementation.
- Atomic base-revision checks and operation-ID idempotency pass concurrent/lost-response tests on real SQLite.
- One bounded execution slot keeps the API responsive; timeout/restart marks attempts failed/interrupted and retry preserves declared inputs.
- Committed corrections survive restart; late output cannot become current; schema mismatch/write failure never silently resets data.

### Completion evidence

Not started; no implementation or verification evidence yet.

### Notes

Refine exact execution mechanism here; no distributed task broker or production identity system.

<a id="cat-010"></a>

## CAT-010 — Integrate save, acceptance, conflicts and export

- Repository: cateniq
- Area: review
- Milestone: M3
- Priority: Normal
- Status: Backlog 📋
- Depends on: CAT-009
- References: [Specification](features/review-lifecycle.md)

### Outcome

Make durable review understandable and complete in the workbench.

### Done when

- Save/reopen and two-session conflict flows preserve drafts and show authoritative revision identity.
- Only matching current validation can be accepted; editing invalidates acceptance and saved undo creates a new revision.
- Schema-versioned export reconstructs effective corrections against the matching source; mismatches are rejected.
- Real browser/API/store journey verifies save, reopen, rerun, acceptance and export with clear failure states.

### Completion evidence

Not started; no implementation or verification evidence yet.

### Notes

No automatic merge and no claims that corrections are unquestioned ground truth.

<a id="cat-011"></a>

## CAT-011 — Verify review races and failure recovery

- Repository: cateniq
- Area: verification
- Milestone: M3
- Priority: Normal
- Status: Backlog 📋
- Depends on: CAT-010
- References: [Specification](features/verification.md)

### Outcome

Produce reproducible evidence for lifecycle correctness under faults.

### Done when

- Exercise concurrent saves, duplicate/conflicting operation IDs, late results and acceptance races in real integration tests.
- Exercise process interruption, retry, solver failure/timeout and store write failure with bounded waits and isolated state.
- Assert correction preservation, no false success and export consistency; record fault mechanisms and limitations.
- M3 exit maps each lifecycle requirement to passing evidence; required gaps remain open tasks.

### Completion evidence

Not started; no implementation or verification evidence yet.

### Notes

Refine fault harness when implementation exists; process crash does not prove power-cut durability.

<a id="cat-012"></a>

## CAT-012 — Measure performance and resource behaviour

- Repository: cateniq
- Area: verification
- Milestone: M4
- Priority: Normal
- Status: Backlog 📋
- Depends on: CAT-011
- References: [Specification](features/verification.md)

### Outcome

Validate the workbench against the budgets established at M1.

### Done when

- Reproduce named workloads and record load, frame, selection/edit, memory and recalculation distributions.
- Test repeated dataset replacement and editing; inspect resource disposal and responsiveness during fitting.
- Meet frozen budgets or explicitly revise scope with evidence; reverify correctness after any optimisation.

### Completion evidence

Not started; no implementation or verification evidence yet.

### Notes

Refine at M3 exit. Do not optimise solely for one scripted camera view.

<a id="cat-013"></a>

## CAT-013 — Package and review the portfolio demonstration

- Repository: cateniq
- Area: deployment
- Milestone: M4
- Priority: Normal
- Status: Backlog 📋
- Depends on: CAT-012
- References: [Specification](features/verification.md)

### Outcome

Deliver reproducible local operation, a concise demo and final evidence review.

### Done when

- Clean-environment setup and safe state/reset/cleanup instructions are verified; README uses actual commands.
- Record the correction and recovery stories; document unsupported cases and measured limits.
- Final evidence index covers the acceptance matrix and milestones; report hosted CI separately and honestly.
- Explain Neara alignment and complementarity with NEMLab/Voltix without overstating domain or production coverage.

### Completion evidence

Not started; no implementation or verification evidence yet.

### Notes

Refine at M3 exit and split only when useful. Public hosting and publication are not implicitly authorised.
