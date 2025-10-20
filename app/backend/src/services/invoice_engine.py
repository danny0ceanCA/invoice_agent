"""Invoice generation engine."""

from __future__ import annotations

from io import BytesIO

from reportlab.pdfgen import canvas


def render_invoice_pdf(student: str, *, total_cost: float) -> bytes:
    """Render a minimal PDF for the supplied student."""
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.drawString(72, 750, f"Invoice for {student}")
    pdf.drawString(72, 720, f"Total Cost: ${total_cost:,.2f}")
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()
