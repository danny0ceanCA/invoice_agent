"""Redis queue helpers."""

from __future__ import annotations

import logging

from rq import Queue
from redis import Redis

from .config import get_settings

logger = logging.getLogger(__name__)


def get_queue(name: str = "default") -> Queue:
    """Return an RQ queue instance if Redis is enabled."""

    settings = get_settings()
    if settings.redis_enabled:
        connection = Redis.from_url(settings.redis_url)
        return Queue(name, connection=connection)
    logger.warning("Redis disabled — running without job queue support.")
    raise RuntimeError("Redis support is disabled for this environment")
