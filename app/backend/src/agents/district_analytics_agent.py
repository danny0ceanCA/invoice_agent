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
from app.backend.src.core.memory import ConversationMemory, RedisConversationMemory
from app.backend.src.db import get_engine
from app.backend.src.services.s3 import get_s3_client
from .ir import AnalyticsEntities, AnalyticsIR, _coerce_rows, _payload_to_ir
from .logic_model import build_logic_system_prompt, run_logic_model
from .rendering_model import build_rendering_system_prompt, run_rendering_model

LOGGER = structlog.get_logger(__name__)

DEFAULT_MODEL = "ft:gpt-4.1-mini-2025-04-14:responsive:carespend-analytics:CgLfCiA5"
MAX_ITERATIONS = 8

class AgentResponse(BaseModel):
    """Standardised response payload returned to the caller."""

    text: str
    html: str
    rows: list[dict[str, Any]] | None = None
    class Config:
        extra = "allow"



def normalize_sql_for_postgres(sql: str, engine=None) -> str:
    # LOCAL TESTING MODE — do not rewrite strftime() to EXTRACT()
    return sql

    """
    Normalize analytics SQL that may contain SQLite-specific functions so it
    runs cleanly on PostgreSQL.

    This is a short-term safety net while we migrate from SQLite to Postgres
    and update agent prompts. It is intentionally conservative and only
    rewrites patterns we know are invalid on Postgres.

    Currently handled:
      - strftime('%m', invoice_date) -> EXTRACT(MONTH FROM invoice_date)

    If additional SQLite-only patterns show up in logs, they can be added
    here in a controlled way.
    """

    # Replace simple month-extraction via strftime with Postgres EXTRACT()
    replacements = [
        # common pattern with spaces: strftime('%m', invoice_date)
        (r"strftime\('%m',\s*invoice_date\)", "EXTRACT(MONTH FROM invoice_date)"),
        # sometimes the agent may qualify the column: strftime('%m', invoices.invoice_date)
        (
            r"strftime\('%m',\s*invoices\.invoice_date\)",
            "EXTRACT(MONTH FROM invoices.invoice_date)",
        ),
    ]

    normalized = sql
    for pattern, replacement in replacements:
        normalized = re.sub(pattern, replacement, normalized)

    return normalized


@dataclass
class AgentContext:
    """Runtime context shared between the workflow and tools."""

    query: str
    user_context: dict[str, Any] = field(default_factory=dict)
    last_rows: list[dict[str, Any]] | None = None
    last_error: str | None = None
    session_id: str | None = None
    memory: ConversationMemory | None = None
    last_sql: str | None = None

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


def _extract_active_filters_from_history(history: list[dict[str, str]]) -> dict[str, str]:
    """
    Inspect assistant messages in Redis-backed history and extract the last
    active student filter (and potentially other filters in the future).

    We look for lines in assistant content of the form:
        ACTIVE_STUDENT_FILTER: <name>
    and return {"student": "<name>"} when found.
    """
    active: dict[str, str] = {}
    if not history:
        return active

    # Walk history from newest to oldest, looking for assistant messages
    # with an ACTIVE_STUDENT_FILTER tag.
    for message in reversed(history):
        if not isinstance(message, dict):
            continue
        if message.get("role") != "assistant":
            continue
        content = message.get("content") or ""
        # Split into lines and look for our tag.
        for line in str(content).splitlines():
            line = line.strip()
            if line.startswith("ACTIVE_STUDENT_FILTER:"):
                # Format: ACTIVE_STUDENT_FILTER: chloe taylor
                parts = line.split(":", 1)
                if len(parts) == 2:
                    name = parts[1].strip()
                    if name:
                        active["student"] = name
                        return active

    # Fallback: if no explicit ACTIVE_STUDENT_FILTER tag was found in assistant
    # messages, try to derive an active student from the most recent user queries.
    if not active:
        for message in reversed(history):
            if not isinstance(message, dict):
                continue
            if message.get("role") != "user":
                continue

            content = (message.get("content") or "").strip()
            if not content:
                continue

            # Look for patterns like:
            #   "for Jack Wilson"
            #   "monthly spend for avery smith"
            #   "give me invoice details for July for Carter Sanchez"
            #
            # This regex captures one or more words after "for ".
            m = re.search(r"\bfor\s+([A-Za-z]+(?:\s+[A-Za-z]+)+)", content, flags=re.IGNORECASE)
            if m:
                name = m.group(1).strip()
                if name:
                    # Use the raw name; SQL already uses LOWER() for matching.
                    active["student"] = name
                    return active

    return active


