"""Celery application factory."""

from __future__ import annotations

import ssl
from pathlib import Path
from typing import Any

import structlog
from celery import Celery, signals
from kombu import Queue

from app.backend.src.core.config import get_settings

LOGGER = structlog.get_logger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[1]

settings = get_settings()


def _resolve_ca_cert_path(path: str | None) -> str | None:
    """Resolve the configured CA certificate path to an absolute path.

    Celery (via redis-py) requires an absolute filesystem path when ``ssl_ca_certs``
    is provided. In production we often configure a project-relative value like
    ``certs/redis_ca.pem``; resolving it here avoids silent failures when the worker
    starts from a different working directory. When the certificate cannot be
    located we log a warning and allow Python's default trust store to handle TLS
    validation instead of pointing Redis at a non-existent path.
    """

    if not path:
        return None

    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = PROJECT_ROOT / candidate

    if candidate.is_file():
        return str(candidate)

    LOGGER.warning(
        "redis_ca_certificate_missing",
        configured_path=path,
        resolved_path=str(candidate),
    )
    return None


def _build_ssl_options() -> dict[str, Any]:
    """Return SSL options for Redis connections."""

    options: dict[str, Any] = {"ssl_cert_reqs": ssl.CERT_REQUIRED}
    resolved_cert = _resolve_ca_cert_path(settings.redis_ca_cert_path)
    if resolved_cert:
        options["ssl_ca_certs"] = resolved_cert
    return options


def _verify_celery_connectivity() -> None:
    """Eagerly validate broker and backend connectivity.

    If the worker cannot connect to Redis we fail fast with a clear log message
    instead of silently idling and leaving jobs stuck in the ``queued`` state.
    """

    try:
        with celery.connection_for_read() as connection:
            connection.ensure_connection(max_retries=1)
    except Exception as exc:  # pragma: no cover - requires broker connectivity
        LOGGER.error(
            "celery_broker_unavailable",
            broker=settings.broker_url,
            error=str(exc),
        )
        raise

    backend = celery.backend
    try:
        if hasattr(backend, "client"):
            backend.client.ping()
    except Exception as exc:  # pragma: no cover - requires backend connectivity
        LOGGER.error(
            "celery_backend_unavailable",
            backend=settings.result_backend,
            error=str(exc),
        )
        raise

LOGGER.info(
    "celery_bootstrap_ready",
    broker=settings.broker_url,
    backend=settings.result_backend,
)


celery = Celery(
    "invoice_agent",
    broker=settings.broker_url,
    backend=settings.result_backend,
)

# Ensure Celery knows about the project task modules. Without this explicit
# registration the worker starts successfully but never sees the
# `tasks.process_invoice` task, so uploads remain stuck in the ``queued`` state
# forever. We also register analytics prefetch tasks.
celery.conf.update(include=["tasks.invoice_tasks", "tasks.prefetch_tasks"])

ssl_options = _build_ssl_options()

celery_conf: dict[str, object] = {
    "task_default_queue": "small",
    "task_queues": (
        Queue("small"),
        Queue("medium"),
        Queue("large"),
    ),
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
    "broker_connection_retry_on_startup": True,
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


@signals.worker_ready.connect
def _log_worker_configuration(sender: Any | None = None, **_: Any) -> None:
    """Emit structured worker configuration details after startup."""

    app = sender.app if sender is not None else celery
    _verify_celery_connectivity()
    queue_names = sorted(
        getattr(queue, "name", str(queue)) for queue in app.conf.task_queues or []
    )
    if not queue_names and app.conf.task_default_queue:
        queue_names = [app.conf.task_default_queue]
    registered_tasks = sorted(
        task_name for task_name in app.tasks.keys() if task_name.startswith("tasks.")
    )
    LOGGER.info(
        "celery_worker_configuration",
        default_queue=app.conf.task_default_queue,
        queues=queue_names,
        registered_tasks=registered_tasks,
    )


@signals.task_prerun.connect
def _log_task_prerun(
    sender: Any | None = None,
    task_id: str | None = None,
    task: Any | None = None,
    args: tuple[Any, ...] = (),
    kwargs: dict[str, Any] | None = None,
    **_: Any,
) -> None:
    """Log when a task begins execution to help debug queue issues."""

    kwargs = kwargs or {}
    task_name = getattr(task, "name", "")
    if task_name and not task_name.startswith("tasks."):
        return
    LOGGER.info(
        "celery_task_prerun",
        task_id=task_id,
        task_name=task_name or None,
        queue=kwargs.get("queue_name"),
        vendor_id=args[1] if len(args) > 1 else None,
    )


@signals.task_postrun.connect
def _log_task_postrun(
    sender: Any | None = None,
    task_id: str | None = None,
    task: Any | None = None,
    retval: Any | None = None,
    state: str | None = None,
    **_: Any,
) -> None:
    """Emit completion information after a task finishes."""

    payload: dict[str, Any] = {
        "task_id": task_id,
        "task_name": getattr(task, "name", None),
        "state": state,
    }
    task_name = payload["task_name"] or ""
    if task_name and not task_name.startswith("tasks."):
        return
    if state == "SUCCESS":
        if isinstance(retval, dict):
            payload["result_keys"] = sorted(retval.keys())
        else:
            payload["result_repr"] = repr(retval)

    LOGGER.info("celery_task_postrun", **payload)

__all__ = ["celery"]
