"""Analytics schemas."""

from pydantic import BaseModel


class SummaryStats(BaseModel):
    total_invoices: int
    approved: int
    pending: int
    total_cost: float
