"""Vendor model."""

from __future__ import annotations

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.backend.src.db.base import Base


class Vendor(Base):
    """Represents a vendor organization."""

    __tablename__ = "vendors"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    company_name: Mapped[str] = mapped_column(
        "name", String(255), unique=True, nullable=False
    )
    contact_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_email: Mapped[str] = mapped_column(String(255), nullable=False)
    phone_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    remit_to_street: Mapped[str | None] = mapped_column(String(255), nullable=True)
    remit_to_city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    remit_to_state: Mapped[str | None] = mapped_column(String(32), nullable=True)
    remit_to_postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    district_key: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("districts.district_key"),
        nullable=True,
        index=True,
    )

    users: Mapped[list["User"]] = relationship("User", back_populates="vendor")
    datasets: Mapped[list["DatasetProfile"]] = relationship("DatasetProfile", back_populates="vendor")
    uploads: Mapped[list["Upload"]] = relationship("Upload", back_populates="vendor")
    invoices: Mapped[list["Invoice"]] = relationship("Invoice", back_populates="vendor")
    jobs: Mapped[list["Job"]] = relationship("Job", back_populates="vendor")
    district: Mapped["District | None"] = relationship(
        "District",
        back_populates="vendors",
        primaryjoin="Vendor.district_key == District.district_key",
        foreign_keys="Vendor.district_key",
    )
