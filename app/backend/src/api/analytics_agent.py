"""Routes for the natural-language analytics agent endpoint."""

from __future__ import annotations

from html import escape
import asyncio
import json
import time
from typing import Any, Iterable, Mapping

import boto3
import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from openai import OpenAI
from sqlalchemy import create_engine, text as sql_text
from sqlalchemy.engine import Engine

from app.backend.src.core.config import get_settings
from app.backend.src.core.security import get_current_user
from app.backend.src.models import User

LOGGER = structlog.get_logger(__name__)

router = APIRouter(prefix="/analytics", tags=["analytics"])

DEFAULT_MODEL = "gpt-4.1-mini"
DEFAULT_POLL_INTERVAL = 0.5

_SQL_ENGINE: Engine | None = None
_OPENAI_CLIENT: OpenAI | None = None
_OPENAI_API_KEY: str | None = None
_S3_CLIENT: Any | None = None


def _build_context(user: User | None, request_context: Any) -> dict[str, Any]:
    """Merge authenticated user details with any caller-provided context."""
    context: dict[str, Any] = {}
    if isinstance(request_context, Mapping):
        for key, value in request_context.items():
            if isinstance(key, str):
                context[key] = value
    if user and getattr(user, "district_id", None) is not None:
        context.setdefault("district_id", user.district_id)
    return context


def _get_sql_engine(settings) -> Engine:
    """Return a cached SQLAlchemy engine."""
    global _SQL_ENGINE
    if _SQL_ENGINE is None:
        _SQL_ENGINE = create_engine(settings.database_url)
    return _SQL_ENGINE


def _get_openai_client(settings) -> OpenAI:
    """Return a cached OpenAI client configured with the API key."""
    global _OPENAI_CLIENT, _OPENAI_API_KEY
    api_key = settings.openai_api_key
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured.")
    if _OPENAI_CLIENT is None or api_key != _OPENAI_API_KEY:
        _OPENAI_CLIENT = OpenAI(api_key=api_key)
        _OPENAI_API_KEY = api_key
    return _OPENAI_CLIENT


def _get_s3_client(settings):
    """Return a cached boto3 S3 client configured from settings."""
    global _S3_CLIENT
    if _S3_CLIENT is None:
        session = boto3.session.Session(
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.aws_region,
        )
        _S3_CLIENT = session.client("s3")
    return _S3_CLIENT


def _json_default(value: Any) -> str:
    """Serialize otherwise non-JSON-serializable values."""
    if hasattr(value, "isoformat"):
        return value.isoformat()  # type: ignore[return-value]
    return str(value)


def run_sql(query: str) -> list[dict[str, Any]]:
    """Execute a read-only SQL query using SQLAlchemy."""
    if not isinstance(query, str) or not query.strip():
        raise ValueError("SQL query must be a non-empty string.")
    normalized = query.strip().lower()
    if not (normalized.startswith("select") or normalized.startswith("with")):
        raise ValueError("Only SELECT queries are permitted.")

    settings = get_settings()
    engine = _get_sql_engine(settings)

    rows: list[dict[str, Any]] = []
    with engine.connect() as connection:
        start = time.monotonic()
        result = connection.execute(sql_text(query))
        LOGGER.info("latency", stage="SQL Execution", duration_ms=(time.monotonic() - start) * 1000)
        for row in result:
            rows.append(dict(row._mapping))
    return rows


def list_s3(prefix: str, max_items: int = 100) -> list[dict[str, Any]]:
    """List objects in the configured S3 bucket."""
    settings = get_settings()
    client = _get_s3_client(settings)

    resolved_prefix = prefix or ""
    try:
        resolved_max = max(1, min(int(max_items), 500))
    except (TypeError, ValueError):
        resolved_max = 100

    paginator = client.get_paginator("list_objects_v2")
    page_iterator = paginator.paginate(
        Bucket=settings.aws_s3_bucket,
        Prefix=resolved_prefix,
    )

    objects: list[dict[str, Any]] = []
    for page in page_iterator:
        for entry in page.get("Contents", []) or []:
            objects.append(
                {
                    "key": entry.get("Key"),
                    "size": entry.get("Size"),
                    "last_modified": _json_default(entry.get("LastModified")),
                }
            )
            if len(objects) >= resolved_max:
                return objects

        if len(objects) >= resolved_max:
            break

    return objects


# Flat tool shape compatible with your current SDK usage
TOOLS = [
    {
        "type": "function",
        "name": "run_sql",
        "description": "Execute a read-only SQL SELECT query.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "A complete SQL SELECT statement.",
                }
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "list_s3",
        "description": "List invoice files in your S3 bucket.",
        "parameters": {
            "type": "object",
            "properties": {
                "prefix": {
                    "type": "string",
                    "description": "Prefix for S3 object lookup.",
                },
                "max_items": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 500,
                    "default": 100,
                },
            },
            "required": ["prefix"],
            "additionalProperties": False,
        },
    }
]


