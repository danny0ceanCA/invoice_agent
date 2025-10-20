"""Dataset schemas."""

from pydantic import BaseModel


class DatasetRead(BaseModel):
    id: int
    vendor_id: int
    name: str
    description: str | None
    rules_json: dict
    active: bool


class DatasetCreate(BaseModel):
    vendor_id: int
    name: str
    description: str | None = None
    rules_json: dict
