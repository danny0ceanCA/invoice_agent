"""Celery application factory."""

from __future__ import annotations

from celery import Celery

from app.backend.src.core.config import get_settings

settings = get_settings()

celery = Celery(
    "invoice_agent",
    broker=settings.broker_url,
    backend=settings.result_backend,
)

celery.conf.update(
    task_routes={
        "tasks.small.*": {"queue": "small"},
        "tasks.medium.*": {"queue": "medium"},
        "tasks.large.*": {"queue": "large"},
    },
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    worker_prefetch_multiplier=1,
)

__all__ = ["celery"]
