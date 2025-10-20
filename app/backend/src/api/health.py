"""Health check endpoints."""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def get_health() -> dict[str, str]:
    """Return basic health information for Render health checks."""
    return {"status": "ok", "service": "invoice-agent"}
