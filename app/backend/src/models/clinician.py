from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, UniqueConstraint

from .base import Base


class Clinician(Base):
    __tablename__ = "clinicians"

    id = Column(Integer, primary_key=True, index=True)
    district_key = Column(String(64), nullable=False, index=True)

    first_name = Column(String(128), nullable=False)
    last_name = Column(String(128), nullable=False)
    full_name = Column(String(256), nullable=False, index=True)

    # Derived from service_code prefix, e.g. "HHA", "LVN"
    license_code = Column(String(32), nullable=True)
    # Human readable, e.g. "Health Aide", "Licensed Vocational Nurse"
    license_title = Column(String(128), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("district_key", "full_name", name="uq_clinicians_district_full_name"),
    )


__all__ = ["Clinician"]
