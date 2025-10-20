"""Approval schemas."""

from datetime import datetime

from pydantic import BaseModel


class ApprovalRead(BaseModel):
    id: int
    invoice_id: int
    reviewer_id: int
    decision: str
    comment: str | None
    created_at: datetime
