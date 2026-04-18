"""FastAPI application factory for the Agnes demo UI."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from agnes.api.artifacts import router as artifacts_router
from agnes.api.runs import router as runs_router
from agnes.api.services.artifact_loader import ArtifactLoader
from agnes.api.services.run_manager import RunManager
from agnes.api.services.supply_network import SupplyNetworkService
from agnes.config.settings import Settings
from agnes.utils.logging import configure_logging


def _cors_origins() -> list[str]:
    raw = os.getenv("AGNES_API_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def _reports_dir() -> Path:
    return Path(os.getenv("AGNES_REPORTS_DIR", "outputs/reports")).resolve()


def _repo_root() -> Path:
    return Path(os.getenv("AGNES_REPO_ROOT", ".")).resolve()


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = Settings()
    configure_logging(settings.log_level)
    app.state.settings = settings
    app.state.artifact_loader = ArtifactLoader(_reports_dir())
    app.state.supply_network_service = SupplyNetworkService(
        settings=settings,
        loader=app.state.artifact_loader,
    )
    app.state.run_manager = RunManager(
        repo_root=_repo_root(),
        artifact_loader=app.state.artifact_loader,
    )
    try:
        yield
    finally:
        await app.state.run_manager.shutdown()


def create_app() -> FastAPI:
    """Construct the FastAPI app instance with all routers mounted."""
    app = FastAPI(
        title="Agnes Demo API",
        version="0.1.0",
        description="Evidence-grounded procurement intelligence — demo transport layer.",
        lifespan=_lifespan,
    )

    app.add_middleware(GZipMiddleware, minimum_size=1024)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    @app.get("/api/health", tags=["meta"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(artifacts_router)
    app.include_router(runs_router)
    return app


app = create_app()
