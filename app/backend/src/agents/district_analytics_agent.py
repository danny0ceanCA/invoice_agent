"""District analytics agent implemented with iterative tool calling."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from html import escape
from typing import Any, Mapping, Sequence

import structlog
from openai import OpenAI
from pydantic import BaseModel
from sqlalchemy import text as sql_text
from sqlalchemy.engine import Engine

from app.backend.src.core.config import get_settings
from app.backend.src.db import get_engine
from app.backend.src.services.s3 import get_s3_client

LOGGER = structlog.get_logger(__name__)

DEFAULT_MODEL = "gpt-4.1-mini"
MAX_ITERATIONS = 8


class AgentResponse(BaseModel):
    """Standardised response payload returned to the caller."""

    text: str
    html: str
    rows: list[dict[str, Any]] | None = None


@dataclass
class AgentContext:
    """Runtime context shared between the workflow and tools."""

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
        except (TypeError, ValueError):  # pragma: no cover - defensive
            return None


@dataclass
class Tool:
    """Descriptor for a callable tool exposed to the model."""

    name: str
    description: str
    input_schema: Mapping[str, Any]
    handler: Any

    def schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "name": self.name,
            "description": self.description,
            "parameters": dict(self.input_schema),
        }

    def invoke(self, context: AgentContext, arguments: Mapping[str, Any]) -> Any:
        return self.handler(context, arguments)


class Workflow:
    """Coordinates model reasoning and tool usage."""

    def __init__(self, system_prompt: str, *, max_iterations: int = MAX_ITERATIONS) -> None:
        self.system_prompt = system_prompt
        self.max_iterations = max_iterations

    def execute(self, agent: "Agent", query: str, user_context: dict[str, Any]) -> AgentResponse:
        context = AgentContext(query=query, user_context=user_context or {})
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self.system_prompt},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "query": query,
                        "context": context.user_context,
                    }
                ),
            },
        ]

        for iteration in range(self.max_iterations):
            LOGGER.debug("agent_iteration_start", iteration=iteration)
            completion = agent.client.chat.completions.create(
                model=agent.model,
                messages=messages,
                temperature=0,
                response_format={"type": "json_object"},
            )
            message = completion.choices[0].message
            raw_content = message.content or ""
            messages.append({"role": "assistant", "content": raw_content})

            try:
                payload = json.loads(raw_content)
            except json.JSONDecodeError:
                LOGGER.warning("agent_invalid_json", iteration=iteration, content=raw_content)
                text = raw_content.strip()
                html = _safe_html(text)
                return AgentResponse(text=text, html=html, rows=context.last_rows)

            action = (payload.get("action") or "").lower()
            if action == "call_tool":
                tool_name = payload.get("tool")
                if not tool_name:
                    raise RuntimeError("Tool response missing name.")
                tool = agent.lookup_tool(tool_name)
                arguments = payload.get("arguments") or {}
                if not isinstance(arguments, Mapping):
                    raise RuntimeError("Tool arguments must be an object.")

                try:
                    tool_result = tool.invoke(context, arguments)
                    tool_payload = {"tool": tool.name, "result": tool_result}
                except Exception as exc:  # pragma: no cover - defensive
                    LOGGER.warning("tool_execution_failed", tool=tool.name, error=str(exc))
                    context.last_error = str(exc)
                    tool_payload = {"tool": tool.name, "error": str(exc)}
                    tool_result = None

                if isinstance(tool_result, list):
                    if tool_result and all(isinstance(item, Mapping) for item in tool_result):
                        context.last_rows = [dict(item) for item in tool_result]  # type: ignore[arg-type]
                    else:
                        context.last_rows = []
                elif tool_result is None:
                    # keep previous rows
                    pass
                else:
                    context.last_rows = None

                tool_message = json.dumps(tool_payload, default=_json_default)
                messages.append({"role": "tool", "name": tool.name, "content": tool_message})
                continue

            if action == "final":
                return _finalise_response(payload, context)

            LOGGER.warning("agent_unknown_action", action=action)
            text = raw_content.strip()
            return AgentResponse(text=text, html=_safe_html(text), rows=context.last_rows)

        raise RuntimeError("Agent workflow exceeded iteration limit.")


class Agent:
    """Agent orchestrating workflow execution with the OpenAI client."""

    def __init__(
        self,
        *,
        client: OpenAI,
        model: str,
        workflow: Workflow,
        tools: Sequence[Tool],
    ) -> None:
        self.client = client
        self.model = model
        self.workflow = workflow
        self.tools = list(tools)
        self._tool_lookup = {tool.name: tool for tool in self.tools}

    def lookup_tool(self, name: str) -> Tool:
        if name not in self._tool_lookup:
            raise RuntimeError(f"Unknown tool '{name}'.")
        return self._tool_lookup[name]

    def run(self, query: str, user_context: dict[str, Any]) -> AgentResponse:
        return self.workflow.execute(self, query, user_context)


def _json_default(value: Any) -> Any:
    if hasattr(value, "isoformat"):
        return value.isoformat()  # type: ignore[return-value]
    return value


def _safe_html(text: str) -> str:
    if not text:
        return "<p></p>"
    return f"<p>{escape(text)}</p>"


def _render_html_table(rows: Sequence[Mapping[str, Any]]) -> str:
    headers = list(rows[0].keys())
    header_html = "".join(f"<th>{escape(str(header))}</th>" for header in headers)
    body_rows: list[str] = []
    for row in rows:
        cells = "".join(f"<td>{escape(str(row.get(header, '')))}</td>" for header in headers)
        body_rows.append(f"<tr>{cells}</tr>")
    body_html = "".join(body_rows)
    return f"<table><thead><tr>{header_html}</tr></thead><tbody>{body_html}</tbody></table>"


def _coerce_rows(candidate: Any) -> list[dict[str, Any]] | None:
    if isinstance(candidate, list) and all(isinstance(item, Mapping) for item in candidate):
        return [dict(item) for item in candidate]  # type: ignore[arg-type]
    return None


def _finalise_response(payload: Mapping[str, Any], context: AgentContext) -> AgentResponse:
    text_value = str(payload.get("text") or "").strip()
    rows_value = _coerce_rows(payload.get("rows"))
    html_value = payload.get("html") if isinstance(payload.get("html"), str) else None

    rows: list[dict[str, Any]] | None = rows_value or context.last_rows

    if not text_value and rows:
        text_value = "See the table below for details."

    if rows:
        html = html_value or _render_html_table(rows)
    else:
        html = html_value or _safe_html(text_value)

    return AgentResponse(text=text_value or "", html=html, rows=rows)


def _apply_district_filter(query: str, district_id: int | None) -> tuple[str, dict[str, Any]]:
    parameters: dict[str, Any] = {}
    if district_id is None:
        return query, parameters

    parameters["district_id"] = district_id

    normalized = query.strip()
    normalized = normalized[:-1] if normalized.endswith(";") else normalized
    lower = normalized.lower()

    if "district_id" in lower:
        return normalized, parameters

    if " where " in lower:
        filtered = f"{normalized}\n  AND district_id = :district_id"
    else:
        filtered = f"{normalized}\nWHERE district_id = :district_id"

    return filtered, parameters


def _build_run_sql_tool(engine: Engine) -> Tool:
    description = "Execute a read-only SQL query against the analytics warehouse."
    schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Complete SQL statement starting with SELECT or WITH.",
            }
        },
        "required": ["query"],
        "additionalProperties": False,
    }

    def handler(context: AgentContext, arguments: Mapping[str, Any]) -> list[dict[str, Any]]:
        query = arguments.get("query")
        if not isinstance(query, str) or not query.strip():
            raise ValueError("SQL query must be a non-empty string.")

        normalized = query.lstrip().lower()
        if not (normalized.startswith("select") or normalized.startswith("with")):
            raise ValueError("Only SELECT and WITH statements are permitted.")

        filtered_query, parameters = _apply_district_filter(query, context.district_id)

        rows: list[dict[str, Any]] = []
        with engine.connect() as connection:
            result = connection.execute(sql_text(filtered_query), parameters)
            for row in result:
                rows.append(dict(row._mapping))

        return rows

    return Tool(name="run_sql", description=description, input_schema=schema, handler=handler)


def _build_list_s3_tool() -> Tool:
    description = "List invoice files stored in S3."
    schema = {
        "type": "object",
        "properties": {
            "prefix": {
                "type": "string",
                "description": "Key prefix to filter objects (e.g. 'invoices/').",
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
    }

    def handler(context: AgentContext, arguments: Mapping[str, Any]) -> list[dict[str, Any]]:
        prefix = arguments.get("prefix")
        if not isinstance(prefix, str):
            raise ValueError("prefix must be a string")

        max_items = arguments.get("max_items", 20)
        try:
            resolved_max = max(1, min(int(max_items), 500))
        except (TypeError, ValueError):
            resolved_max = 20

        client = get_s3_client()
        settings = get_settings()
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
                if len(objects) >= resolved_max:
                    return objects

            if len(objects) >= resolved_max:
                break

        return objects

    return Tool(name="list_s3", description=description, input_schema=schema, handler=handler)


def _build_system_prompt() -> str:
    return (
        "You are a district analytics assistant for school finance teams. "
        "Use the available tools to answer questions about invoices and spending. "
        "When writing SQL, use SQLite syntax including strftime for date grouping. "
        "Always respect any provided district_id by filtering queries with 'district_id = :district_id'. "
        "Decide between tools: use list_s3 for file listing requests, and run_sql for data analysis. "
        "Respond in JSON with either {\"action\": \"call_tool\", \"tool\": name, \"arguments\": {...}} "
        "or {\"action\": \"final\", \"text\": str, \"rows\": [..], \"html\": optional}. "
        "Keep summaries concise and reference table columns when relevant."
    )


def _build_agent() -> Agent:
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured.")

    client = OpenAI(api_key=settings.openai_api_key)
    engine = get_engine()
    workflow = Workflow(system_prompt=_build_system_prompt(), max_iterations=MAX_ITERATIONS)
    tools = [_build_run_sql_tool(engine), _build_list_s3_tool()]
    return Agent(client=client, model=DEFAULT_MODEL, workflow=workflow, tools=tools)


_AGENT: Agent | None = None


def _get_agent() -> Agent:
    global _AGENT
    if _AGENT is None:
        _AGENT = _build_agent()
    return _AGENT


def run_analytics_agent(query: str, user_context: dict[str, Any] | None = None) -> AgentResponse:
    if not isinstance(query, str) or not query.strip():
        raise ValueError("A query is required.")

    try:
        agent = _get_agent()
    except Exception as exc:  # pragma: no cover - configuration issue
        LOGGER.error("analytics_agent_init_failed", error=str(exc))
        raise

    return agent.run(query.strip(), user_context or {})


__all__ = ["AgentResponse", "run_analytics_agent", "AgentContext", "Tool", "Workflow", "Agent"]
