# 002 — One correction workflow and a small local stack

Date: 2026-10-22

Status: Accepted as the initial planning baseline; implementation gates remain open.

## Context

The reviewed concept targets Neara's digitisation workflow and complements NEMLab and Voltix. Earlier discussion expanded into feeder limits and multiple editing tools; that diluted the first complete demonstration.

## Decision

Deliver one endpoint-correction journey using synthetic evidence, supplied topology/labels and real geometric fitting/diagnostics. Use TypeScript/React/Vite with Three.js, Python/FastAPI/NumPy/SciPy, REST and SQLite in one repository. Select compatible versions during bootstrap. Use direct Three.js behind a scene adapter initially; do not introduce an additional rendering abstraction before a demonstrated need.

Begin with one conductor per span in a supported vertical-plane geometry, local coordinates and full-corridor recomputation. Demonstrate local operation, durable review, revision conflicts and recovery. Declare any injected prediction error explicitly. Numerical thresholds and interaction budgets remain gated by feasibility evidence.

Exclude DOE, power-flow/thermal simulation, trained classification, full active learning, general CAD editing, full simultaneous collaborative editing and public mutable hosting from the initial milestones.

## Alternatives

Matching Neara's full Dart/C++/Rust/Java stack adds learning scope without being necessary to demonstrate the targeted workflow. PostgreSQL, GraphQL and distributed workers are unnecessary for this bounded local deployment. A static visual mock alone cannot demonstrate revision safety or durable recovery. Multiple correction tools are deferred until the first journey works.

## Consequences and follow-up

The demo will be portable and focused but does not establish utility-scale processing, real-world extraction accuracy or production multi-user operations. Close the [numerical and interaction gates](../blockers.md) and revise this baseline if evidence requires it. No calendar estimate is committed.

## Acceptance source

Selected within the user's delegated request on 2026-10-22 to bootstrap planning from the agreed [concept](../../project-concept.md). These are initial engineering choices, not an assertion that the user separately approved every implementation detail.

## References

[Architecture](../architecture.md), [roadmap](../roadmap.md), [CAT-002](../backlog.md#cat-002).
