"""Invoice model."""

from __future__ import annotations

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Invoice(Base):
    """Represents an invoice generated from a dataset upload."""

    __tablename__ = "invoices"
    __table_args__ = ({"sqlite_autoincrement": True},)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    invoice_no: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    vendor_id: Mapped[int] = mapped_column(ForeignKey("vendors.id"), nullable=False, index=True)
    upload_id: Mapped[int | None] = mapped_column(ForeignKey("uploads.id"))
    month: Mapped[str] = mapped_column(String(7), nullable=False, index=True)
    total_cost: Mapped[Numeric] = mapped_column(Numeric(scale=2), nullable=False, default=0)
    total_hours: Mapped[Numeric] = mapped_column(Numeric(scale=2), nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    pdf_s3_key: Mapped[str | None] = mapped_column(String(512))
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    approved_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    vendor: Mapped["Vendor"] = relationship("Vendor", back_populates="invoices")
    upload: Mapped["Upload" | None] = relationship("Upload", back_populates="invoices")
    line_items: Mapped[list["InvoiceLineItem"]] = relationship("InvoiceLineItem", back_populates="invoice")
    approvals: Mapped[list["Approval"]] = relationship("Approval", back_populates="invoice")