def _maybe_apply_active_student_filter(raw_query: str, active_filters: dict[str, str]) -> str:
    """
    If there is an active student filter (e.g., from a prior 'monthly spend for X' query),
    and the current query does NOT explicitly change scope, rewrite the query text to
    include that student so the model receives an explicit filter.
    """
    active_student = (active_filters.get("student") or "").strip()
    if not active_student:
        return raw_query

    q_lower = raw_query.lower()

    # If the user explicitly asks for "all students" / "entire district" / similar,
    # do NOT apply the sticky filter.
    if "all students" in q_lower or "entire district" in q_lower or "district" in q_lower:
        return raw_query

    # If the query already explicitly mentions this student, don't modify it.
    if active_student.lower() in q_lower:
        return raw_query

    # Only apply the sticky filter for queries that look like detail/summary follow-ups.
    trigger_phrases = [
        "invoice detail",
        "invoice details",
        "monthly spend",
        "monthly summary",
        "invoice totals",
        "invoice summary",
        "details for",
        "invoice info",
        "only show me",
        "only for",
    ]
    month_words = [
        "january",
        "february",
        "march",
        "april",
        "may",
        "june",
        "july",
        "august",
        "september",
        "october",
        "november",
        "december",
    ]
    has_month = any(m in q_lower for m in month_words)

    if not any(p in q_lower for p in trigger_phrases) and not has_month:
        return raw_query

    # If the user already wrote a "for student ..." pattern, don't overwrite it.
    if "for student" in q_lower:
        return raw_query

    # Rewrite by appending an explicit student clause in natural language.
    # Example: "give me invoice details for September"
    # becomes: "give me invoice details for September for student Chloe Taylor"
    rewritten_query = raw_query.rstrip() + f" for student {active_student}"
    LOGGER.debug(
        "sticky_student_filter_applied",
        active_student=active_student,
        original=raw_query,
        rewritten=rewritten_query,
    )
    return rewritten_query


