"""Add district organization profiles and link users."""

"""Add district organization profiles and link users."""

from __future__ import annotations

from sqlalchemy import (
    Column,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    inspect,
    select,
    text,
)

from app.backend.src.db import get_engine


def _generate_company_name(
    name: str | None,
    email: str | None,
    suffix: str,
    identifier: int,
) -> str:
    """Return a reasonable default company name."""

    base = (name or "").strip()
    if not base and email:
        base = email.split("@")[0]
    if not base:
        base = "Organization"
    return f"{base} {suffix} {identifier}"[:255]


def upgrade() -> None:
    """Apply the migration."""

    engine = get_engine()
    with engine.begin() as connection:
        inspector = inspect(connection)

        if "districts" not in inspector.get_table_names():
            metadata = MetaData()
            Table(
                "districts",
                metadata,
                Column("id", Integer, primary_key=True, autoincrement=True),
                Column("name", String(255), unique=True, nullable=False),
                Column("contact_name", String(255), nullable=True),
                Column("contact_email", String(255), nullable=True),
                Column("phone_number", String(50), nullable=True),
                Column("mailing_address", Text, nullable=True),
            )
            metadata.create_all(connection)

        user_columns = {column["name"] for column in inspector.get_columns("users")}
        if "district_id" not in user_columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN district_id INTEGER"))

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
                            WHERE conname = 'fk_users_district_id'
                        ) THEN
                            ALTER TABLE users
                            ADD CONSTRAINT fk_users_district_id
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
                    "CREATE INDEX IF NOT EXISTS ix_users_district_id ON users (district_id)"
                )
            )
        elif dialect == "sqlite":
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_users_district_id ON users (district_id)"
                )
            )
        else:  # pragma: no cover - unexpected dialects should fail fast
            raise RuntimeError(f"Unsupported database dialect: {dialect}")

        metadata = MetaData()
        metadata.reflect(bind=connection, only=["users", "vendors", "districts"])
        users_table = metadata.tables["users"]
        vendors_table = metadata.tables["vendors"]
        districts_table = metadata.tables["districts"]

        vendor_rows = connection.execute(
            select(
                users_table.c.id,
                users_table.c.name,
                users_table.c.email,
            ).where(
                users_table.c.role == "vendor",
                users_table.c.vendor_id.is_(None),
            )
        ).fetchall()

        for row in vendor_rows:
            company_name = _generate_company_name(row.name, row.email, "Vendor", row.id)
            insert_result = connection.execute(
                vendors_table.insert().values(
                    name=company_name,
                    contact_name=row.name,
                    contact_email=row.email,
                    phone_number=None,
                    remit_to_address=None,
                )
            )
            vendor_id = insert_result.inserted_primary_key[0]
            connection.execute(
                users_table.update()
                .where(users_table.c.id == row.id)
                .values(vendor_id=vendor_id)
            )

        district_rows = connection.execute(
            select(
                users_table.c.id,
                users_table.c.name,
                users_table.c.email,
            ).where(
                users_table.c.role == "district",
                users_table.c.district_id.is_(None),
            )
        ).fetchall()

        for row in district_rows:
            company_name = _generate_company_name(row.name, row.email, "District", row.id)
            insert_result = connection.execute(
                districts_table.insert().values(
                    name=company_name,
                    contact_name=row.name,
                    contact_email=row.email,
                    phone_number=None,
                    mailing_address=None,
                )
            )
            district_id = insert_result.inserted_primary_key[0]
            connection.execute(
                users_table.update()
                .where(users_table.c.id == row.id)
                .values(district_id=district_id)
            )


__all__ = ["upgrade"]
