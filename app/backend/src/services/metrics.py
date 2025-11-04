"""Prometheus metric definitions for invoice processing."""

from __future__ import annotations

from prometheus_client import Counter, Histogram

invoice_jobs_total = Counter(
    "invoice_jobs_total",
    "Total invoice processing jobs by outcome.",
    labelnames=["status"],
)

job_duration_seconds = Histogram(
    "job_duration_seconds",
    "Duration of invoice processing jobs in seconds.",
    labelnames=["queue"],
)

pdf_generation_seconds = Histogram(
    "pdf_generation_seconds",
    "Time spent rendering a single invoice PDF.",
)

__all__ = [
    "invoice_jobs_total",
    "job_duration_seconds",
    "pdf_generation_seconds",
]
