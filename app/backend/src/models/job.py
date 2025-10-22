"""Job model for tracking processing tasks."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:  # pragma: no cover - imported for typing only
    from .invoice import Invoice
    from .vendor import Vendor


class Job(Base):
    """Represents an asynchronous processing job."""

    __tablename__ = "jobs"
    __table_args__ = ({"sqlite_autoincrement": True},)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vendor_id: Mapped[int] = mapped_column(ForeignKey("vendors.id"), nullable=False, index=True)
    invoice_id: Mapped[int | None] = mapped_column(ForeignKey("invoices.id"))
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    message: Mapped[str | None] = mapped_column(String(1024))
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    vendor: Mapped["Vendor"] = relationship("Vendor", back_populates="jobs")
    invoice: Mapped["Invoice | None"] = relationship("Invoice", back_populates="jobs")
