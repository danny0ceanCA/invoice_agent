"""Association table linking district users to their districts."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class DistrictMembership(Base):
    """Represents a user's access to a district via a shared key."""

    __tablename__ = "district_memberships"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "district_id",
            name="uq_district_memberships_user_district",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    district_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("districts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship("User", back_populates="district_memberships")
    district: Mapped["District"] = relationship(
        "District", back_populates="memberships"
    )


__all__ = ["DistrictMembership"]