class Workflow:
    """Coordinates model reasoning and tool usage."""

    def __init__(
        self,
        *,
        logic_system_prompt: str,
        rendering_system_prompt: str,
        max_iterations: int = MAX_ITERATIONS,
        memory: ConversationMemory | None = None,
    ) -> None:
        self.logic_system_prompt = logic_system_prompt
        self.rendering_system_prompt = rendering_system_prompt
        self.max_iterations = max_iterations
        self.memory = memory

    def execute(self, agent: "Agent", query: str, user_context: dict[str, Any]) -> AgentResponse:
        session_id = _build_session_id(user_context)
        context = AgentContext(
            query=query, user_context=user_context or {}, session_id=session_id, memory=self.memory
        )
        history: list[dict[str, str]] = []
        if self.memory and session_id:
            try:
                history = self.memory.load_messages(session_id)
            except Exception as exc:  # pragma: no cover - defensive
                LOGGER.warning("analytics_memory_load_failed", error=str(exc))

        # Apply sticky student filter by inspecting history and, if we find an
        # ACTIVE_STUDENT_FILTER tag, rewriting the incoming query so the model
        # sees the student explicitly.
        active_filters = _extract_active_filters_from_history(history)
        if active_filters:
            query = _maybe_apply_active_student_filter(query, active_filters)

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self.logic_system_prompt}
        ]

        if history:
            messages.extend(history)

        messages.append(
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "query": query,
                        "context": context.user_context,
                    }
                ),
            }
        )

        def _extract_student_name(user_query: str) -> str | None:
            """Return a best-effort student name match from the query."""

            import re

            match = re.findall(r"[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+", user_query)
            if match:
                return match[0]
            return None

        for iteration in range(self.max_iterations):
            LOGGER.debug("agent_iteration_start", iteration=iteration)

            normalized_query = query.lower()

            # Special-case: include provider information based on the last result set
            if (
                "includ" in normalized_query  # catches 'include', 'including'
                and "provid" in normalized_query  # catches 'provider', 'providers', 'provide'
                and context.last_rows
            ):
                # Try to infer the service_month from the last rows
                months = {
                    str(r.get("service_month", "")).strip().lower()
                    for r in (context.last_rows or [])
                    if r.get("service_month")
                }
                months = {m for m in months if m}

                # If the user says 'same month' or 'this month' and we have exactly one month in context,
                # show ALL providers for that month across the district (month-scope provider summary).
                if ("same month" in normalized_query or "this month" in normalized_query) and len(months) == 1:
                    month = next(iter(months))
                    sql = """
                    SELECT
                        ili.clinician            AS provider,
                        SUM(ili.cost)            AS total_spend,
                        LOWER(i.service_month)   AS service_month
                    FROM invoice_line_items AS ili
                    JOIN invoices AS i ON ili.invoice_id = i.id
                    WHERE i.district_key = :district_key
                      AND LOWER(i.service_month) = :month
                    GROUP BY
                        ili.clinician,
                        LOWER(i.service_month)
                    ORDER BY
                        total_spend DESC;
                    """
                    try:
                        run_sql_tool = agent.lookup_tool("run_sql")
                    except RuntimeError:
                        LOGGER.warning("run_sql_tool_unavailable_for_provider_month", query=query)
                    else:
                        try:
                            rows = run_sql_tool.invoke(context, {"query": sql, "month": month})
                        except Exception as exc:  # pragma: no cover - defensive
                            context.last_error = str(exc)
                            payload = {
                                "text": f"Failed to fetch provider spend for {month}: {exc}",
                                "rows": None,
                                "html": None,
                            }
                        else:
                            context.last_rows = rows
                            payload = {"text": "", "rows": rows, "html": None}
                        return _finalise_response(payload, context)

                # Otherwise, fall back to invoice-scope provider breakdown using invoice_numbers from the last rows
                inv_values = {
                    str(r.get("invoice_number", "")).strip()
                    for r in (context.last_rows or [])
                    if r.get("invoice_number")
                }
                inv_values = sorted({v for v in inv_values if v})
                if inv_values:
                    inv_list_sql = ", ".join(
                        "'" + inv.replace("'", "''") + "'" for inv in inv_values
                    )
                    sql = f"""
                    SELECT
                        i.invoice_number,
                        i.student_name,
                        LOWER(i.service_month)   AS service_month,
                        ili.clinician            AS provider,
                        SUM(ili.cost)            AS provider_cost
                    FROM invoice_line_items AS ili
                    JOIN invoices AS i ON ili.invoice_id = i.id
                    WHERE i.district_key = :district_key
                      AND i.invoice_number IN ({inv_list_sql})
                    GROUP BY
                        i.invoice_number,
                        i.student_name,
                        LOWER(i.service_month),
                        ili.clinician
                    ORDER BY
                        i.invoice_number,
                        provider_cost DESC;
                    """
                    try:
                        run_sql_tool = agent.lookup_tool("run_sql")
                    except RuntimeError:
                        LOGGER.warning("run_sql_tool_unavailable_for_provider_include", query=query)
                    else:
                        try:
                            rows = run_sql_tool.invoke(context, {"query": sql})
                        except Exception as exc:  # pragma: no cover - defensive
                            context.last_error = str(exc)
                            payload = {
                                "text": f"Failed to include provider information: {exc}",
                                "rows": None,
                                "html": None,
                            }
                        else:
                            context.last_rows = rows
                            payload = {"text": "", "rows": rows, "html": None}

                        return _finalise_response(payload, context)

            if "student list" in normalized_query and "ytd" in normalized_query:
                sql = """
                SELECT DISTINCT student_name
                FROM invoices
                WHERE district_key = :district_key
                  AND strftime('%Y', invoice_date) = strftime('%Y','now')
                ORDER BY student_name
                """

                try:
                    run_sql_tool = agent.lookup_tool("run_sql")
                except RuntimeError:
                    LOGGER.warning("run_sql_tool_unavailable_for_student_list", query=query)
                else:
                    try:
                        rows = run_sql_tool.invoke(context, {"query": sql})
                    except Exception as exc:  # pragma: no cover - defensive
                        context.last_error = str(exc)
                        payload = {
                            "text": f"Failed to fetch YTD student list: {exc}",
                            "rows": None,
                            "html": None,
                        }
                    else:
                        context.last_rows = rows
                        if rows:
                            text = f"Found {len(rows)} student{'' if len(rows) == 1 else 's'} for the current year."
                        else:
                            text = "No students found for the current year."
                        payload = {"text": text, "rows": rows}

                    return _finalise_response(payload, context)

            student_list_phrases = [
                "list of students",
                "student list",
                "students ytd",
                "all students",
                "students in our system",
                "students by year",
            ]

            if any(phrase in normalized_query for phrase in student_list_phrases):
                sql = """
                SELECT DISTINCT student_name
                FROM invoices
                WHERE district_key = :district_key
                ORDER BY student_name
                """

                try:
                    run_sql_tool = agent.lookup_tool("run_sql")
                except RuntimeError:
                    LOGGER.warning(
                        "run_sql_tool_unavailable_for_student_list", query=query
                    )
                else:
                    try:
                        rows = run_sql_tool.invoke(context, {"query": sql})
                    except Exception as exc:  # pragma: no cover - defensive
                        context.last_error = str(exc)
                        payload = {
                            "text": f"Failed to fetch student list: {exc}",
                            "rows": None,
                            "html": None,
                        }
                    else:
                        context.last_rows = rows
                        if rows:
                            text = (
                                f"Found {len(rows)} student{'' if len(rows) == 1 else 's'}"
                            )
                        else:
                            text = "No students found."
                        payload = {"text": text, "rows": rows}

                    return _finalise_response(payload, context)

            student_name = _extract_student_name(query)
            if student_name and context.district_key:
                # STUDENT-ONLY SHORTCUT:
                # This shortcut is safe when the query is essentially just the student's
                # name (e.g., "Avery Smith") and does NOT mention months or other filters.
                # If the query mentions a month (e.g., "July") or the word "month", we
                # skip the shortcut so the model can construct a full student+month query.
                q_lower = query.lower()
                month_words = [
                    "january",
                    "february",
                    "march",
                    "april",
                    "may",
                    "june",
                    "july",
                    "august",
                    "september",
                    "october",
                    "november",
                    "december",
                ]
                mentions_month = "month" in q_lower or any(m in q_lower for m in month_words)

                if mentions_month:
                    # Example: "Jayden Ramsey and the month is for July"
                    # -> let the model + tools build:
                    #    WHERE student_name LIKE '%jayden ramsey%'
                    #      AND LOWER(service_month) = LOWER('july')
                    # instead of returning all months.
                    pass
                else:
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

            message = run_logic_model(
                agent.client,
                model=agent.logic_model,
                messages=messages,
                tools=[tool.schema() for tool in agent.tools],
                temperature=agent.logic_temperature,
            )
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

            logic_ir = _payload_to_ir(payload, context.last_rows)
            render_payload = run_rendering_model(
                user_query=context.query,
                ir=logic_ir,
                client=agent.client,
                model=agent.render_model,
                system_prompt=self.rendering_system_prompt,
                temperature=agent.render_temperature,
            )
            return _finalise_response(render_payload, context)

        raise RuntimeError("Agent workflow exceeded iteration limit.")


