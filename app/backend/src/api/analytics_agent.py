"""Routes for the natural-language analytics agent endpoint."""

from __future__ import annotations

from html import escape
import asyncio
import inspect
import json
import time
from typing import Any, Iterable, Mapping

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from openai import OpenAI

from app.backend.src.core.config import get_settings
from app.backend.src.core.security import get_current_user
from app.backend.src.models import User

LOGGER = structlog.get_logger(__name__)

router = APIRouter(prefix="/analytics", tags=["analytics"])


class AnalyticsAgentConfig:
    """Configuration required to execute the hosted analytics agent."""

    def __init__(
        self,
        *,
        agent_id: str,
        api_key: str,
        polling_interval: float = 0.5,
        max_poll_attempts: int = 120,
    ) -> None:
        self.agent_id = agent_id
        self.api_key = api_key
        self.polling_interval = polling_interval
        self.max_poll_attempts = max_poll_attempts


_AGENT: AnalyticsAgentConfig | None = None


def _ensure_agent_available() -> AnalyticsAgentConfig | Any:
    """Return the analytics agent configuration if the feature is enabled."""

    global _AGENT
    if _AGENT is not None:
        return _AGENT

    settings = get_settings()
    api_key = settings.openai_api_key
    agent_id = (
        settings.get("ANALYTICS_AGENT_ID")
        or settings.get("analytics_agent_id")
        or settings.get("OPENAI_ANALYTICS_AGENT_ID")
    )

    if not api_key or not agent_id:
        LOGGER.warning(
            "analytics_agent_missing_configuration",
            missing=[
                key
                for key, value in {
                    "OPENAI_API_KEY": api_key,
                    "ANALYTICS_AGENT_ID": agent_id,
                }.items()
                if not value
            ],
        )
        raise RuntimeError("Analytics agent configuration is incomplete.")

    poll_seconds = settings.get("ANALYTICS_AGENT_POLL_INTERVAL", 0.5)
    max_attempts = settings.get("ANALYTICS_AGENT_MAX_POLLS", 120)

    try:
        polling_interval = max(0.1, float(poll_seconds))
    except (TypeError, ValueError):
        polling_interval = 0.5

    try:
        max_poll_attempts = max(1, int(max_attempts))
    except (TypeError, ValueError):
        max_poll_attempts = 120

    _AGENT = AnalyticsAgentConfig(
        agent_id=str(agent_id),
        api_key=str(api_key),
        polling_interval=polling_interval,
        max_poll_attempts=max_poll_attempts,
    )

    LOGGER.info("analytics_agent_initialized", agent_id=_AGENT.agent_id)

    return _AGENT


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


def _extract_rows(value: Any) -> list[dict[str, Any]] | None:
    """Attempt to coerce arbitrary values into a list of mapping rows."""

    if isinstance(value, Mapping):
        rows = value.get("rows")
        if isinstance(rows, Iterable):
            return _extract_rows(rows)

    if isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
        candidate_rows: list[dict[str, Any]] = []
        for item in value:
            if isinstance(item, Mapping):
                candidate_rows.append({str(key): item[key] for key in item.keys()})
            else:
                return None
        if candidate_rows:
            return candidate_rows

    return None


def _try_parse_json(value: str) -> Any:
    """Parse JSON content when the payload appears to be structured data."""

    normalized = value.strip()
    if not normalized or normalized[0] not in "[{":
        return None

    try:
        return json.loads(normalized)
    except json.JSONDecodeError:
        return None


def _coerce_response_output(response: Any) -> Any:
    """Normalize OpenAI response objects into consumable payloads."""

    if response is None:
        return None

    output_items = getattr(response, "output", None) or []
    text_segments: list[str] = []
    detected_rows: list[dict[str, Any]] | None = None

    for item in output_items:
        item_type = getattr(item, "type", None)
        if item_type == "message":
            contents = getattr(item, "content", None) or []
            for content in contents:
                content_type = getattr(content, "type", None)
                if content_type == "output_text":
                    text_value = getattr(content, "text", "")
                    if text_value:
                        text_segments.append(str(text_value))
                else:
                    maybe_rows = _extract_rows(getattr(content, "output", None))
                    if maybe_rows:
                        detected_rows = maybe_rows
        else:
            maybe_rows = _extract_rows(getattr(item, "output", None))
            if maybe_rows:
                detected_rows = maybe_rows

    combined_text = "\n\n".join(segment.strip() for segment in text_segments if segment).strip()

    if detected_rows:
        if combined_text:
            return {"text": combined_text, "rows": detected_rows}
        return detected_rows

    if combined_text:
        parsed = _try_parse_json(combined_text)
        if parsed is not None:
            rows = _extract_rows(parsed)
            if rows:
                return {"rows": rows}
            return parsed
        return combined_text

    fallback_text = getattr(response, "output_text", None)
    if isinstance(fallback_text, str) and fallback_text.strip():
        parsed = _try_parse_json(fallback_text)
        if parsed is not None:
            rows = _extract_rows(parsed)
            if rows:
                return {"rows": rows}
            return parsed
        return fallback_text.strip()

    return getattr(response, "model_dump", lambda: response)()


async def _execute_agent_query(
    agent_resource: AnalyticsAgentConfig | Any,
    query: str,
    context: Mapping[str, Any],
) -> Any:
    """Invoke either the stubbed agent or the hosted REST agent."""

    query_callable = getattr(agent_resource, "query", None)
    if callable(query_callable):
        result = query_callable(prompt=query, context=dict(context))
        if inspect.isawaitable(result):
            result = await result
        return result

    if not isinstance(agent_resource, AnalyticsAgentConfig):
        raise RuntimeError("Analytics agent is misconfigured.")

    def _run_rest_agent() -> Any:
        client = OpenAI(api_key=agent_resource.api_key)
        request_kwargs: dict[str, Any] = {
            "model": agent_resource.agent_id,
            "input": query,
        }
        if context:
            request_kwargs["metadata"] = {"context": dict(context)}

        response = client.responses.create(**request_kwargs)
        attempts = 0
        while getattr(response, "status", "completed") not in {
            "completed",
            "failed",
            "cancelled",
        }:
            attempts += 1
            if attempts >= agent_resource.max_poll_attempts:
                raise RuntimeError("Timed out waiting for analytics agent response.")

            time.sleep(agent_resource.polling_interval)
            response = client.responses.retrieve(response.id)

        if getattr(response, "status", "completed") != "completed":
            raise RuntimeError(
                f"Analytics agent run ended with status {getattr(response, 'status', 'unknown')}."
            )

        return _coerce_response_output(response)

    return await asyncio.to_thread(_run_rest_agent)


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

    context = _build_context(user, request.get("context"))

    try:
        sdk_result = await _execute_agent_query(agent, query, context)
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

    response_payload: dict[str, Any] = {"text": text, "html": html}
    if isinstance(final_output, Mapping):
        for key, value in final_output.items():
            response_payload.setdefault(key, value)

    return response_payload
