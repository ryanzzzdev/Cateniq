# Cateniq

A spatial QA workbench for reviewing, correcting and validating automatically extracted electricity-network models.

The first demonstration will follow one incorrectly fitted conductor endpoint from computed diagnostic to spatial inspection, reversible correction, revalidation and a saved provenance record. Synthetic observations and injected errors will be labelled. The product does not certify physical safety or calculate network operating limits.

Cateniq complements NEMLab's market analysis and Voltix's simulated edge control with spatial computation and expert-facing interactive software. See the [project concept](docs/project-concept.md) for motivation, the Neara role connection and portfolio positioning.

## Development

Toolchain: uv (Python ≥3.12; locked environment uses 3.14) and Node 22/npm. The API package lives in `backend/`, the browser app in `apps/web/`. Exact dependency versions are locked in `backend/uv.lock` and `apps/web/package-lock.json`.

```bash
# Backend: install locked deps, then lint/format/typecheck/test
cd backend
uv sync --locked
uv run ruff check . && uv run ruff format --check .
uv run mypy
uv run pytest -q

# Frontend: install locked deps, then typecheck/unit-test/build
cd apps/web
npm ci
npm run typecheck && npm run test && npm run build

# Run locally (two terminals); the Vite dev and preview servers proxy /api to :8000
cd backend && uv run uvicorn cateniq.app:app --reload --port 8000
cd apps/web && npm run dev

# Browser smoke: builds the app, serves it, starts the real API, loads the shell in chromium
cd apps/web && npx playwright install chromium   # once per machine
npm run test:e2e
```

Verified on Linux (kernel 7.0), Python 3.14.4, uv 0.11.29, Node 22.23.1, npm 10.9.8, Chromium headless shell 156 via Playwright 1.64.1. A GitHub Actions workflow (`.github/workflows/ci.yml`) runs the same checks; a hosted green run has not been observed yet.

## Project records

- [Agent workflow](AGENTS.md) and [documentation guide](docs/project/documentation-guide.md)
- [Roadmap](docs/project/roadmap.md) and [backlog](docs/project/backlog.md)
- [Architecture](docs/project/architecture.md) and [open questions](docs/project/blockers.md)
- Feature contracts: [datasets and geometry](docs/project/features/datasets-and-geometry.md), [workbench](docs/project/features/workbench.md), [review lifecycle](docs/project/features/review-lifecycle.md), [verification](docs/project/features/verification.md)
- Decisions: [tracking](docs/project/decisions/001-markdown-project-tracking.md), [scope and stack](docs/project/decisions/002-scope-and-stack.md), [correction lifecycle](docs/project/decisions/003-correction-lifecycle.md)
- [Work journal](docs/project/journal/2026-10.md)

The project-management skill travels with the repository at [.devin/skills/project-management/SKILL.md](.devin/skills/project-management/SKILL.md). Cateniq owns its records independently of Voltix and NEMLab. Background conversations remain preserved under `docs/initial-discussion/`.