class Agent:
    """Agent orchestrating workflow execution with the OpenAI client."""

    def __init__(
        self,
        *,
        client: OpenAI,
        logic_model: str,
        render_model: str,
        workflow: Workflow,
        tools: Sequence[Tool],
        logic_temperature: float = 0.1,
        render_temperature: float = 0.1,
    ) -> None:
        self.client = client
        self.logic_model = logic_model
        self.render_model = render_model
        self.logic_temperature = logic_temperature
        self.render_temperature = render_temperature
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
    """
    Render a generic HTML table from rows, applying basic formatting rules:

    - Columns with amount-like names (e.g., total_cost, total_spend, amount, cost)
      are rendered as currency ($X,XXX.XX) and tagged with class="amount-col".
    - Columns with date-like names (e.g., invoice_date, service_date, created_at)
      are rendered as date-only (YYYY-MM-DD), stripping any time component.
    - All other values are rendered as plain text.
    - The table is wrapped in <div class="table-wrapper"><table class="analytics-table">...</table></div>
      to align with analytics styling.
    """
    if not rows:
        return "<div class=\"table-wrapper\"><table class=\"analytics-table\"></table></div>"

    headers = list(rows[0].keys())

    amount_like = {
        "total_cost",
        "total_spend",
        "amount",
        "cost",
        "highest_amount",
        "provider_cost",
        "code_total",
        "daily_cost",
    }
    date_like = {
        "invoice_date",
        "service_date",
        "created_at",
        "last_modified",
    }

    header_html = "".join(f"<th>{escape(str(header))}</th>" for header in headers)
    body_rows: list[str] = []

    for row in rows:
        cells_html: list[str] = []
        for header in headers:
            key = str(header)
            raw = row.get(header, "")

            # Currency formatting for amount-like columns
            if key in amount_like:
                try:
                    value = float(raw)
                    display = f"${value:,.2f}"
                except Exception:
                    display = str(raw)
                cell_html = f"<td class=\"amount-col\">{escape(display)}</td>"

            # Date-only formatting for date-like columns
            elif key in date_like:
                text = str(raw)
                # Split off time if present (supports 'YYYY-MM-DD HH:MM:SS' or ISO 'YYYY-MM-DDTHH:MM:SS')
                if "T" in text:
                    date_part = text.split("T", 1)[0]
                else:
                    date_part = text.split(" ", 1)[0]
                cell_html = f"<td>{escape(date_part)}</td>"

            # Default plain text
            else:
                cell_html = f"<td>{escape(str(raw))}</td>"

            cells_html.append(cell_html)

        body_rows.append("<tr>" + "".join(cells_html) + "</tr>")

    body_html = "".join(body_rows)
    return (
        "<div class=\"table-wrapper\">"
        "<table class=\"analytics-table\">"
        "<thead><tr>"
        f"{header_html}"
        "</tr></thead>"
        "<tbody>"
        f"{body_html}"
        "</tbody>"
        "</table>"
        "</div>"
    )


