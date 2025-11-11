"""Migration to allow nullable user roles and enforce valid values."""

from __future__ import annotations

from sqlalchemy import text

from .. import get_engine


def upgrade() -> None:
    """Apply the migration."""

    engine = get_engine()
    with engine.begin() as connection:
        dialect = connection.dialect.name

        if dialect == "sqlite":
            # SQLite tables created after this migration will already include the new
            # constraint metadata. Existing local databases should be recreated because
            # SQLite does not support altering a column's nullability in-place without
            # rebuilding the table.
            return

        if dialect not in {"postgresql", "postgres"}:
            raise RuntimeError(f"Unsupported database dialect: {dialect}")

        connection.execute(
            text("ALTER TABLE users ALTER COLUMN role DROP NOT NULL")
        )
        connection.execute(
            text("ALTER TABLE users DROP CONSTRAINT IF EXISTS ck_users_role_valid")
        )
        connection.execute(
            text(
                """
                ALTER TABLE users
                ADD CONSTRAINT ck_users_role_valid
                CHECK (role IS NULL OR role IN ('vendor','district','admin'))
                """
            )
        )


__all__ = ["upgrade"]
