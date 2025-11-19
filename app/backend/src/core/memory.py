"""Conversation memory utilities backed by Redis."""

from __future__ import annotations

import json
from typing import Any, Iterable, Mapping

import structlog
from redis import Redis

LOGGER = structlog.get_logger(__name__)


class ConversationMemory:
    """Interface for storing and retrieving chat history."""

    def load_messages(self, session_id: str) -> list[dict[str, str]]:
        raise NotImplementedError

    def append_interaction(
        self, session_id: str, *, user_message: Mapping[str, Any], assistant_message: Mapping[str, Any]
    ) -> None:
        raise NotImplementedError


class RedisConversationMemory(ConversationMemory):
    """Redis-backed conversation history for agents."""

    def __init__(
        self,
        url: str,
        *,
        key_prefix: str = "analytics_agent",
        ttl_seconds: int = 60 * 60 * 24 * 7,
        max_messages: int = 20,
    ) -> None:
        self.client = Redis.from_url(url)
        self.key_prefix = key_prefix
        self.ttl_seconds = ttl_seconds
        self.max_messages = max_messages

    def load_messages(self, session_id: str) -> list[dict[str, str]]:
        key = self._key(session_id)
        try:
            raw = self.client.get(key)
        except Exception as exc:  # pragma: no cover - defensive
            LOGGER.warning("redis_memory_read_failed", key=key, error=str(exc))
            return []

        if not raw:
            return []

        try:
            payload = json.loads(raw)
        except Exception as exc:  # pragma: no cover - defensive
            LOGGER.warning("redis_memory_json_error", key=key, error=str(exc))
            return []

        return self._coerce_messages(payload)

    def append_interaction(
        self, session_id: str, *, user_message: Mapping[str, Any], assistant_message: Mapping[str, Any]
    ) -> None:
        messages = self.load_messages(session_id)
        messages.append({"role": "user", "content": str(user_message.get("content", ""))})
        messages.append(
            {"role": "assistant", "content": str(assistant_message.get("content", ""))}
        )

        trimmed = messages[-(self.max_messages * 2) :]
        serialized = json.dumps(trimmed)

        key = self._key(session_id)
        try:
            self.client.setex(key, self.ttl_seconds, serialized)
        except Exception as exc:  # pragma: no cover - defensive
            LOGGER.warning("redis_memory_write_failed", key=key, error=str(exc))

    def _key(self, session_id: str) -> str:
        return f"{self.key_prefix}:{session_id}"

    @staticmethod
    def _coerce_messages(candidate: Any) -> list[dict[str, str]]:
        if not isinstance(candidate, Iterable):
            return []

        messages: list[dict[str, str]] = []
        for item in candidate:
            if not isinstance(item, Mapping):
                continue
            role = item.get("role")
            content = item.get("content")
            if isinstance(role, str) and isinstance(content, str) and role in {"user", "assistant"}:
                messages.append({"role": role, "content": content})
        return messages


__all__ = ["ConversationMemory", "RedisConversationMemory"]
