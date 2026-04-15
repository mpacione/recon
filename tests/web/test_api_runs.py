"""Tests for the POST /api/runs endpoint and the fake LLM client.

The endpoint kicks off a real Pipeline, but with a deterministic
fake LLM client so tests never hit the network. We verify:

- happy-path: returns a run_id + SSE events URL
- invalid workspace: 404
- FakeLLMClient satisfies the LLMClient interface pipeline.py depends on
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from recon.web.api import create_app
from recon.web.fake_llm import FakeLLMClient


@pytest.fixture()
def client() -> TestClient:
    return TestClient(create_app())


class TestStartRun:
    def test_returns_run_id_and_events_url(
        self, client: TestClient, tmp_workspace: Path,
    ) -> None:
        # The workspace has no competitors yet — plan() should still
        # succeed (it creates a run row even for an empty target list),
        # so we get a run_id back. The execute() task runs in the
        # background and either no-ops or fails gracefully; either way
        # the caller has a run_id to subscribe to.
        response = client.post(
            "/api/runs", json={"path": str(tmp_workspace)},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["run_id"]
        assert body["events_url"] == f"/api/runs/{body['run_id']}/events"
        assert body["use_fake_llm"] is True

    def test_returns_404_for_missing_workspace(
        self, client: TestClient, tmp_path: Path,
    ) -> None:
        response = client.post(
            "/api/runs", json={"path": str(tmp_path / "nope")},
        )
        assert response.status_code == 404

    def test_rejects_missing_path(self, client: TestClient) -> None:
        response = client.post("/api/runs", json={})
        assert response.status_code == 422  # validation error


class TestFakeLLMClient:
    async def test_complete_returns_llm_response_shape(self) -> None:
        client = FakeLLMClient(latency_seconds=0.0)
        result = await client.complete(
            system_prompt="sys",
            user_prompt="Research the overview of Acme Corp.",
        )
        assert result.text
        assert result.model == "fake-claude-sonnet"
        assert result.stop_reason == "end_turn"
        assert result.input_tokens > 0
        assert result.output_tokens > 0

    async def test_complete_tracks_cumulative_token_counts(self) -> None:
        client = FakeLLMClient(latency_seconds=0.0)
        await client.complete(system_prompt="s", user_prompt="first")
        await client.complete(system_prompt="s", user_prompt="second")
        assert client.call_count == 2
        assert client.total_input_tokens > 0
        assert client.total_output_tokens > 0

    async def test_complete_varies_output_by_prompt(self) -> None:
        # Lets streaming UIs render distinct rows per section.
        client = FakeLLMClient(latency_seconds=0.0)
        first = await client.complete(system_prompt="s", user_prompt="overview")
        second = await client.complete(system_prompt="s", user_prompt="pricing")
        assert first.text != second.text
