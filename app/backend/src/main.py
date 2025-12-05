"""Entrypoint for the FastAPI application."""

import os
from dotenv import load_dotenv

# Explicitly point to the project root .env
import os
from dotenv import load_dotenv

# Explicitly load the .env file located in app/backend/
env_path = os.path.join(os.path.dirname(__file__), "../.env")
load_dotenv(dotenv_path=os.path.abspath(env_path))
print("DEBUG: OpenAI key loaded (hidden)")


from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import (
    admin,
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
from app.api import analytics_agent
from .core.logging import configure_logging


def create_app() -> FastAPI:
    """Create the FastAPI application and register routers."""
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
    app.include_router(admin.router, prefix="/api")
    app.include_router(admin_users.router, prefix="/api")
    app.include_router(admin_districts.router, prefix="/api")
    app.include_router(users.router, prefix="/api")
    app.include_router(vendors.router, prefix="/api")
    app.include_router(districts.router, prefix="/api")

    return app


app = create_app()
