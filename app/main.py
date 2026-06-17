"""FCMR FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from fcmr_core.catalog.store import init_catalog
from fcmr_core.config import settings
from app.api import uploads, runs, downloads


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.ensure_dirs()
    init_catalog()
    yield


app = FastAPI(
    title="FCMR — Loan Audit Analytics",
    description="Deterministic KYC and data-quality analytics for NBFC loan audits.",
    version="0.1.0",
    lifespan=lifespan,
)

# Static files
_static_dir = settings.base_dir / "app" / "web" / "static"
app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")

# API routers
app.include_router(uploads.router)
app.include_router(runs.router)
app.include_router(downloads.router)
