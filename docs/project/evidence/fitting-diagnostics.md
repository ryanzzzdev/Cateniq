# CAT-007 — Production fitting and computed diagnostics evidence

Date: 2026-10-23. Environment: Linux 7.0.0-38-generic, Python 3.14.4, uv 0.11.29, Node 22.23.1 — same reference machine as prior evidence.

Scope: explicit domain outcomes, constrained-refit semantics, provenance, and the full-corridor rerun. Verification: `cd backend && uv run pytest -q` (52 checks, including 13 new in `tests/test_fitting_production.py`), `ruff check`, `ruff format --check`, strict `mypy` — all pass. Frontend consumers typecheck; journey e2e unchanged (7 pass).

## Explicit fit outcomes

`FitStatus` now covers `ok`, `insufficient_evidence`, `failed`, `infeasible`, `unsupported` (`cateniq.geometry.profile`). Demonstrated in tests:

- UNSUPPORTED: span < 10 m, span > 120 m, degenerate endpoints (`u_b ≤ u_a`), and free-fit evidence implying sag/span > 0.20 (measured sag/span 0.24 on a 50 m span).
- INFEASIBLE: constrained fits whose endpoints can only be satisfied with sag/span > 0.20 or an out-of-range `a` — constraints never relaxed.
- INSUFFICIENT_EVIDENCE: unchanged frozen gates (points/coverage/gap); adverse fixtures still unresolved after a corridor rerun.
- FAILED: solver failure or Jacobian condition > 1e10 (unchanged).

## Constrained-refit semantics

The corrected endpoints themselves define the refit plane via `span_plane` — corrected endpoints are no longer projected into the predicted plane (the review's handoff concern). Degenerate corrections (no horizontal separation) return `unsupported` with the reason. Provenance is measured, not gated:

- `constraints.attach_a/attach_b` — echoed submitted constraints.
- `constraints.off_plane_m` — perpendicular offset of each corrected endpoint from the *predicted* plane (verified ≈2.0 m for a 2 m lateral edit).
- `constraints.obs_lateral_rms_m` — observation lateral scatter about the corrected plane.
- `basis` = `corrected` and `units` = `m` on every constrained result; `basis` = `prediction` on diagnostics.

## Independent evidence

`tests/test_fitting_production.py` generates observation samples with a plain `a·(cosh(x/a)−1)` expression written inline — a different code path from `catenary_v`'s `2a·sinh²` form — so parameter recovery is independent evidence, not implementation self-consistency (the reviewer's distinction is preserved). Recovery: `a` within 2% on clean data at moderate sag; shallow-sag case (a=3500) recovers an in-range `a` with RMS < 0.15 m.

## Corridor rerun

`POST /api/datasets/{id}/refit` accepts `{"edits": {span_id: {attach_a, attach_b}}}` and recomputes every span: constrained fit where edits exist (`basis: corrected`), free fit elsewhere (`basis: prediction`). Verified: S2 corrected to P3:high → `ok` RMS < 0.15 m; unedited spans keep prediction basis; `corridor-adverse` still reports `insufficient_evidence` — reruns do not manufacture success.

## Limits

- Refit is still a preview: durable constraint storage is CAT-009 (M3).
- Off-plane corrections are supported by plane re-definition rather than rejected; provenance records the measured offset. There is no gate on how far a correction may move laterally — a large rotation changes the observation projection; `obs_lateral_rms_m` exposes it.
- Independent-evidence coverage is per-span geometry; evaluation-asset separation is exercised by `test_datasets.py` and remains untouched.
