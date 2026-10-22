# Evidence — numerical profile feasibility (CAT-004 / BLK-001)

Date: 2026-10-22
Environment: Linux kernel 7.0, Python 3.14.4, numpy 2.5.4, scipy 1.18.1 (per `backend/uv.lock`)
Procedure: `cd backend && uv run pytest tests/test_geometry_profile.py` — 19 checks, all passing
Code under test: `backend/src/cateniq/geometry/profile.py` (frozen constants) and `backend/src/cateniq/geometry/catenary.py` (reference implementation; CAT-007 hardens it into the production fitter)

## Model and parameterisation

- Span-local plane coordinates: `u` horizontal (m) along the span's vertical plane from attachment A, `v` height (m) = world Z; span occupies u in [0, L].
- Fit model: `v(u) = v_v + a(cosh((u−u_v)/a) − 1)`, evaluated as `2a·sinh²((u−u_v)/2a)` to avoid cosh−1 cancellation at large `a`. Parameters: vertex `(u_v, v_v)` and catenary constant `a = H/w` (CIGRE TB 324; Southwire Overhead Conductor Manual via O-Calc documentation; Irvine, *Cable Structures*; Hatibović 2014, doi:10.3311/ppee.6993).
- Free fit: bounded `scipy.optimize.least_squares` on vertical residuals; vertex allowed ±2 span lengths beyond attachments so vertex-outside-span (monotonic) cases converge.
- Constrained fit: both endpoints fixed → `u_v`, `v_v` determined analytically (`vertex_from_endpoints`, closed form via `asinh`); bounded scalar minimisation over `a`. Constraints are never relaxed; hitting the `a` bound returns INFEASIBLE.

## Measured results vs frozen tolerances

| Case | Observed | Frozen tolerance |
| --- | --- | --- |
| Clean symmetric (a=800, L=50) | a relative error 4.3e-16, vertex error 3.6e-15 m, RMS 2.8e-16 | a rtol 0.02, vertex 0.05 m |
| Clean unequal heights (10→13.5 m, L=45, a=650; vertex at −28 m, outside span) | a relative error 3.5e-16, endpoint dev ~7e-14 m | a rtol 0.02, endpoint est. 0.10 m |
| Noisy (σ=0.05 m, n=400, a=900, L=60) | a rel. err 0.7%, endpoint dev ≤ 5 mm, RMS 0.0475, cond 5.9e3 | a rtol 0.02 for clean; endpoint est. 0.10 m |
| Shallow sag (a=3000, sag/span ~0.2%, σ=0.02) | a rel. err 1.8%, endpoint dev ≤ 5 mm, cond 1.0e5 | a rtol 0.15 (a weakly identified; report fitted sag rather than a) |
| Monotonic unequal heights (10→16 m, L=50, a=300, vertex outside span) | a rel. err 0.9%, endpoint dev ≤ 11 mm, cond 1.0e3 | endpoint est. 0.10 m |
| Wrong correction (+1.5 m endpoint constraint) | fit OK but RMS 0.534 > 0.15 m gate | constraint respected, quality fails |
| Absurd correction (−6 m endpoint) | INFEASIBLE: minimiser hits a=A_MAX=5000 | infeasible declared, not forced |

Jacobian condition numbers observed: ~1e3–1e5 on supported cases; COND_MAX = 1e10 leaves wide margin before reporting FAILED/unstable.

## Design finding recorded

A "vertex must be bracketed by observations" gate was tried and **dropped**: legitimately unequal-height spans place the vertex outside the observed extent (monotonic conductor), so the gate rejected a supported case. Identifiability is instead bounded by the conditioning check and the `a` range; weak `a` identifiability in shallow sags is handled by the looser shallow-sag tolerance (and downstream code should present fitted sag/geometry, not raw `a`, in that regime).

## Parabola-vs-catenary boundary

IEEE Std 605-2008 §11.4.3: parabola adequate when sag/span < 1/8. Southwire: parabola within ~1% when sag < 10% of span. Measured on our reference implementation: at sag/span ~0.2% the osculating parabola differs from the catenary by 0.001 mm; at the supported boundary sag/span ~0.21 the difference is ~109 mm. MAX_SAG_FRACTION = 0.20 deliberately exceeds the parabola regime, so the catenary is the required model at the top of the supported domain.

## Supported-domain justification

`a ∈ [3, 5000] m`: lower bound follows from `a ≈ L²/(8·sag)` at sag/span 0.2 on short spans; upper bound covers tight transmission geometry (Hatibović thesis: a typically 500–2000 m for transmission under most conditions). Spans 10–120 m cover LV (~50 m) and MV (~100 m) distribution practice (SEC SDCS-01; We Energies ruling spans 49–91 m). Fitting precedent for least-squares catenary estimation from point data: McLaughlin 2006 (doi:10.1109/LGRS.2005.863390), Jwa & Sohn 2012 (doi:10.14358/PERS.78.11.1227), UNSW catenary least-squares teaching notes (vertex + shape parameter parametrisation recommended — matches the vertex form chosen).

## Limitations

- Reference implementation validates feasibility only; production fitter, diagnostics plumbing and result provenance are CAT-007 scope.
- Tolerances derived from synthetic exact-catenary data; real LiDAR residuals are not yet characterised (synthetic scope is declared in the dataset contract).
- Cross-platform bitwise identity is not claimed; tolerances carry margin for solver/platform variation.
