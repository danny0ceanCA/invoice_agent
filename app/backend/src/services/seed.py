"""Utilities for seeding development data."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.backend.src.models import User, Vendor

DEFAULT_VENDOR_NAME = "SCUSD Accounts Payable"
DEFAULT_VENDOR_EMAIL = "ap@scusd.example"
DEFAULT_USER_EMAIL = "daniel@responsivehcsolutions.com"
DEFAULT_USER_NAME = "Daniel Ojeda"
DEFAULT_USER_ROLE = "admin"


@dataclass
class SeedResult:
    """Information about the seeded vendor and user."""

    vendor: Vendor
    user: User
    vendor_created: bool
    user_created: bool
    vendor_updated: bool
    user_updated: bool


def seed_development_user(
    session: Session,
    *,
    vendor_name: str = DEFAULT_VENDOR_NAME,
    vendor_email: str = DEFAULT_VENDOR_EMAIL,
    user_email: str = DEFAULT_USER_EMAIL,
    user_name: str = DEFAULT_USER_NAME,
    user_role: str = DEFAULT_USER_ROLE,
    auth0_sub: str | None = None,
) -> SeedResult:
    """Ensure a demo vendor and user exist for local development.

    Returns a :class:`SeedResult` describing whether new records were created.
    Existing records are updated so they remain associated.
    """

    vendor = session.query(Vendor).filter(Vendor.name == vendor_name).one_or_none()
    vendor_created = False
    vendor_updated = False
    if vendor is None:
        vendor = Vendor(name=vendor_name, contact_email=vendor_email)
        session.add(vendor)
        session.flush()
        vendor_created = True
    else:
        if vendor.contact_email != vendor_email:
            vendor.contact_email = vendor_email
            vendor_updated = True

    user = session.query(User).filter(User.email == user_email).one_or_none()
    user_created = False
    user_updated = False
    if user is None:
        user = User(
            email=user_email,
            name=user_name,
            role=user_role,
            vendor_id=vendor.id,
            auth0_sub=auth0_sub,
        )
        session.add(user)
        session.flush()
        user_created = True
    else:
        if user.vendor_id != vendor.id:
            user.vendor_id = vendor.id
            user_updated = True
        if user.role != user_role:
            user.role = user_role
            user_updated = True
        if user.name != user_name:
            user.name = user_name
            user_updated = True
        if auth0_sub and user.auth0_sub != auth0_sub:
            user.auth0_sub = auth0_sub
            user_updated = True

    return SeedResult(
        vendor=vendor,
        user=user,
        vendor_created=vendor_created,
        user_created=user_created,
        vendor_updated=vendor_updated,
        user_updated=user_updated,
    )


__all__ = ["seed_development_user", "SeedResult"]
