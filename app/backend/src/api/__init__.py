"""Public API routers exposed by the FastAPI application."""

from . import (
    admin,
    admin_users,
    admin_districts,
    agents,
    analytics,
    analytics_agent,
    auth,
    debug,
    districts,
    health,
    invoices,
    jobs,
    uploads,
    users,
    vendors,
)

__all__ = [
    "admin",
    "admin_users",
    "admin_districts",
    "agents",
    "analytics",
    "auth",
    "debug",
    "districts",
    "health",
    "invoices",
    "jobs",
    "uploads",
    "users",
    "vendors",
    "analytics_agent",
]
