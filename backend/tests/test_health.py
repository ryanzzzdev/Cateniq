"""Smoke test for the API skeleton."""

from fastapi.testclient import TestClient

from cateniq.app import create_app


def test_health() -> None:
    client = TestClient(create_app())
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "cateniq"}
