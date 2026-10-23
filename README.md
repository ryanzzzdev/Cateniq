# Cateniq

A spatial QA workbench for reviewing, correcting and validating automatically extracted electricity-network models.

The demonstration follows one incorrectly fitted conductor endpoint from computed diagnostic to spatial inspection, reversible correction, revalidation, durable save/reopen and an exportable provenance record — plus a clean acceptance path and a two-session save conflict. Synthetic observations and injected errors are labelled; unresolved cases stay flagged rather than forced green. The product does not certify physical safety or calculate network operating limits.

Cateniq complements NEMLab's market analysis and Voltix's simulated edge control with spatial computation and expert-facing interactive software. See the [project concept](docs/project-concept.md) for motivation, the Neara role connection and portfolio positioning, and [the demo walkthrough](docs/project/demo.md) for the recorded sequences.

## Demo

Recorded walkthroughs live in [docs/demo/](docs/demo/) with the narrative in [docs/project/demo.md](docs/project/demo.md). Reproduce them (production build, real API, isolated database, headless Chromium):

```bash
cd apps/web
npx playwright test -c playwright.demo.config.ts   # videos → test-results/demo-*/video.webm
```

## Run it

Requires uv (Python ≥3.12) and Node 22/npm. Committed fixtures are used as-is — no data setup needed.

```bash
# Terminal 1 — API on :8000
cd backend && uv sync --locked && uv run uvicorn cateniq.app:app --port 8000

# Terminal 2 — workbench on http://localhost:5173 (Vite proxies /api to :8000)
cd apps/web && npm ci && npm run dev
```

Suggested first path — the recorded demo flow ([docs/project/demo.md](docs/project/demo.md)): open **corridor-a**, select span **S2** (flagged `endpoint_mismatch`), inspect the diagnostic, edit endpoint B's z to the high attachment, commit, refit, run validation, save and reopen. corridor-b is the clean path for acceptance and a second-window save conflict; corridor-adverse demonstrates honest `insufficient_evidence` outcomes.

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

# Browser tests: builds the app, serves it, starts the real API against an isolated DB
cd apps/web && npx playwright install chromium   # once per machine
npm run test:e2e                                # verification suite (isolated .e2e-reviews.db)
npx playwright test -c playwright.perf.config.ts # named-workload performance check
```

## State, configuration and reset

- The backend persists review data in SQLite at `backend/reviews.db` (WAL sidecars `reviews.db-shm/-wal`). Override with `CATENIQ_DB_PATH`; fixture location with `CATENIQ_FIXTURES_DIR`.
- **Reset**: stop the backend, then `rm backend/reviews.db*` — a fresh schema is created on next start. Saved revisions, runs and acceptance are deleted; this is the only supported reset.
- Test/demo databases (`.e2e-reviews.db`, `.e2e-demo.db`) are recreated automatically and gitignored; `reviews.db` must never be committed.
- Corrupt or wrong-version databases fail explicitly at startup — there is no silent reset or migration.

## Limitations

- Synthetic labelled fixtures only — no real LiDAR ingestion, no electrical clearance or safety analysis.
- One executor slot with a 30 s cooperative deadline; solver concurrency and run history are bounded/append-only by contract (see [review-lifecycle](docs/project/features/review-lifecycle.md)).
- Conflicted saves are rejected, not merged. Undo/redo covers local edits only; reverting a saved revision is a new save.
- Acceptance is workflow bookkeeping for a validated revision, not a certification.

Verified on Linux (kernel 7.0), Python 3.14.4, uv 0.11.29, Node 22.23.1, npm 10.9.8, Chromium headless shell 156 via Playwright 1.64.1. A GitHub Actions workflow (`.github/workflows/ci.yml`) runs the same checks; a hosted green run has not been observed yet — CI status is reported separately from local verification.

## Project records

- [Agent workflow](AGENTS.md) and [documentation guide](docs/project/documentation-guide.md)
- [Roadmap](docs/project/roadmap.md) and [backlog](docs/project/backlog.md)
- [Architecture](docs/project/architecture.md) and [open questions](docs/project/blockers.md)
- Feature contracts: [datasets and geometry](docs/project/features/datasets-and-geometry.md), [workbench](docs/project/features/workbench.md), [review lifecycle](docs/project/features/review-lifecycle.md), [verification](docs/project/features/verification.md)
- Decisions: [tracking](docs/project/decisions/001-markdown-project-tracking.md), [scope and stack](docs/project/decisions/002-scope-and-stack.md), [correction lifecycle](docs/project/decisions/003-correction-lifecycle.md)
- [Work journal](docs/project/journal/2026-10.md)

The project-management skill travels with the repository at [.devin/skills/project-management/SKILL.md](.devin/skills/project-management/SKILL.md). Cateniq owns its records independently of Voltix and NEMLab. Background conversations remain preserved under `docs/initial-discussion/`.
