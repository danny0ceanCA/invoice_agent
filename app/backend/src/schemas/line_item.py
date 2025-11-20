"""Invoice line item schema."""

from decimal import Decimal

from pydantic import BaseModel


class InvoiceLineItemRead(BaseModel):
    id: int
    invoice_id: int
    invoice_number: str
    student: str
    clinician: str
    service_code: str
    site: str | None
    hours: Decimal
    rate: Decimal
    cost: Decimal
    service_date: str
