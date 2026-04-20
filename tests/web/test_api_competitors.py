"""Tests for competitor management endpoints (Phase 6).

The web UI's Discovery screen manages profiles directly rather than
using the in-memory ``DiscoveryState`` the TUI holds. This keeps the
server stateless — the on-disk profile directory IS the state — and
means reloads don't lose work.

Endpoints under test:
- GET    /api/competitors?path=         — list profiles on disk
- POST   /api/competitors               — create a profile
- DELETE /api/competitors/{slug}?path=  — remove a profile

LLM-backed discovery search is out of scope for Phase 6; it lands
separately so users can opt in with visible cost warnings.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from recon.web.api import create_app


@pytest.fixture()
def client() -> TestClient:
    return TestClient(create_app())


class TestCompetitorInputSafety:
    """Guards against hostile-report findings (empty name, giant
    name, javascript: URL, other non-http schemes)."""

    def test_rejects_whitespace_only_name(
        self, client: TestClient, tmp_workspace: Path,
    ) -> None:
        res = client.post(
            "/api/competitors",
            json={"path": str(tmp_workspace), "name": "   "},
        )
        assert res.status_code == 422

    def test_rejects_overlong_name(
        self, client: TestClient, tmp_workspace: Path,
    ) -> None:
        res = client.post(
            "/api/competitors",
            json={"path": str(tmp_workspace), "name": "A" * 500},
        )
        assert res.status_code == 422

    def test_rejects_javascript_url(
        self, client: TestClient, tmp_workspace: Path,
    ) -> None:
        res = client.post(
            "/api/competitors",
            json={
                "path": str(tmp_workspace),
                "name": "Evil Co",
                "url": "javascript:alert(1)",
            },
        )
        assert res.status_code == 422
        assert "http" in res.json()["detail"].lower()

    def test_rejects_non_http_url(
        self, client: TestClient, tmp_workspace: Path,
    ) -> None:
        for scheme in ("data:text/html,x", "file:///etc/passwd", "vbscript:msgbox"):
            res = client.post(
                "/api/competitors",
                json={"path": str(tmp_workspace), "name": "T", "url": scheme},
            )
            assert res.status_code == 422, scheme


# ---------------------------------------------------------------------------
# GET /api/competitors
# ---------------------------------------------------------------------------


class TestListCompetitors:
    def test_empty_workspace_returns_empty_list(
        self, client: TestClient, tmp_workspace: Path,
    ) -> None:
        response = client.get(f"/api/competitors?path={tmp_workspace}")
        assert response.status_code == 200
        assert response.json() == {"competitors": []}

    def test_lists_existing_profiles(
        self, client: TestClient, tmp_workspace: Path,
    ) -> None:
        (tmp_workspace / "competitors" / "prusa-research.md").write_text(
            "---\n"
            "name: Prusa Research\n"
            "type: competitor\n"
            "research_status: scaffold\n"
            "---\n\n"
            "# Prusa Research\n",
        )
        (tmp_workspace / "competitors" / "creality.md").write_text(
            "---\n"
            "name: Creality\n"
            "type: competitor\n"
            "research_status: researched\n"
            "---\n\n"
            "# Creality\n",
        )

        response = client.get(f"/api/competitors?path={tmp_workspace}")
        assert response.status_code == 200
        body = response.json()
        assert len(body["competitors"]) == 2
        names = sorted(c["name"] for c in body["competitors"])
        assert names == ["Creality", "Prusa Research"]

        # Each row carries the status so the Discovery screen can
        # show what's already been researched.
        creality = next(c for c in body["competitors"] if c["name"] == "Creality")
        assert creality["status"] == "researched"
        assert creality["slug"] == "creality"

    def test_404_for_missing_workspace(
        self, client: TestClient, tmp_path: Path,
    ) -> None:
        response = client.get(f"/api/competitors?path={tmp_path / 'nope'}")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/competitors
# ---------------------------------------------------------------------------


class TestCreateCompetitor:
    def test_creates_profile_on_disk(
        self, client: TestClient, tmp_workspace: Path,
    ) -> None:
        response = client.post(
            "/api/competitors",
            json={
                "path": str(tmp_workspace),
                "name": "Formlabs",
                "url": "https://formlabs.com",
                "blurb": "Boston-based SLA/resin specialist",
            },
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["name"] == "Formlabs"
        assert body["slug"] == "formlabs"
        assert body["status"] == "scaffold"

        profile_path = tmp_workspace / "competitors" / "formlabs.md"
        assert profile_path.exists()
        text = profile_path.read_text()
        # Frontmatter carries the URL + blurb so later stages can use them.
        assert "Formlabs" in text
        assert "formlabs.com" in text

    def test_conflicts_when_slug_already_exists(
        self, client: TestClient, tmp_workspace: Path,
    ) -> None:
        # Create once.
        first = client.post(
            "/api/competitors",
            json={"path": str(tmp_workspace), "name": "Elegoo"},
        )
        assert first.status_code == 201

        # Duplicate attempts return 409 so the UI can show a message
        # instead of silently losing the second click.
        dup = client.post(
            "/api/competitors",
            json={"path": str(tmp_workspace), "name": "Elegoo"},
        )
        assert dup.status_code == 409

    def test_requires_name(
        self, client: TestClient, tmp_workspace: Path,
    ) -> None:
        response = client.post(
            "/api/competitors",
            json={"path": str(tmp_workspace)},
        )
        # FastAPI validation surfaces missing required fields as 422.
        assert response.status_code == 422

    def test_404_for_missing_workspace(
        self, client: TestClient, tmp_path: Path,
    ) -> None:
        response = client.post(
            "/api/competitors",
            json={"path": str(tmp_path / "nope"), "name": "Acme"},
        )
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/competitors/{slug}
# ---------------------------------------------------------------------------


class TestDeleteCompetitor:
    def test_removes_profile_by_slug(
        self, client: TestClient, tmp_workspace: Path,
    ) -> None:
        target = tmp_workspace / "competitors" / "anker-make.md"
        target.write_text(
            "---\nname: AnkerMake\ntype: competitor\n---\n\n# AnkerMake\n",
        )
        assert target.exists()

        response = client.delete(
            f"/api/competitors/anker-make?path={tmp_workspace}",
        )
        assert response.status_code == 204
        assert not target.exists()

    def test_404_when_slug_does_not_exist(
        self, client: TestClient, tmp_workspace: Path,
    ) -> None:
        response = client.delete(
            f"/api/competitors/nope?path={tmp_workspace}",
        )
        assert response.status_code == 404

    def test_rejects_slug_with_path_traversal(
        self, client: TestClient, tmp_workspace: Path,
    ) -> None:
        # An attacker-controlled slug must not escape competitors/.
        # Whether we 400 or 404, we must NOT 200, and we must NOT
        # touch anything outside the competitors dir.
        (tmp_workspace / "recon.yaml").write_text(
            (tmp_workspace / "recon.yaml").read_text(),
        )

        response = client.delete(
            f"/api/competitors/..%2Frecon.yaml?path={tmp_workspace}",
        )
        assert response.status_code in {400, 404}
        # The recon.yaml we care about is still there.
        assert (tmp_workspace / "recon.yaml").exists()
