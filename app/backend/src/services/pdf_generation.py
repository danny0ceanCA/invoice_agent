"""Utilities for rendering invoice PDFs."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from tempfile import gettempdir
from typing import Mapping

from pandas import DataFrame
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas


def _format_currency(value: float) -> str:
    """Return a currency string for the numeric value."""

    return f"${value:,.2f}"


def generate_invoice_pdf(
    student: str,
    df: DataFrame,
    totals: Mapping[str, float],
    invoice_date: date | None,
    service_month: datetime,
    invoice_code: str,
    invoice_number: str,
) -> Path:
    """Render the invoice PDF and return the temporary file path."""

    output_path = Path(gettempdir()) / f"{invoice_number}.pdf"

    _, canvas_height = LETTER
    pdf = canvas.Canvas(str(output_path), pagesize=LETTER)
    pdf.setTitle(f"Invoice {invoice_number}")

    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(50, canvas_height - 80, "ASCS x SCUSD Invoice")

    pdf.setFont("Helvetica", 12)
    pdf.drawString(50, canvas_height - 110, f"Student: {student}")
    pdf.drawString(50, canvas_height - 130, f"Service Month: {service_month.strftime('%B %Y')}")

    invoice_date_label = invoice_date.strftime("%B %d, %Y") if invoice_date else "N/A"
    pdf.drawString(50, canvas_height - 150, f"Invoice #: {invoice_number}")
    pdf.drawString(300, canvas_height - 150, f"Invoice Date: {invoice_date_label}")
    pdf.drawString(50, canvas_height - 170, f"Invoice Code: {invoice_code}")

    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(50, canvas_height - 210, "Service Summary")

    pdf.setFont("Helvetica", 11)
    y_position = canvas_height - 240
    pdf.drawString(50, y_position, "Service Code")
    pdf.drawString(170, y_position, "Hours")
    pdf.drawString(240, y_position, "Rate")
    pdf.drawString(320, y_position, "Cost")
    y_position -= 20

    for _, row in df.iterrows():
        pdf.drawString(50, y_position, str(row.get("Service Code", "-")))
        pdf.drawString(170, y_position, f"{float(row['Hours']):.2f}")
        pdf.drawString(240, y_position, _format_currency(float(row.get("Rate", 0.0))))
        pdf.drawString(320, y_position, _format_currency(float(row.get("Cost", 0.0))))
        y_position -= 18

        if y_position < 80:
            pdf.showPage()
            pdf.setFont("Helvetica", 11)
            y_position = canvas_height - 80

    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(50, y_position - 10, "Totals")
    pdf.setFont("Helvetica", 11)
    pdf.drawString(170, y_position - 30, f"Hours: {totals['Hours']:.2f}")
    pdf.drawString(320, y_position - 30, f"Total: {_format_currency(totals['Cost'])}")

    pdf.showPage()
    pdf.save()

    return output_path
