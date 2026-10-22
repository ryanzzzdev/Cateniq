"""Catenary reference implementation validating the frozen profile (CAT-004).

Deliberately small: it exists so the profile's feasibility evidence is
reproducible. CAT-007 hardens this into the production fitter without changing
the contracts in `cateniq.geometry.profile`.

Model: in a span's vertical plane the conductor follows

    v(u) = v_v + a * (cosh((u - u_v) / a) - 1)

with vertex (u_v, v_v) and catenary constant a = H/w > 0.
"""

import numpy as np
import numpy.typing as npt
from scipy import optimize

from cateniq.geometry.profile import (
    A_MAX,
    A_MIN,
    COND_MAX,
    MAX_GAP_FRACTION,
    MAX_SAG_FRACTION,
    MIN_COVERAGE,
    MIN_POINTS,
    SPAN_MAX_M,
    SPAN_MIN_M,
    Attachments,
    FitResult,
    FitStatus,
)

F64 = npt.NDArray[np.float64]


def catenary_v(u: F64, u_v: float, v_v: float, a: float) -> F64:
    """Evaluate the catenary at horizontal positions u.

    Uses 2a*sinh^2((u-u_v)/2a), identical to a*(cosh((u-u_v)/a) - 1) but without
    the cosh-1 cancellation that loses precision for shallow sags (large a).
    """
    return v_v + 2.0 * a * np.sinh((u - u_v) / (2.0 * a)) ** 2


def vertex_from_endpoints(att: Attachments, a: float) -> tuple[float, float]:
    """Vertex (u_v, v_v) of the catenary with parameter a through both endpoints.

    From v_b - v_a = a(cosh((u_b-u_v)/a) - cosh((u_a-u_v)/a)) and the identity
    cosh(p+q)-cosh(p) = 2*sinh(p+q/2)*sinh(q/2) with q = L/a:

        u_v = u_a - a * (asinh(dv / (2a*sinh(L/(2a)))) - L/(2a))

    For dv == 0 this reduces exactly to u_v = u_a + L/2.
    """
    length, dv = att.length, att.v_b - att.v_a
    half_q = length / (2.0 * a)
    u_v = att.u_a - a * (float(np.arcsinh(dv / (2.0 * a * np.sinh(half_q)))) - half_q)
    v_v = att.v_a - a * (float(np.cosh((att.u_a - u_v) / a)) - 1.0)
    return u_v, v_v


def arc_length(att: Attachments, u_v: float, a: float) -> float:
    """Arc length of the catenary between the two attachments."""
    return float(a * (np.sinh((att.u_b - u_v) / a) - np.sinh((att.u_a - u_v) / a)))


def check_domain(att: Attachments) -> str | None:
    """Return a reason string if the declared span is outside the domain."""
    if att.u_b <= att.u_a:
        return f"degenerate span: u_b {att.u_b} <= u_a {att.u_a}"
    if not SPAN_MIN_M <= att.length <= SPAN_MAX_M:
        return f"span {att.length:.2f} m outside [{SPAN_MIN_M}, {SPAN_MAX_M}] m"
    return None


def check_evidence(u: F64, att: Attachments) -> str | None:
    """Return a reason string if the observation evidence is insufficient."""
    n = int(u.shape[0])
    if n < MIN_POINTS:
        return f"insufficient points: {n} < {MIN_POINTS}"
    span = att.length
    ordered = np.sort(u)
    coverage = float((ordered[-1] - ordered[0]) / span)
    if coverage < MIN_COVERAGE:
        return f"insufficient coverage: {coverage:.3f} < {MIN_COVERAGE}"
    max_gap = float(np.max(np.diff(ordered)) / span) if n > 1 else 1.0
    if max_gap > MAX_GAP_FRACTION:
        return f"observation gap too large: {max_gap:.3f} > {MAX_GAP_FRACTION}"
    return None


def sag_fraction(params: tuple[float, float, float], att: Attachments) -> float:
    """Deepest dip of the fitted curve below the endpoint chord, per span."""
    u_v, v_v, a = params
    u = np.linspace(att.u_a, att.u_b, 257)
    chord = att.v_a + (att.v_b - att.v_a) * (u - att.u_a) / att.length
    dip = np.max(chord - catenary_v(u, u_v, v_v, a))
    return float(dip / att.length)


def _condition(res: optimize.OptimizeResult) -> float | None:
    jac = getattr(res, "jac", None)
    if jac is None or not np.asarray(jac).size:
        return None
    return float(np.linalg.cond(np.asarray(jac, dtype=np.float64)))


