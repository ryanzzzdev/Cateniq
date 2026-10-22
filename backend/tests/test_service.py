"""Service-level tests: dataset serving and computed diagnostics over HTTP."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from cateniq.app import create_app

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app(FIXTURES))


def test_datasets_list(client: TestClient) -> None:
    res = client.get("/api/datasets")
    assert res.status_code == 200
    ids = {d["dataset_id"] for d in res.json()}
    assert {"corridor-a", "corridor-b", "corridor-adverse"} <= ids


def test_dataset_payload_has_no_evaluation(client: TestClient) -> None:
    res = client.get("/api/datasets/corridor-a")
    assert res.status_code == 200
    body = res.json()
    assert "evaluation" not in body
    assert {s["span_id"] for s in body["spans"]} == {"S1", "S2", "S3", "S4"}
    assert body["predictions"]["S2"]["attach_b"][2] == pytest.approx(10.5)
    assert "S1" in body["observations"] and "context" in body
    assert len(body["observations"]["S1"]["x"]) > 0


def test_unknown_dataset_404(client: TestClient) -> None:
    res = client.get("/api/datasets/nope")
    assert res.status_code == 404


def test_diagnostics_are_computed(client: TestClient) -> None:
    res = client.get("/api/datasets/corridor-a/diagnostics")
    assert res.status_code == 200
    spans = {s["span_id"]: s for s in res.json()["spans"]}
    s2 = spans["S2"]
    kinds = {i["kind"] for i in s2["issues"]}
    assert "endpoint_mismatch" in kinds
    assert s2["endpoint_deviations"][1] == pytest.approx(1.51, abs=0.05)
    assert spans["S1"]["issues"] == []
    assert "high_residual" in {i["kind"] for i in spans["S4"]["issues"]}


def test_diagnostics_adverse(client: TestClient) -> None:
    res = client.get("/api/datasets/corridor-adverse/diagnostics")
    spans = {s["span_id"]: s for s in res.json()["spans"]}
    assert spans["A1"]["status"] == "insufficient_evidence"
    assert spans["A2"]["status"] == "insufficient_evidence"


def test_constrained_fit_correction(client: TestClient) -> None:
    """Correcting S2's endpoint to the true candidate refits clean."""
    ds = client.get("/api/datasets/corridor-a").json()
    p3 = next(p for p in ds["poles"] if p["pole_id"] == "P3")
    high = next(
        c for c in p3["attachment_candidates"] if c["candidate_id"] == "P3:high"
    )
    low = next(c for c in p3["attachment_candidates"] if c["candidate_id"] == "P3:low")
    res = client.post(
        "/api/datasets/corridor-a/fit",
        json={
            "span_id": "S2",
            "attach_a": ds["predictions"]["S2"]["attach_a"],
            "attach_b": high["point"],
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["rms"] < 0.15
    assert len(body["fit"]["curve"]) == 129

    bad = client.post(
        "/api/datasets/corridor-a/fit",
        json={
            "span_id": "S2",
            "attach_a": ds["predictions"]["S2"]["attach_a"],
            "attach_b": low["point"],
        },
    )
    assert bad.json()["status"] == "infeasible"
