"""Entrypoint for the FastAPI application."""

from fastapi import FastAPI

from .api import admin, analytics, auth, health, invoices, uploads
from .core.logging import configure_logging


def create_app() -> FastAPI:
    """Create the FastAPI application and register routers."""
    configure_logging()
    app = FastAPI(title="ASCS x SCUSD Invoice Agent", version="0.1.0")

    app.include_router(health.router, prefix="/api")
    app.include_router(auth.router, prefix="/api")
    app.include_router(uploads.router, prefix="/api")
    app.include_router(invoices.router, prefix="/api")
    app.include_router(analytics.router, prefix="/api")
    app.include_router(admin.router, prefix="/api")

    return app


app = create_app()
