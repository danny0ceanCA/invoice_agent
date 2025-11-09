"""Health check endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..db import get_session_dependency

router = APIRouter(tags=["health"])


@router.get("/health/live")
def liveness() -> dict[str, str]:
    """Return a liveness indicator."""

    return {"status": "live"}


@router.get("/health/ready")
def readiness(session: Session = Depends(get_session_dependency)) -> dict[str, str]:
    """Return readiness information, ensuring the database connection is healthy."""

    session.execute(text("SELECT 1"))
    return {"status": "ready"}


@router.get("/metrics")
def metrics() -> Response:
    """Expose Prometheus metrics."""

    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
