"""Production fitting outcomes (CAT-007): explicit domain results, provenance
and the corridor-level rerun.

Independent-evaluator rule: observation samples below are generated with the
plain cosh expression written inline — a different code path from
`catenary.catenary_v`'s cancellation-safe sinh² form — so parameter recovery
is evidence, not implementation self-consistency.
"""

from pathlib import Path

import numpy as np
import numpy.typing as npt
import pytest
from fastapi.testclient import TestClient

from cateniq.app import create_app
from cateniq.geometry.catenary import (
    check_domain,
    fit_constrained,
    fit_free,
    sag_fraction,
)
from cateniq.geometry.profile import (
    A_MAX,
    LATERAL_TOLERANCE_M,
    MAX_SAG_FRACTION,
    RMS_MAX_M,
    Attachments,
    FitStatus,
)

F64 = npt.NDArray[np.float64]
FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"


def _cosh_obs(u: F64, u_v: float, v_v: float, a: float) -> F64:
    """Independent catenary evaluator: plain cosh form, no cancellation guard."""
    return v_v + a * (np.cosh((u - u_v) / a) - 1.0)


def _obs(
    att: Attachments,
    u_v: float,
    v_v: float,
    a: float,
    n: int = 400,
    noise: float = 0.02,
) -> tuple[F64, F64]:
    rng = np.random.default_rng(11)
    u = np.sort(rng.uniform(att.u_a, att.u_b, n))
    return u, _cosh_obs(u, u_v, v_v, a) + rng.normal(0.0, noise, n)


class TestDomainOutcomes:
    def test_span_too_short_unsupported(self) -> None:
        att = Attachments(0.0, 10.0, 5.0, 10.0)
        u, v = _obs(att, 2.5, 9.0, 40.0)
        res = fit_free(u, v, att)
        assert res.status == FitStatus.UNSUPPORTED
        assert "outside" in (res.reason or "")

    def test_span_too_long_unsupported(self) -> None:
        att = Attachments(0.0, 10.0, 150.0, 10.0)
        u, v = _obs(att, 75.0, 8.0, 400.0)
        res = fit_free(u, v, att)
        assert res.status == FitStatus.UNSUPPORTED

    def test_degenerate_span_unsupported(self) -> None:
        att = Attachments(0.0, 10.0, 0.0, 10.0)
        res = fit_free(np.array([0.0]), np.array([10.0]), att)
        assert res.status == FitStatus.UNSUPPORTED
        assert "degenerate" in (res.reason or "")
        assert check_domain(att) is not None

    def test_deep_sag_evidence_unsupported(self) -> None:
        # sag/span ~0.24 on a 50 m span — beyond the supported domain.
        att = Attachments(0.0, 12.0, 50.0, 12.0)
        u_v, v_v, a = 25.0, 0.5, 26.0
        u, v = _obs(att, u_v, v_v, a)
        res = fit_free(u, v, att)
        assert res.status == FitStatus.UNSUPPORTED
        assert res.params is not None
        assert sag_fraction(res.params, att) > MAX_SAG_FRACTION

    def test_constrained_deep_sag_infeasible(self) -> None:
        # Same evidence with endpoints fixed: constraints cannot be satisfied
        # inside the supported domain, so the outcome is INFEASIBLE.
        att = Attachments(0.0, 12.0, 50.0, 12.0)
        u, v = _obs(att, 25.0, 0.5, 26.0)
        res = fit_constrained(u, v, att)
        assert res.status == FitStatus.INFEASIBLE
        assert "sag/span" in (res.reason or "")

    def test_constrained_absurd_endpoints_infeasible(self) -> None:
        # Endpoints far above the evidence: only an out-of-range a could
        # satisfy them.
        att = Attachments(0.0, 12.0, 50.0, 12.0)
        u, v = _obs(att, 25.0, 7.0, 60.0)
        bad = Attachments(0.0, 30.0, 50.0, 30.0)
        res = fit_constrained(u, v, bad)
        assert res.status == FitStatus.INFEASIBLE


class TestIndependentEvidence:
    def test_recovery_from_independent_cosh_samples(self) -> None:
        att = Attachments(0.0, 12.0, 50.0, 12.0)
        u, v = _obs(att, 25.0, 6.5, 90.0)
        res = fit_free(u, v, att)
        assert res.status == FitStatus.OK
        assert res.params is not None and res.rms is not None
        assert res.params[2] == pytest.approx(90.0, rel=0.02)
        assert res.rms < 0.15

    def test_shallow_sag_recovery(self) -> None:
        # a near the top of the range: the curve is nearly straight; a is
        # weakly identified but the geometry is still recoverable.
        att = Attachments(0.0, 12.0, 60.0, 12.0)
        u, v = _obs(att, 30.0, 11.0, 3500.0, noise=0.03)
        res = fit_free(u, v, att)
        assert res.status == FitStatus.OK
        assert res.params is not None
        assert 0 < res.params[2] <= A_MAX
        assert res.rms is not None and res.rms < 0.15


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(FIXTURES, tmp_path / "reviews.db"))