def _extract_final_output(response: Any) -> Any:
    """Extract the final model output from the Responses API payload."""
    # Allow synthetic final payloads to pass straight through.
    if isinstance(response, Mapping) and any(k in response for k in ("text", "rows", "html")):
        return response

    output_items = getattr(response, "output", None) or []
    text_segments: list[str] = []

    for item in output_items:
        item_type = getattr(item, "type", None)
        if item_type is None and isinstance(item, Mapping):
            item_type = item.get("type")
        if item_type != "message":
            continue

        contents = getattr(item, "content", None)
        if contents is None and isinstance(item, Mapping):
            contents = item.get("content")
        contents = contents or []

        for content in contents:
            content_type = getattr(content, "type", None)
            if content_type is None and isinstance(content, Mapping):
                content_type = content.get("type")
            if content_type != "output_text":
                continue

            text_value = getattr(content, "text", None)
            if text_value is None and isinstance(content, Mapping):
                text_value = content.get("text")
            if not isinstance(text_value, str):
                continue

            normalized = text_value.strip()
            if normalized and normalized[0] in "[{":
                try:
                    return json.loads(normalized)
                except json.JSONDecodeError:
                    pass
            text_segments.append(text_value)

    if text_segments:
        return "".join(text_segments)
    return ""


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


def _try_parse_json(value: str) -> Any:
    """Parse JSON content when the payload appears to be structured data."""
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if not normalized or normalized[0] not in "[{":
        return None
    try:
        return json.loads(normalized)
    except json.JSONDecodeError:
        return None


def _format_final_output(final_output: Any) -> tuple[str, str]:
    """Convert the agent's final output into text and HTML payloads."""
    if isinstance(final_output, str):
        parsed_output = _try_parse_json(final_output)
        if parsed_output is not None:
            return _format_final_output(parsed_output)
    # strings
        text = final_output
        html = f"<p>{escape(text)}</p>" if text else ""
        return text, html

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

        html_value = final_output.get("html")
        text_value = final_output.get("text")
        if html_value is not None:
            text = str(text_value) if text_value is not None else ""
            return text, str(html_value)

        if text_value is not None:
            text = str(text_value)
            return text, f"<p>{escape(text)}</p>" if text else ""

    if final_output is None:
        return "", ""

    text = str(final_output)
    html = f"<p>{escape(text)}</p>" if text else ""
    return text, html


def _collect_tool_calls_container(response: Any) -> Any | None:
    """
    Return an object that has `.tool_calls` (attr or dict), from either:
      - response.required_action.submit_tool_outputs.tool_calls, or
      - response.output items with type == "function_call".
    """
    # Typical path: requires_action
    ra = getattr(response, "required_action", None)
    if ra is not None:
        st = getattr(ra, "submit_tool_outputs", None)
        if st is not None:
            if getattr(st, "tool_calls", None):
                return st
            if isinstance(st, Mapping) and st.get("tool_calls"):
                return st

    # Fallback path: function calls in output even when status is 'completed'
    output_items = getattr(response, "output", None) or []
    pending = [it for it in output_items if getattr(it, "type", None) == "function_call"]
    if pending:
        return {"tool_calls": pending}
    return None


async def _process_tool_calls_to_contents(tool_calls: Any) -> list[dict[str, str]]:
    """
    Execute the model-requested tool calls and return content items of type 'tool_result'
    suitable for a Responses.create continuation (previous_response_id).

    Each item shape:
      {"type": "tool_result", "tool_call_id": "...", "output": "<string JSON result>"}
    """
    # Normalize container
    if isinstance(tool_calls, dict):
        calls = tool_calls.get("tool_calls", []) or []
    else:
        calls = getattr(tool_calls, "tool_calls", []) or []

    contents: list[dict[str, str]] = []

    for call in calls:
        if isinstance(call, Mapping):
            function = call.get("function")
            call_id = call.get("id")
        else:
            function = getattr(call, "function", None)
            call_id = getattr(call, "id", None)

        if isinstance(function, Mapping):
            name = function.get("name")
            args_raw = function.get("arguments")
        else:
            name = getattr(function, "name", None) if function else None
            args_raw = getattr(function, "arguments", None) if function else None

        try:
            args = json.loads(args_raw or "{}")
        except Exception:
            args = {}

        try:
            if name == "run_sql":
                query = str(args.get("query", "")).strip()
                result = await asyncio.to_thread(run_sql, query)
            elif name == "list_s3":
                prefix = str(args.get("prefix", "")).strip()
                max_items = int(args.get("max_items", 100))
                result = await asyncio.to_thread(list_s3, prefix, max_items)
            else:
                result = {"error": f"Unknown tool {name}"}
        except Exception as exc:
            result = {"error": str(exc)}

        contents.append(
            {
                "type": "tool_result",
                "tool_call_id": call_id,
                # IMPORTANT: field must be 'output' and it must be a STRING
                "output": json.dumps(result, default=_json_default),
            }
        )

    return contents


