"""Vendor schemas."""

from pydantic import BaseModel, EmailStr


class VendorRead(BaseModel):
    id: int
    name: str
    contact_email: EmailStr


class VendorCreate(BaseModel):
    name: str
    contact_email: EmailStr
