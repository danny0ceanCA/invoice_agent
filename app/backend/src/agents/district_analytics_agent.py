"""District analytics agent implemented with iterative tool calling."""

from __future__ import annotations

import json
import re
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
You are querying a SQLite database for a school district invoice system.

### invoices
- id INTEGER PRIMARY KEY
- vendor_id INTEGER NOT NULL
- upload_id INTEGER
- student_name VARCHAR(255)
- invoice_number VARCHAR(128)
- invoice_code VARCHAR(64)
- service_month VARCHAR(32)
- invoice_date DATETIME
- total_hours FLOAT
- total_cost FLOAT                      -- THIS is the invoice money amount
- status VARCHAR(50)
- pdf_s3_key VARCHAR(512)
- district_key VARCHAR(64)              -- tenancy boundary: which district owns the invoice
- created_at DATETIME

### vendors
- id INTEGER PRIMARY KEY
- name VARCHAR(255)
- contact_email VARCHAR(255)
- district_key VARCHAR(64)              -- used by vendors to register access to a district

### invoice_line_items
- id INTEGER PRIMARY KEY
- invoice_id INTEGER NOT NULL
- student VARCHAR(255)
- clinician VARCHAR(255)
- service_code VARCHAR(50)
- hours FLOAT
- rate FLOAT
- cost FLOAT                            -- line-item amount
- service_date VARCHAR(32)

Important invariants:
- Every invoice row belongs to exactly one district via invoices.district_key.
- Multiple vendors may share the same district_key to submit invoices to that district.
- Vendors may hold multiple district_keys (serve multiple districts).
- There is NO column called amount_due, invoice_total, balance_due, due_amount, invoice_amount, etc.
- The ONLY correct invoice money field is invoices.total_cost.

When building SQL, the model MUST prioritise queries that:
- Use invoices.district_key = :district_key for tenant scoping.
- Use invoices.student_name for student lookups.
- Join vendors only when searching by vendor name.
- Treat service_month as free-form TEXT (e.g. "November", "December").
- Extract years or month numbers using strftime on invoice_date.

Example: Student search

SELECT invoice_number, student_name, total_cost
FROM invoices
WHERE invoices.district_key = :district_key
  AND LOWER(student_name) LIKE '%' || LOWER(:student_query) || '%';

Example: Vendor name search (without schema change)

SELECT i.invoice_number, i.student_name, i.total_cost
FROM invoices i
JOIN vendors v ON v.id = i.vendor_id
WHERE i.district_key = :district_key
  AND LOWER(v.name) LIKE '%' || LOWER(:vendor_query) || '%';

Example: Month/year query using invoice_date

