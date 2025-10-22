"""Invoice schemas."""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel

from .line_item import InvoiceLineItemRead


class InvoiceRead(BaseModel):
    id: int
    vendor_id: int
    student_name: str
    invoice_number: str
    service_month: str
    invoice_date: date | None
    total_cost: Decimal
    total_hours: Decimal
    pdf_s3_key: str | None
    line_items: list[InvoiceLineItemRead] = []


class InvoiceSummary(BaseModel):
    id: int
    vendor_id: int
    student_name: str
    invoice_number: str
    service_month: str