def _month_sort_key(month_str: Any) -> int:
    """
    Return a sort key for textual month names. Unknown values sort last.
    """
    if month_str is None:
        return 99
    name = str(month_str).strip().lower()
    months = [
        "january",
        "february",
        "march",
        "april",
        "may",
        "june",
        "july",
        "august",
        "september",
        "october",
        "november",
        "december",
    ]
    try:
        return months.index(name)
    except ValueError:
        return 99


def _should_pivot_student_month(
    rows: Sequence[Mapping[str, Any]], query: str | None
) -> bool:
    """
    Decide whether to render a student-by-month pivot table.

    Conditions:
    - Rows contain student_name and service_month keys.
    - Rows contain a numeric total field (e.g., total_cost).
    - Rows do NOT contain obvious invoice-detail or line-item fields
      such as invoice_number, invoice_date, clinician, service_code,
      service_date, hours, rate, or cost.
    In other words, we only pivot "pure summary" row shapes and skip
    true invoice-detail result sets.
    """
    if not rows:
        return False

    sample = rows[0]
    keys = {str(k) for k in sample.keys()}

    # Require summary shape: student_name + service_month present.
    if "student_name" not in keys or "service_month" not in keys:
        return False

    # Identify the numeric total field.
    amount_key = None
    for candidate in ["total_cost", "total_spend", "amount", "total"]:
        if candidate in keys:
            amount_key = candidate
            break

    if amount_key is None:
        return False

    # If there are obvious invoice-detail / line-item fields, this is not
    # a pure summary rowset and should NOT be pivoted.
    detail_like_keys = {
        "invoice_number",
        "invoice_date",
        "status",
        "clinician",
        "service_code",
        "service_date",
        "hours",
        "rate",
        "cost",
    }
    if any(k in keys for k in detail_like_keys):
        return False

    # Basic numeric check on the first row
    try:
        float(sample[amount_key])
    except Exception:
        return False

    return True


def _render_student_month_pivot(rows: Sequence[Mapping[str, Any]]) -> str:
    """
    Render a pivot table of student vs month from long-format rows.

    Expected keys in each row: student_name, service_month, and a numeric amount
    (e.g., total_cost or total_spend).
    """
    if not rows:
        return _render_html_table(rows)

    sample = rows[0]
    keys = {str(k) for k in sample.keys()}

    student_key = "student_name"
    month_key = "service_month"
    amount_key = None
    for candidate in ["total_cost", "total_spend", "amount", "total"]:
        if candidate in keys:
            amount_key = candidate
            break

    if amount_key is None:
        return _render_html_table(rows)

    # Collect unique students and months
    students_set: set[str] = set()
    months_set: set[str] = set()
    data: dict[tuple[str, str], float] = {}

    for row in rows:
        student_raw = str(row.get(student_key, "")).strip()
        month_raw = str(row.get(month_key, "")).strip()
        if not student_raw or not month_raw:
            continue

        # Use title case for display
        student = student_raw.title()
        month = month_raw.title()

        students_set.add(student)
        months_set.add(month)

        try:
            amount = float(row.get(amount_key) or 0.0)
        except Exception:
            amount = 0.0

        data[(student, month)] = data.get((student, month), 0.0) + amount

    students = sorted(students_set)
    months = sorted(months_set, key=_month_sort_key)

    # Build HTML
    header_cells = ["<th>Student</th>"] + [f"<th>{escape(m)}</th>" for m in months] + [
        "<th>Total Spend ($)</th>"
    ]
    header_html = "<tr>" + "".join(header_cells) + "</tr>"

    body_rows: list[str] = []
    for student in students:
        row_cells: list[str] = [f"<td>{escape(student)}</td>"]
        total_for_student = 0.0
        for month in months:
            amount = data.get((student, month), 0.0)
            total_for_student += amount
            display = f"${amount:,.2f}" if amount != 0.0 else ""
            row_cells.append(f"<td class=\"amount-col\">{escape(display)}</td>")
        total_display = f"${total_for_student:,.2f}"
        row_cells.append(f"<td class=\"amount-col\">{escape(total_display)}</td>")
        body_rows.append("<tr>" + "".join(row_cells) + "</tr>")

    body_html = "".join(body_rows)

    return (
        "<div class=\"table-wrapper\">"
        "<table class=\"analytics-table\">"
        "<thead>"
        f"{header_html}"
        "</thead>"
        "<tbody>"
        f"{body_html}"
        "</tbody>"
        "</table>"
        "</div>"
    )


