"""FastAPI routing for analytics agent operations."""

from __future__ import annotations

from html import escape
from typing import Any

import structlog
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.backend.src.agents.district_analytics_agent import (
    AgentResponse,
    run_analytics_agent as _execute_analytics_agent,
)
from app.backend.src.core.security import get_current_user
from app.backend.src.db import get_session_dependency
from app.backend.src.models import District, User

LOGGER = structlog.get_logger(__name__)

router = APIRouter(prefix="/agents", tags=["agents"])


class AnalyticsAgentRequest(BaseModel):
    """Request payload for invoking the analytics agent."""

    query: str = Field(..., description="Natural language analytics query")
    context: dict[str, Any] | None = Field(
        default=None, description="Optional execution context overrides"
    )


def run_analytics_agent(query: str, user_context: dict[str, Any]) -> dict[str, Any]:
    """Execute the analytics agent and return a JSON-serialisable payload."""

    response = _execute_analytics_agent(query=query, user_context=user_context)
    return response.model_dump()


@router.post("/analytics", response_model=AgentResponse)
def analytics_agent_endpoint(
    payload: AnalyticsAgentRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session_dependency),
) -> dict[str, Any]:
    """Execute the district analytics agent and return the structured output."""

    query = (payload.query or "").strip()
    if not query:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A query is required.",
        )

    context: dict[str, Any] = dict(payload.context or {})
    district_id = context.get("district_id")

    if user and getattr(user, "district_id", None) is not None and district_id is None:
        district_id = user.district_id

    district = session.get(District, district_id) if district_id is not None else None
    district_key = (district.district_key if district is not None else None) or None

    context.update({
        "district_key": district_key,
        "district_id": district_id,
    })

    try:
        return run_analytics_agent(query=query, user_context=context)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except (SQLAlchemyError, BotoCoreError, ClientError, NoCredentialsError) as exc:
        LOGGER.warning("analytics_agent_data_error", error=str(exc))
        message = "Unable to complete the requested analytics operation."
        return AgentResponse(text=message, html=_as_html(message), rows=None).model_dump()
    except Exception as exc:  # pragma: no cover - defensive logging
        LOGGER.error("analytics_agent_unexpected_error", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Analytics agent is temporarily unavailable.",
        ) from exc


def _as_html(text: str) -> str:
    if not text:
        return "<p></p>"
    return f"<p>{escape(text)}</p>"


__all__ = ["router", "run_analytics_agent"]