def _residual_stats(
    u: F64, v: F64, params: tuple[float, float, float]
) -> tuple[float, float]:
    r = v - catenary_v(u, *params)
    return float(np.sqrt(np.mean(r**2))), float(np.quantile(np.abs(r), 0.95))


def fit_free(u: F64, v: F64, att: Attachments) -> FitResult:
    """Unconstrained vertex-form least-squares fit to observations."""
    reason = check_domain(att)
    if reason:
        return FitResult(FitStatus.UNSUPPORTED, None, None, None, None, reason)
    reason = check_evidence(u, att)
    if reason:
        return FitResult(
            FitStatus.INSUFFICIENT_EVIDENCE, None, None, None, None, reason
        )

    span = att.length
    i_low = int(np.argmin(v))
    sag0 = max(float(max(v[0], v[-1]) - v[i_low]), 0.05 * span)
    a0 = float(np.clip(span**2 / (8.0 * sag0), A_MIN, A_MAX))
    x0 = [float(u[i_low]), float(v[i_low]), a0]
    bounds = (
        [att.u_a - 2.0 * span, float(np.min(v)) - span, A_MIN],
        [att.u_b + 2.0 * span, float(np.min(v)) + 1.0, A_MAX],
    )

    def residual(p: F64, *args: object) -> F64:
        return catenary_v(u, p[0], p[1], p[2]) - v

    res = optimize.least_squares(
        residual, x0, bounds=bounds, xtol=1e-12, ftol=1e-12, gtol=1e-12
    )
    if not res.success:
        return FitResult(FitStatus.FAILED, None, None, None, None, str(res.message))

    params = (float(res.x[0]), float(res.x[1]), float(res.x[2]))
    rms, p95 = _residual_stats(u, v, params)
    cond = _condition(res)
    if cond is not None and cond > COND_MAX:
        return FitResult(
            FitStatus.FAILED, params, rms, p95, cond, "ill-conditioned solution"
        )
    sag = sag_fraction(params, att)
    if sag > MAX_SAG_FRACTION:
        return FitResult(
            FitStatus.UNSUPPORTED,
            params,
            rms,
            p95,
            cond,
            f"evidence implies sag/span {sag:.3f} > {MAX_SAG_FRACTION}",
        )
    return FitResult(FitStatus.OK, params, rms, p95, cond, None)


def fit_constrained(u: F64, v: F64, att: Attachments) -> FitResult:
    """Fit with both endpoints fixed to the declared/corrected attachments.

    The endpoints determine u_v and v_v analytically for each trial a, leaving a
    bounded scalar minimisation over a in [A_MIN, A_MAX]. Constraints that can
    only be satisfied outside the supported domain are reported INFEASIBLE,
    never relaxed.
    """
    reason = check_domain(att)
    if reason:
        return FitResult(FitStatus.UNSUPPORTED, None, None, None, None, reason)
    reason = check_evidence(u, att)
    if reason:
        return FitResult(
            FitStatus.INSUFFICIENT_EVIDENCE, None, None, None, None, reason
        )

    def objective(a: float) -> float:
        u_v, v_v = vertex_from_endpoints(att, a)
        r = v - catenary_v(u, u_v, v_v, a)
        return float(np.mean(r**2))

    res = optimize.minimize_scalar(objective, bounds=(A_MIN, A_MAX), method="bounded")
    if not res.success:
        return FitResult(FitStatus.FAILED, None, None, None, None, str(res.message))
    a = float(res.x)
    u_v, v_v = vertex_from_endpoints(att, a)
    params = (u_v, v_v, a)
    rms, p95 = _residual_stats(u, v, params)
    if a <= A_MIN * 1.001 or a >= A_MAX * 0.999:
        return FitResult(
            FitStatus.INFEASIBLE,
            params,
            rms,
            p95,
            None,
            f"constraints incompatible with supported a in [{A_MIN}, {A_MAX}]",
        )
    sag = sag_fraction(params, att)
    if sag > MAX_SAG_FRACTION:
        return FitResult(
            FitStatus.INFEASIBLE,
            params,
            rms,
            p95,
            None,
            f"constraints imply sag/span {sag:.3f} > {MAX_SAG_FRACTION}",
        )
    return FitResult(FitStatus.OK, params, rms, p95, None, None)


def endpoint_deviations(
    params: tuple[float, float, float], att: Attachments
) -> tuple[float, float]:
    """Signed deviation of the fitted curve from each declared attachment (m)."""
    u_v, v_v, a = params
    ends = np.array([att.u_a, att.u_b], dtype=np.float64)
    vs = np.array([att.v_a, att.v_b], dtype=np.float64)
    dev = catenary_v(ends, u_v, v_v, a) - vs
    return float(dev[0]), float(dev[1])
