"""Storage helpers for S3 interactions."""

from __future__ import annotations

from typing import Protocol


class StorageBackend(Protocol):
    """Minimal protocol for storage backends."""

    def put(self, key: str, data: bytes) -> str:
        """Persist bytes and return an object key."""

    def url(self, key: str) -> str:
        """Return an access URL."""


class InMemoryStorage:
    """Simple in-memory storage placeholder for early development."""

    def __init__(self) -> None:
        self._store: dict[str, bytes] = {}

    def put(self, key: str, data: bytes) -> str:
        self._store[key] = data
        return key

    def url(self, key: str) -> str:
        if key not in self._store:
            raise KeyError(key)
        return f"memory://{key}"
