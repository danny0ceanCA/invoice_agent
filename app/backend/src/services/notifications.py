"""Notification service stubs."""

from __future__ import annotations


def send_email(recipient: str, subject: str, body: str) -> None:
    """Log that an email would have been sent."""
    print(f"Email to {recipient}: {subject}\n{body}")
