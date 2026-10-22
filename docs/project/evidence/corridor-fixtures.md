# Evidence — reproducible corridor fixtures (CAT-005)

Date: 2026-10-22
Environment: Linux kernel 7.0, Python 3.14.4, numpy 2.5.4, scipy 1.18.1 (per `backend/uv.lock`)
Procedure: `cd backend && uv run pytest tests/test_datasets.py` — 14 checks, all passing; committed fixtures verified byte-identical to current generator output
Code under test: `backend/src/cateniq/datasets/` (`manifest.py`, `gen.py`, `plane.py`), `scripts/generate_corridor.py`, `fixtures/`

## Inventory

Three deterministic datasets (~284 KB total), each with `manifest.json`, observation `.npy` assets, `predictions/predicted_geometry.json` and `evaluation/reference.json`:

| Dataset | Role | Spans | Seeds distinguish it from |
| --- | --- | --- | --- |
| `fixtures/corridor-a` | demo | S1–S4 + context | — |
| `fixtures/corridor-b` | evaluation-holdout | B1–B3 + context | held-out geometry and seed |
| `fixtures/corridor-adverse` | adverse | A1–A2 + context | insufficient-evidence cases |

Each manifest records schema version, generator name/version/seed, coordinate convention (m, right-handed, +Z up), topology (poles with named attachment candidates, spans referencing them) and SHA-256 hashes for every asset.

## Case coverage and measured outcomes

Fit path: `load_manifest` → `load_observations`/`load_predictions` → `predicted_plane` → `fit_free` (frozen profile from CAT-004). Measured on the committed fixtures:

| Span | Designed case | Result |
| --- | --- | --- |
| S1 | nominal | ok, RMS 0.031 m, endpoint dev (−0.006, −0.001) m |
| S2 | planted endpoint error (predicted attach_b 10.5 m vs true 12.0 m, declared in manifest `predicted_issues`) | ok, endpoint dev (−0.004, **+1.513** m) — mismatch surfaces via `endpoint_deviations` vs the 0.50 m gate, computed from geometry, not the planted-error declaration |
| S3 | unequal support heights | ok, RMS 0.040 m, endpoint dev (−0.002, +0.012) m |
| S4 | noisy observations (σ 0.15 m) | ok, RMS 0.176 m > 0.15 m quality gate — fails validation as designed |
| B1–B3 | held-out seed/geometry | all ok, RMS ≤ 0.049 m; B3 `a` rel. err 0.054 but curve deviation 0.027 m max — geometry asserted, not raw `a` |
| A1 | occluded observations | INSUFFICIENT_EVIDENCE: gap 0.311 > 0.25 fraction |
| A2 | sparse observations | INSUFFICIENT_EVIDENCE: 14 < 30 points |

S2 correction journey: refit constrained to the `P3:high` attachment candidate returns ok with RMS 0.033 m; refit constrained to `P3:low` returns INFEASIBLE (a hits the A_MIN bound). Good spans S1/S3 are unaffected — validation does not flag every entity.

## Separation guarantees

- `load_observations` verifies only fitter-facing assets (observations, predictions, context). It never reads `evaluation/`; a corrupted/missing `reference.json` does not fail the fitter path.
- `verify_assets` covers everything including evaluation; `verify_fitter_assets` covers only the fitter set. `load_reference` is evaluation-only and marked "never call from the fitting path".
- `predicted_issues` metadata discloses the planted error's origin but is metadata-only: no loader maps it to diagnostics, and the endpoint check is a geometric computation.

## Validation and reproducibility

`tests/test_datasets.py` (14 checks): valid manifest loads; malformed/mismatched assets rejected (bad hash, missing span ref, duplicate IDs, non-finite coordinates, wrong units/schema version, missing file); regeneration of all three datasets is byte-identical across runs (same seed); fitter/evaluation separation enforced; intended outcomes per case as tabled above.

Design note mirrored from CAT-004 evidence: `a` is weakly identified in some regimes (B3: 5.4% `a` error, 2.7 cm curve error). Fixture acceptance asserts curve deviation and endpoint deviation, not raw parameter agreement.