SELECT COUNT(*) AS invoice_count
FROM invoices
WHERE invoices.district_key = :district_key
  AND strftime('%Y', invoice_date) = '2025'
  AND LOWER(service_month) = LOWER('November');
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

    @property
    def district_key(self) -> str | None:
        value = self.user_context.get("district_key")
        if not value:
            return None
        try:
            return str(value)
        except Exception:  # pragma: no cover - defensive
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

        def _extract_student_name(user_query: str) -> str | None:
            """Return a best-effort student name match from the query."""

            import re

            match = re.findall(r"[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+", user_query)
            if match:
                return match[0]
            return None

        for iteration in range(self.max_iterations):
            LOGGER.debug("agent_iteration_start", iteration=iteration)

            student_name = _extract_student_name(query)
            if student_name and context.district_key:
                safe_name = student_name.replace("'", "''")
                sql = (
                    "SELECT invoice_number, student_name, total_cost, "
                    "service_month, status "
                    "FROM invoices "
                    "WHERE invoices.district_key = :district_key "
                    "AND LOWER(invoices.student_name) LIKE LOWER('%{name}%') "
                    "ORDER BY invoice_date DESC, total_cost DESC;"
                ).format(name=safe_name)

                try:
                    run_sql_tool = agent.lookup_tool("run_sql")
                except RuntimeError:
                    LOGGER.warning("run_sql_tool_unavailable_for_student", query=query)
                else:
                    try:
                        rows = run_sql_tool.invoke(context, {"query": sql})
                    except Exception as exc:  # pragma: no cover - defensive
                        context.last_error = str(exc)
                        payload = {
                            "text": f"Failed to fetch invoices for {student_name}: {exc}",
                            "rows": None,
                            "html": None,
                        }
                    else:
                        context.last_rows = rows
                        if rows:
                            text = (
                                f"Fetched {len(rows)} invoice"
                                f"{'s' if len(rows) != 1 else ''} for {student_name}."
                            )
                        else:
                            text = f"No invoices found for {student_name}."
                        payload = {"text": text, "rows": rows}

                    return _finalise_response(payload, context)

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
                        if tool.name == "run_sql":
                            error_text = f"I was unable to complete that SQL query: {exc}"
                            payload = {
                                "text": error_text,
                                "rows": None,
                                "html": _safe_html(error_text),
                            }
                            return _finalise_response(payload, context)
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
                text = raw_content.strip() or "No response provided."
                fallback_payload = {"text": text, "rows": context.last_rows, "html": None}
                return _finalise_response(fallback_payload, context)

            if isinstance(payload, Mapping):
                return _finalise_response(payload, context)

            if isinstance(payload, str):
                fallback_payload = {"text": payload, "rows": context.last_rows, "html": None}
                return _finalise_response(fallback_payload, context)

            if isinstance(payload, list):
                rows = _coerce_rows(payload)
                if rows is not None:
                    fallback_payload = {"text": "", "rows": rows, "html": None}
                    return _finalise_response(fallback_payload, context)

            text = str(payload).strip()
            fallback_payload = {"text": text, "rows": context.last_rows, "html": None}
            return _finalise_response(fallback_payload, context)

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


def _strip_html(s: str) -> str:
    return re.sub(r"<[^>]*>", "", s or "").strip()


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
    text_value = _strip_html(text_value)
    rows_value = _coerce_rows(payload.get("rows"))
    html_value = payload.get("html") if isinstance(payload.get("html"), str) else None

    rows: list[dict[str, Any]] | None = rows_value or context.last_rows

    if not text_value and rows:
        text_value = "See the table below for details."

    if rows:
        html = html_value or _render_html_table(rows)
    else:
        html = html_value or _safe_html(text_value)

    # If HTML exists, suppress text to avoid rendering duplicate data
    if html:
        return AgentResponse(text="", html=html, rows=rows)

    # Otherwise return text-only version
    return AgentResponse(text=text_value or "", html=html, rows=rows)


def _apply_district_filter(
    query: str, district_id: int | None, district_key: str | None
) -> tuple[str, dict[str, Any]]:
    """
    Normalize SQL and prepare parameters.

    We DO NOT inject WHERE clauses automatically.

    Instead:
    - We normalize whitespace and remove a trailing semicolon.
    - If a district_key is provided, we expose it as :district_key.
    - If a district_id is provided, we may expose it as :district_id for advanced joins,
      but the preferred tenant boundary is invoices.district_key.
    """

    normalized = query.strip()
    if normalized.endswith(";"):
        normalized = normalized[:-1]

    params: dict[str, Any] = {}

    if district_key:
        params["district_key"] = district_key

    if district_id is not None:
        params["district_id"] = district_id

    return normalized, params


