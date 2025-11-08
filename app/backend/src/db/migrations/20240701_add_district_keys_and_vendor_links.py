"""Add district access keys and link vendors to districts."""

from __future__ import annotations

import secrets
import string

from sqlalchemy import MetaData, inspect, select, text

from app.backend.src.db import get_engine

ALPHABET = string.ascii_uppercase + string.digits


def _generate_key() -> str:
    """Return a random district access key."""

    raw = "".join(secrets.choice(ALPHABET) for _ in range(12))
    return "-".join(raw[i : i + 4] for i in range(0, len(raw), 4))


def _ensure_unique_key(connection, districts_table, existing_keys: set[str]) -> str:
    """Generate a district key that is unique in the database."""

    while True:  # pragma: no branch - loop is bounded by randomness
        candidate = _generate_key()
        if candidate in existing_keys:
            continue
        duplicate = connection.execute(
            select(districts_table.c.id).where(districts_table.c.district_key == candidate)
        ).first()
        if duplicate is None:
            existing_keys.add(candidate)
            return candidate


def upgrade() -> None:
    """Apply the migration."""

    engine = get_engine()
    with engine.begin() as connection:
        inspector = inspect(connection)

        district_columns = {
            column["name"] for column in inspector.get_columns("districts")
        }
        if "district_key" not in district_columns:
            connection.execute(
                text("ALTER TABLE districts ADD COLUMN district_key VARCHAR(64)")
            )

        vendor_columns = {column["name"] for column in inspector.get_columns("vendors")}
        if "district_id" not in vendor_columns:
            connection.execute(
                text("ALTER TABLE vendors ADD COLUMN district_id INTEGER")
            )

        dialect = connection.dialect.name
        if dialect in {"postgresql", "postgres"}:
            connection.execute(
                text(
                    """
                    DO $$
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1
                            FROM pg_constraint
                            WHERE conname = 'fk_vendors_district_id'
                        ) THEN
                            ALTER TABLE vendors
                            ADD CONSTRAINT fk_vendors_district_id
                            FOREIGN KEY (district_id)
                            REFERENCES districts (id)
                            ON DELETE SET NULL;
                        END IF;
                    END$$;
                    """
                )
            )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_vendors_district_id ON vendors (district_id)"
                )
            )
        elif dialect == "sqlite":
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_vendors_district_id ON vendors (district_id)"
                )
            )
        else:  # pragma: no cover - unexpected dialects should fail fast
            raise RuntimeError(f"Unsupported database dialect: {dialect}")

        if "district_key" not in district_columns:
            connection.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS ix_districts_district_key ON districts (district_key)"
                )
            )

        metadata = MetaData()
        metadata.reflect(bind=connection, only=["districts"])
        districts_table = metadata.tables["districts"]

        existing_keys: set[str] = set()
        rows = connection.execute(
            select(districts_table.c.id, districts_table.c.district_key)
        ).fetchall()
        for row in rows:
            if row.district_key:
                existing_keys.add(row.district_key)

        for row in rows:
            if row.district_key:
                continue
            new_key = _ensure_unique_key(connection, districts_table, existing_keys)
            connection.execute(
                districts_table.update()
                .where(districts_table.c.id == row.id)
                .values(district_key=new_key)
            )


__all__ = ["upgrade"]
