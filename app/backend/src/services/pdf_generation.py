"""Utilities for generating invoice PDFs."""

from __future__ import annotations

from pathlib import Path
from tempfile import gettempdir
from time import perf_counter

import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from app.backend.src.services.metrics import pdf_generation_seconds


def _resolve_output_path(student: str, service_month: str) -> Path:
    safe_student = student.replace(" ", "_")
    filename = f"Invoice_{safe_student}_{service_month}.pdf"
    return Path(gettempdir()) / filename


def generate_invoice_pdf(
    student: str,
    df: pd.DataFrame,
    totals: dict[str, float],
    invoice_date: str,
    service_month: str,
    invoice_code: str | None = None,
) -> Path:
    """Render a student-level invoice PDF and return the file path."""

    output_path = _resolve_output_path(student, service_month)
    start = perf_counter()
    pdf_canvas = canvas.Canvas(str(output_path), pagesize=letter)
    _, height = letter

    pdf_canvas.setFont("Helvetica-Bold", 16)
    pdf_canvas.drawString(50, height - 60, "Action Supportive Care Services")
    pdf_canvas.setFont("Helvetica", 12)
    pdf_canvas.drawString(50, height - 90, f"Student: {student}")
    pdf_canvas.drawString(50, height - 110, f"Service Month: {service_month}")
    pdf_canvas.drawString(50, height - 130, f"Invoice Date: {invoice_date}")
    if invoice_code:
        pdf_canvas.drawString(50, height - 150, f"Invoice #: {invoice_code}")

    y_position = height - 190
    headers = [
        "Service Date",
        "Clinician",
        "Service Code",
        "Hours",
        "Rate",
        "Cost",
    ]
    columns = [50, 160, 290, 400, 470, 540]

    pdf_canvas.setFont("Helvetica-Bold", 10)
    for idx, header in enumerate(headers):
        pdf_canvas.drawString(columns[idx], y_position, header)

    pdf_canvas.setFont("Helvetica", 10)
    y_position -= 20

    for _, row in df.iterrows():
        if y_position < 100:
            pdf_canvas.showPage()
            y_position = height - 100
            pdf_canvas.setFont("Helvetica-Bold", 10)
            for idx, header in enumerate(headers):
                pdf_canvas.drawString(columns[idx], y_position, header)
            pdf_canvas.setFont("Helvetica", 10)
            y_position -= 20

        pdf_canvas.drawString(columns[0], y_position, str(row["Schedule Date"]))
        pdf_canvas.drawString(columns[1], y_position, str(row["Employee"]))
        pdf_canvas.drawString(columns[2], y_position, str(row["Service Code"]))
        pdf_canvas.drawRightString(columns[3] + 30, y_position, f"{row['Hours']:.2f}")
        pdf_canvas.drawRightString(columns[4] + 30, y_position, f"${row['Rate']:.2f}")
        pdf_canvas.drawRightString(columns[5] + 30, y_position, f"${row['Cost']:.2f}")
        y_position -= 16

    pdf_canvas.setFont("Helvetica-Bold", 12)
    pdf_canvas.drawRightString(columns[4] + 30, y_position - 20, "Total:")
    pdf_canvas.drawRightString(
        columns[5] + 30,
        y_position - 20,
        f"${totals['Cost']:.2f}",
    )
    pdf_canvas.save()

    pdf_generation_seconds.observe(perf_counter() - start)
    return output_path


__all__ = ["generate_invoice_pdf"]