def _build_run_sql_tool(engine: Engine) -> Tool:
    description = (
        "Execute a read-only SQL query against the analytics database. "
        "Use invoices.total_cost for money amounts. "
        "Use invoices.district_key = :district_key to restrict by district. "
        "Supports searching by student name (invoices.student_name) and vendor name (JOIN vendors on vendor_id). "
        "Supports month/year filters using service_month TEXT and invoice_date."
    )
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

        filtered_query, parameters = _apply_district_filter(
            query, context.district_id, context.district_key
        )

        sql_text_query = filtered_query.strip()
        log_params = dict(parameters or {})

        LOGGER.info(
            "analytics_run_sql_request",
            sql=sql_text_query,
            params=log_params,
        )

        with engine.connect() as connection:
            try:
                result = connection.execute(sql_text(sql_text_query), parameters)
                rows = [dict(row._mapping) for row in result]
            except Exception as exc:
                LOGGER.error(
                    "analytics_run_sql_error",
                    sql=sql_text_query,
                    params=log_params,
                    error=str(exc),
                )
                raise

        LOGGER.info(
            "analytics_run_sql_result",
            sql=sql_text_query,
            row_count=len(rows),
        )

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
        "You are an analytics agent for a school district invoice system. "
        "You answer questions using SQLite via the run_sql tool and return structured JSON.\n\n"
        f"{DB_SCHEMA_HINT}\n\n"
        "TOOL USAGE:\n"
        "- Use list_s3 ONLY when the user asks about invoice files, PDFs, S3 keys, or prefixes.\n"
        "- Use run_sql for counts, totals, vendors, students, spending, and summaries.\n\n"
        "DISTRICT SCOPING:\n"
        "- The tenancy boundary is invoices.district_key.\n"
        "- When a district_key parameter is available, you MUST scope invoice-level queries as:\n"
        "    WHERE invoices.district_key = :district_key\n"
        "- Do NOT attempt to use invoices.district_id or vendors.district_id (they are not reliable).\n"
        "- Multiple vendors may share the same district_key; invoices are already tagged with it.\n\n"
        "SQL RULES:\n"
        "- Only use columns that exist in the schema.\n"
        "- For invoice money totals, ALWAYS use invoices.total_cost.\n"
        "- For monthly buckets, interpret 'October invoices', 'spend in August', etc. as **month of service**, and use service_month/service_year or service_month_num.\n"
        "- Example: LOWER(service_month) = LOWER('October') or service_month_num = 10.\n"
        "- Only use invoice_date when the user explicitly asks about when invoices were processed or uploaded (e.g., 'when were October invoices submitted?').\n"
        "- Keep queries simple: avoid unnecessary joins unless the question truly needs them.\n\n"
        "FULL RESULTS vs. LIMITS:\n"
        "- If the user asks for \"all invoices\", \"full table\", or similar wording, you MUST NOT add a LIMIT clause.\n"
        "- You MAY use LIMIT or return only top N rows ONLY if the user explicitly asks for \"top\", \"highest\", \"sample\", or similar phrasing.\n"
        "- When the user asks for all rows (e.g., \"all invoices with invoice information for November\"), you must return the full result set subject only to district_key and the user-specified filters.\n\n"
        "ADDITIONAL RULES:\n"
        "- If user asks about a STUDENT, your SQL must use invoices.student_name with a case-insensitive LIKE match.\n"
        "- If user asks about a VENDOR, JOIN vendors ON vendors.id = invoices.vendor_id and filter vendors.name with LIKE.\n"
        "- If user references a month like 'November', search using LOWER(service_month).\n"
        "- If user references a year, extract using strftime('%Y', invoice_date).\n"
        "- Do NOT guess column names. Use only: student_name, vendor_id, vendors.name, service_month, invoice_date, total_cost.\n\n"
        "CLINICIAN QUERIES:\n"
        "- Clinician names live in invoice_line_items.clinician, not invoices.student_name.\n"
        "- When counting how many students a clinician serves, use invoice_line_items joined to invoices:\n"
        "  SELECT COUNT(DISTINCT ili.student) AS student_count\n"
        "  FROM invoice_line_items AS ili\n"
        "  JOIN invoices AS i ON ili.invoice_id = i.id\n"
        "  WHERE i.district_key = :district_key\n"
        "    AND LOWER(ili.clinician) LIKE LOWER(:clinician_name);\n\n"
        "- When listing which students a clinician serves, use:\n"
        "  SELECT DISTINCT ili.student AS student_name\n"
        "  FROM invoice_line_items AS ili\n"
        "  JOIN invoices AS i ON ili.invoice_id = i.id\n"
        "  WHERE i.district_key = :district_key\n"
        "    AND LOWER(ili.clinician) LIKE LOWER(:clinician_name)\n"
        "  ORDER BY ili.student;\n\n"
        "- When computing hours per clinician for a specific student, use:\n"
        "  SELECT ili.clinician,\n"
        "         SUM(ili.hours) AS total_hours\n"
        "  FROM invoice_line_items AS ili\n"
        "  JOIN invoices AS i ON ili.invoice_id = i.id\n"
        "  WHERE i.district_key = :district_key\n"
        "    AND LOWER(ili.student) LIKE LOWER(:student_name)\n"
        "  GROUP BY ili.clinician\n"
        "  ORDER BY total_hours DESC;\n\n"
        "- Do NOT search for clinician names in invoices.student_name; clinician names are only in invoice_line_items.clinician.\n\n"
        "EXAMPLES (assume :district_key is provided when appropriate):\n"
        "1) Count vendors (global):\n"
        "   SELECT COUNT(*) AS vendor_count FROM vendors;\n\n"
        "2) Count invoices for November 2025 for a district:\n"
        "   SELECT COUNT(*) AS invoice_count\n"
        "   FROM invoices\n"
        "   WHERE invoices.district_key = :district_key\n"
        "     AND strftime('%Y-%m', invoice_date) = '2025-11';\n\n"
        "3) Highest invoice total in November 2025 for a district:\n"
        "   SELECT invoice_number, student_name, total_cost AS highest_amount\n"
        "   FROM invoices\n"
        "   WHERE invoices.district_key = :district_key\n"
        "     AND strftime('%Y-%m', invoice_date) = '2025-11'\n"
        "   ORDER BY total_cost DESC\n"
        "   LIMIT 1;\n\n"
        "4) Total spend in 2025 for a district:\n"
        "   SELECT SUM(total_cost) AS total_spend\n"
        "   FROM invoices\n"
        "   WHERE invoices.district_key = :district_key\n"
        "     AND strftime('%Y', invoice_date) = '2025';\n\n"
        "5) Full invoice table for November (no LIMIT):\n"
        "   User: \"Give me a table for all invoices with invoice information for November.\"\n"
        "   SQL:\n"
        "   SELECT invoice_number, student_name, total_cost, service_month, invoice_date, status\n"
        "   FROM invoices\n"
        "   WHERE invoices.district_key = :district_key\n"
        "     AND LOWER(service_month) = LOWER('November')\n"
        "   ORDER BY invoice_date, invoice_number;\n\n"
        "STUDENT NAME LOGIC:\n"
        "- When the user asks about a specific student (example: ‘Why is Yuritzi low?’, ‘Show invoices for Chase Porraz’, ‘Give student summary for Aidan Borrelli’), ALWAYS use run_sql.\n"
        "- Perform a case-insensitive match on invoices.student_name:\n"
        "      WHERE LOWER(invoices.student_name) LIKE LOWER('%{student_name}%')\n"
        "- When a student may have multiple invoices, return all matching rows sorted by invoice_date DESC.\n"
        "- When asking ‘why is amount low?’ or ‘what happened?’, extract that student’s invoice(s) and return invoice_number, student_name, total_cost, service_month, status.\n"
        "- NEVER assume the student is a vendor — students and vendors are separate entities.\n\n"
        "FINAL OUTPUT FORMAT:\n"
        "- You MUST respond with a single JSON object: {\"text\": str, \"rows\": list|None, \"html\": str}.\n"
        "- text: a concise human-readable summary.\n"
        "- rows: a list of result row dicts OR null.\n"
        "- html: an HTML fragment (e.g. <table> with rows) derived from the rows or summary.\n"
        "- Do NOT output plain text outside this JSON structure.\n"
        "OUTPUT FORMAT DISCIPLINE RULES:\n"
        "- The 'text' field MUST contain ONLY plain English. NO HTML. NO <tags>. NO table markup.\n"
        "- The 'html' field MUST contain ALL formatted HTML (tables, td, tr, th, p, strong, etc.).\n"
        "- NEVER duplicate information. Whatever appears in 'html' MUST NOT also appear in 'text'.\n"
        "- The 'rows' field MUST contain ONLY raw structured data from SQL, not markup.\n"
        "- The model MUST NOT include </td>, <tr>, <table>, <p>, or any HTML-like text in the 'text' field.\n"
        "- 'text' should be a concise human-readable summary, e.g.:\n"
        "    { \"text\": \"Here are the top 5 invoices by total cost.\" }\n"
        "- 'html' should contain the visual result table ONLY, e.g.:\n"
        "    { \"html\": \"<table>...</table>\" }\n"
        "- NEVER put HTML in 'rows'.\n"
        "- NEVER mix description and table markup in the same field.\n"
        "- If generating a table, put it ONLY inside the 'html' field."
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
