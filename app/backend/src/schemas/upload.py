"""Upload schemas."""

from datetime import datetime

from pydantic import BaseModel


class UploadRead(BaseModel):
    id: int
    vendor_id: int
    dataset_id: int
    filename: str
    month: str
    row_count: int | None
    status: str
    created_at: datetime


class UploadCreate(BaseModel):
    vendor_id: int
    dataset_id: int
    filename: str
    month: str
