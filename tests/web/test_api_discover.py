"""Tests for POST /api/discover — LLM-backed competitor search.

The endpoint drives :class:`recon.discovery.DiscoveryAgent` with
whatever API keys are saved. Tests exercise the routing logic and
error paths without making real LLM calls.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from recon.discovery import CompetitorTier, DiscoveryCandidate
from recon.web.api import create_app


@pytest.fixture()
def client() -> TestClient:
    return TestClient(create_app())


class TestDiscoverRouting:
    def test_returns_400_when_no_keys_and_not_fake(
        self,
        client: TestClient,
        tmp_workspace: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # No keys anywhere — endpoint surfaces a clean "save a key
        # first" message rather than dying on agent creation.
        monkeypatch.setenv("ANTHROPIC_API_KEY", "")
        monkeypatch.setenv("GOOGLE_AI_API_KEY", "")
        monkeypatch.setattr(
            "recon.api_keys.load_api_keys",
            lambda *args, **kwargs: {},
        )

        response = client.post(
            "/api/discover",
            json={"path": str(tmp_workspace), "seeds": []},
        )
        assert response.status_code == 400
        assert "api key" in response.json()["detail"].lower()

    def test_returns_404_for_missing_workspace(
        self, client: TestClient, tmp_path: Path,
    ) -> None:
        response = client.post(
            "/api/discover",
            json={"path": str(tmp_path / "nope"), "seeds": []},
        )
        assert response.status_code == 404

    def test_requires_path(self, client: TestClient) -> None:
        response = client.post("/api/discover", json={})
        assert response.status_code == 422


class TestDiscoverFakeMode:
    def test_runs_via_fake_llm_without_keys(
        self, client: TestClient, tmp_workspace: Path,
    ) -> None:
        # use_fake_llm short-circuits the key check and drives the
        # agent with the deterministic stub — useful for UI demos.
        response = client.post(
            "/api/discover",
            json={"path": str(tmp_workspace), "use_fake_llm": True},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        # The fake LLM returns non-JSON text, so the agent parses
        # zero candidates. What matters is the response shape.
        assert "candidates" in body
        assert isinstance(body["candidates"], list)
        assert body["domain"]  # populated from workspace schema
        # Web search is off in fake mode.
        assert body["used_web_search"] is False

    def test_returns_candidates_when_agent_finds_some(
        self, client: TestClient, tmp_workspace: Path,
    ) -> None:
        # Patch DiscoveryAgent.search so we can test the happy path
        # without depending on LLM parsing. The endpoint should pass
        # the results through to the response model.
        fake_candidates = [
            DiscoveryCandidate(
                name="Bambu Lab",
                url="https://bambulab.com",
                blurb="Consumer 3D printer brand.",
                provenance="well-known",
                suggested_tier=CompetitorTier.ESTABLISHED,
            ),
            DiscoveryCandidate(
                name="Prusa Research",
                url="https://www.prusa3d.com",
                blurb="Open-source desktop printers.",
                provenance="G2",
                suggested_tier=CompetitorTier.ESTABLISHED,
            ),
        ]

        async def fake_search(self, state):  # noqa: ANN001, ARG001
            return fake_candidates

        with patch(
            "recon.discovery.DiscoveryAgent.search",
            new=AsyncMock(side_effect=lambda state: fake_candidates),
        ):
            response = client.post(
                "/api/discover",
                json={"path": str(tmp_workspace), "use_fake_llm": True},
            )

        assert response.status_code == 200, response.text
        body = response.json()
        names = [c["name"] for c in body["candidates"]]
        assert "Bambu Lab" in names
        assert "Prusa Research" in names
        # The URL + blurb should round-trip.
        first = body["candidates"][0]
        assert first["url"].startswith("https://")
        assert first["blurb"]

    def test_does_not_leak_key_values(
        self,
        client: TestClient,
        tmp_workspace: Path,
    ) -> None:
        # The /api/discover response body should never include the
        # user's API keys — only candidate data. Belt-and-braces
        # check since keys briefly transit through os.environ.
        response = client.post(
            "/api/discover",
            json={"path": str(tmp_workspace), "use_fake_llm": True},
        )
        assert "sk-ant" not in response.text
        assert "AIza" not in response.text
