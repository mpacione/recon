"""Tests for the workspace creation + API-key endpoints (Phase 5).

Endpoints under test:
- POST /api/workspaces       — create a new workspace from a description
- GET  /api/api-keys?path=   — return presence map of saved keys
- POST /api/api-keys         — save a key to workspace .env

These tests do not call any LLMs; description parsing uses a
heuristic so the flow works offline. Real LLM-based parsing arrives
in Phase 6 when we wire up the discovery agent.

The api_keys module already targets a per-workspace .env, so writing
keys never touches ~/.recon/.env in the suite.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from recon.web.api import create_app


@pytest.fixture()
def client() -> TestClient:
    return TestClient(create_app())


@pytest.fixture(autouse=True)
def _isolate_api_key_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Block real env vars + the user's global ~/.recon/.env from
    leaking into api-key tests.

    api_keys.load_api_keys layers workspace.env > os.environ >
    ~/.recon/.env. The dev box where the suite runs almost certainly
    has ANTHROPIC_API_KEY exported, which would falsely populate
    every "key not set" assertion below.
    """
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_AI_API_KEY", raising=False)
    # Redirect the global ~/.recon dir to a sibling of tmp_path so
    # the API never reads the user's real saved keys during tests.
    monkeypatch.setattr(
        "recon.api_keys._DEFAULT_GLOBAL_DIR", tmp_path / "global_recon",
    )


# ---------------------------------------------------------------------------
# POST /api/workspaces
# ---------------------------------------------------------------------------


