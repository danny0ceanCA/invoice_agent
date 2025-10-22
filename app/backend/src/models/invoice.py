"""Invoice model."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:  # pragma: no cover - imported for type checking only
    from .approval import Approval
    from .job import Job
    from .line_item import InvoiceLineItem
    from .vendor import Vendor


class Invoice(Base):
    """Represents an invoice generated for a vendor and student."""

    __tablename__ = "invoices"
    __table_args__ = ({"sqlite_autoincrement": True},)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vendor_id: Mapped[int] = mapped_column(ForeignKey("vendors.id"), nullable=False, index=True)
    student_name: Mapped[str] = mapped_column(String(255), nullable=False)
    invoice_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    total_hours: Mapped[Numeric] = mapped_column(Numeric(scale=2), nullable=False, default=0)
    total_cost: Mapped[Numeric] = mapped_column(Numeric(scale=2), nullable=False, default=0)
    service_month: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    invoice_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    pdf_s3_key: Mapped[str | None] = mapped_column(String(512))
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    vendor: Mapped["Vendor"] = relationship("Vendor", back_populates="invoices")
    line_items: Mapped[list["InvoiceLineItem"]] = relationship("InvoiceLineItem", back_populates="invoice")
    approvals: Mapped[list["Approval"]] = relationship("Approval", back_populates="invoice")
    jobs: Mapped[list["Job"]] = relationship("Job", back_populates="invoice")
