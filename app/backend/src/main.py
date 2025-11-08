"""Entrypoint for the FastAPI application."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import (
    admin,
    admin_users,
    admin_districts,
    analytics,
    auth,
    districts,
    health,
    invoices,
    jobs,
    vendors,
    uploads,
    users,
)
from .core.logging import configure_logging


def create_app() -> FastAPI:
    """Create the FastAPI application and register routers."""
    configure_logging()
    app = FastAPI(title="ASCS x SCUSD Invoice Agent", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router, prefix="/api")
    app.include_router(auth.router, prefix="/api")
    app.include_router(uploads.router, prefix="/api")
    app.include_router(invoices.router, prefix="/api")
    app.include_router(jobs.router, prefix="/api")
    app.include_router(analytics.router, prefix="/api")
    app.include_router(admin.router, prefix="/api")
    app.include_router(admin_users.router, prefix="/api")
    app.include_router(admin_districts.router, prefix="/api")
    app.include_router(users.router, prefix="/api")
    app.include_router(vendors.router, prefix="/api")
    app.include_router(districts.router, prefix="/api")

    return app


app = create_app()
