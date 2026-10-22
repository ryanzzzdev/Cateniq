"""FastAPI application factory for the Cateniq review service."""

from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(title="cateniq")

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "cateniq"}

    return app


app = create_app()
