"""Routes for the natural-language analytics agent endpoint."""

from __future__ import annotations
from collections.abc import Mapping
from typing import Any, Callable

import boto3
import structlog
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import create_engine, text

from html import escape

try:  # pragma: no cover - fallback for environments without the Agents SDK
    from agents import Agent, Runner, function_tool
except ImportError:  # pragma: no cover - graceful degradation for local tests
    Agent = None  # type: ignore[assignment]
    Runner = None  # type: ignore[assignment]

    def function_tool(func: Callable[..., Any]) -> Callable[..., Any]:
        return func
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

    @function_tool
    def run_sql(query: str) -> list[dict[str, Any]]:
        """Execute a read-only SQL query against the district invoice database."""

        normalized = (query or "").strip()
        if not normalized:
            raise ValueError("SQL query is required.")

        lowered = normalized.lower()
        if not lowered.startswith("select"):
            raise ValueError("Only read-only SELECT queries are permitted.")

        if ";" in normalized.rstrip(";"):
            raise ValueError("Multiple SQL statements are not supported.")

        with engine.connect() as connection:
            result = connection.execute(text(normalized))
            rows = [dict(row._mapping) for row in result]

        return rows

    @function_tool
    def list_invoice_files(prefix: str = "", max_items: int = 100) -> list[dict[str, Any]]:
        """List invoice files stored in the district's S3 bucket."""

        sanitized_prefix = (prefix or "").strip()
        try:
            candidate_max = int(max_items)
        except (TypeError, ValueError):
            candidate_max = 100

        safe_max_items = max(1, min(candidate_max, 500))

        paginator = s3_client.get_paginator("list_objects_v2")
        try:
            page_iterator = paginator.paginate(
                Bucket=settings.aws_s3_bucket,
                Prefix=sanitized_prefix,
                PaginationConfig={"MaxItems": safe_max_items},
            )
        except (BotoCoreError, ClientError) as exc:  # pragma: no cover - defensive
            raise RuntimeError("Unable to access invoice file storage.") from exc

        items: list[dict[str, Any]] = []
        for page in page_iterator:
            for obj in page.get("Contents", []):
                if len(items) >= safe_max_items:
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

    return [run_sql, list_invoice_files]


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
                "You are the District Analytics Assistant for school finance leaders.\n"
                "You have access to two tools and must decide when to use them:\n"
                "1. run_sql(query: str) -> rows: Executes read-only SQL SELECT queries "
                "against the district invoice database. Use it for any question about "
                "invoices, spending, totals, trends, vendors, students, or amounts. "
                "All queries MUST start with SELECT and never modify data.\n"
                "2. list_invoice_files(prefix: str = \"\", max_items: int = 100) -> list: "
                "Lists invoice-related files from S3. Use it when the user asks about "
                "files, documents, storage locations, or attachments.\n"
                "Reason step-by-step, call the appropriate tool, and inspect the "
                "results before answering. Provide clear SQL that targets the requested "
                "information and includes filters or ordering as needed.\n"
                "After every tool call, summarize the findings. When returning tabular "
                "data, include an HTML <table> with column headers in your final "
                "response along with a narrative summary.\n"
                "If no tool is required, answer directly but still provide actionable "
                "context."
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


def _render_html_table(rows: list[Mapping[str, Any]]) -> str:
    """Render a list of mapping rows as an HTML table."""

    if not rows:
        return "<table><thead><tr><th>No results</th></tr></thead><tbody></tbody></table>"

    headers = list(rows[0].keys())
    header_html = "".join(f"<th>{escape(str(header))}</th>" for header in headers)

    body_rows = []
    for row in rows:
        cells = []
        for header in headers:
            value = row.get(header, "")
            cells.append(f"<td>{escape(str(value))}</td>")
        body_rows.append(f"<tr>{''.join(cells)}</tr>")

    body_html = "".join(body_rows)
    return f"<table><thead><tr>{header_html}</tr></thead><tbody>{body_html}</tbody></table>"


def _normalize_agent_result(result: Any) -> tuple[str, str, dict[str, Any]]:
    """Convert the agent SDK response into display text, HTML, and extras."""

    if hasattr(result, "model_dump"):
        result = result.model_dump()
    elif hasattr(result, "dict"):
        result = result.dict()

    extras: dict[str, Any] = {}

    if isinstance(result, Mapping):
        text = str(result.get("text") or "")
        html = str(result.get("html") or "")
        extras = {k: v for k, v in result.items() if k not in {"text", "html"}}

        if not html:
            for key in ("rows", "data", "results"):
                candidate = extras.get(key)
                if isinstance(candidate, list) and candidate and all(
                    isinstance(item, Mapping) for item in candidate
                ):
                    html = _render_html_table(candidate)
                    break

        if not text and html:
            text = "See the table below for details."

        return text, html, extras

    if isinstance(result, list):
        if not result:
            html = _render_html_table([])
            text = "No results were returned for that query."
            extras = {"data": result}
            return text, html, extras

        if all(isinstance(item, Mapping) for item in result):
            html = _render_html_table(result)
            text = "See the table below for details."
            extras = {"data": result}
            return text, html, extras

        text = str(result)
        html = f"<p>{escape(text)}</p>"
        return text, html, extras

    text = str(result) if result is not None else ""
    html = f"<p>{escape(text)}</p>" if text else ""
    return text, html, extras


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
        if Runner is not None and hasattr(Runner, "run"):
            sdk_result = await Runner.run(agent, query)
            result = getattr(sdk_result, "final_output", sdk_result)
        else:
            context: dict[str, Any] = {}
            district_id = getattr(user, "district_id", None)
            if district_id is not None:
                context["district_id"] = district_id

            if hasattr(agent, "query"):
                legacy_result = agent.query(prompt=query, context=context)
                result = legacy_result
            else:  # pragma: no cover - defensive fallback
                raise RuntimeError("Agent runner is unavailable.")

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
