"""Routes for the natural-language analytics agent endpoint."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.backend.src.core.config import get_settings
from app.backend.src.core.security import get_current_user
from app.backend.src.models import User

LOGGER = structlog.get_logger(__name__)

try:  # pragma: no cover - optional dependency in certain environments
    from agentsdk import Agent
except ImportError:  # pragma: no cover - executed when SDK is absent
    Agent = None  # type: ignore[assignment]


router = APIRouter(prefix="/analytics", tags=["analytics"])


class AnalyticsAgentRequest(BaseModel):
    """Schema describing the incoming analytics agent request."""

    query: str = Field(..., description="Natural-language analytics prompt")

    def cleaned_query(self) -> str:
        """Return a stripped query or raise a validation error."""

        value = (self.query or "").strip()
        if not value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The query field cannot be empty.",
            )
        return value


class AnalyticsAgentResponse(BaseModel):
    """Normalized response returned to the frontend."""

    text: str
    html: str


_AGENT: Agent | None = None
_AGENT_INITIALIZED = False


def _initialize_agent() -> Agent | None:
    """Lazily create the analytics agent instance when available."""

    global _AGENT_INITIALIZED, _AGENT

    if _AGENT_INITIALIZED:
        return _AGENT

    _AGENT_INITIALIZED = True

    if Agent is None:
        LOGGER.info("analytics_agent_sdk_missing")
        return None

    try:
        settings = get_settings()
        _AGENT = Agent(
            name="district_analytics_agent",
            description="Answers district finance and operations questions.",
            tools=[
                {
                    "type": "sql",
                    "connection": settings.database_url,
                    "readonly": True,
                }
            ],
        )
    except Exception as exc:  # pragma: no cover - defensive logging
        LOGGER.warning("analytics_agent_initialization_failed", error=str(exc))
        _AGENT = None

    return _AGENT


def _normalize_agent_result(result: Any) -> tuple[str, str]:
    """Convert the agent SDK response into display text and HTML."""

    if isinstance(result, Mapping):
        text = str(result.get("text") or "")
        html = str(result.get("html") or "")
        return text, html

    if hasattr(result, "model_dump"):
        payload = result.model_dump()  # type: ignore[call-arg]
        return _normalize_agent_result(payload)

    if hasattr(result, "dict"):
        payload = result.dict()  # type: ignore[call-arg]
        return _normalize_agent_result(payload)

    text = str(result) if result is not None else ""
    return text, ""


@router.post("/agent", response_model=AnalyticsAgentResponse)
async def run_agent(
    payload: AnalyticsAgentRequest,
    user: User = Depends(get_current_user),
) -> AnalyticsAgentResponse:
    """Execute the analytics agent and format its response."""

    query = payload.cleaned_query()
    agent = _initialize_agent()

    if agent is None:
        text = "Analytics assistant is not configured."
        html = f"<p>{text} Received query: {query}</p>"
        return AnalyticsAgentResponse(text=text, html=html)

    try:
        result = agent.query(prompt=query, context={"district_id": user.district_id})
    except Exception as exc:  # pragma: no cover - defensive logging
        LOGGER.error("analytics_agent_query_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Analytics agent failed to process the request.",
        ) from exc

    text, html = _normalize_agent_result(result)
    if not html:
        html = f"<p>{text}</p>" if text else "<p>No details available.</p>"

    return AnalyticsAgentResponse(text=text, html=html)
