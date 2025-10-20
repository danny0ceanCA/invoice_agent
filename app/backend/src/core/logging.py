"""Structured logging configuration."""

from __future__ import annotations

import logging


def configure_logging() -> None:
    """Configure basic JSON-style logging for the service."""

    logging.basicConfig(level=logging.INFO, format='{"level": "%(levelname)s", "message": "%(message)s"}')
