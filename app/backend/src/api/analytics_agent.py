"""Routes for the natural-language analytics agent endpoint."""

from __future__ import annotations
from collections.abc import Mapping
from typing import Any, Callable

import boto3
import structlog
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import create_engine, text

from agents import Agent, Runner, tool
from app.backend.src.core.config import get_settings
from app.backend.src.core.security import get_current_user
from app.backend.src.models import User

LOGGER = structlog.get_logger(__name__)

router = APIRouter(prefix="/analytics", tags=["analytics"])
_AGENT: Agent | None = None
_AGENT_INITIALIZED = False


def _build_agent_functions(settings: Any) -> list[Callable[..., Any]]:
    """Create the callable tool functions supplied to the Agent SDK."""

    engine = create_engine(settings.database_url, future=True)
    s3_client = boto3.client(
        "s3",
        region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
    )

    @tool
    def district_invoice_database(query: str) -> list[dict[str, Any]]:
        """Execute a read-only SQL query against the district invoice database."""

        normalized = (query or "").strip()
        if not normalized:
            raise ValueError("SQL query is required.")

        if not normalized.lower().startswith("select"):
            raise ValueError("Only read-only SELECT queries are permitted.")

        if ";" in normalized.rstrip(";"):
            raise ValueError("Multiple SQL statements are not supported.")

        with engine.connect() as connection:
            result = connection.execute(text(normalized))
            rows = [dict(row._mapping) for row in result]

        return rows

    @tool
    def district_invoice_file_storage(prefix: str = "", max_items: int = 100) -> list[dict[str, Any]]:
        """List invoice files stored in the district's S3 bucket."""

        paginator = s3_client.get_paginator("list_objects_v2")
        try:
            page_iterator = paginator.paginate(
                Bucket=settings.aws_s3_bucket,
                Prefix=prefix or "",
                PaginationConfig={"MaxItems": max(1, max_items)},
            )
        except (BotoCoreError, ClientError) as exc:  # pragma: no cover - defensive
            raise RuntimeError("Unable to access invoice file storage.") from exc

        items: list[dict[str, Any]] = []
        for page in page_iterator:
            for obj in page.get("Contents", []):
                if len(items) >= max_items:
                    return items

                last_modified = obj.get("LastModified")
                items.append(
                    {
                        "key": obj.get("Key"),
                        "size": obj.get("Size"),
                        "last_modified": last_modified.isoformat() if last_modified else None,
                        "storage_class": obj.get("StorageClass"),
                    }
                )

        return items

    return [district_invoice_database, district_invoice_file_storage]


def _ensure_agent_available() -> Agent | None:
    """Create the analytics agent instance when the SDK and config are present."""
    global _AGENT_INITIALIZED, _AGENT

    if _AGENT_INITIALIZED:
        return _AGENT

    _AGENT_INITIALIZED = True

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
            LOGGER.warning("analytics_agent_missing_configuration", missing=missing)
            return None

        agent_functions = _build_agent_functions(settings)

        _AGENT = Agent(
            name="district_analytics_agent",
            instructions=(
                "You have two tools: run_sql(query) and list_s3(prefix).\n"
                "Use run_sql for any question involving totals, months, vendors, students, spending, invoices, amounts, etc.\n"
                "Use SELECT queries only.\n"
                "Use list_s3 for questions about invoice files or document retrieval.\n"
                "After calling a tool, analyze the returned data and produce a human-readable answer.\n"
                "If the data is tabular, produce an HTML <table> with headers.\n"
                "Always return a final natural-language summary plus the HTML table when appropriate."
            ),
            functions=agent_functions,
        )

        # Extra guard to ensure valid Agent instance
        if not hasattr(_AGENT, "name"):
            LOGGER.warning("analytics_agent_invalid_instance")
            return None

        LOGGER.info(
            "analytics_agent_initialized",
            database=required_settings["database_url"],
            bucket=required_settings["aws_s3_bucket"],
        )

    except Exception as exc:  # defensive logging
        LOGGER.warning("analytics_agent_initialization_failed", error=str(exc))
        _AGENT = None

    return _AGENT


def _normalize_agent_result(result: Any) -> tuple[str, str, dict[str, Any]]:
    """Convert the agent SDK response into display text, HTML, and extras."""
    if isinstance(result, Mapping):
        text = str(result.get("text") or "")
        html = str(result.get("html") or "")
        extras = {k: v for k, v in result.items() if k not in {"text", "html"}}
        return text, html, extras

    if hasattr(result, "model_dump"):
        payload = result.model_dump()
        return _normalize_agent_result(payload)

    if hasattr(result, "dict"):
        payload = result.dict()
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
        sdk_result = await Runner.run(agent, query)

        # Convert the SDK Result object to a dict for normalization
        if hasattr(sdk_result, "final_output"):
            result = {
                "text": sdk_result.final_output,
                "html": f"<p>{sdk_result.final_output}</p>",
            }
        else:
            result = sdk_result

    except Exception as exc:
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


if Agent is not None:
    _ensure_agent_available()
