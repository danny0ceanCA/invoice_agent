"""Introduce district membership association table."""

from __future__ import annotations

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    Table,
    UniqueConstraint,
    inspect,
    select,
    text,
)
from sqlalchemy.engine import Connection

from .. import get_engine


def _ensure_membership_table(connection: Connection) -> Table:
    """Create the district membership table when it is missing."""

    inspector = inspect(connection)
    if "district_memberships" in inspector.get_table_names():
        metadata = MetaData()
        metadata.reflect(bind=connection, only=["district_memberships"])
        return metadata.tables["district_memberships"]

    # ✅ Reflect existing tables so foreign keys resolve
    metadata = MetaData()
    metadata.reflect(bind=connection, only=["users", "districts"])

    memberships = Table(
        "district_memberships",
        metadata,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column(
            "user_id",
            Integer,
            ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        Column(
            "district_id",
            Integer,
            ForeignKey("districts.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        Column(
            "created_at",
            DateTime(timezone=True),
            server_default=text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        UniqueConstraint(
            "user_id",
            "district_id",
            name="uq_district_memberships_user_district",
        ),
    )

    memberships.create(bind=connection, checkfirst=True)

    # ✅ Add indexes manually (SQLite safe)
    connection.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_district_memberships_user_id "
            "ON district_memberships (user_id)"
        )
    )
    connection.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_district_memberships_district_id "
            "ON district_memberships (district_id)"
        )
    )

    metadata.reflect(bind=connection, only=["district_memberships"])
    return metadata.tables["district_memberships"]


def _backfill_memberships(connection: Connection, memberships: Table) -> None:
    """Populate memberships for users that already have a district assigned."""

    metadata = MetaData()
    metadata.reflect(bind=connection, only=["users"])
    users = metadata.tables["users"]

    rows = connection.execute(
        select(users.c.id, users.c.district_id).where(users.c.district_id.is_not(None))
    ).fetchall()

    for row in rows:
        user_id = row.id
        district_id = row.district_id
        if district_id is None:
            continue

        exists = connection.execute(
            select(memberships.c.id).where(
                (memberships.c.user_id == user_id)
                & (memberships.c.district_id == district_id)
            )
        ).first()
        if exists:
            continue

        connection.execute(
            memberships.insert().values(user_id=user_id, district_id=district_id)
        )


def upgrade() -> None:
    """Apply the migration."""

    engine = get_engine()
    with engine.begin() as connection:
        memberships = _ensure_membership_table(connection)
        _backfill_memberships(connection, memberships)


__all__ = ["upgrade"]

# ✅ Ensure the migration runs when executed directly
if __name__ == "__main__":
    upgrade()
