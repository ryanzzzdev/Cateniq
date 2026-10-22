"""FastAPI application factory for the Cateniq review service."""

import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from cateniq.datasets.manifest import ManifestError
from cateniq.service import CorridorService
from cateniq.store import (
    ConflictError,
    OperationConflictError,
    StoreError,
    ValidationError,
)

_DEFAULT_FIXTURES = Path(__file__).resolve().parents[3] / "fixtures"


class FitRequest(BaseModel):
    span_id: str
    attach_a: list[float]
    attach_b: list[float]


class RefitRequest(BaseModel):
    edits: dict[str, dict[str, list[float]]] = {}


class SaveRequest(BaseModel):
    operation_id: str
    base_revision: int
    edits: dict[str, dict[str, list[float]]] = {}


class VerifyRequest(BaseModel):
    export: dict[str, Any]


def create_app(
    fixtures_dir: Path | None = None, db_path: Path | None = None
) -> FastAPI:
    app = FastAPI(title="cateniq")
    root = fixtures_dir or Path(
        os.environ.get("CATENIQ_FIXTURES_DIR", _DEFAULT_FIXTURES)
    )
    db = db_path or (
        Path(os.environ["CATENIQ_DB_PATH"]) if "CATENIQ_DB_PATH" in os.environ else None
    )
    service = CorridorService(root, db)

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

    @app.post("/api/datasets/{dataset_id}/refit")
    def corridor_refit(dataset_id: str, body: RefitRequest) -> dict[str, Any]:
        try:
            return service.refit(dataset_id, body.edits)
        except (ManifestError, FileNotFoundError, IndexError, ValueError) as exc:
            raise HTTPException(400, str(exc)) from exc

    # -- durable review (CAT-009) --------------------------------------------

    @app.get("/api/datasets/{dataset_id}/review")
    def get_review(dataset_id: str) -> dict[str, Any]:
        try:
            return service.review_state(dataset_id)
        except (ManifestError, FileNotFoundError) as exc:
            raise HTTPException(404, str(exc)) from exc

    @app.post("/api/datasets/{dataset_id}/review/operations")
    def save_operation(dataset_id: str, body: SaveRequest) -> dict[str, Any]:
        try:
            return service.save_operation(
                dataset_id, body.operation_id, body.base_revision, body.edits
            )
        except ConflictError as exc:
            raise HTTPException(
                409,
                {"detail": str(exc), "current_revision": exc.current_revision},
            ) from exc
        except OperationConflictError as exc:
            raise HTTPException(409, str(exc)) from exc
        except ValidationError as exc:
            raise HTTPException(422, str(exc)) from exc
        except (ManifestError, FileNotFoundError, StoreError) as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.get("/api/datasets/{dataset_id}/review/export")
    def export_review(dataset_id: str) -> dict[str, Any]:
        try:
            return service.export_review(dataset_id)
        except (ManifestError, FileNotFoundError) as exc:
            raise HTTPException(404, str(exc)) from exc

    @app.post("/api/export/verify")
    def verify_export(body: VerifyRequest) -> dict[str, Any]:
        try:
            return service.verify_export(body.export)
        except ValidationError as exc:
            raise HTTPException(422, str(exc)) from exc
        except (ManifestError, FileNotFoundError) as exc:
            raise HTTPException(404, str(exc)) from exc

    return app


app = create_app()
