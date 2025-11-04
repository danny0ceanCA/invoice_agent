"""Dataset profile model."""

from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class DatasetProfile(Base):
    """Represents a dataset processing profile."""

    __tablename__ = "dataset_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vendor_id: Mapped[int] = mapped_column(ForeignKey("vendors.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1024))
    rules_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    vendor: Mapped["Vendor"] = relationship("Vendor", back_populates="datasets")
    uploads: Mapped[list["Upload"]] = relationship("Upload", back_populates="dataset")


__all__ = ["DatasetProfile"]
