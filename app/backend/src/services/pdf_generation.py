"""Utilities for generating invoice PDFs."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from time import perf_counter

import pandas as pd
from reportlab.lib.colors import HexColor
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
    width, height = letter

    margin = 50
    header_height = 120
    primary_color = HexColor("#0F172A")
    accent_color = HexColor("#6366F1")
    muted_text = HexColor("#64748B")
    light_panel = HexColor("#F8FAFC")
    table_header_color = HexColor("#EEF2FF")
    border_color = HexColor("#E2E8F0")

    def draw_brand_header() -> float:
        badge_width = 118
        badge_height = 30
        badge_x = width - margin - badge_width
        badge_y = height - header_height + 38

        pdf_canvas.setFillColor(primary_color)
        pdf_canvas.rect(0, height - header_height, width, header_height, fill=1, stroke=0)

        pdf_canvas.setFont("Helvetica-Bold", 18)
        pdf_canvas.setFillColor(HexColor("#FFFFFF"))
        pdf_canvas.drawString(margin, height - 58, "Action Supportive Care Services")
        pdf_canvas.setFont("Helvetica", 10)
        pdf_canvas.setFillColor(HexColor("#CBD5F5"))
        pdf_canvas.drawString(margin, height - 78, "Comprehensive Behavioral Support Solutions")

        pdf_canvas.setFillColor(accent_color)
        pdf_canvas.roundRect(badge_x, badge_y, badge_width, badge_height, 8, fill=1, stroke=0)
        pdf_canvas.setFont("Helvetica-Bold", 12)
        pdf_canvas.setFillColor(HexColor("#FFFFFF"))
        pdf_canvas.drawRightString(badge_x + badge_width - 10, badge_y + 18, "INVOICE")
        pdf_canvas.setFont("Helvetica", 9)
        pdf_canvas.setFillColor(HexColor("#E2E8F0"))
        pdf_canvas.drawRightString(width - margin, height - 78, service_month)
        pdf_canvas.drawRightString(width - margin, height - 92, f"Issue Date: {invoice_date}")

        pdf_canvas.setStrokeColor(border_color)
        pdf_canvas.setFillColor(primary_color)
        return height - header_height - 36

    def draw_invoice_summary(top: float) -> float:
        card_height = 96
        left_x = margin + 24
        middle_x = margin + 220
        right_box_width = 150
        card_bottom = top - card_height

        pdf_canvas.setFillColor(light_panel)
        pdf_canvas.roundRect(margin, card_bottom, width - 2 * margin, card_height, 12, fill=1, stroke=0)

        pdf_canvas.setFillColor(primary_color)
        pdf_canvas.setFont("Helvetica-Bold", 11)
        pdf_canvas.drawString(left_x, top - 28, "Bill To")
        pdf_canvas.setFont("Helvetica", 10)
        pdf_canvas.setFillColor(muted_text)
        pdf_canvas.drawString(left_x, top - 45, student)
        pdf_canvas.drawString(left_x, top - 61, "Service Month")
        pdf_canvas.setFont("Helvetica-Bold", 10)
        pdf_canvas.setFillColor(primary_color)
        pdf_canvas.drawString(left_x + 90, top - 61, service_month)

        pdf_canvas.setFont("Helvetica-Bold", 11)
        pdf_canvas.drawString(middle_x, top - 28, "Invoice Details")
        pdf_canvas.setFont("Helvetica", 10)
        pdf_canvas.setFillColor(muted_text)
        pdf_canvas.drawString(middle_x, top - 45, f"Invoice Date: {invoice_date}")
        label = invoice_number or invoice_code
        if label:
            pdf_canvas.drawString(middle_x, top - 61, f"Invoice #: {label}")

        highlight_x = width - margin - right_box_width - 20
        pdf_canvas.setFillColor(table_header_color)
        pdf_canvas.roundRect(
            highlight_x,
            card_bottom + 18,
            right_box_width,
            card_height - 36,
            10,
            fill=1,
            stroke=0,
        )
        pdf_canvas.setFont("Helvetica", 9)
        pdf_canvas.setFillColor(muted_text)
        pdf_canvas.drawRightString(highlight_x + right_box_width - 14, card_bottom + card_height - 30, "Total Due")
        pdf_canvas.setFont("Helvetica-Bold", 16)
        pdf_canvas.setFillColor(accent_color)
        pdf_canvas.drawRightString(
            highlight_x + right_box_width - 14,
            card_bottom + card_height - 52,
            f"${totals['Cost']:.2f}",
        )

        pdf_canvas.setFillColor(primary_color)
        return card_bottom - 32

    def draw_table_header(top: float) -> float:
        header_height = 26
        pdf_canvas.setFillColor(table_header_color)
        pdf_canvas.roundRect(
            margin,
            top - header_height,
            width - 2 * margin,
            header_height,
            8,
            fill=1,
            stroke=0,
        )

        headers = [
            "Service Date",
            "Clinician",
            "Service Code",
            "Hours",
            "Rate",
            "Cost",
        ]
        columns = [
            margin + 18,
            margin + 175,
            margin + 315,
            margin + 420,
            margin + 490,
            width - margin - 10,
        ]

        pdf_canvas.setFillColor(primary_color)
        pdf_canvas.setFont("Helvetica-Bold", 10)
        for idx, header in enumerate(headers):
            x = columns[idx]
            if header in {"Hours", "Rate", "Cost"}:
                pdf_canvas.drawRightString(x, top - 10, header)
            else:
                pdf_canvas.drawString(x, top - 10, header)

        pdf_canvas.setFont("Helvetica", 10)
        pdf_canvas.setFillColor(primary_color)
        return top - header_height - 18

    y_position = draw_brand_header()
    y_position = draw_invoice_summary(y_position)
    y_position = draw_table_header(y_position)

    columns = [
        margin + 18,
        margin + 175,
        margin + 315,
        margin + 420,
        margin + 490,
        width - margin - 10,
    ]

    rows = df.reset_index(drop=True)
    row_height = 22
    for idx, row in rows.iterrows():
        if y_position < 110:
            pdf_canvas.showPage()
            y_position = draw_brand_header()
            y_position = draw_table_header(y_position)

        if idx % 2 == 0:
            pdf_canvas.setFillColor(light_panel)
            pdf_canvas.roundRect(
                margin,
                y_position - row_height + 6,
                width - 2 * margin,
                row_height - 4,
                6,
                fill=1,
                stroke=0,
            )

        pdf_canvas.setFillColor(primary_color)
        pdf_canvas.setFont("Helvetica", 10)
        pdf_canvas.drawString(columns[0], y_position - 10, str(row["Schedule Date"]))
        pdf_canvas.drawString(columns[1], y_position - 10, str(row["Employee"]))
        pdf_canvas.drawString(columns[2], y_position - 10, str(row["Service Code"]))
        pdf_canvas.drawRightString(columns[3], y_position - 10, f"{row['Hours']:.2f}")
        pdf_canvas.drawRightString(columns[4], y_position - 10, f"${row['Rate']:.2f}")
        pdf_canvas.drawRightString(columns[5], y_position - 10, f"${row['Cost']:.2f}")
        y_position -= row_height

    pdf_canvas.setStrokeColor(border_color)
    pdf_canvas.line(margin, y_position - 6, width - margin, y_position - 6)
    pdf_canvas.setFont("Helvetica-Bold", 11)
    pdf_canvas.setFillColor(muted_text)
    pdf_canvas.drawRightString(columns[4], y_position - 26, "Total Due")
    pdf_canvas.setFont("Helvetica-Bold", 14)
    pdf_canvas.setFillColor(accent_color)
    pdf_canvas.drawRightString(columns[5], y_position - 26, f"${totals['Cost']:.2f}")

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
