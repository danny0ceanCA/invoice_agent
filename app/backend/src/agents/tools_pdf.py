"""Placeholder utilities for PDF generation."""

from reportlab.pdfgen import canvas


def build_basic_pdf(buffer, *, title: str, body: str) -> None:
    """Render a very small PDF document for smoke testing."""
    pdf = canvas.Canvas(buffer)
    pdf.setTitle(title)
    pdf.drawString(72, 750, title)
    pdf.drawString(72, 720, body)
    pdf.showPage()
    pdf.save()
