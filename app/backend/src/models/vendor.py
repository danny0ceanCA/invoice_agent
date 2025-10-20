"""Vendor model."""

from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Vendor(Base):
    """Represents a vendor organization."""

    __tablename__ = "vendors"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    contact_email: Mapped[str] = mapped_column(String(255), nullable=False)

    users: Mapped[list["User"]] = relationship("User", back_populates="vendor")
    datasets: Mapped[list["Dataset"]] = relationship("Dataset", back_populates="vendor")
    uploads: Mapped[list["Upload"]] = relationship("Upload", back_populates="vendor")
    invoices: Mapped[list["Invoice"]] = relationship("Invoice", back_populates="vendor")
