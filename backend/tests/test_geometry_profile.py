"""Feasibility evidence for the frozen numerical profile (CAT-004 / BLK-001).

Reference cases are derived analytically from the catenary equation, not from
the implementation under test: expected vertices, sags and arc lengths come
from closed-form identities and hand-checkable reasoning.
"""

import numpy as np
import numpy.typing as npt
import pytest

from cateniq.geometry import profile
from cateniq.geometry.catenary import (
    arc_length,
    catenary_v,
    check_evidence,
    endpoint_deviations,
    fit_constrained,
    fit_free,
    vertex_from_endpoints,
)

F64 = npt.NDArray[np.float64]

# Tolerances frozen from measured behaviour of these reference cases. They are
# intentionally above the observed errors by a margin; see
# docs/project/evidence/geometry-profile.md for the measured values.
A_RECOVERY_RTOL = 0.02  # clean data, moderate sag
A_RECOVERY_RTOL_SHALLOW = 0.15  # shallow sag: a is weakly identified
VERTEX_TOL_M = 0.05  # clean data
VERTEX_TOL_SHALLOW_M = 0.15
ENDPOINT_ESTIMATE_TOL_M = 0.10  # noisy data, sigma = 0.05


def sample_catenary(
    u_v: float,
    v_v: float,
    a: float,
    u_min: float,
    u_max: float,
    n: int,
    noise: float = 0.0,
    seed: int = 0,
) -> tuple[F64, F64]:
    """Points sampled exactly on a catenary, optionally with vertical noise."""
    rng = np.random.default_rng(seed)
    u = np.linspace(u_min, u_max, n)
    v = catenary_v(u, u_v, v_v, a)
    if noise:
        v = v + rng.normal(0.0, noise, size=u.shape)
    return u, v


def symmetric(
    a: float, span: float, v_attach: float
) -> tuple[profile.Attachments, tuple[float, float, float]]:
    """Equal-height case: vertex is analytically at the span midpoint."""
    att = profile.Attachments(0.0, v_attach, span, v_attach)
    u_v = span / 2.0
    v_v = v_attach - a * (np.cosh((span - u_v) / a) - 1.0)
    return att, (u_v, float(v_v), a)


class TestClosedForm:
    def test_vertex_closed_form_hits_both_endpoints(self) -> None:
        att = profile.Attachments(0.0, 10.0, 45.0, 13.5)
        for a in (50.0, 650.0, 3000.0):
            u_v, v_v = vertex_from_endpoints(att, a)
            ends = np.array([att.u_a, att.u_b])
            vals = catenary_v(ends, u_v, v_v, a)
            assert np.allclose(vals, [att.v_a, att.v_b], atol=1e-9)

    def test_vertex_closed_form_symmetric_case(self) -> None:
        att = profile.Attachments(0.0, 12.0, 50.0, 12.0)
        u_v, _ = vertex_from_endpoints(att, 800.0)
        assert u_v == pytest.approx(25.0, abs=1e-12)

    def test_arc_length_matches_independent_quadrature(self) -> None:
        att, (u_v, _v_v, a) = symmetric(800.0, 50.0, 12.0)
        # Independent method: trapezoid quadrature of ds = sqrt(1 + (dv/du)^2)
        u = np.linspace(att.u_a, att.u_b, 200_001)
        slope = np.sinh((u - u_v) / a)  # analytic derivative dv/du
        numeric = float(np.trapezoid(np.sqrt(1.0 + slope**2), u))
        assert arc_length(att, u_v, a) == pytest.approx(numeric, rel=1e-9)


