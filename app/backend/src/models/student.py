from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, UniqueConstraint

from .base import Base


class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    district_key = Column(String(64), nullable=False, index=True)

    # Internal student key, e.g. "SK-00000001"
    student_key = Column(String(32), nullable=False, unique=True, index=True)

    first_name = Column(String(128), nullable=False)
    last_name = Column(String(128), nullable=False)
    full_name = Column(String(256), nullable=False, index=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    __table_args__ = (
        # Natural key (for lookups), not enforced as unique across all time
        UniqueConstraint("district_key", "full_name", name="uq_students_district_full_name"),
    )


__all__ = ["Student"]
