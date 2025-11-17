"""Invoice line item model."""

from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.backend.src.db.base import Base


class InvoiceLineItem(Base):
    """Represents a detailed invoice line item."""

    __tablename__ = "invoice_line_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"), nullable=False, index=True)
    student: Mapped[str] = mapped_column(String(255), nullable=False)
    clinician: Mapped[str] = mapped_column(String(255), nullable=False)
    service_code: Mapped[str] = mapped_column(String(50), nullable=False)
    hours: Mapped[float] = mapped_column(Float, nullable=False)
    rate: Mapped[float] = mapped_column(Float, nullable=False)
    cost: Mapped[float] = mapped_column(Float, nullable=False)
    service_date: Mapped[str] = mapped_column(String(32), nullable=False)

    invoice: Mapped["Invoice"] = relationship("Invoice", back_populates="line_items")


__all__ = ["InvoiceLineItem"]