class TestFreeFit:
    def test_recovers_symmetric_case(self) -> None:
        att, truth = symmetric(a=800.0, span=50.0, v_attach=12.0)
        u, v = sample_catenary(*truth, 0.0, 50.0, 200)
        res = fit_free(u, v, att)
        assert res.status == profile.FitStatus.OK and res.params is not None
        assert res.params[2] == pytest.approx(800.0, rel=A_RECOVERY_RTOL)
        assert res.params[0] == pytest.approx(truth[0], abs=VERTEX_TOL_M)
        assert res.params[1] == pytest.approx(truth[1], abs=VERTEX_TOL_M)
        assert res.rms is not None and res.rms < 1e-6

    def test_recovers_unequal_heights(self) -> None:
        att = profile.Attachments(0.0, 10.0, 45.0, 13.5)
        a = 650.0
        u_v, v_v = vertex_from_endpoints(att, a)
        u, v = sample_catenary(u_v, v_v, a, 0.0, 45.0, 200)
        res = fit_free(u, v, att)
        assert res.status == profile.FitStatus.OK and res.params is not None
        assert res.params[2] == pytest.approx(a, rel=A_RECOVERY_RTOL)
        dev = endpoint_deviations(res.params, att)
        assert max(abs(d) for d in dev) < ENDPOINT_ESTIMATE_TOL_M

    def test_recovers_with_noise(self) -> None:
        att, truth = symmetric(a=900.0, span=60.0, v_attach=14.0)
        u, v = sample_catenary(*truth, 0.0, 60.0, 400, noise=0.05, seed=42)
        res = fit_free(u, v, att)
        assert res.status == profile.FitStatus.OK and res.params is not None
        dev = endpoint_deviations(res.params, att)
        assert max(abs(d) for d in dev) < ENDPOINT_ESTIMATE_TOL_M
        assert res.rms is not None and res.rms == pytest.approx(0.05, abs=0.02)

    def test_shallow_sag_recovers_with_looser_a_tolerance(self) -> None:
        att, truth = symmetric(a=3000.0, span=50.0, v_attach=12.0)
        u, v = sample_catenary(*truth, 0.0, 50.0, 400, noise=0.02, seed=7)
        res = fit_free(u, v, att)
        assert res.status == profile.FitStatus.OK and res.params is not None
        assert res.params[2] == pytest.approx(3000.0, rel=A_RECOVERY_RTOL_SHALLOW)
        dev = endpoint_deviations(res.params, att)
        assert max(abs(d) for d in dev) < ENDPOINT_ESTIMATE_TOL_M


class TestEvidenceGates:
    def test_too_few_points(self) -> None:
        att, truth = symmetric(800.0, 50.0, 12.0)
        u, v = sample_catenary(*truth, 0.0, 50.0, profile.MIN_POINTS - 18)
        res = fit_free(u, v, att)
        assert res.status == profile.FitStatus.INSUFFICIENT_EVIDENCE

    def test_large_observation_gap(self) -> None:
        att, truth = symmetric(800.0, 50.0, 12.0)
        u1, v1 = sample_catenary(*truth, 0.0, 15.0, 80)
        u2, v2 = sample_catenary(*truth, 35.0, 50.0, 80)
        res = fit_free(np.concatenate([u1, u2]), np.concatenate([v1, v2]), att)
        assert res.status == profile.FitStatus.INSUFFICIENT_EVIDENCE
        assert res.reason is not None and "gap" in res.reason

    def test_insufficient_coverage(self) -> None:
        att, truth = symmetric(800.0, 50.0, 12.0)
        u, v = sample_catenary(*truth, 0.0, 18.0, 120)
        res = fit_free(u, v, att)
        assert res.status == profile.FitStatus.INSUFFICIENT_EVIDENCE
        assert res.reason is not None and "coverage" in res.reason

    def test_monotonic_span_fits(self) -> None:
        # Steeply unequal heights place the vertex outside the observed span;
        # this is a supported case and must not be rejected.
        att = profile.Attachments(0.0, 10.0, 50.0, 16.0)
        a = 300.0
        u_v, v_v = vertex_from_endpoints(att, a)
        assert u_v < 0.0  # vertex genuinely outside the span
        u, v = sample_catenary(u_v, v_v, a, 0.0, 50.0, 300, noise=0.03, seed=5)
        res = fit_free(u, v, att)
        assert res.status == profile.FitStatus.OK and res.params is not None
        assert res.params[2] == pytest.approx(a, rel=A_RECOVERY_RTOL_SHALLOW)
        dev = endpoint_deviations(res.params, att)
        assert max(abs(d) for d in dev) < ENDPOINT_ESTIMATE_TOL_M

    def test_evidence_check_is_pure(self) -> None:
        att, _ = symmetric(800.0, 50.0, 12.0)
        assert check_evidence(np.linspace(0, 50, 5), att) is not None
        assert check_evidence(np.linspace(0, 50, 200), att) is None


