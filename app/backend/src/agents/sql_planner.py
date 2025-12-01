"""SQL template routing and rendering."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from jinja2 import Environment, FileSystemLoader


_TEMPLATES_DIR = Path(__file__).parent / "sql_templates"
_ENV = Environment(loader=FileSystemLoader(_TEMPLATES_DIR), autoescape=False)


def render_template(template_name: str, context: Mapping[str, Any]) -> str:
    """Render a SQL template with the provided context."""

    template = _ENV.get_template(template_name)
    return template.render(context)


def route_sql_template(
    *, intent: str, entities: dict[str, Any] | None, time_period: dict[str, Any] | None
) -> str:
    """Select and render the SQL template for the given intent."""

    entities = entities or {}
    time_period = time_period or {}

    # Detect invoice-details-by-month-for-student
    if intent == "invoice_details" \
       and entities.get("student_name") \
       and time_period.get("month"):

        print("[sql-planner] ROUTE invoice_details_month_student", flush=True)
        print("[sql-planner-debug] student_month_template", flush=True)

        return render_template(
            "invoice_details_month_student.sql",
            {
                "student_name": entities["student_name"],
                "month": time_period["month"],
                "start_date": time_period["start_date"],
                "end_date": time_period["end_date"],
            }
        )

    if intent == "invoice_details" and entities.get("student_name"):
        print("[sql-planner] ROUTE invoice_details_student_year", flush=True)
        return render_template(
            "invoice_details_student_year.sql",
            {
                "student_name": entities["student_name"],
                "start_date": time_period.get("start_date"),
                "end_date": time_period.get("end_date"),
            },
        )

    if intent == "invoice_details":
        print("[sql-planner] ROUTE invoice_details_year", flush=True)
        return render_template(
            "invoice_details_year.sql",
            {
                "start_date": time_period.get("start_date"),
                "end_date": time_period.get("end_date"),
            },
        )

    print("[sql-planner] ROUTE invoice_summary", flush=True)
    return render_template("invoice_summary.sql", {})


__all__ = ["render_template", "route_sql_template"]
