"""Storage helpers for invoice artifacts."""

from __future__ import annotations

import shutil
from pathlib import Path


def upload_file(pdf_path: Path) -> str:
    """Persist the PDF to local storage and return its path."""

    storage_dir = Path("storage/invoices")
    storage_dir.mkdir(parents=True, exist_ok=True)

    destination = storage_dir / pdf_path.name
    if destination.exists():
        destination.unlink()

    shutil.move(str(pdf_path), destination)
    return str(destination)