class TestEndpointCorrection:
    """The demo scenario: a displaced predicted endpoint must be detectable and
    a wrong correction must not silently pass."""

    def test_displaced_prediction_is_detected(self) -> None:
        att, truth = symmetric(a=800.0, span=50.0, v_attach=12.0)
        u, v = sample_catenary(*truth, 0.0, 50.0, 300, noise=0.03, seed=11)
        res = fit_free(u, v, att)
        assert res.status == profile.FitStatus.OK and res.params is not None

        predicted = profile.Attachments(0.0, 12.0, 50.0, 12.0 + 1.5)
        dev_a, dev_b = endpoint_deviations(res.params, predicted)
        assert abs(dev_a) < profile.ENDPOINT_TOLERANCE_M  # good end: no issue
        assert abs(dev_b) > profile.ENDPOINT_TOLERANCE_M  # displaced end: issue fires

    def test_corrected_constraint_recovers_fit(self) -> None:
        att, truth = symmetric(a=800.0, span=50.0, v_attach=12.0)
        u, v = sample_catenary(*truth, 0.0, 50.0, 300, noise=0.03, seed=11)
        res = fit_constrained(u, v, att)
        assert res.status == profile.FitStatus.OK and res.params is not None
        assert res.params[2] == pytest.approx(800.0, rel=A_RECOVERY_RTOL)
        assert res.rms is not None and res.rms < profile.RMS_MAX_M

    def test_wrong_correction_fails_validation(self) -> None:
        att, truth = symmetric(a=800.0, span=50.0, v_attach=12.0)
        u, v = sample_catenary(*truth, 0.0, 50.0, 300, noise=0.03, seed=11)
        wrong = profile.Attachments(att.u_a, att.v_a, att.u_b, att.v_b + 1.5)
        res = fit_constrained(u, v, wrong)
        # The constraint is respected (curve threads the wrong endpoint) but the
        # result must not pass quality validation.
        assert res.status in (profile.FitStatus.OK, profile.FitStatus.INFEASIBLE)
        assert res.rms is not None and res.rms > profile.RMS_MAX_M
        if res.params:
            u_v, v_v, a = res.params
            ends = catenary_v(np.array([wrong.u_a, wrong.u_b]), u_v, v_v, a)
            assert np.allclose(ends, [wrong.v_a, wrong.v_b], atol=1e-6)

    def test_absurd_correction_is_infeasible(self) -> None:
        att, truth = symmetric(a=800.0, span=50.0, v_attach=12.0)
        u, v = sample_catenary(*truth, 0.0, 50.0, 300, noise=0.03, seed=11)
        absurd = profile.Attachments(att.u_a, att.v_a, att.u_b, att.v_b - 6.0)
        res = fit_constrained(u, v, absurd)
        assert res.status == profile.FitStatus.INFEASIBLE


class TestModelLimits:
    def test_shallow_sag_close_to_parabola(self) -> None:
        # For shallow sag the osculating parabola is a close approximation.
        _att, truth = symmetric(a=3000.0, span=50.0, v_attach=12.0)
        u_v, v_v, a = truth
        u = np.linspace(0.0, 50.0, 1001)
        exact = catenary_v(u, u_v, v_v, a)
        parabola = v_v + (u - u_v) ** 2 / (2.0 * a)
        assert np.max(np.abs(exact - parabola)) < 0.001  # ~ 1 mm at sag/span ~0.2%

    def test_deep_sag_diverges_from_parabola(self) -> None:
        # At the supported sag boundary (sag/span ~ 0.2, a ~ 6.25 on a 10 m
        # span) the parabola error is decimetric — catenary, not parabola, is
        # the fit model.
        _att, truth = symmetric(a=6.25, span=10.0, v_attach=8.0)
        u_v, v_v, a = truth
        u = np.linspace(0.0, 10.0, 1001)
        exact = catenary_v(u, u_v, v_v, a)
        parabola = v_v + (u - u_v) ** 2 / (2.0 * a)
        assert np.max(np.abs(exact - parabola)) > 0.01
