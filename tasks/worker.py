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

ssl_options = {
    "ssl_cert_reqs": "CERT_REQUIRED",
    "ssl_ca_certs": settings.redis_ca_cert_path,
}

celery_conf: dict[str, object] = {
    "task_routes": {
        "tasks.small.*": {"queue": "small"},
        "tasks.medium.*": {"queue": "medium"},
        "tasks.large.*": {"queue": "large"},
    },
    "task_serializer": "json",
    "accept_content": ["json"],
    "result_serializer": "json",
    "worker_prefetch_multiplier": 1,
}

if settings.broker_url.startswith("rediss://"):
    celery_conf["broker_use_ssl"] = ssl_options.copy()

if settings.result_backend.startswith("rediss://"):
    celery_conf["redis_backend_use_ssl"] = ssl_options.copy()

celery.conf.update(**celery_conf)

__all__ = ["celery"]
