"""Add approval and activation flags to the users table."""

from __future__ import annotations

from sqlalchemy import text

from .. import get_engine


def upgrade() -> None:
    """Apply the migration."""

    engine = get_engine()
    with engine.begin() as connection:
        dialect = connection.dialect.name

        if dialect == "sqlite":
            connection.execute(
                text(
                    "ALTER TABLE users ADD COLUMN is_approved BOOLEAN NOT NULL DEFAULT 0"
                )
            )
            connection.execute(
                text(
                    "ALTER TABLE users ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT 1"
                )
            )
            return

        if dialect not in {"postgresql", "postgres"}:
            raise RuntimeError(f"Unsupported database dialect: {dialect}")

        connection.execute(
            text(
                "ALTER TABLE users ADD COLUMN is_approved BOOLEAN NOT NULL DEFAULT FALSE"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE users ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT TRUE"
            )
        )


__all__ = ["upgrade"]

