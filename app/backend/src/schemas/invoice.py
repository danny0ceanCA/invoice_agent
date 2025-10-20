"""Invoice schemas."""

from decimal import Decimal

from pydantic import BaseModel

from .line_item import InvoiceLineItemRead


class InvoiceRead(BaseModel):
    id: int
    invoice_no: str
    vendor_id: int
    month: str
    total_cost: Decimal
    total_hours: Decimal
    status: str
    pdf_s3_key: str | None
    line_items: list[InvoiceLineItemRead] = []


class InvoiceSummary(BaseModel):
    id: int
    invoice_no: str
    vendor_id: int
    month: str
    status: str
