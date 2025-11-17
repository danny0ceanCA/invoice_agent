"""Invoice model."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.backend.src.db.base import Base


class Invoice(Base):
    """Represents an invoice generated from a dataset upload."""

    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vendor_id: Mapped[int] = mapped_column(ForeignKey("vendors.id"), nullable=False, index=True)
    upload_id: Mapped[int | None] = mapped_column(ForeignKey("uploads.id"))
    student_name: Mapped[str] = mapped_column(String(255), nullable=False)
    invoice_number: Mapped[str] = mapped_column(
        String(128), unique=True, nullable=False, index=True
    )
    invoice_code: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    service_month: Mapped[str] = mapped_column(String(32), nullable=False)
    service_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    service_month_num: Mapped[int | None] = mapped_column(Integer, nullable=True)
    invoice_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    total_hours: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    total_cost: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="generated")
    pdf_s3_key: Mapped[str] = mapped_column(String(512), nullable=False)
    district_key: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    vendor_name_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    vendor: Mapped["Vendor"] = relationship("Vendor", back_populates="invoices")
    upload: Mapped["Upload | None"] = relationship("Upload", back_populates="invoices")
    line_items: Mapped[list["InvoiceLineItem"]] = relationship(
        "InvoiceLineItem", back_populates="invoice", cascade="all, delete-orphan"
    )
    approvals: Mapped[list["Approval"]] = relationship("Approval", back_populates="invoice")

    @property
    def s3_key(self) -> str:
        """Return the storage object key for the generated invoice PDF."""

        return self.pdf_s3_key

    @s3_key.setter
    def s3_key(self, value: str) -> None:
        """Persist the storage object key for compatibility with legacy code paths."""

        self.pdf_s3_key = value


__all__ = ["Invoice"]
