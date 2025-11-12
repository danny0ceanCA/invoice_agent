"""Routes for the natural-language analytics agent endpoint."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, status

from agents import Runner

from app.backend.src.core.config import get_settings
from app.backend.src.core.security import get_current_user
from app.backend.src.models import User

LOGGER = structlog.get_logger(__name__)

try:  # pragma: no cover - optional dependency in certain environments
    from agents import Agent
except ImportError:  # pragma: no cover - executed when SDK is absent
    Agent = None  # type: ignore[assignment]


router = APIRouter(prefix="/analytics", tags=["analytics"])
_AGENT: Agent | None = None
_AGENT_INITIALIZED = False


def _build_agent_tools(settings: Any) -> list[dict[str, Any]]:
    """Return the tool configuration supplied to the Agent SDK."""

    tools: list[dict[str, Any]] = []

    tools.append(
        {
            "type": "sql",
            "name": "district_invoice_database",
            "description": (
                "Execute read-only SQL queries against the district invoice database "
                "to retrieve invoices, vendors, students, and approval details."
            ),
            "connection": settings.database_url,
            "readonly": True,
        }
    )

    tools.append(
        {
            "type": "s3",
            "name": "district_invoice_file_storage",
            "description": (
                "Access the AWS S3 bucket storing vendor invoice files. List invoice "
                "objects by vendor or month prefixes and generate presigned download "
                "URLs valid for one hour."
            ),
            "bucket": settings.aws_s3_bucket,
            "region": settings.aws_region,
            "access_key_id": settings.aws_access_key_id,
            "secret_access_key": settings.aws_secret_access_key,
            "presign_ttl_seconds": 3600,
            "local_cache_path": settings.local_storage_path,
        }
    )

    return tools


def _ensure_agent_available() -> Agent | None:
    """Create the analytics agent instance when the SDK and config are present."""

    global _AGENT_INITIALIZED, _AGENT

    if _AGENT_INITIALIZED:
        return _AGENT

    _AGENT_INITIALIZED = True

    if Agent is None:
        LOGGER.info("analytics_agent_sdk_missing")
        return None

    try:
        settings = get_settings()

        required_settings = {
            "database_url": settings.database_url,
            "aws_region": settings.aws_region,
            "aws_s3_bucket": settings.aws_s3_bucket,
            "aws_access_key_id": settings.aws_access_key_id,
            "aws_secret_access_key": settings.aws_secret_access_key,
        }

        missing = [key for key, value in required_settings.items() if not value]
        if missing:
            LOGGER.warning(
                "analytics_agent_missing_configuration",
                missing=missing,
            )
            return None

        agent_tools = _build_agent_tools(settings)

        _AGENT = Agent(
            name="district_analytics_agent",
            instructions=(
                "You are an AI analytics assistant that answers finance and operations "
                "questions using district data."
            ),
        )
        _AGENT.tools = agent_tools
        LOGGER.info(
            "analytics_agent_initialized",
            database=required_settings["database_url"],
            bucket=required_settings["aws_s3_bucket"],
        )
    except Exception as exc:  # pragma: no cover - defensive logging
        LOGGER.warning("analytics_agent_initialization_failed", error=str(exc))
        _AGENT = None

    return _AGENT


def _normalize_agent_result(result: Any) -> tuple[str, str, dict[str, Any]]:
    """Convert the agent SDK response into display text, HTML, and extras."""

    if isinstance(result, Mapping):
        text = str(result.get("text") or "")
        html = str(result.get("html") or "")
        extras = {
            key: value
            for key, value in result.items()
            if key not in {"text", "html"}
        }
        return text, html, extras

    if hasattr(result, "model_dump"):
        payload = result.model_dump()  # type: ignore[call-arg]
        return _normalize_agent_result(payload)

    if hasattr(result, "dict"):
        payload = result.dict()  # type: ignore[call-arg]
        return _normalize_agent_result(payload)

    text = str(result) if result is not None else ""
    return text, "", {}


@router.post("/agent")
async def run_agent(request: dict, user: User = Depends(get_current_user)) -> dict[str, Any]:
    """Execute the analytics agent and format its response."""

    query = str(request.get("query") or "").strip()
    if not query:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A natural-language query is required.",
        )

    agent = _ensure_agent_available()

    if agent is None:
        text = (
            "Analytics assistant is temporarily unavailable. "
            "Please try again later."
        )
        html = f"<p>{text} Received query: {query}</p>"
        return {"text": text, "html": html}

    try:
        result = Runner.run_sync(agent, query)
    except Exception as exc:  # pragma: no cover - defensive logging
        LOGGER.error("analytics_agent_query_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Analytics agent failed to process the request.",
        ) from exc

    text, html, extras = _normalize_agent_result(result)
    if not html:
        html = f"<p>{text}</p>" if text else "<p>No details available.</p>"

    response: dict[str, Any] = {"text": text, "html": html}
    response.update(extras)
    return response


if Agent is not None:  # pragma: no cover - eager initialization when SDK available
    _ensure_agent_available()
