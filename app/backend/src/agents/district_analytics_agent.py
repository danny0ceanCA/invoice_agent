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

DB_SCHEMA_HINT = """
You are querying a SQLite database with these key tables:

1) invoices
   - id INTEGER PRIMARY KEY
   - vendor_id INTEGER NOT NULL  -- FK to vendors.id
   - upload_id INTEGER NOT NULL  -- FK to uploads.id
   - student_name VARCHAR(255) NOT NULL
   - invoice_number VARCHAR(128) NOT NULL
   - invoice_code VARCHAR(64) NOT NULL
   - service_month VARCHAR(32) NOT NULL      -- e.g. '2025-11' or 'Nov 2025'
   - invoice_date DATETIME NOT NULL
   - total_hours FLOAT NOT NULL
   - total_cost FLOAT NOT NULL               -- use this for money amounts / invoice totals
   - status VARCHAR(50) NOT NULL
   - pdf_s3_key VARCHAR(512) NOT NULL
   - created_at DATETIME NOT NULL

2) invoice_line_items
   - id INTEGER PRIMARY KEY
   - invoice_id INTEGER NOT NULL             -- FK to invoices.id
   - student VARCHAR(255) NOT NULL
   - clinician VARCHAR(255) NOT NULL
   - service_code VARCHAR(50) NOT NULL
   - hours FLOAT NOT NULL
   - rate FLOAT NOT NULL
   - cost FLOAT NOT NULL                     -- line-item amount
   - service_date VARCHAR(32) NOT NULL

3) vendors
   - id INTEGER PRIMARY KEY
   - name VARCHAR(255) NOT NULL
   - contact_email VARCHAR(255) NOT NULL
   - district_id INTEGER NOT NULL            -- use this to scope invoices by district
   - contact_name VARCHAR(255) NOT NULL
   - phone_number VARCHAR(255) NOT NULL
   - remit_to_address TEXT
   - district_key VARCHAR(64)
   - remit_to_street VARCHAR(255)
   - remit_to_city VARCHAR(100)
   - remit_to_state VARCHAR(32)
   - remit_to_postal_code VARCHAR(20)

Important patterns:
- District scoping for invoices is done via vendors:
  JOIN invoices i ON i.vendor_id = v.id
  WHERE v.district_id = :district_id

- There is NO column called amount_due, invoice_total, balance_due, due_amount, etc.
  For invoice totals use invoices.total_cost.
  For line item amounts use invoice_line_items.cost.
"""


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
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": dict(self.input_schema),
            },
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
                tools=[tool.schema() for tool in agent.tools],
                tool_choice="auto",
                temperature=0,
            )
            message = completion.choices[0].message
            tool_calls = message.tool_calls or []
            assistant_message: dict[str, Any] = {
                "role": "assistant",
                "content": message.content or "",
            }

            if tool_calls:
                assistant_tool_calls: list[dict[str, Any]] = []
                for tool_call in tool_calls:
                    assistant_tool_calls.append(
                        {
                            "id": tool_call.id,
                            "type": tool_call.type,
                            "function": {
                                "name": tool_call.function.name,
                                "arguments": tool_call.function.arguments,
                            },
                        }
                    )
                assistant_message["tool_calls"] = assistant_tool_calls
            messages.append(assistant_message)

            if tool_calls:
                for tool_call in tool_calls:
                    tool_name = tool_call.function.name
                    arguments_json = tool_call.function.arguments or "{}"
                    try:
                        arguments = json.loads(arguments_json)
                    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
                        LOGGER.warning(
                            "agent_tool_arguments_invalid_json",
                            iteration=iteration,
                            tool=tool_name,
                            error=str(exc),
                        )
                        arguments = {}

                    tool = agent.lookup_tool(tool_name)

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
                            context.last_rows = [
                                dict(item) for item in tool_result
                            ]  # type: ignore[arg-type]
                        else:
                            context.last_rows = []
                    elif tool_result is None:
                        # keep previous rows
                        pass
                    else:
                        context.last_rows = None

                    tool_message = json.dumps(tool_payload, default=_json_default)
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": tool_message,
                        }
                    )
                continue

            raw_content = message.content or ""

            try:
                payload = json.loads(raw_content)
            except json.JSONDecodeError:
                LOGGER.warning("agent_invalid_json", iteration=iteration, content=raw_content)
                text = raw_content.strip()
                html = _safe_html(text)
                return AgentResponse(text=text, html=html, rows=context.last_rows)

            return _finalise_response(payload, context)

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
    """
    Return the query and parameter dict.

    We DO NOT blindly inject 'district_id = :district_id' anymore, because only
    some tables (e.g. vendors, users, districts, district_memberships) have
    that column. For invoices, district scoping must be implemented as a JOIN
    against vendors (vendors.district_id).

    Behavior:
    - If district_id is provided, we add it to the parameters dict so the
      model can reference :district_id in its own SQL.
    - We leave the query text unchanged.
    """
    parameters: dict[str, Any] = {}
    if district_id is not None:
        parameters["district_id"] = district_id

    normalized = query.strip()
    normalized = normalized[:-1] if normalized.endswith(";") else normalized
    return normalized, parameters


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
        "You are a strict analytics agent for a school district finance system. "
        "You answer questions about invoices, vendors, students, and spending. "
        "All final answers MUST be returned as a JSON object with keys text, rows, and html.\n\n"
        f"{DB_SCHEMA_HINT}\n\n"
        "Tool usage rules:\n"
        "- If the user asks about invoice files, PDFs, or S3 paths → use list_s3.\n"
        "- If the user asks about amounts, spending, totals, dates, vendors, students, or summaries → use run_sql.\n"
        "- When writing SQL, use SQLite syntax. Use strftime('%Y-%m', invoice_date) to bucket by year/month.\n"
        "- For invoice-level queries, ALWAYS scope by district via the vendors table:\n"
        "  JOIN invoices i ON i.vendor_id = v.id\n"
        "  WHERE v.district_id = :district_id\n"
        "- Never invent column names. Only use the columns listed in the schema hint.\n\n"
        "Examples:\n"
        "1) Highest invoice total for November 2025 for a district:\n"
        "SELECT i.invoice_number, i.student_name, i.total_cost AS highest_amount_due\n"
        "FROM invoices i\n"
        "JOIN vendors v ON v.id = i.vendor_id\n"
        "WHERE v.district_id = :district_id\n"
        "  AND strftime('%Y-%m', i.invoice_date) = '2025-11'\n"
        "ORDER BY i.total_cost DESC\n"
        "LIMIT 1;\n\n"
        "2) Total spend for November 2025 for a district:\n"
        "SELECT SUM(i.total_cost) AS total_spend\n"
        "FROM invoices i\n"
        "JOIN vendors v ON v.id = i.vendor_id\n"
        "WHERE v.district_id = :district_id\n"
        "  AND strftime('%Y-%m', i.invoice_date) = '2025-11';\n\n"
        "Behavioral rules:\n"
        "- Do NOT output natural language outside of JSON.\n"
        "- Use the tools via OpenAI function calling; do not fabricate tool results.\n"
        "- ALWAYS finish with a single JSON object: {\"text\": str, \"rows\": list|None, \"html\": str}.\n"
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
