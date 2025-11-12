"""AI-powered analytics router for natural language queries."""

from __future__ import annotations

from typing import Any, Mapping

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.backend.src.core.config import get_settings
from app.backend.src.core.security import get_current_user
from app.backend.src.models import User

try:  # pragma: no cover - optional dependency in some environments
    from agentsdk import Agent
except ImportError:  # pragma: no cover - graceful fallback when SDK missing
    Agent = None  # type: ignore[assignment]


LOGGER = structlog.get_logger(__name__)

router = APIRouter(prefix="/analytics", tags=["analytics"])


class AnalyticsAgentRequest(BaseModel):
    """Expected payload from the frontend analytics assistant."""

    query: str

    def normalized_query(self) -> str:
        """Return the sanitized query string or raise if invalid."""

        candidate = (self.query or "").strip()
        if not candidate:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A natural-language query is required.",
            )
        return candidate


class AnalyticsAgentResponse(BaseModel):
    """Normalized response returned to the frontend assistant."""

    text: str
    html: str
    csv_url: str | None = None


def _initialize_agent() -> Agent | None:
    """Instantiate the analytics agent if the SDK is available."""

    if Agent is None:  # pragma: no cover - handled at runtime
        LOGGER.warning("analytics_agent_sdk_unavailable")
        return None

    settings = get_settings()
    connection_url = settings.database_url

    return Agent(
        name="district_analytics_agent",
        description="Provides natural-language analytics over invoices, vendors, and students",
        tools=[
            {
                "type": "sql",
                "connection": connection_url,
                "tables": ["invoices", "students", "vendors"],
                "readonly": True,
            },
            {
                "type": "custom",
                "name": "render_table",
                "description": "Render JSON query results as HTML table",
            },
        ],
    )


_ANALYTICS_AGENT = _initialize_agent()


def _ensure_agent_available() -> Agent:
    """Return the configured analytics agent or raise a service error."""

    if _ANALYTICS_AGENT is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Analytics agent is currently unavailable.",
        )
    return _ANALYTICS_AGENT


def _normalize_agent_result(result: Any) -> AnalyticsAgentResponse:
    """Convert arbitrary agent SDK responses into the public schema."""

    if isinstance(result, AnalyticsAgentResponse):
        return result

    text = ""
    html = ""
    csv_url: str | None = None

    if isinstance(result, Mapping):
        text = str(result.get("text") or "")
        html = str(result.get("html") or "")
        csv_url_value = result.get("csv_url") or result.get("csvUrl")
        if isinstance(csv_url_value, str) and csv_url_value:
            csv_url = csv_url_value
    elif hasattr(result, "model_dump"):
        data = result.model_dump()  # type: ignore[call-arg]
        return _normalize_agent_result(data)
    elif hasattr(result, "dict"):
        data = result.dict()  # type: ignore[call-arg]
        return _normalize_agent_result(data)
    else:
        # Fall back to treating the result as plain text
        text = str(result) if result is not None else ""

    return AnalyticsAgentResponse(text=text, html=html, csv_url=csv_url)


@router.post("/agent", response_model=AnalyticsAgentResponse)
async def run_agent(
    request: AnalyticsAgentRequest,
    user: User = Depends(get_current_user),
) -> AnalyticsAgentResponse:
    """Execute the analytics agent against the provided natural language query."""

    query = request.normalized_query()

    agent = _ensure_agent_available()
    context = {"district_id": user.district_id}

    try:
        result = agent.query(prompt=query, context=context)
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - defensive logging
        LOGGER.error(
            "analytics_agent_query_failed",
            error=str(exc),
            district_id=user.district_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Analytics agent failed to process the request.",
        ) from exc

    return _normalize_agent_result(result)
