"""FastAPI application factory for the Cateniq review service."""

import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from cateniq.datasets.manifest import ManifestError
from cateniq.service import CorridorService

_DEFAULT_FIXTURES = Path(__file__).resolve().parents[3] / "fixtures"


class FitRequest(BaseModel):
    span_id: str
    attach_a: list[float]
    attach_b: list[float]


def create_app(fixtures_dir: Path | None = None) -> FastAPI:
    app = FastAPI(title="cateniq")
    root = fixtures_dir or Path(
        os.environ.get("CATENIQ_FIXTURES_DIR", _DEFAULT_FIXTURES)
    )
    service = CorridorService(root)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "cateniq"}

    @app.get("/api/datasets")
    def list_datasets() -> list[dict[str, Any]]:
        return service.list_datasets()

    @app.get("/api/datasets/{dataset_id}")
    def get_dataset(dataset_id: str) -> dict[str, Any]:
        try:
            return service.dataset(dataset_id)
        except (ManifestError, FileNotFoundError) as exc:
            raise HTTPException(404, str(exc)) from exc

    @app.get("/api/datasets/{dataset_id}/diagnostics")
    def get_diagnostics(dataset_id: str) -> dict[str, Any]:
        try:
            return service.diagnostics(dataset_id)
        except (ManifestError, FileNotFoundError) as exc:
            raise HTTPException(404, str(exc)) from exc

    @app.post("/api/datasets/{dataset_id}/fit")
    def refit(dataset_id: str, body: FitRequest) -> dict[str, Any]:
        try:
            return service.constrained_fit(
                dataset_id, body.span_id, body.attach_a, body.attach_b
            )
        except (ManifestError, FileNotFoundError, IndexError, ValueError) as exc:
            raise HTTPException(400, str(exc)) from exc

    return app


app = create_app()
