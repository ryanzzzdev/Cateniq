# Cateniq

A spatial QA workbench for reviewing, correcting and validating automatically extracted electricity-network models.

The first demonstration will follow one incorrectly fitted conductor endpoint from computed diagnostic to spatial inspection, reversible correction, revalidation and a saved provenance record. Synthetic observations and injected errors will be labelled. The product does not certify physical safety or calculate network operating limits.

Cateniq complements NEMLab's market analysis and Voltix's simulated edge control with spatial computation and expert-facing interactive software. See the [project concept](docs/project-concept.md) for motivation, the Neara role connection and portfolio positioning.

## Development

This repository currently contains the concept and planning baseline. There is no runnable application, installed toolchain, application test result or verified deployment yet. Setup commands will be added when [CAT-003](docs/project/backlog.md#cat-003) verifies them; do not copy sibling-project commands as Cateniq setup.

Planned stack: TypeScript, React, Vite and Three.js in the browser; Python, FastAPI, NumPy/SciPy and SQLite behind a REST API. Exact compatible versions will be selected and locked during development bootstrap.

## Project records

- [Agent workflow](AGENTS.md) and [documentation guide](docs/project/documentation-guide.md)
- [Roadmap](docs/project/roadmap.md) and [backlog](docs/project/backlog.md)
- [Architecture](docs/project/architecture.md) and [open questions](docs/project/blockers.md)
- Feature contracts: [datasets and geometry](docs/project/features/datasets-and-geometry.md), [workbench](docs/project/features/workbench.md), [review lifecycle](docs/project/features/review-lifecycle.md), [verification](docs/project/features/verification.md)
- Decisions: [tracking](docs/project/decisions/001-markdown-project-tracking.md), [scope and stack](docs/project/decisions/002-scope-and-stack.md), [correction lifecycle](docs/project/decisions/003-correction-lifecycle.md)
- [Work journal](docs/project/journal/2026-10.md)

The project-management skill travels with the repository at [.devin/skills/project-management/SKILL.md](.devin/skills/project-management/SKILL.md). Cateniq owns its records independently of Voltix and NEMLab. Background conversations remain preserved under `docs/initial-discussion/`.
