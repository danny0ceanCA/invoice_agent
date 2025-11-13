"""FastAPI routes that expose analytics agents."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.backend.src.core.security import get_current_user
from app.backend.src.models import User
from app.backend.src.agents.district_analytics_agent import AgentResponse, run_analytics_agent

LOGGER = structlog.get_logger(__name__)

router = APIRouter(prefix="/agents", tags=["agents"])


class AnalyticsAgentRequest(BaseModel):
    query: str = Field(..., description="Natural language analytics question")
    context: dict[str, Any] | None = Field(default=None, description="Optional context overrides")


@router.post("/analytics", response_model=AgentResponse)
def analytics_agent_endpoint(
    payload: AnalyticsAgentRequest,
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Execute the district analytics agent and return its structured output."""

    query = payload.query.strip()
    if not query:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A query is required.",
        )

    context: dict[str, Any] = dict(payload.context or {})
    if user and getattr(user, "district_id", None) is not None:
        context.setdefault("district_id", user.district_id)

    try:
        response = run_analytics_agent(query=query, user_context=context)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive logging
        LOGGER.error("analytics_agent_endpoint_failure", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Analytics agent is temporarily unavailable.",
        ) from exc

    return response.model_dump()


__all__ = ["router"]
