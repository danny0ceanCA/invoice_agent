"""Entrypoint for the FastAPI application."""

import os
from dotenv import load_dotenv

# Load .env locally only (Render injects env vars)
env_path = os.path.join(os.path.dirname(__file__), "../.env")
if os.path.exists(env_path):
    load_dotenv(dotenv_path=os.path.abspath(env_path))
    print("DEBUG: .env loaded for local dev")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import (
    admin_users,
    admin_districts,
    agents,
    analytics,
    auth,
    debug,
    districts,
    health,
    invoices,
    jobs,
    vendors,
    uploads,
    users,
)
from .api import analytics_agent
from .api.admin.analytics import router as admin_analytics_router
from .core.logging import configure_logging


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(title="CareSpend Analytics", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router, prefix="/api")
    app.include_router(auth.router, prefix="/api")
    app.include_router(debug.router, prefix="/api")
    app.include_router(uploads.router, prefix="/api")
    app.include_router(invoices.router, prefix="/api")
    app.include_router(jobs.router, prefix="/api")
    app.include_router(analytics.router, prefix="/api")
    app.include_router(analytics_agent.router, prefix="/api")
    app.include_router(agents.router, prefix="/api")
    app.include_router(admin_users.router, prefix="/api")
    app.include_router(admin_districts.router, prefix="/api")
    app.include_router(admin_analytics_router, prefix="/api")
    app.include_router(users.router, prefix="/api")
    app.include_router(vendors.router, prefix="/api")
    app.include_router(districts.router, prefix="/api")

    return app


app = create_app()
