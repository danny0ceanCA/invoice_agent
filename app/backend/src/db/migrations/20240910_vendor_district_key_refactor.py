"""Refactor vendor district linkage to use district keys."""

from __future__ import annotations

from sqlalchemy import MetaData, inspect, select, text

from app.backend.src.db import get_engine


def _drop_index(connection, name: str) -> None:
    """Drop the provided index if it exists."""

    dialect = connection.dialect.name
    statement = text(f"DROP INDEX IF EXISTS {name}")
    if dialect in {"postgresql", "postgres"}:
        connection.execute(statement)
    elif dialect == "sqlite":
        connection.execute(statement)
    else:  # pragma: no cover - unexpected dialects should fail fast
        raise RuntimeError(f"Unsupported database dialect: {dialect}")


def upgrade() -> None:
    """Apply the migration."""

    engine = get_engine()
    with engine.begin() as connection:
        inspector = inspect(connection)
        vendor_columns = {column["name"] for column in inspector.get_columns("vendors")}
        district_columns = {column["name"] for column in inspector.get_columns("districts")}

        if "district_key" not in district_columns:
            raise RuntimeError("districts.district_key column is required for this migration")

        if "district_key" not in vendor_columns:
            connection.execute(
                text("ALTER TABLE vendors ADD COLUMN district_key VARCHAR(64)")
            )

        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_vendors_district_key "
                "ON vendors (district_key)"
            )
        )

        metadata = MetaData()
        metadata.reflect(bind=connection, only=["vendors", "districts"])
        vendors_table = metadata.tables["vendors"]
        districts_table = metadata.tables["districts"]

        district_rows = connection.execute(
            select(districts_table.c.id, districts_table.c.district_key)
        ).fetchall()
        id_to_key = {
            row.id: row.district_key
            for row in district_rows
            if row.district_key
        }
        valid_keys = {row.district_key for row in district_rows if row.district_key}

        if "district_id" in vendor_columns:
            vendor_rows = connection.execute(
                select(vendors_table.c.id, vendors_table.c.district_id)
                .where(vendors_table.c.district_id.is_not(None))
            ).fetchall()
            for row in vendor_rows:
                mapped_key = id_to_key.get(row.district_id)
                if mapped_key:
                    connection.execute(
                        vendors_table.update()
                        .where(vendors_table.c.id == row.id)
                        .values(district_key=mapped_key)
                    )

        existing_links = connection.execute(
            select(vendors_table.c.id, vendors_table.c.district_key)
            .where(vendors_table.c.district_key.is_not(None))
        ).fetchall()
        for row in existing_links:
            if row.district_key not in valid_keys:
                connection.execute(
                    vendors_table.update()
                    .where(vendors_table.c.id == row.id)
                    .values(district_key=None)
                )

        indexes = {index["name"] for index in inspector.get_indexes("vendors")}
        if "ix_vendors_district_id" in indexes:
            _drop_index(connection, "ix_vendors_district_id")

        dialect = connection.dialect.name
        if "district_id" in vendor_columns:
            if dialect in {"postgresql", "postgres"}:
                connection.execute(
                    text(
                        """
                        DO $$
                        BEGIN
                            IF EXISTS (
                                SELECT 1
                                FROM pg_constraint
                                WHERE conname = 'fk_vendors_district_id'
                            ) THEN
                                ALTER TABLE vendors
                                DROP CONSTRAINT fk_vendors_district_id;
                            END IF;
                        END$$;
                        """
                    )
                )
            connection.execute(text("ALTER TABLE vendors DROP COLUMN district_id"))

        if dialect in {"postgresql", "postgres"}:
            connection.execute(
                text(
                    """
                    DO $$
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1
                            FROM pg_constraint
                            WHERE conname = 'fk_vendors_district_key'
                        ) THEN
                            ALTER TABLE vendors
                            ADD CONSTRAINT fk_vendors_district_key
                            FOREIGN KEY (district_key)
                            REFERENCES districts (district_key)
                            ON DELETE SET NULL;
                        END IF;
                    END$$;
                    """
                )
            )


__all__ = ["upgrade"]
