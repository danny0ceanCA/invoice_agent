"""AI-powered analytics router for natural language queries."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, status

from app.backend.src.core.config import get_settings
from app.backend.src.core.security import get_current_user
from app.backend.src.models import User

try:  # pragma: no cover - optional dependency in some environments
    from agentsdk import Agent
except ImportError:  # pragma: no cover - graceful fallback when SDK missing
    Agent = None  # type: ignore[assignment]


LOGGER = structlog.get_logger(__name__)

router = APIRouter(prefix="/analytics", tags=["analytics"])


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


@router.post("/agent")
async def run_agent(request: dict[str, Any], user: User = Depends(get_current_user)) -> dict[str, str]:
    """Execute the analytics agent against the provided natural language query."""

    query = (request or {}).get("query", "")
    if not isinstance(query, str) or not query.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A natural-language query is required.",
        )

    agent = _ensure_agent_available()
    context = {"district_id": user.district_id}

    try:
        result = agent.query(prompt=query.strip(), context=context)
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

    text = getattr(result, "text", "")
    html = getattr(result, "html", "")

    return {"text": text or "", "html": html or ""}
