"""Upload model."""

from __future__ import annotations

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Upload(Base):
    """Represents a vendor upload event."""

    __tablename__ = "uploads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vendor_id: Mapped[int] = mapped_column(ForeignKey("vendors.id"), nullable=False, index=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("dataset_profiles.id"), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    month: Mapped[str] = mapped_column(String(7), nullable=False, index=True)
    row_count: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="queued")
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    vendor: Mapped["Vendor"] = relationship("Vendor", back_populates="uploads")
    dataset: Mapped["DatasetProfile"] = relationship("DatasetProfile", back_populates="uploads")
    invoices: Mapped[list["Invoice"]] = relationship("Invoice", back_populates="upload")
