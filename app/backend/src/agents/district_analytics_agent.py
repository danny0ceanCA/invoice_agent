"""Analytics Agent built on OpenAI AgentKit primitives."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from html import escape
from typing import Any, Callable, Iterable, Mapping

import boto3
import structlog
from openai import OpenAI
from pydantic import BaseModel
from sqlalchemy import create_engine, text as sql_text
from sqlalchemy.engine import Engine

from app.backend.src.core.config import get_settings

LOGGER = structlog.get_logger(__name__)

DEFAULT_MODEL = "gpt-4.1-mini"
MAX_ITERATIONS = 8

_SQL_ENGINE: Engine | None = None
_OPENAI_CLIENT: OpenAI | None = None
_OPENAI_API_KEY: str | None = None
_S3_CLIENT: Any | None = None


class AgentResponse(BaseModel):
    """Standardised response payload returned to the caller."""

    text: str
    html: str
    rows: list[dict[str, Any]] | None = None


@dataclass
class AnalyticsToolContext:
    """Runtime context provided to tool handlers."""

    query: str
    user_context: dict[str, Any] = field(default_factory=dict)
    last_rows: list[dict[str, Any]] | None = None
    last_error: str | None = None

    @property
    def district_id(self) -> int | None:
        value = self.user_context.get("district_id")
        try:
            if value is None:
                return None
            return int(value)
        except (TypeError, ValueError):
            return None


def _json_default(value: Any) -> Any:
    if hasattr(value, "isoformat"):
        return value.isoformat()  # type: ignore[return-value]
    return str(value)


def _render_html_table(rows: Iterable[Mapping[str, Any]]) -> str:
    """Render tabular rows as a HTML table."""

    rows = list(rows)
    if not rows:
        return "<table><thead><tr><th>No results</th></tr></thead><tbody></tbody></table>"

    headers = list(rows[0].keys())
    header_html = "".join(f"<th>{escape(str(header))}</th>" for header in headers)

    body_cells: list[str] = []
    for row in rows:
        row_cells = []
        for header in headers:
            value = row.get(header, "")
            row_cells.append(f"<td>{escape(str(value))}</td>")
        body_cells.append(f"<tr>{''.join(row_cells)}</tr>")

    body_html = "".join(body_cells)
    return f"<table><thead><tr>{header_html}</tr></thead><tbody>{body_html}</tbody></table>"


def _safe_html(text: str) -> str:
    if not text:
        return ""
    return f"<p>{escape(text)}</p>"


def _parse_json(value: str) -> Any:
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return None


def _format_agent_response(raw_output: Any, context: AnalyticsToolContext) -> AgentResponse:
    """Convert model output into AgentResponse."""

    if isinstance(raw_output, AgentResponse):
        return raw_output

    if isinstance(raw_output, str):
        parsed = _parse_json(raw_output.strip()) if raw_output.strip() else None
        if parsed is None:
            text = raw_output.strip()
            html = _safe_html(text)
            rows = context.last_rows
            return AgentResponse(text=text, html=html, rows=rows)
        raw_output = parsed

    if isinstance(raw_output, Mapping):
        text_value = str(raw_output.get("text", "")) if "text" in raw_output else ""
        html_value = raw_output.get("html")
        rows_value = raw_output.get("rows")

        rows: list[dict[str, Any]] | None = None
        if isinstance(rows_value, list) and all(isinstance(item, Mapping) for item in rows_value):
            rows = [dict(item) for item in rows_value]  # type: ignore[arg-type]

        html: str
        if isinstance(html_value, str) and html_value.strip():
            html = html_value
        elif rows:
            html = _render_html_table(rows)
        else:
            html = _safe_html(text_value)

        if not text_value and rows:
            text_value = "See the table below for details."

        return AgentResponse(text=text_value, html=html, rows=rows)

    if isinstance(raw_output, list) and raw_output and all(
        isinstance(item, Mapping) for item in raw_output
    ):
        rows = [dict(item) for item in raw_output]  # type: ignore[arg-type]
        html = _render_html_table(rows)
        return AgentResponse(text="See the table below for details.", html=html, rows=rows)

    if raw_output is None and context.last_rows:
        html = _render_html_table(context.last_rows)
        return AgentResponse(text="See the table below for details.", html=html, rows=context.last_rows)

    text = str(raw_output) if raw_output is not None else ""
    return AgentResponse(text=text, html=_safe_html(text), rows=context.last_rows)


class Tool:
    """Minimal Tool abstraction compatible with AgentKit expectations."""

    def __init__(
        self,
        name: str,
        description: str,
        input_schema: Mapping[str, Any],
        handler: Callable[[AnalyticsToolContext, Mapping[str, Any]], Any],
    ) -> None:
        self.name = name
        self.description = description
        self.input_schema = dict(input_schema)
        self._handler = handler

    def schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "name": self.name,
            "description": self.description,
            "parameters": self.input_schema,
        }

    def invoke(self, context: AnalyticsToolContext, arguments: Mapping[str, Any]) -> Any:
        return self._handler(context, arguments)


class Workflow:
    """Workflow coordinates LLM reasoning with tool invocations."""

    def __init__(self, system_prompt: str, max_iterations: int = MAX_ITERATIONS) -> None:
        self.system_prompt = system_prompt
        self.max_iterations = max_iterations

    def execute(
        self,
        agent: "Agent",
        query: str,
        user_context: dict[str, Any],
    ) -> AgentResponse:
        context = AnalyticsToolContext(query=query, user_context=user_context or {})
        messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": [
                    {"type": "input_text", "text": self.system_prompt},
                    {
                        "type": "input_text",
                        "text": (
                            "Return JSON with keys text, html, rows. "
                            "Prefer HTML tables when tabular data is returned."
                        ),
                    },
                ],
            }
        ]

        if user_context:
            messages.append(
                {
                    "role": "developer",
                    "content": [
                        {
                            "type": "input_text",
                            "text": f"User context JSON: {json.dumps(user_context, default=_json_default)}",
                        }
                    ],
                }
            )

        messages.append(
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": query,
                    }
                ],
            }
        )

        tool_schemas = [tool.schema() for tool in agent.tools]
        executed_call_signatures: set[str] = set()

        for iteration in range(self.max_iterations):
            LOGGER.info("district_analytics_agent_iteration", iteration=iteration)
            response = agent.client.responses.create(
                model=agent.model,
                input=messages,
                tools=tool_schemas,
                tool_choice="auto",
            )

            tool_calls = _extract_tool_calls(response)
            if tool_calls:
                LOGGER.info("district_analytics_agent_tool_calls", count=len(tool_calls))
                for call in tool_calls:
                    signature = f"{call.name}:{call.arguments}:{call.call_id}"
                    if signature in executed_call_signatures:
                        continue
                    executed_call_signatures.add(signature)

                    tool = agent.get_tool(call.name)
                    if tool is None:
                        payload = {
                            "tool": call.name,
                            "error": f"Unknown tool '{call.name}'",
                        }
                        messages.append(
                            {
                                "role": "developer",
                                "content": [
                                    {
                                        "type": "input_text",
                                        "text": json.dumps(payload),
                                    }
                                ],
                            }
                        )
                        continue

                    try:
                        arguments = json.loads(call.arguments or "{}")
                        if not isinstance(arguments, Mapping):
                            raise ValueError("Tool arguments must be an object.")
                    except Exception as exc:  # pragma: no cover - defensive
                        arguments = {}
                        payload = {
                            "tool": call.name,
                            "error": f"Unable to parse arguments: {exc}",
                        }
                        messages.append(
                            {
                                "role": "developer",
                                "content": [
                                    {
                                        "type": "input_text",
                                        "text": json.dumps(payload),
                                    }
                                ],
                            }
                        )
                        continue

                    try:
                        result = tool.invoke(context, arguments)
                        context.last_error = None
                    except Exception as exc:  # pragma: no cover - defensive
                        LOGGER.warning(
                            "district_analytics_agent_tool_error",
                            tool=tool.name,
                            error=str(exc),
                        )
                        result = {"error": str(exc)}
                        context.last_error = str(exc)

                    if isinstance(result, list) and result and all(
                        isinstance(item, Mapping) for item in result
                    ):
                        context.last_rows = [dict(item) for item in result]  # type: ignore[arg-type]
                    elif isinstance(result, dict) and "rows" in result:
                        rows_value = result.get("rows")
                        if isinstance(rows_value, list) and all(
                            isinstance(item, Mapping) for item in rows_value
                        ):
                            context.last_rows = [dict(item) for item in rows_value]  # type: ignore[arg-type]
                    elif isinstance(result, dict) and "error" in result:
                        context.last_rows = None

                    messages.append(
                        {
                            "role": "developer",
                            "content": [
                                {
                                    "type": "input_text",
                                    "text": json.dumps(
                                        {
                                            "tool": tool.name,
                                            "arguments": arguments,
                                            "result": result,
                                        },
                                        default=_json_default,
                                    ),
                                }
                            ],
                        }
                    )

                continue

            final_output = _extract_final_output(response)
            if final_output is not None:
                LOGGER.info("district_analytics_agent_completed")
                return _format_agent_response(final_output, context)

            messages.append(
                {
                    "role": "developer",
                    "content": [
                        {
                            "type": "input_text",
                            "text": "No answer produced. Please try summarising previous tool results.",
                        }
                    ],
                }
            )

        raise RuntimeError("Agent workflow exceeded iteration limit.")


class Agent:
    """Agent orchestrates workflow execution with the OpenAI client."""

    def __init__(self, client: OpenAI, model: str, workflow: Workflow, tools: list[Tool]):
        self.client = client
        self.model = model
        self.workflow = workflow
        self.tools = tools
        self._tool_map = {tool.name: tool for tool in tools}

    def get_tool(self, name: str) -> Tool | None:
        return self._tool_map.get(name)

    def run(self, query: str, user_context: dict[str, Any]) -> AgentResponse:
        return self.workflow.execute(self, query, user_context)


@dataclass
class ToolCall:
    name: str
    arguments: str
    call_id: str | None = None


def _extract_tool_calls(response: Any) -> list[ToolCall]:
    """Extract tool calls from a Responses API payload."""

    tool_calls: list[ToolCall] = []
    output_items = getattr(response, "output", None) or []

    for item in output_items:
        item_type = getattr(item, "type", None) or getattr(item, "get", lambda _: None)("type")
        if isinstance(item, Mapping):
            item_type = item.get("type")

        if item_type in {"tool_call", "function_call"}:
            function = getattr(item, "function", None)
            if isinstance(item, Mapping):
                function = item.get("function", function)
            name = None
            arguments = "{}"
            if function:
                name = getattr(function, "name", None)
                if isinstance(function, Mapping):
                    name = function.get("name", name)
                arguments = getattr(function, "arguments", arguments)
                if isinstance(function, Mapping):
                    arguments = function.get("arguments", arguments)
            call_id = getattr(item, "id", None)
            if isinstance(item, Mapping):
                call_id = item.get("id", call_id)
            if name:
                tool_calls.append(ToolCall(name=name, arguments=arguments or "{}", call_id=call_id))
            continue

        if item_type != "message":
            continue

        contents = getattr(item, "content", None)
        if isinstance(item, Mapping):
            contents = item.get("content", contents)
        contents = contents or []
        for content in contents:
            content_type = getattr(content, "type", None)
            if isinstance(content, Mapping):
                content_type = content.get("type", content_type)

            if content_type not in {"tool_call", "function_call"}:
                continue

            function = getattr(content, "function", None)
            if isinstance(content, Mapping):
                function = content.get("function", function)
            name = None
            arguments = "{}"
            if function:
                name = getattr(function, "name", None)
                if isinstance(function, Mapping):
                    name = function.get("name", name)
                arguments = getattr(function, "arguments", arguments)
                if isinstance(function, Mapping):
                    arguments = function.get("arguments", arguments)
            call_id = getattr(content, "id", None)
            if isinstance(content, Mapping):
                call_id = content.get("id", call_id)
            if name:
                tool_calls.append(ToolCall(name=name, arguments=arguments or "{}", call_id=call_id))

    return tool_calls


def _extract_final_output(response: Any) -> Any:
    output_items = getattr(response, "output", None) or []
    text_segments: list[str] = []

    for item in output_items:
        item_type = getattr(item, "type", None)
        if isinstance(item, Mapping):
            item_type = item.get("type", item_type)

        if item_type != "message":
            continue

        contents = getattr(item, "content", None)
        if isinstance(item, Mapping):
            contents = item.get("content", contents)
        contents = contents or []

        for content in contents:
            content_type = getattr(content, "type", None)
            if isinstance(content, Mapping):
                content_type = content.get("type", content_type)

            if content_type != "output_text":
                continue

            text_value = getattr(content, "text", None)
            if isinstance(content, Mapping):
                text_value = content.get("text", text_value)
            if isinstance(text_value, str):
                text_segments.append(text_value)

    if text_segments:
        combined = "".join(text_segments).strip()
        if combined:
            parsed = _parse_json(combined) if combined[0] in "[{" else None
            if parsed is not None:
                return parsed
            return combined

    return None


def _get_sql_engine(settings) -> Engine:
    global _SQL_ENGINE
    if _SQL_ENGINE is None:
        _SQL_ENGINE = create_engine(settings.database_url)
    return _SQL_ENGINE


def _get_openai_client(settings) -> OpenAI:
    global _OPENAI_CLIENT, _OPENAI_API_KEY
    api_key = settings.openai_api_key
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured.")

    if _OPENAI_CLIENT is None or api_key != _OPENAI_API_KEY:
        _OPENAI_CLIENT = OpenAI(api_key=api_key)
        _OPENAI_API_KEY = api_key
    return _OPENAI_CLIENT


def _get_s3_client(settings):
    global _S3_CLIENT
    if _S3_CLIENT is None:
        session = boto3.session.Session(
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.aws_region,
        )
        _S3_CLIENT = session.client("s3")
    return _S3_CLIENT


def _apply_district_scoping(query: str, district_id: int | None) -> str:
    if district_id is None:
        return query

    replacements = ["{{district_id}}", "{district_id}", ":district_id"]
    for token in replacements:
        if token in query:
            return query.replace(token, str(district_id))

    return f"WITH district_scope AS (SELECT {district_id} AS district_id)\n{query}"


def _run_sql_handler(context: AnalyticsToolContext, arguments: Mapping[str, Any]) -> list[dict[str, Any]]:
    query = str(arguments.get("query", "")).strip()
    if not query:
        raise ValueError("SQL query must be provided.")

    normalized = query.lstrip().lower()
    if not (normalized.startswith("select") or normalized.startswith("with")):
        raise ValueError("Only SELECT or WITH queries are allowed.")

    scoped_query = _apply_district_scoping(query, context.district_id)

    settings = get_settings()
    engine = _get_sql_engine(settings)

    rows: list[dict[str, Any]] = []
    with engine.connect() as connection:
        result = connection.execute(sql_text(scoped_query))
        for row in result:
            rows.append(dict(row._mapping))

    return rows


def _list_s3_handler(context: AnalyticsToolContext, arguments: Mapping[str, Any]) -> list[dict[str, Any]]:
    prefix = str(arguments.get("prefix", "")).strip()
    if not prefix:
        raise ValueError("prefix is required")
    max_items_raw = arguments.get("max_items", 20)
    try:
        max_items = max(1, min(int(max_items_raw), 500))
    except (TypeError, ValueError):
        max_items = 20

    settings = get_settings()
    client = _get_s3_client(settings)

    paginator = client.get_paginator("list_objects_v2")
    page_iterator = paginator.paginate(Bucket=settings.aws_s3_bucket, Prefix=prefix)

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
            if len(objects) >= max_items:
                return objects
        if len(objects) >= max_items:
            break

    return objects


def _build_agent() -> Agent:
    settings = get_settings()
    client = _get_openai_client(settings)

    run_sql_tool = Tool(
        name="run_sql",
        description="Execute a read-only SQL query using the analytics database (SQLite dialect).",
        input_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Full SQL SELECT statement (SQLite dialect).",
                }
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        handler=_run_sql_handler,
    )

    list_s3_tool = Tool(
        name="list_s3",
        description="List invoice files from the district S3 bucket.",
        input_schema={
            "type": "object",
            "properties": {
                "prefix": {
                    "type": "string",
                    "description": "Prefix to filter invoice keys (e.g. invoices/).",
                },
                "max_items": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 500,
                    "default": 20,
                },
            },
            "required": ["prefix"],
            "additionalProperties": False,
        },
        handler=_list_s3_handler,
    )

    workflow = Workflow(
        system_prompt=(
            "You are the district analytics assistant. "
            "Interpret natural language questions, decide whether to query SQL or list S3 objects, "
            "and provide accurate summaries. Use SQLite syntax (strftime('%Y', column)). "
            "When answering, always return JSON with keys text, html, rows."
        )
    )

    return Agent(client=client, model=DEFAULT_MODEL, workflow=workflow, tools=[run_sql_tool, list_s3_tool])


_AGENT: Agent | None = None


def _get_agent() -> Agent:
    global _AGENT
    if _AGENT is None:
        _AGENT = _build_agent()
    return _AGENT


def run_analytics_agent(query: str, user_context: dict[str, Any] | None = None) -> AgentResponse:
    query = (query or "").strip()
    if not query:
        raise ValueError("A query is required for the analytics agent.")

    context = dict(user_context or {})

    try:
        agent = _get_agent()
        return agent.run(query=query, user_context=context)
    except Exception as exc:
        LOGGER.error("district_analytics_agent_failure", error=str(exc))
        text = f"Analytics agent failed: {exc}"
        return AgentResponse(text=text, html=_safe_html(text), rows=None)


__all__ = ["AgentResponse", "run_analytics_agent"]
