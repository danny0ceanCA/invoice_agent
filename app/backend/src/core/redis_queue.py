"""Redis queue helpers."""

from __future__ import annotations

from rq import Queue
from redis import Redis

from .config import get_settings


def get_queue(name: str = "default") -> Queue:
    """Return an RQ queue instance."""

    connection = Redis.from_url(get_settings().redis_url)
    return Queue(name, connection=connection)
