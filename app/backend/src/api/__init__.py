"""Public API routers exposed by the FastAPI application."""

from . import (
    admin,
    admin_users,
    analytics,
    auth,
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
    "analytics",
    "auth",
    "districts",
    "health",
    "invoices",
    "jobs",
    "uploads",
    "users",
    "vendors",
]
