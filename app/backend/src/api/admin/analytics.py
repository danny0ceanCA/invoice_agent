"""Admin analytics observability endpoints."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from redis import Redis
from sqlalchemy import create_engine, func
from sqlalchemy.orm import Session, sessionmaker

from app.backend.src.core.config import get_settings
from app.backend.src.core.security import get_current_user
from app.backend.src.models import User
from app.backend.src.models.materialized_report import MaterializedReport

LOGGER = structlog.get_logger(__name__)

router = APIRouter(prefix="/admin/analytics", tags=["admin-analytics"])


def _require_admin(user: User = Depends(get_current_user)) -> User:
    if not user or getattr(user, "role", "").lower() != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


@router.get("/cache")
def list_cache_entries(_: User = Depends(_require_admin)) -> dict[str, Any]:
    settings = get_settings()

    items: list[dict[str, Any]] = []
    total = 0
    try:
        client = Redis.from_url(settings.redis_url)
        for key in client.scan_iter(match="analytics_cache:*", count=100):
            total += 1
            if len(items) >= 100:
                continue

            try:
                ttl = client.ttl(key)
            except Exception:
                ttl = None

            approx_bytes = None
            has_payload = False
            district_key = None
            created_at = None
            last_accessed = None

            value = None
            try:
                value = client.get(key)
                if value is not None:
                    has_payload = True
            except Exception:
                value = None

            try:
                approx_bytes = client.memory_usage(key)
            except Exception:
                if value is not None:
                    approx_bytes = len(value)

            if value is not None:
                try:
                    decoded = value.decode("utf-8") if isinstance(value, (bytes, bytearray)) else value
                    payload = json.loads(decoded)
                    if isinstance(payload, dict):
                        district_key = payload.get("district_key")
                        created_at = payload.get("created_at")
                        last_accessed = payload.get("last_accessed") or payload.get(
                            "last_accessed_at"
                        )
                except Exception:
                    pass

            items.append(
                {
                    "key": key.decode("utf-8") if isinstance(key, (bytes, bytearray)) else key,
                    "ttl_seconds": ttl,
                    "approx_bytes": approx_bytes,
                    "has_payload": has_payload,
                    "district_key": district_key,
                    "created_at": created_at,
                    "last_accessed": last_accessed,
                }
            )
    except Exception as exc:  # pragma: no cover - defensive
        LOGGER.warning("admin_cache_inspect_failed", error=str(exc))
        return {"items": [], "total_keys": 0}

    return {"items": items, "total_keys": total}


@router.get("/materialized-reports")
def list_materialized_reports(
    *,
    district_key: str | None = None,
    report_kind: str | None = None,
    primary_entity: str | None = None,
    limit: int = 50,
    offset: int = 0,
    raw: bool = False,
    user: User = Depends(_require_admin),
) -> dict[str, Any]:
    settings = get_settings()
    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(bind=engine)

    with SessionLocal() as session:  # type: Session
        query = session.query(MaterializedReport)
        if district_key:
            query = query.filter(MaterializedReport.district_key == district_key)
        if report_kind:
            query = query.filter(MaterializedReport.report_kind == report_kind)
        if primary_entity:
            query = query.filter(MaterializedReport.primary_entity == primary_entity)

        total = query.with_entities(func.count()).scalar() or 0

        rows = (
            query.order_by(MaterializedReport.created_at.desc())
            .offset(max(offset, 0))
            .limit(max(limit, 1))
            .all()
        )

        items: list[dict[str, Any]] = []
        for row in rows:
            payload_preview: dict[str, Any] | None = None
            if isinstance(row.payload, dict):
                text = row.payload.get("text")
                rows_data = row.payload.get("rows")
                rows_count = len(rows_data) if isinstance(rows_data, list) else None
                payload_preview = {"text": text, "rows_count": rows_count}

            item = {
                "id": row.id,
                "district_key": row.district_key,
                "cache_key": row.cache_key,
                "report_kind": row.report_kind,
                "primary_entity": row.primary_entity,
                "created_at": row.created_at.isoformat() if isinstance(row.created_at, datetime) else None,
                "last_accessed_at": row.last_accessed_at.isoformat()
                if isinstance(row.last_accessed_at, datetime)
                else None,
                "payload_preview": payload_preview,
            }

            if raw:
                item["payload"] = row.payload

            items.append(item)

    return {"items": items, "total": total}


@router.get("/prefetch")
def list_prefetch_history(_: User = Depends(_require_admin)) -> dict[str, Any]:
    settings = get_settings()
    try:
        client = Redis.from_url(settings.redis_url, decode_responses=True)
        entries = client.lrange("prefetch:history", 0, 49) or []
    except Exception as exc:  # pragma: no cover - defensive
        LOGGER.warning("prefetch_history_read_failed", error=str(exc))
        return {"items": []}

    items: list[dict[str, Any]] = []
    for entry in entries:
        try:
            decoded = json.loads(entry)
            if isinstance(decoded, dict):
                items.append(decoded)
        except Exception:
            continue

    return {"items": items}
