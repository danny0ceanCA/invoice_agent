"""Utilities for generating invoice PDFs."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from time import perf_counter

import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from app.backend.src.services.metrics import pdf_generation_seconds
from app.backend.src.services.s3 import upload_bytes


@dataclass(frozen=True, slots=True)
class InvoicePdf:
    """Representation of a generated invoice PDF stored in S3."""

    key: str
    filename: str
    content: bytes


def _build_filename(student: str, service_month: str) -> str:
    safe_student = student.replace(" ", "_")
    return f"Invoice_{safe_student}_{service_month}.pdf"


def generate_invoice_pdf(
    student: str,
    df: pd.DataFrame,
    totals: dict[str, float],
    invoice_date: str,
    service_month: str,
    invoice_code: str | None = None,
    invoice_number: str | None = None,
) -> InvoicePdf:
    """Render a student-level invoice PDF and upload it to S3."""

    filename = _build_filename(student, service_month)
    start = perf_counter()
    buffer = BytesIO()
    pdf_canvas = canvas.Canvas(buffer, pagesize=letter)
    _, height = letter

    pdf_canvas.setFont("Helvetica-Bold", 16)
    pdf_canvas.drawString(50, height - 60, "Action Supportive Care Services")
    pdf_canvas.setFont("Helvetica", 12)
    pdf_canvas.drawString(50, height - 90, f"Student: {student}")
    pdf_canvas.drawString(50, height - 110, f"Service Month: {service_month}")
    pdf_canvas.drawString(50, height - 130, f"Invoice Date: {invoice_date}")
    label = invoice_number or invoice_code
    if label:
        pdf_canvas.drawString(50, height - 150, f"Invoice #: {label}")

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

    buffer.seek(0)
    pdf_bytes = buffer.read()
    pdf_generation_seconds.observe(perf_counter() - start)
    key = upload_bytes(
        pdf_bytes,
        filename=filename,
        content_type="application/pdf",
    )
    return InvoicePdf(key=key, filename=filename, content=pdf_bytes)


__all__ = ["InvoicePdf", "generate_invoice_pdf"]
