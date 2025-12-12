from __future__ import annotations
import json
import structlog
from typing import Any
from redis import Redis

from .config import get_settings

LOGGER = structlog.get_logger(__name__)

class RedisAnalyticsCache:
    """Simple Redis cache for full analytics responses."""

    def __init__(self, *, key_prefix: str = "analytics_cache", ttl_seconds: int = 3600):
        settings = get_settings()
        self.client = Redis.from_url(settings.redis_url)
        self.key_prefix = key_prefix
        self.ttl_seconds = ttl_seconds

    def _key(self, suffix: str) -> str:
        return f"{self.key_prefix}:{suffix}"

    def get(self, suffix: str) -> Any | None:
        key = self._key(suffix)
        try:
            raw = self.client.get(key)
            if not raw:
                return None
            return json.loads(raw)
        except Exception as exc:
            LOGGER.warning("redis_cache_read_failed", key=key, error=str(exc))
            return None

    def set(self, suffix: str, value: Any) -> None:
        key = self._key(suffix)
        try:
            self.client.setex(key, self.ttl_seconds, json.dumps(value))
        except Exception as exc:
            LOGGER.warning("redis_cache_write_failed", key=key, error=str(exc))
