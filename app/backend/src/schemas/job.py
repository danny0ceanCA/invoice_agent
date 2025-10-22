"""Job API schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class JobRead(BaseModel):
    """Schema for job records exposed via the API."""

    id: int
    vendor_id: int
    invoice_id: int | None
    filename: str
    status: str
    message: str | None
    created_at: datetime
    download_url: str | None
