"""District model."""

from __future__ import annotations

import secrets
import string

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.backend.src.db.base import Base


class District(Base):
    """Represents a district organization."""

    __tablename__ = "districts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    company_name: Mapped[str] = mapped_column(
        "name", String(255), unique=True, nullable=False
    )
    contact_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    mailing_street: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mailing_city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    mailing_state: Mapped[str | None] = mapped_column(String(32), nullable=True)
    mailing_postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    district_key: Mapped[str] = mapped_column(
        String(32), unique=True, nullable=False, index=True, default=lambda: _generate_district_key()
    )

    users: Mapped[list["User"]] = relationship("User", back_populates="district")
    memberships: Mapped[list["DistrictMembership"]] = relationship(
        "DistrictMembership",
        back_populates="district",
        cascade="all, delete-orphan",
    )
    vendors: Mapped[list["Vendor"]] = relationship(
        "Vendor",
        back_populates="district",
        primaryjoin="District.district_key == Vendor.district_key",
        foreign_keys="Vendor.district_key",
    )


__all__ = ["District"]


ALPHABET = string.ascii_uppercase + string.digits


def _generate_district_key() -> str:
    """Return a random district access key."""

    raw = "".join(secrets.choice(ALPHABET) for _ in range(12))
    return "-".join(raw[i : i + 4] for i in range(0, len(raw), 4))
