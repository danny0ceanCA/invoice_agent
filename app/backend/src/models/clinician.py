from __future__ import annotations

from sqlalchemy import Column, Integer, String, UniqueConstraint
from app.backend.src.db.base import Base


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

    __table_args__ = (
        UniqueConstraint("district_key", "full_name", name="uq_clinicians_district_full_name"),
    )
