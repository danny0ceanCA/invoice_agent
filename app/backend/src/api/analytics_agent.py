"""Routes for the natural-language analytics agent endpoint."""

from __future__ import annotations

from html import escape
from typing import Any, Iterable, Mapping

import boto3
import structlog
from agents import Agent, Runner, tool
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import create_engine, text

from app.backend.src.core.config import get_settings
from app.backend.src.core.security import get_current_user
from app.backend.src.models import User

LOGGER = structlog.get_logger(__name__)

router = APIRouter(prefix="/analytics", tags=["analytics"])
_AGENT: Agent | None = None


def _build_agent_functions(settings: Any) -> list[Any]:
    """Create the callable tool functions supplied to the Agent SDK."""

    engine = create_engine(settings.database_url, future=True)
    s3_client = boto3.client(
        "s3",
        region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
    )

    @tool
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

    @tool
    def list_s3(prefix: str = "", max_items: int = 100) -> list[dict[str, Any]]:
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

    return [run_sql, list_s3]


def _ensure_agent_available() -> Agent:
    """Create the analytics agent instance when configuration is present."""

    global _AGENT
    if _AGENT is not None:
        return _AGENT

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
        raise RuntimeError("Analytics agent configuration is incomplete.")

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
            "2. list_s3(prefix: str = \"\", max_items: int = 100) -> list: Lists "
            "invoice-related files from S3. Use it when the user asks about files, "
            "documents, storage locations, or attachments.\n"
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

    LOGGER.info(
        "analytics_agent_initialized",
        database=required_settings["database_url"],
        bucket=required_settings["aws_s3_bucket"],
    )

    return _AGENT


def _render_html_table(rows: Iterable[Mapping[str, Any]]) -> str:
    """Render a list of mapping rows as an HTML table."""

    rows = list(rows)
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


def _format_final_output(final_output: Any) -> tuple[str, str]:
    """Convert the agent's final output into text and HTML payloads."""

    if isinstance(final_output, list) and final_output and all(
        isinstance(item, Mapping) for item in final_output
    ):
        html = _render_html_table(final_output)
        return "See the table below for details.", html

    if isinstance(final_output, list) and not final_output:
        html = _render_html_table([])
        return "No results were returned for that query.", html

    if isinstance(final_output, Mapping):
        rows = final_output.get("rows")
        if isinstance(rows, list) and rows and all(isinstance(item, Mapping) for item in rows):
            html = _render_html_table(rows)
            return str(final_output.get("text") or "See the table below for details."), html

        text_value = final_output.get("text")
        if text_value is not None:
            text = str(text_value)
            return text, f"<p>{escape(text)}</p>" if text else ""

    if final_output is None:
        return "", ""

    text = str(final_output)
    html = f"<p>{escape(text)}</p>" if text else ""
    return text, html


@router.post("/agent")
async def run_agent(request: dict, user: User = Depends(get_current_user)) -> dict[str, Any]:
    """Execute the analytics agent and format its response."""

    query = str(request.get("query") or "").strip()
    if not query:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A natural-language query is required.",
        )

    try:
        agent = _ensure_agent_available()
    except RuntimeError as exc:
        LOGGER.warning("analytics_agent_unavailable", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Analytics assistant is temporarily unavailable. Please try again later.",
        ) from exc

    _ = user  # Ensures authentication via dependency while avoiding unused variable warnings.

    try:
        sdk_result = await Runner.run(agent, query)
    except Exception as exc:  # pragma: no cover - defensive logging
        LOGGER.error("analytics_agent_query_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Analytics agent failed to process the request.",
        ) from exc

    final_output = getattr(sdk_result, "final_output", sdk_result)
    text, html = _format_final_output(final_output)

    if isinstance(final_output, list) and final_output and all(
        isinstance(item, Mapping) for item in final_output
    ):
        text = text or "See the table below for details."
    elif isinstance(final_output, str) and text:
        html = html or f"<p>{escape(text)}</p>"

    return {"text": text, "html": html}
