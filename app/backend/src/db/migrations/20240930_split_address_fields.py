"""Split remit-to and mailing addresses into dedicated columns."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import MetaData, inspect, select, text

from app.backend.src.db import get_engine



def _parse_address(value: str | None) -> tuple[str | None, str | None, str | None, str | None]:
    """Heuristically split a multiline address into components."""

    if value is None:
        return None, None, None, None

    lines = [line.strip() for line in value.splitlines() if line.strip()]
    if not lines:
        return None, None, None, None

    street: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None

    if len(lines) == 1:
        street = lines[0]
    else:
        street = ", ".join(lines[:-1]) or lines[0]
        location = lines[-1]
        if "," in location:
            city_part, remainder = location.split(",", 1)
            city = city_part.strip() or None
            remainder = remainder.strip()
        else:
            remainder = location
        if remainder:
            parts = remainder.split()
            if parts:
                state = parts[0].strip()
                if len(parts) > 1:
                    postal_code = " ".join(parts[1:]).strip() or None
    return street, city, state, postal_code


def _ensure_columns(connection, table: str, columns: Sequence[tuple[str, str]]) -> None:
    """Add columns to a table if they do not already exist."""

    inspector = inspect(connection)
    existing = {column["name"] for column in inspector.get_columns(table)}
    for name, ddl in columns:
        if name not in existing:
            connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {ddl}"))


def upgrade() -> None:
    """Apply the migration."""

    engine = get_engine()
    with engine.begin() as connection:
        _ensure_columns(
            connection,
            "vendors",
            [
                ("remit_to_street", "VARCHAR(255)"),
                ("remit_to_city", "VARCHAR(100)"),
                ("remit_to_state", "VARCHAR(32)"),
                ("remit_to_postal_code", "VARCHAR(20)"),
            ],
        )
        _ensure_columns(
            connection,
            "districts",
            [
                ("mailing_street", "VARCHAR(255)"),
                ("mailing_city", "VARCHAR(100)"),
                ("mailing_state", "VARCHAR(32)"),
                ("mailing_postal_code", "VARCHAR(20)"),
            ],
        )

        metadata = MetaData()
        metadata.reflect(bind=connection, only=["vendors", "districts"])
        vendors_table = metadata.tables["vendors"]
        districts_table = metadata.tables["districts"]

        if "remit_to_address" in vendors_table.c:
            vendor_rows = connection.execute(
                select(vendors_table.c.id, vendors_table.c.remit_to_address)
            ).fetchall()
            for row in vendor_rows:
                street, city, state, postal_code = _parse_address(row.remit_to_address)
                updates = {}
                if street:
                    updates["remit_to_street"] = street
                if city:
                    updates["remit_to_city"] = city
                if state:
                    updates["remit_to_state"] = state
                if postal_code:
                    updates["remit_to_postal_code"] = postal_code
                if updates:
                    connection.execute(
                        vendors_table.update()
                        .where(vendors_table.c.id == row.id)
                        .values(**updates)
                    )

        if "mailing_address" in districts_table.c:
            district_rows = connection.execute(
                select(districts_table.c.id, districts_table.c.mailing_address)
            ).fetchall()
            for row in district_rows:
                street, city, state, postal_code = _parse_address(row.mailing_address)
                updates = {}
                if street:
                    updates["mailing_street"] = street
                if city:
                    updates["mailing_city"] = city
                if state:
                    updates["mailing_state"] = state
                if postal_code:
                    updates["mailing_postal_code"] = postal_code
                if updates:
                    connection.execute(
                        districts_table.update()
                        .where(districts_table.c.id == row.id)
                        .values(**updates)
                    )


def downgrade() -> None:
    """Revert the migration."""

    engine = get_engine()
    with engine.begin() as connection:
        inspector = inspect(connection)
        vendor_columns = {column["name"] for column in inspector.get_columns("vendors")}
        district_columns = {column["name"] for column in inspector.get_columns("districts")}

        metadata = MetaData()
        metadata.reflect(bind=connection, only=["vendors", "districts"])
        vendors_table = metadata.tables["vendors"]
        districts_table = metadata.tables["districts"]

        if "remit_to_address" not in vendor_columns:
            connection.execute(text("ALTER TABLE vendors ADD COLUMN remit_to_address TEXT"))
        if "mailing_address" not in district_columns:
            connection.execute(text("ALTER TABLE districts ADD COLUMN mailing_address TEXT"))

        vendor_rows = connection.execute(
            select(
                vendors_table.c.id,
                vendors_table.c.remit_to_street,
                vendors_table.c.remit_to_city,
                vendors_table.c.remit_to_state,
                vendors_table.c.remit_to_postal_code,
            )
        ).fetchall()
        for row in vendor_rows:
            components = [
                (row.remit_to_street or "").strip(),
                " ".join(
                    part
                    for part in [
                        (row.remit_to_city or "").strip(),
                        (row.remit_to_state or "").strip(),
                        (row.remit_to_postal_code or "").strip(),
                    ]
                    if part
                ).strip(),
            ]
            address = "\n".join(part for part in components if part)
            connection.execute(
                vendors_table.update()
                .where(vendors_table.c.id == row.id)
                .values(remit_to_address=address or None)
            )

        district_rows = connection.execute(
            select(
                districts_table.c.id,
                districts_table.c.mailing_street,
                districts_table.c.mailing_city,
                districts_table.c.mailing_state,
                districts_table.c.mailing_postal_code,
            )
        ).fetchall()
        for row in district_rows:
            components = [
                (row.mailing_street or "").strip(),
                " ".join(
                    part
                    for part in [
                        (row.mailing_city or "").strip(),
                        (row.mailing_state or "").strip(),
                        (row.mailing_postal_code or "").strip(),
                    ]
                    if part
                ).strip(),
            ]
            address = "\n".join(part for part in components if part)
            connection.execute(
                districts_table.update()
                .where(districts_table.c.id == row.id)
                .values(mailing_address=address or None)
            )


__all__ = ["upgrade", "downgrade"]
