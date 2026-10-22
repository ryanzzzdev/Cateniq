# Dataset and geometry contract

Date: 2026-10-22

Status: Numerical profile frozen (CAT-004, [evidence](../evidence/geometry-profile.md)); production fitter not yet implemented.

## Inputs and output boundary

The first corridor uses local Cartesian metres, Z up, stable pole/span/point IDs, supplied support topology and labelled synthetic observations. One conductor per span lies in a declared vertical plane. Support extraction, ML classification, CRS conversion, branching circuits and multi-conductor identification are excluded.

A manifest identifies schema version, generator version/seed, coordinate convention, point count, asset hashes, topology and parameters. Hash identity takes precedence over a friendly dataset name. Reject non-finite coordinates, duplicate point IDs, missing support references, mismatched counts/hashes and unsupported schema versions before fitting.

Separate observation assets, any intentionally corrupted prediction, and reference geometry. The fitter and diagnostic engine must not read the reference answer or the list of planted issues. Fixture labels are supplied inputs, not inferred classifications. Reference assets are available only to tests and explicit evaluation views.

## Fitting and diagnostics

Fit conductor geometry from observation points under explicit endpoint constraints. Recompute using the saved human constraint set after a rerun. Do not silently relax a correction to force convergence; return an infeasible or unsupported result with the reason.

The numerical profile is frozen in `backend/src/cateniq/geometry/profile.py` (the single source of truth for constants) with measured feasibility evidence in [docs/project/evidence/geometry-profile.md](../evidence/geometry-profile.md):

- **Plane coordinates:** span-local `(u, v)`; `u` horizontal along the span's vertical plane from attachment A toward B, `v` = world Z height in metres; a span occupies u ∈ [0, L] for L ∈ [10, 120] m.
- **Fit model:** `v(u) = v_v + a(cosh((u−u_v)/a) − 1)`, evaluated as `2a·sinh²((u−u_v)/2a)` to avoid cosh−1 cancellation at large `a`. Parameters: vertex `(u_v, v_v)` and catenary constant `a = H/w` ∈ [3, 5000] m. Sag/span ≤ 0.20 — deliberately beyond the parabola regime, so the catenary is the required model.
- **Free fit:** bounded least squares on vertical residuals; the vertex may lie up to two span lengths beyond the attachments so vertex-outside-span (monotonic) cases converge.
- **Constrained fit:** endpoints fixed to declared/corrected attachments; `u_v`, `v_v` determined analytically, leaving a bounded scalar minimisation over `a`. Constraints are never relaxed; hitting the `a` bound returns INFEASIBLE.
- **Evidence gates:** ≥30 points, observed extent ≥ 0.60·L, largest gap ≤ 0.25·L — otherwise INSUFFICIENT_EVIDENCE, distinct from a FAILED or OK fit.
- **Fit quality:** vertical residuals in metres; RMS ≤ 0.15 m and p95 ≤ 0.30 m required to pass validation.
- **Endpoint check:** |fitted v(u_attach) − v_attach| > 0.50 m raises an endpoint-mismatch diagnostic.
- **Solver hygiene:** Jacobian condition > 1e10 reports FAILED/unstable; solver failure reports FAILED. Fit statuses: `ok`, `insufficient_evidence`, `failed`, `infeasible`.

Diagnostics are computed from observations and predicted geometry: residual summaries, supporting-point coverage and endpoint/support consistency where the evidence allows. Each issue includes affected entity, measurement, configured threshold, input/run revision and an actionable explanation. Unsupported evidence is distinct from a failed fit and from a model that passes configured checks. Avoid uncalibrated probability/confidence labels.

An intentionally displaced predicted endpoint may drive the demonstration, provided its origin is disclosed. Diagnostic generation cannot depend on a flag saying that the fixture contains that error. Residual reduction alone is not sufficient: a proposed correction must also satisfy applicable support and coverage checks.

## Fixture coverage

Prepare a small nominal case, an endpoint-error case, noisy observations, missing/occluded observations, insufficient evidence, unequal support heights within the supported model, and an infeasible correction. Include unchanged good spans so validation does not merely flag every entity. Test at least one held-out seed/geometry beyond the main demo.

For the initial full-corridor rebuild, results must be repeatable within the declared numerical tolerance for identical inputs, versions and parameters. Cross-platform bitwise identity is not promised.

## Acceptance

- Manifest validation rejects malformed and mismatched evidence without partial publication.
- Independent known-geometry fixtures check coordinate transforms and fitted endpoints/curve error; generator/fitter agreement alone is insufficient.
- Tests cover shallow sag, missing evidence, invalid inputs and solver failure; tolerances and solver limits are explicit.
- Main demo diagnostics are computed, reproducible and disappear or change only when the corrected result warrants it.
- Validation can remain unresolved after a user edit; the UI does not force success.
- Results identify data, prediction, correction and algorithm revisions and do not imply thermal limits, engineering safety or active learning.

Tasks: [CAT-004](../backlog.md#cat-004), [CAT-005](../backlog.md#cat-005), [CAT-007](../backlog.md#cat-007).
