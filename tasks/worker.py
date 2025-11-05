"""Celery application factory."""

from __future__ import annotations

import ssl

from celery import Celery

from app.backend.src.core.config import get_settings

settings = get_settings()

celery = Celery(
    "invoice_agent",
    broker=settings.broker_url,
    backend=settings.result_backend,
)

# Ensure Celery knows about the project task modules. Without this explicit
# registration the worker starts successfully but never sees the
# `tasks.process_invoice` task, so uploads remain stuck in the ``queued`` state
# forever.
celery.conf.update(include=["tasks.invoice_tasks"])

ssl_options = {
    "ssl_cert_reqs": ssl.CERT_REQUIRED,
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
    "broker_transport_options": {
        "global_keyprefix": "invoice-agent-broker:",
    },
    "result_backend_transport_options": {
        "global_keyprefix": "invoice-agent-result:",
    },
}

if settings.broker_url.startswith("rediss://"):
    celery_conf["broker_use_ssl"] = ssl_options.copy()

if settings.result_backend.startswith("rediss://"):
    celery_conf["redis_backend_use_ssl"] = ssl_options.copy()

celery.conf.update(**celery_conf)

# Import task definitions so Celery registers them when the worker starts. The
# import happens at module import time so workers launched from any entrypoint
# automatically load the `tasks.process_invoice` task.
from . import invoice_tasks  # noqa: F401  # isort: skip

__all__ = ["celery"]
