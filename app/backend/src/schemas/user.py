"""Pydantic schemas for users."""

from pydantic import BaseModel, EmailStr


class UserRead(BaseModel):
    """Public user representation."""

    id: int
    email: EmailStr
    name: str
    role: str


class UserCreate(BaseModel):
    """Schema for creating a user."""

    email: EmailStr
    name: str
    role: str
    vendor_id: int | None = None
