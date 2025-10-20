"""Stub for the AI-powered processing agent."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ProcessingJobResult:
    """Lightweight container for processing results."""

    job_id: str
    status: str
    message: str


class ProcessingAgent:
    """Placeholder processing agent that will coordinate the automation pipeline."""

    def run(self, upload_id: str) -> ProcessingJobResult:
        """Return a dummy result until the OpenAI AgentKit integration is wired up."""
        return ProcessingJobResult(job_id=upload_id, status="pending", message="Not implemented")