def _strip_sensitive_columns(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Remove sensitive keys (like rate) from all row dicts before returning them
    to the frontend. This ensures we never display pay rates in analytics tables.
    """
    if not rows:
        return rows

    # Any key that matches these (case-insensitive) will be dropped.
    banned_keys = {"rate", "hourly_rate", "pay_rate"}

    sanitized: list[dict[str, Any]] = []
    for row in rows:
        clean_row: dict[str, Any] = {}
        for key, value in row.items():
            key_lower = str(key).lower()
            if key_lower in banned_keys:
                continue
            clean_row[key] = value
        sanitized.append(clean_row)
    return sanitized


def _remember_interaction(context: AgentContext, response: AgentResponse) -> None:
    if not context.memory or not context.session_id:
        return

    try:
        context.memory.append_interaction(
            context.session_id,
            user_message={"content": context.query},
            assistant_message={"content": _summarize_response(response)},
        )
    except Exception as exc:  # pragma: no cover - defensive
        LOGGER.warning("analytics_memory_append_failed", error=str(exc))


def _summarize_response(response: AgentResponse) -> str:
    """
    Build a compact, entity-rich summary of the agent's response for memory storage.

    Priority:
    - If 'text' exists, use it directly.
    - Otherwise, if 'rows' exist, report row count and, when possible, list key entities
      such as students, providers, vendors, or invoice numbers.
    - Otherwise, fall back to stripped HTML or an empty string.
    """
    if response.text:
        return response.text

    if response.rows:
        rows = response.rows
        count = len(rows)
        summary_parts = [f"Returned {count} row{'s' if count != 1 else ''}."]
        sample = rows[0]
        keys = {str(k) for k in sample.keys()}

        # PRIORITIZE invoice numbers in memory for drill-down behavior
        if "invoice_number" in keys:
            invoice_values = {
                str(r.get("invoice_number", "")).strip()
                for r in rows
                if r.get("invoice_number")
            }
            invoice_values = sorted({v for v in invoice_values if v})
            if invoice_values:
                # invoice list, truncated to a reasonable size
                inv_list = ", ".join(invoice_values[:10])
                # insert at the front so invoices are always prominent in memory
                summary_parts.insert(0, f"Invoices: {inv_list}.")

        # Helper to extract distinct values for a given column name
        def collect_entities(col_name: str, label: str, max_items: int = 10) -> str | None:
            if col_name not in sample:
                return None
            values = {
                str(r.get(col_name, "")).strip()
                for r in rows
                if r.get(col_name)
            }
            values = {v for v in values if v}
            if not values:
                return None
            sorted_vals = sorted(values)
            shown = sorted_vals[:max_items]
            more = len(sorted_vals) - len(shown)
            base = ", ".join(shown)
            if more > 0:
                base += f" (and {more} more)"
            return f"{label}: {base}."

        # Try students
        if "student_name" in keys:
            ent = collect_entities("student_name", "Students")
            if ent:
                summary_parts.append(ent)
        elif "student" in keys:
            ent = collect_entities("student", "Students")
            if ent:
                summary_parts.append(ent)

        # Try providers/clinicians
        if "clinician" in keys:
            ent = collect_entities("clinician", "Providers")
            if ent:
                summary_parts.append(ent)
        elif "provider" in keys:
            ent = collect_entities("provider", "Providers")
            if ent:
                summary_parts.append(ent)

        # Try vendors
        if "vendor_name" in keys:
            ent = collect_entities("vendor_name", "Vendors")
            if ent:
                summary_parts.append(ent)
        elif "name" in keys and "vendor_id" in keys:
            ent = collect_entities("name", "Vendors")
            if ent:
                summary_parts.append(ent)

        # If we have a single, clear student in this result set, record an
        # ACTIVE_STUDENT_FILTER tag so future queries can be auto-scoped.
        student_values: set[str] = set()
        if "student_name" in keys:
            student_values = {
                str(r.get("student_name", "")).strip()
                for r in rows
                if r.get("student_name")
            }
        elif "student" in keys:
            student_values = {
                str(r.get("student", "")).strip()
                for r in rows
                if r.get("student")
            }

        student_values = {v for v in student_values if v}
        if len(student_values) == 1:
            only_student = sorted(student_values)[0]
            # Append a special tag that _extract_active_filters_from_history can read.
            summary_parts.append(f"ACTIVE_STUDENT_FILTER: {only_student}")

        return " ".join(summary_parts)

    if response.html:
        return _strip_html(response.html)

    return ""


def _build_session_id(user_context: Mapping[str, Any] | None) -> str | None:
    if not user_context:
        return None

    parts: list[str] = []
    user_id = user_context.get("user_id")
    district_key = user_context.get("district_key")

    if user_id:
        parts.append(f"user:{user_id}")
    if district_key:
        parts.append(f"district:{district_key}")

    if not parts:
        return None

    return "|".join(parts)


def _finalise_response(payload: Mapping[str, Any], context: AgentContext) -> AgentResponse:
    text_value = str(payload.get("text") or "").strip()
    text_value = _strip_html(text_value)

    # We need to distinguish between:
    # - rows not mentioned at all (reuse last_rows for follow-up views)
    # - rows explicitly set to null (clarifying questions: no table)
    # - rows set to a new list (new result set)
    rows_field_present = "rows" in payload
    raw_rows_field = payload.get("rows", None)
    rows_value = _coerce_rows(raw_rows_field)
    html_value = payload.get("html") if isinstance(payload.get("html"), str) else None

    # Decide which rows to show:
    # - If the model returned a valid row list, use it.
    # - If the model explicitly returned rows: null, show no rows.
    # - If the model omitted the 'rows' field entirely, reuse last_rows
    #   (typical follow-up / restatement behavior).
    if rows_value is not None:
        rows: list[dict[str, Any]] | None = rows_value
    elif rows_field_present:
        rows = None
    else:
        rows = context.last_rows

    if rows:
        # Strip sensitive columns like 'rate' so they never appear in tables or memory.
        rows = _strip_sensitive_columns(rows)
        context.last_rows = rows

    if not text_value and rows:
        text_value = "See the table below for details."

    if rows:
        # For the special case of monthly spend by student, always render
        # a student-by-month pivot table from the long-format rows, even if
        # the model provided its own HTML.
        if _should_pivot_student_month(rows, context.query):
            html = _render_student_month_pivot(rows)
        else:
            # In all other cases, respect any HTML provided by the model,
            # or fall back to the generic table renderer.
            html = html_value or _render_html_table(rows)
    else:
        html = html_value or _safe_html(text_value)

    # If HTML exists, keep both: conversational text + visuals.
    # 'text' should be a short explanation, not a duplication of the table.
    if html:
        response = AgentResponse(text=text_value or "", html=html, rows=rows)
    else:
        # Otherwise return text-only version
        response = AgentResponse(text=text_value or "", html=html, rows=rows)

    # ATTACH SQL (THIS IS THE IMPORTANT PART)
    setattr(response, "debug_sql", context.last_sql)

    _remember_interaction(context, response)
    return response


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

        sql_statement = filtered_query.strip()
        params = dict(parameters)

        # If the caller did not provide a district_key but we have a district_id,
        # resolve the key from the districts table so parameter binding succeeds.
        if "district_key" not in params and context.district_id is not None:
            try:
                with engine.connect() as connection:
                    result = connection.execute(
                        sql_text(
                            "SELECT district_key FROM districts WHERE id = :district_id"
                        ),
                        {"district_id": context.district_id},
                    )
                    resolved_key = result.scalar_one_or_none()
            except Exception as exc:  # pragma: no cover - defensive
                resolved_key = None
                LOGGER.warning(
                    "district_key_lookup_failed",
                    district_id=context.district_id,
                    error=str(exc),
                )

            if resolved_key:
                params["district_key"] = resolved_key
                context.user_context["district_key"] = resolved_key

        # Remove any hard-coded district_key string literals from the SQL.
        # This fixes queries like "i.district_key = '1'" that incorrectly
        # filter out all rows. Since the current deployment is effectively
        # single-tenant, dropping this predicate is safe.
        sql_no_dk = sql_statement

        # Case 1: "WHERE i.district_key = '... ' AND ..." -> drop the predicate, keep the rest.
        sql_no_dk = re.sub(
            r"(?i)\bWHERE\s+(?:i|invoices)\.district_key\s*=\s*'[^']*'\s+AND\s+",
            "WHERE ",
            sql_no_dk,
        )

        # Case 2: "WHERE i.district_key = '...'" with no trailing AND -> replace with neutral WHERE 1=1.
        sql_no_dk = re.sub(
            r"(?i)\bWHERE\s+(?:i|invoices)\.district_key\s*=\s*'[^']*'\s*(?=$|\s*(ORDER|GROUP|LIMIT|;))",
            "WHERE 1=1 ",
            sql_no_dk,
        )

        # Case 3: "AND i.district_key = '...'" in the middle of other conditions -> remove that AND clause.
        sql_no_dk = re.sub(
            r"(?i)\bAND\s+(?:i|invoices)\.district_key\s*=\s*'[^']*'\s*",
            " ",
            sql_no_dk,
        )

        # Additional cleanup for bare district_key predicates without table alias.
        # Case A: "WHERE district_key = '... ' AND ..." -> drop the predicate, keep the rest.
        sql_no_dk = re.sub(
            r"(?i)\bWHERE\s+district_key\s*=\s*'[^']*'\s+AND\s+",
            "WHERE ",
            sql_no_dk,
        )

        # Case B: "WHERE district_key = '...'" with no trailing AND -> replace with neutral WHERE 1=1.
        sql_no_dk = re.sub(
            r"(?i)\bWHERE\s+district_key\s*=\s*'[^']*'\s*(?=$|\s*(ORDER|GROUP|LIMIT|;))",
            "WHERE 1=1 ",
            sql_no_dk,
        )

        # Case C: "AND district_key = '...'" -> remove that AND clause.
        sql_no_dk = re.sub(
            r"(?i)\bAND\s+district_key\s*=\s*'[^']*'\s*",
            " ",
            sql_no_dk,
        )

        sql_statement = sql_no_dk

        lowered = sql_statement.lower()
        needs_wrap = (
            " from invoices" in lowered
            and "district_key" not in lowered
            and "sub.district_key" not in lowered
        )

        # Only auto-wrap when the query selects * from invoices; if it uses an explicit
        # column list (no "*"), skip wrapping to avoid referencing sub.district_key when
        # that column is not present in the projection.
        if needs_wrap and re.search(r"(?i)\bselect\s+\*", sql_statement):
            sql_statement = f"""
        SELECT *
        FROM (
            {sql_statement}
        ) AS sub
        WHERE sub.district_key = :district_key
        """

        normalized_sql = normalize_sql_for_postgres(sql_statement)

        LOGGER.info(
            "analytics_run_sql_request",
            sql=normalized_sql,
            params=params,
        )

        try:
            with engine.connect() as connection:
                result = connection.execute(sql_text(normalized_sql), params)
                rows = [dict(row) for row in result.mappings()]
        except Exception as exc:
            LOGGER.error(
                "analytics_run_sql_error",
                sql=normalized_sql,
                params=params,
                error=str(exc),
            )
            raise

        LOGGER.info(
            "analytics_run_sql_result",
            sql=normalized_sql,
            row_count=len(rows),
        )

        context.last_sql = normalized_sql

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




def _build_agent() -> Agent:
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured.")

    client = OpenAI(api_key=settings.openai_api_key)
    engine = get_engine()
    memory = _build_memory_store(settings)
    workflow = Workflow(
        logic_system_prompt=build_logic_system_prompt(),
        rendering_system_prompt=build_rendering_system_prompt(),
        max_iterations=MAX_ITERATIONS,
        memory=memory,
    )
    tools = [_build_run_sql_tool(engine), _build_list_s3_tool()]
    return Agent(
        client=client,
        logic_model=DEFAULT_MODEL,
        render_model=DEFAULT_MODEL,
        workflow=workflow,
        tools=tools,
    )


def _build_memory_store(settings: Any) -> ConversationMemory | None:
    redis_url = getattr(settings, "redis_memory_dsn", None)
    if not redis_url:
        LOGGER.info("analytics_memory_disabled", reason="redis_url_missing")
        return None

    try:
        return RedisConversationMemory(redis_url)
    except Exception as exc:  # pragma: no cover - defensive
        LOGGER.warning("analytics_memory_init_failed", error=str(exc))
        return None


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
