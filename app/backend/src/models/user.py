"""User model."""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class User(Base):
    """Represents an application user."""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "(role IS NULL) OR (role IN ('vendor','district','admin'))",
            name="ck_users_role_valid",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_approved: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    vendor_id: Mapped[int | None] = mapped_column(
        ForeignKey("vendors.id"), nullable=True, index=True
    )
    district_id: Mapped[int | None] = mapped_column(
        ForeignKey("districts.id"), nullable=True, index=True
    )
    auth0_sub: Mapped[str | None] = mapped_column(
        String(255), unique=True, nullable=True, index=True
    )
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    vendor: Mapped["Vendor | None"] = relationship("Vendor", back_populates="users")
    district: Mapped["District | None"] = relationship(
        "District", back_populates="users"
    )
    district_memberships: Mapped[list["DistrictMembership"]] = relationship(
        "DistrictMembership",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    approvals: Mapped[list["Approval"]] = relationship("Approval", back_populates="reviewer")
    jobs: Mapped[list["Job"]] = relationship("Job", back_populates="user")

    @property
    def vendor_company_name(self) -> str | None:
        """Return the associated vendor's company name, if available."""

        return self.vendor.company_name if self.vendor else None

    @property
    def district_company_name(self) -> str | None:
        """Return the associated district's company name, if available."""

        return self.district.company_name if self.district else None

    @property
    def active_district_id(self) -> int | None:
        """Return the identifier for the user's active district selection."""

        if getattr(self, "district_id", None) is not None:
            return self.district_id
        if self.district_memberships:
            return self.district_memberships[0].district_id
        return None
