"""Stub helpers for QuickBooks Online integration."""

from __future__ import annotations

from pathlib import Path


def export_qbo_csv(destination: Path) -> Path:
    """Write a placeholder QuickBooks import file."""
    destination.write_text("Customer,Amount\nExample,0.00\n", encoding="utf-8")
    return destination