class TestCreateWorkspace:
    def test_creates_workspace_at_explicit_path(
        self, client: TestClient, tmp_path: Path,
    ) -> None:
        target = tmp_path / "bambu"
        response = client.post(
            "/api/workspaces",
            json={
                "path": str(target),
                "description": "Bambu Lab makes consumer 3D printers",
                "company_name": "Bambu Lab",
                "domain": "additive manufacturing",
            },
        )
        assert response.status_code == 201, response.text
        body = response.json()

        # Workspace metadata returned in the same shape as
        # GET /api/workspace, so the SPA can navigate straight to the
        # describe → discovery flow without a second fetch.
        assert body["path"] == str(target)
        assert body["domain"] == "additive manufacturing"
        assert body["company_name"] == "Bambu Lab"

        # On disk: standard workspace layout.
        assert (target / "recon.yaml").exists()
        assert (target / "competitors").is_dir()
        assert (target / ".recon").is_dir()

    def test_derives_path_from_company_name_when_missing(
        self, client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Default parent dir is ~/recon. Redirect to tmp so the test
        # doesn't pollute the user's home.
        monkeypatch.setattr(
            "recon.web.api._DEFAULT_WORKSPACES_PARENT", tmp_path / "recon",
        )

        response = client.post(
            "/api/workspaces",
            json={
                "description": "Bambu Lab makes consumer 3D printers",
                "company_name": "Bambu Lab",
                "domain": "additive manufacturing",
            },
        )
        assert response.status_code == 201, response.text
        body = response.json()

        # Slugified company name under the default parent.
        assert body["path"].endswith("/bambu-lab")
        assert (Path(body["path"]) / "recon.yaml").exists()

    def test_extracts_company_name_from_description_heuristically(
        self, client: TestClient, tmp_path: Path,
    ) -> None:
        # When company_name is omitted the API derives it from the
        # description using a simple "first capitalized noun phrase"
        # heuristic — sufficient for the offline path; LLM parsing
        # arrives in Phase 6.
        target = tmp_path / "ws"
        response = client.post(
            "/api/workspaces",
            json={
                "path": str(target),
                "description": "Acme Corp makes widgets and gadgets",
            },
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["company_name"] == "Acme Corp"

    def test_refuses_when_path_already_exists_with_recon_yaml(
        self, client: TestClient, tmp_workspace: Path,
    ) -> None:
        # tmp_workspace already has a recon.yaml — POSTing into it is
        # ambiguous (overwrite? merge? error?) so we reject explicitly.
        # This only applies to EXPLICIT path submissions; derived paths
        # get auto-suffixed (see test_auto_suffixes_derived_path below).
        response = client.post(
            "/api/workspaces",
            json={
                "path": str(tmp_workspace),
                "description": "Acme",
                "company_name": "Acme",
                "domain": "things",
            },
        )
        assert response.status_code == 409
        assert "already" in response.json()["detail"].lower()

    def test_auto_suffixes_derived_path_when_slug_collides(
        self, client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Users repeatedly clicking "new project" with the same
        # description used to hit raw 409s. Derived paths now
        # auto-suffix (-2, -3, ...) so the flow stays unblocked.
        monkeypatch.setattr(
            "recon.web.api._DEFAULT_WORKSPACES_PARENT", tmp_path / "ws",
        )

        payload = {
            "description": "Acme Corp builds rockets",
            "company_name": "Acme Corp",
            "domain": "rockets",
        }

        first = client.post("/api/workspaces", json=payload)
        assert first.status_code == 201
        assert first.json()["path"].endswith("/acme-corp")

        second = client.post("/api/workspaces", json=payload)
        assert second.status_code == 201
        assert second.json()["path"].endswith("/acme-corp-2")

        third = client.post("/api/workspaces", json=payload)
        assert third.status_code == 201
        assert third.json()["path"].endswith("/acme-corp-3")

    def test_requires_description(
        self, client: TestClient, tmp_path: Path,
    ) -> None:
        response = client.post(
            "/api/workspaces",
            json={"path": str(tmp_path / "x")},
        )
        # FastAPI validation surfaces this as 422.
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# /api/api-keys
# ---------------------------------------------------------------------------


@pytest.fixture()
def workspace_with_keys(tmp_workspace: Path) -> Path:
    # Pre-populate the workspace .env so GET has something to find.
    env_path = tmp_workspace / ".env"
    env_path.write_text(
        "ANTHROPIC_API_KEY=sk-ant-test-1234\n"
        "GOOGLE_AI_API_KEY=\n",  # Empty value should report as not-set
    )
    return tmp_workspace


class TestGetApiKeys:
    def test_returns_presence_map(
        self, client: TestClient, workspace_with_keys: Path,
    ) -> None:
        response = client.get(f"/api/api-keys?path={workspace_with_keys}")
        assert response.status_code == 200
        body = response.json()
        assert body["anthropic"] is True
        assert body["google_ai"] is False

    def test_returns_all_false_for_workspace_with_no_env(
        self, client: TestClient, tmp_workspace: Path,
    ) -> None:
        response = client.get(f"/api/api-keys?path={tmp_workspace}")
        assert response.status_code == 200
        body = response.json()
        # Both well-known providers reported, both false.
        assert body == {"anthropic": False, "google_ai": False}

    def test_404_for_missing_workspace(
        self, client: TestClient, tmp_path: Path,
    ) -> None:
        response = client.get(f"/api/api-keys?path={tmp_path / 'nope'}")
        assert response.status_code == 404


class TestGetGlobalApiKeys:
    """GET /api/api-keys/global — describe screen calls this on mount
    so users aren't prompted to re-enter keys already saved in
    ~/.recon/.env from a prior workspace."""

    def test_reports_presence_from_global_env(
        self,
        client: TestClient,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        global_dir = tmp_path / ".recon"
        global_dir.mkdir()
        (global_dir / ".env").write_text(
            "ANTHROPIC_API_KEY=sk-ant-global-abc\nGOOGLE_AI_API_KEY=\n",
        )
        monkeypatch.setattr("recon.api_keys._DEFAULT_GLOBAL_DIR", global_dir)

        response = client.get("/api/api-keys/global")
        assert response.status_code == 200
        body = response.json()
        assert body == {"anthropic": True, "google_ai": False}

    def test_returns_all_false_when_global_env_missing(
        self,
        client: TestClient,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # No global env file at all — endpoint must still return a
        # clean shape so the describe screen can short-circuit cleanly.
        monkeypatch.setattr(
            "recon.api_keys._DEFAULT_GLOBAL_DIR", tmp_path / "nope",
        )
        response = client.get("/api/api-keys/global")
        assert response.status_code == 200
        assert response.json() == {"anthropic": False, "google_ai": False}

    def test_never_returns_key_values(
        self,
        client: TestClient,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Security guard: the endpoint must only ever report booleans.
        # A leak here would expose keys to anything that reached the
        # HTTP layer before authentication lands.
        global_dir = tmp_path / ".recon"
        global_dir.mkdir()
        (global_dir / ".env").write_text(
            "ANTHROPIC_API_KEY=sk-ant-secret-should-not-leak\n",
        )
        monkeypatch.setattr("recon.api_keys._DEFAULT_GLOBAL_DIR", global_dir)

        response = client.get("/api/api-keys/global")
        assert "sk-ant-secret-should-not-leak" not in response.text


class TestSaveApiKey:
    def test_writes_key_to_workspace_env(
        self, client: TestClient, tmp_workspace: Path,
    ) -> None:
        response = client.post(
            "/api/api-keys",
            json={
                "path": str(tmp_workspace),
                "name": "anthropic",
                "value": "sk-ant-newvalue",
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["anthropic"] is True

        env_text = (tmp_workspace / ".env").read_text()
        assert "ANTHROPIC_API_KEY=sk-ant-newvalue" in env_text

    def test_rejects_unknown_key_name(
        self, client: TestClient, tmp_workspace: Path,
    ) -> None:
        response = client.post(
            "/api/api-keys",
            json={
                "path": str(tmp_workspace),
                "name": "openai",  # not in the recognized provider set
                "value": "sk-test",
            },
        )
        assert response.status_code == 400

    def test_404_for_missing_workspace(
        self, client: TestClient, tmp_path: Path,
    ) -> None:
        response = client.post(
            "/api/api-keys",
            json={
                "path": str(tmp_path / "nope"),
                "name": "anthropic",
                "value": "x",
            },
        )
        assert response.status_code == 404
