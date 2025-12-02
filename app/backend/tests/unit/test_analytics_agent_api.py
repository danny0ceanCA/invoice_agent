"""Tests for the analytics agent FastAPI endpoint."""

from __future__ import annotations

from typing import Any

import sys
from pathlib import Path
import types
import importlib.util

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parents[4]
sys.path.append(str(ROOT_DIR))

if "jose" not in sys.modules:
    jose_stub = types.ModuleType("jose")

    class JWTError(Exception):
        pass

    jwt_stub = types.ModuleType("jwt")

    def _jwt_stub(*args: object, **kwargs: object) -> None:  # pragma: no cover
        raise NotImplementedError("JWT operations are not available in tests.")

    jwt_stub.get_unverified_header = _jwt_stub
    jwt_stub.decode = _jwt_stub

    jose_stub.JWTError = JWTError
    jose_stub.jwt = jwt_stub

    sys.modules["jose"] = jose_stub
    sys.modules["jose.jwt"] = jwt_stub

spec = importlib.util.spec_from_file_location(
    "analytics_agent_module",
    ROOT_DIR / "app/backend/src/api/analytics_agent.py",
)
analytics_agent = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(analytics_agent)  # type: ignore[call-arg]

from app.backend.src.models import User

app = FastAPI()
app.include_router(analytics_agent.router, prefix="/api")


@pytest.fixture(autouse=True)
def override_user_dependency() -> None:
    """Authenticate requests with a synthetic district user."""

    def _override() -> User:
        return User(
            id=101,
            email="district@example.com",
            name="District Analyst",
            role="district",
            is_approved=True,
            district_id=404,
        )

    app.dependency_overrides[analytics_agent.get_current_user] = _override
    yield
    app.dependency_overrides.pop(analytics_agent.get_current_user, None)


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


def test_run_agent_success(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    """The endpoint returns normalized agent output."""

    async def _stub_workflow(query: str, context: dict[str, Any]) -> dict[str, Any]:
        assert query == "How many invoices were approved?"
        assert context == {"district_id": 404}
        return {
            "text": "There were 12 approved invoices last month.",
            "html": "<p>There were <strong>12</strong> approved invoices last month.</p>",
            "csv_url": "https://example.com/report.csv",
        }

    monkeypatch.setattr(analytics_agent, "_execute_responses_workflow", _stub_workflow)

    response = client.post(
        "/api/analytics/agent",
        json={"query": "  How many invoices were approved?  "},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload.pop("latency_ms") >= 0
    assert payload == {
        "text": "There were 12 approved invoices last month.",
        "html": "<p>There were <strong>12</strong> approved invoices last month.</p>",
        "csv_url": "https://example.com/report.csv",
    }


def test_run_agent_rejects_blank_query(client: TestClient) -> None:
    """Empty prompts should produce a client error instead of hitting the agent."""

    response = client.post("/api/analytics/agent", json={"query": "   "})

    assert response.status_code == 400
    assert response.json() == {"detail": "A natural-language query is required."}


def test_run_agent_handles_agent_errors(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    """Exceptions raised by the Agent SDK surface as a controlled error."""

    async def _exploding_workflow(*_: Any, **__: Any) -> None:  # pragma: no cover
        raise RuntimeError("boom")

    monkeypatch.setattr(analytics_agent, "_execute_responses_workflow", _exploding_workflow)

    response = client.post(
        "/api/analytics/agent",
        json={"query": "Show me vendor totals."},
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Analytics assistant is temporarily unavailable. Please try again later.",
    }
