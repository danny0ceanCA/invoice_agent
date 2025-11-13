"""Routes for the natural-language analytics agent endpoint."""

from __future__ import annotations

from html import escape
import asyncio
import json
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
        result = connection.execute(sql_text(query))
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


TOOLS = [
    {
        "type": "function",
        "function": {
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
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_s3",
            "description": "List objects in the analytics S3 bucket.",
            "parameters": {
                "type": "object",
                "properties": {
                    "prefix": {"type": "string"},
                    "max_items": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 500,
                    },
                },
            },
        },
    },
]


def _extract_final_text(response):
    """Extract message text from Responses API output format."""

    output_items = getattr(response, "output", None) or []
    for item in output_items:
        if getattr(item, "type", None) == "message":
            contents = getattr(item, "content", []) or []
            for c in contents:
                if getattr(c, "type", None) == "output_text":
                    return c.text
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


async def _process_tool_calls(tool_calls: Any) -> list[dict[str, str]]:
    """Execute tool calls requested by the model."""

    outputs: list[dict[str, str]] = []
    for call in getattr(tool_calls, "tool_calls", []) or []:
        function = getattr(call, "function", None)
        name = getattr(function, "name", "")
        arguments_raw = getattr(function, "arguments", "{}")
        try:
            arguments = json.loads(arguments_raw or "{}")
        except json.JSONDecodeError:
            arguments = {}

        LOGGER.info("analytics_agent_tool_invocation", tool=name, arguments=arguments)

        try:
            if name == "run_sql":
                if "query" not in arguments:
                    output = json.dumps(
                        {"error": "the run_sql tool requires a query parameter"},
                        default=_json_default,
                    )
                    outputs.append({"tool_call_id": call.id, "output": output})
                    continue
                result = await asyncio.to_thread(run_sql, arguments["query"])
            elif name == "list_s3":
                prefix = str(arguments.get("prefix", ""))
                max_items = arguments.get("max_items", 100)
                result = await asyncio.to_thread(list_s3, prefix, max_items)
            else:
                raise ValueError(f"Unknown tool requested: {name}")
            output = json.dumps(result, default=_json_default)
        except Exception as exc:  # pragma: no cover - defensive logging
            LOGGER.error("analytics_agent_tool_failed", tool=name, error=str(exc))
            output = json.dumps(
                {"error": f"Tool {name} failed: {exc}"},
                default=_json_default,
            )

        outputs.append({"tool_call_id": call.id, "output": output})

    return outputs


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
        "Return concise explanations and include JSON-formatted tabular data when appropriate."
    )

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": [{"type": "input_text", "text": system_prompt}]}
    ]

    if context:
        context_text = json.dumps(context, default=_json_default)
        messages.append(
            {
                "role": "system",
                "content": [
                    {
                        "type": "input_text",
                        "text": f"User context (JSON): {context_text}",
                    }
                ],
            }
        )

    messages.append(
        {"role": "user", "content": [{"type": "input_text", "text": query}]}
    )

    create_kwargs: dict[str, Any] = {}

    if context:
        create_kwargs["metadata"] = {"context": json.dumps(context, default=_json_default)}

    response = await asyncio.to_thread(
        client.responses.create,
        model=DEFAULT_MODEL,
        input=messages,
        tools=TOOLS,
        tool_choice="auto",
        **create_kwargs,
    )

    while True:
        status = getattr(response, "status", "completed")

        if status == "completed":
            return response

        if status == "requires_action":
            required_action = getattr(response, "required_action", None)
            if not required_action:
                raise RuntimeError("Model requested action but no details were provided.")

            tool_outputs = await _process_tool_calls(
                getattr(required_action, "submit_tool_outputs", None)
            )

            if not tool_outputs:
                raise RuntimeError("Model requested tools but none could be executed.")

            response = await asyncio.to_thread(
                client.responses.submit_tool_outputs,
                response.id,
                tool_outputs=tool_outputs,
            )
            continue

        if status in {"failed", "cancelled"}:
            raise RuntimeError(f"Analytics run ended with status '{status}'.")

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

    # FIXED: extract proper output from Responses API
    final_text = _extract_final_text(response)
    parsed_output = _try_parse_json(final_text)
    final_output = parsed_output if parsed_output is not None else final_text
    text, html = _format_final_output(final_output)

    response_payload: dict[str, Any] = {"text": text, "html": html}

    if isinstance(final_output, Mapping):
        for key, value in final_output.items():
            response_payload.setdefault(key, value)
    elif isinstance(final_output, list) and final_output and all(
        isinstance(item, Mapping) for item in final_output
    ):
        response_payload.setdefault("rows", final_output)

    return response_payload


__all__ = ["run_agent"]