class TestConstrainedFitService:
    def test_off_plane_correction_reports_provenance(self, client: TestClient) -> None:
        """An off predicted-plane correction is measured as provenance; when
        it leaves the plane unsupported by evidence it is rejected, and the
        rejection still carries the measured offsets."""
        ds = client.get("/api/datasets/corridor-a").json()
        pred = ds["predictions"]["S2"]
        moved = [
            pred["attach_b"][0],
            pred["attach_b"][1] + 2.0,
            pred["attach_b"][2],
        ]
        res = client.post(
            "/api/datasets/corridor-a/fit",
            json={
                "span_id": "S2",
                "attach_a": pred["attach_a"],
                "attach_b": moved,
            },
        )
        body = res.json()
        c = body["constraints"]
        assert body["basis"] == "corrected"
        assert body["status"] == "unsupported"
        assert "LATERAL_TOLERANCE_M" in body["reason"]
        assert c["attach_b"] == moved
        assert c["off_plane_m"][0] == pytest.approx(0.0, abs=1e-6)
        assert abs(c["off_plane_m"][1]) == pytest.approx(2.0, abs=0.01)
        assert c["obs_lateral_rms_m"] > LATERAL_TOLERANCE_M
        assert body["issues"][0]["kind"] == "unsupported_domain"

    def test_wrong_but_convergent_correction_fails_validation(
        self, client: TestClient
    ) -> None:
        """A corrected fit can converge yet violate the quality gates — the
        solver status stays ok but validation issues must be reported, not
        silently accepted."""
        ds = client.get("/api/datasets/corridor-a").json()
        pred = ds["predictions"]["S2"]
        # z = 13.5 is in-plane but wrong: the constrained curve sits ~0.5 m
        # above the observations near the end of the span.
        moved = [
            pred["attach_b"][0],
            pred["attach_b"][1],
            pred["attach_b"][2] + 3.0,
        ]
        body = client.post(
            "/api/datasets/corridor-a/fit",
            json={
                "span_id": "S2",
                "attach_a": pred["attach_a"],
                "attach_b": moved,
            },
        ).json()
        assert body["status"] == "ok"  # solver converged on the constraint
        assert body["rms"] > RMS_MAX_M
        kinds = {i["kind"] for i in body["issues"]}
        assert "high_residual" in kinds
        assert "high_residual_p95" in kinds

    def test_degenerate_correction_unsupported(self, client: TestClient) -> None:
        ds = client.get("/api/datasets/corridor-a").json()
        pred = ds["predictions"]["S2"]
        res = client.post(
            "/api/datasets/corridor-a/fit",
            json={
                "span_id": "S2",
                "attach_a": pred["attach_a"],
                "attach_b": pred["attach_a"],
            },
        )
        body = res.json()
        assert body["status"] == "unsupported"
        assert body["basis"] == "corrected"
        assert body["constraints"] is None

    def test_diagnostics_carry_provenance(self, client: TestClient) -> None:
        spans = client.get("/api/datasets/corridor-a/diagnostics").json()["spans"]
        for s in spans:
            assert s["basis"] == "prediction"
            assert s["units"] == "m"
            assert s["status"] in {
                "ok",
                "insufficient_evidence",
                "failed",
                "infeasible",
                "unsupported",
            }


class TestCorridorRefit:
    def test_refit_marks_corrected_vs_prediction(self, client: TestClient) -> None:
        ds = client.get("/api/datasets/corridor-a").json()
        p3 = next(p for p in ds["poles"] if p["pole_id"] == "P3")
        high = next(
            c for c in p3["attachment_candidates"] if c["candidate_id"] == "P3:high"
        )
        pred = ds["predictions"]["S2"]
        res = client.post(
            "/api/datasets/corridor-a/refit",
            json={
                "edits": {
                    "S2": {
                        "attach_a": pred["attach_a"],
                        "attach_b": high["point"],
                    }
                }
            },
        )
        assert res.status_code == 200
        body = res.json()
        spans = {s["span_id"]: s for s in body["spans"]}
        assert set(spans) == {"S1", "S2", "S3", "S4"}
        assert spans["S2"]["basis"] == "corrected"
        assert spans["S2"]["status"] == "ok"
        assert spans["S2"]["rms"] < 0.15
        # The corrected result echoes the constraint it was fitted against.
        assert spans["S2"]["constraints"]["attach_b"] == high["point"]
        for sid in ("S1", "S3", "S4"):
            assert spans[sid]["basis"] == "prediction"

    def test_refit_preserves_unresolved_evidence(self, client: TestClient) -> None:
        """A corridor rerun does not manufacture success on adverse spans."""
        res = client.post("/api/datasets/corridor-adverse/refit", json={"edits": {}})
        spans = {s["span_id"]: s for s in res.json()["spans"]}
        assert spans["A1"]["status"] == "insufficient_evidence"
        assert spans["A2"]["status"] == "insufficient_evidence"

    def test_refit_counts_issues_on_corrected_spans(self, client: TestClient) -> None:
        """Corrected spans contribute issues to the corridor count — a wrong
        correction and an unchanged failing span must not vanish."""
        ds = client.get("/api/datasets/corridor-a").json()
        pred = ds["predictions"]["S2"]
        s4 = ds["predictions"]["S4"]
        body = client.post(
            "/api/datasets/corridor-a/refit",
            json={
                "edits": {
                    # In-plane but wrong height: converges, fails quality gates.
                    "S2": {
                        "attach_a": pred["attach_a"],
                        "attach_b": [
                            pred["attach_b"][0],
                            pred["attach_b"][1],
                            pred["attach_b"][2] + 3.0,
                        ],
                    },
                    # S4 unchanged: its high_residual must survive the rerun.
                    "S4": {
                        "attach_a": s4["attach_a"],
                        "attach_b": s4["attach_b"],
                    },
                }
            },
        ).json()
        spans = {s["span_id"]: s for s in body["spans"]}
        s2_kinds = {i["kind"] for i in spans["S2"]["issues"]}
        assert "high_residual" in s2_kinds
        s4_kinds = {i["kind"] for i in spans["S4"]["issues"]}
        assert s4_kinds  # unresolved issues preserved under corrected basis
        assert body["issue_count"] == sum(len(s["issues"]) for s in body["spans"])