async def _execute_responses_workflow(query: str, context: Mapping[str, Any]) -> Any:
    """Run the analytics workflow using the OpenAI Responses API."""
    settings = get_settings()
    client = _get_openai_client(settings)

    poll_interval = getattr(settings, "poll_interval_seconds", None)
    try:
        poll_interval_seconds = max(
            0.1, float(poll_interval) if poll_interval is not None else DEFAULT_POLL_INTERVAL
        )
    except (TypeError, ValueError):
        poll_interval_seconds = DEFAULT_POLL_INTERVAL

    system_prompt = (
        "You are an analytics assistant. Use the available tools to answer questions. "
        "Return concise explanations and include JSON-formatted tabular data when appropriate. "
        "Database dialect = SQLite. When filtering dates use strftime('%Y', <date_col>) and "
        "strftime('%m', <date_col>) (e.g., strftime('%Y','invoice_date')='2025' and strftime('%m','invoice_date')='11'). "
        "When listing invoice files, use list_s3 with an appropriate 'prefix' like 'invoices/' and respect 'max_items' when given."
    )

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": [{"type": "input_text", "text": system_prompt}]}
    ]

    # Optional visibility into the tools being sent
    try:
        LOGGER.info("analytics_agent_tools_shape", tools=TOOLS)
    except Exception:
        pass

    if context:
        context_text = json.dumps(context, default=_json_default)
        messages.append(
            {
                "role": "system",
                "content": [{"type": "input_text", "text": f"User context (JSON): {context_text}"}],
            }
        )

    messages.append({"role": "user", "content": [{"type": "input_text", "text": query}]})

    def _create_response() -> Any:
        return client.responses.create(
            model=DEFAULT_MODEL,
            input=messages,
            tools=TOOLS,
            tool_choice="auto",
        )

    response = await asyncio.to_thread(_create_response)

    while True:
        # If the model asked for tools (either via required_action or directly in output), run them
        container = _collect_tool_calls_container(response)
        if container:
            tool_result_contents = await _process_tool_calls_to_contents(container)
            if not tool_result_contents:
                raise RuntimeError("Model requested tools but none could be executed.")

            # Continue the run by sending back tool_result content for each call
            def _continue_with_tool_results() -> Any:
                return client.responses.create(
                    model=DEFAULT_MODEL,
                    previous_response_id=response.id,
                    input=[{"role": "developer", "content": tool_result_contents}],
                    tools=TOOLS,
                    tool_choice="auto",
                )

            LOGGER.info(
                "analytics_agent_submitting_tool_results",
                previous_response_id=response.id,
                num_results=len(tool_result_contents),
                tool_call_ids=[c.get("tool_call_id") for c in tool_result_contents],
            )

            response = await asyncio.to_thread(_continue_with_tool_results)
            # Loop again: model may chain more tools or produce a final message
            continue

        status = getattr(response, "status", "completed")
        if status in {"failed", "cancelled"}:
            raise RuntimeError(f"Analytics run ended with status '{status}'.")
        if status == "completed":
            return response

        # Otherwise, still in progress — poll
        await asyncio.sleep(poll_interval_seconds)
        response = await asyncio.to_thread(client.responses.retrieve, response.id)


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
        context = _build_context(user, request.get("context"))
        response = await _execute_responses_workflow(query, context)
        # DEBUG LOGGING – dump the raw Responses API object
        try:
            from pprint import pformat
            LOGGER.warning("DEBUG_OPENAI_RESPONSE_RAW", raw=pformat(response))
        except Exception as e:
            LOGGER.warning("DEBUG_OPENAI_RESPONSE_RAW_FAILED", error=str(e))
    except RuntimeError as exc:
        LOGGER.warning("analytics_agent_unavailable", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Analytics assistant is temporarily unavailable. Please try again later.",
        ) from exc
    except Exception as exc:  # pragma: no cover - defensive logging
        LOGGER.error("analytics_agent_query_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Analytics agent failed to process the request.",
        ) from exc

    final_output = _extract_final_output(response)
    text, html = _format_final_output(final_output)

    response_payload: dict[str, Any] = {"text": text, "html": html}

    rows_payload: list[Mapping[str, Any]] | None = None
    if isinstance(final_output, Mapping):
        rows_value = final_output.get("rows")
        if isinstance(rows_value, list) and all(isinstance(item, Mapping) for item in rows_value):
            rows_payload = rows_value
    elif isinstance(final_output, list) and all(isinstance(item, Mapping) for item in final_output):
        rows_payload = final_output

    if rows_payload is not None:
        response_payload["rows"] = rows_payload

    return response_payload


__all__ = ["run_agent"]
