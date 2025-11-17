from __future__ import annotations

from sqlalchemy.orm import declarative_base

# Shared SQLAlchemy declarative base for all models.
Base = declarative_base()

__all__ = ["Base"]
