"""Tests for the read-only API surface (Phase 3).

Endpoints under test:
- GET /api/recents          — recent projects from ~/.recon/recent.json
- GET /api/workspace?path=  — workspace state (domain, competitors, sections, cost)
- GET /api/dashboard?path=  — full dashboard data (mirrors the TUI dashboard)
- GET /api/results?path=    — exec summary preview + theme/output files

These all read on-disk state and the existing engine APIs — no
mutations, no LLM calls, no network. Each test creates an isolated
workspace under tmp_path and validates the response Pydantic shape.

Conftest's autouse ``_isolate_recent_projects`` already redirects
~/.recon/recent.json to a tmp file, so writes from these tests
don't leak into the user's real recents.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from recon.web.api import create_app


@pytest.fixture()
def client() -> TestClient:
    return TestClient(create_app())


@pytest.fixture()
def populated_workspace(tmp_workspace: Path) -> Path:
    """Add a competitor profile and an executive summary to tmp_workspace.

    The bare ``tmp_workspace`` fixture from the root conftest only
    creates the directory + recon.yaml. Most read-only API tests need
    a profile and (for results) a synthesized exec summary on disk.
    """
    competitors_dir = tmp_workspace / "competitors"
    (competitors_dir / "acme-corp.md").write_text(
        "---\n"
        "name: Acme Corp\n"
        "type: competitor\n"
        "research_status: researched\n"
        "section_status:\n"
        "  overview:\n"
        "    status: researched\n"
        "---\n\n"
        "# Acme Corp\n\n## Overview\n\nAcme makes widgets.\n",
    )
    return tmp_workspace


@pytest.fixture()
def workspace_with_results(populated_workspace: Path) -> Path:
    """Add a fake exec summary + a theme markdown file."""
    (populated_workspace / "executive_summary.md").write_text(
        "# Executive Summary\n\n"
        "The widget market is dominated by Acme. Three trends:\n"
        "1. Consolidation\n2. Pricing pressure\n3. New entrants from Asia.\n",
    )
    themes_dir = populated_workspace / "themes"
    themes_dir.mkdir(exist_ok=True)
    (themes_dir / "consolidation.md").write_text(
        "# Consolidation\n\nThe top 3 vendors hold 80% share.\n",
    )
    return populated_workspace


# ---------------------------------------------------------------------------
# /api/recents
# ---------------------------------------------------------------------------


class TestRecents:
    def test_returns_empty_list_when_no_recents(self, client: TestClient) -> None:
        response = client.get("/api/recents")
        assert response.status_code == 200
        assert response.json() == {"projects": []}

    def test_returns_persisted_recents_in_order(
        self, client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        recent_file = tmp_path / "recent.json"
        recent_file.write_text(
            json.dumps([
                {"path": "/work/bambu", "name": "Bambu Lab", "last_opened": "2026-04-13T10:00:00+00:00"},
                {"path": "/work/acme", "name": "Acme Corp", "last_opened": "2026-04-12T10:00:00+00:00"},
            ]),
        )
        monkeypatch.setattr(
            "recon.tui.screens.welcome._DEFAULT_RECENT_PATH", recent_file,
        )

        response = client.get("/api/recents")
        body = response.json()
        assert len(body["projects"]) == 2
        assert body["projects"][0]["name"] == "Bambu Lab"
        assert body["projects"][0]["path"] == "/work/bambu"
        assert body["projects"][1]["name"] == "Acme Corp"

    def test_drops_malformed_entries_silently(
        self, client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # The TUI manager already tolerates malformed entries — make
        # sure the API surfaces the same forgiveness instead of 500ing.
        recent_file = tmp_path / "recent.json"
        recent_file.write_text(
            json.dumps([
                {"path": "/work/ok", "name": "OK", "last_opened": "2026-04-13T10:00:00+00:00"},
                {"path": "/work/bad"},  # missing name + last_opened
                "not-a-dict",
            ]),
        )
        monkeypatch.setattr(
            "recon.tui.screens.welcome._DEFAULT_RECENT_PATH", recent_file,
        )

        response = client.get("/api/recents")
        assert response.status_code == 200
        assert len(response.json()["projects"]) == 1


# ---------------------------------------------------------------------------
# /api/workspace
# ---------------------------------------------------------------------------


class TestWorkspace:
    def test_returns_400_when_path_query_missing(self, client: TestClient) -> None:
        response = client.get("/api/workspace")
        assert response.status_code == 422  # FastAPI validation error

    def test_returns_404_when_path_does_not_exist(
        self, client: TestClient, tmp_path: Path,
    ) -> None:
        missing = tmp_path / "nope"
        response = client.get(f"/api/workspace?path={missing}")
        assert response.status_code == 404

    def test_returns_404_when_recon_yaml_missing(
        self, client: TestClient, tmp_path: Path,
    ) -> None:
        empty = tmp_path / "empty"
        empty.mkdir()
        response = client.get(f"/api/workspace?path={empty}")
        assert response.status_code == 404

    def test_returns_workspace_metadata(
        self, client: TestClient, populated_workspace: Path,
    ) -> None:
        response = client.get(f"/api/workspace?path={populated_workspace}")
        assert response.status_code == 200
        body = response.json()
        # From the MINIMAL_SCHEMA_DICT in tests/conftest.py
        assert body["domain"] == "Developer Tools"
        assert body["company_name"] == "Acme Corp"
        assert body["competitor_count"] == 1
        assert body["section_count"] == 1
        assert body["path"] == str(populated_workspace)
        assert body["total_cost"] == 0.0


# ---------------------------------------------------------------------------
# /api/dashboard
# ---------------------------------------------------------------------------


class TestDashboard:
    def test_returns_dashboard_data(
        self, client: TestClient, populated_workspace: Path,
    ) -> None:
        response = client.get(f"/api/dashboard?path={populated_workspace}")
        assert response.status_code == 200
        body = response.json()
        assert body["domain"] == "Developer Tools"
        assert body["company_name"] == "Acme Corp"
        assert body["total_competitors"] == 1
        assert body["total_sections"] == 1

        # Shape of competitor_rows
        assert len(body["competitor_rows"]) == 1
        row = body["competitor_rows"][0]
        assert row["name"] == "Acme Corp"
        assert row["status"] == "researched"

        # Shape of section_statuses
        assert len(body["section_statuses"]) == 1
        section = body["section_statuses"][0]
        assert section["key"] == "overview"
        assert section["title"] == "Overview"
        assert section["completed"] == 1
        assert section["total"] == 1

    def test_returns_404_for_missing_workspace(
        self, client: TestClient, tmp_path: Path,
    ) -> None:
        missing = tmp_path / "nope"
        response = client.get(f"/api/dashboard?path={missing}")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# /api/results
# ---------------------------------------------------------------------------


class TestResults:
    def test_returns_summary_and_theme_files(
        self, client: TestClient, workspace_with_results: Path,
    ) -> None:
        response = client.get(f"/api/results?path={workspace_with_results}")
        assert response.status_code == 200
        body = response.json()

        assert body["executive_summary_path"].endswith("executive_summary.md")
        assert "widget market" in body["executive_summary_preview"].lower()

        # Theme files enumerated from themes/ (excluding the
        # themes/distilled subdirectory which holds different content).
        theme_names = {t["name"] for t in body["theme_files"]}
        assert "consolidation" in theme_names

    def test_handles_workspace_with_no_results_yet(
        self, client: TestClient, populated_workspace: Path,
    ) -> None:
        # No exec summary, no themes/ — still a valid response.
        response = client.get(f"/api/results?path={populated_workspace}")
        assert response.status_code == 200
        body = response.json()
        assert body["executive_summary_path"] is None
        assert body["executive_summary_preview"] == ""
        assert body["theme_files"] == []

    def test_truncates_long_executive_summary_preview(
        self, client: TestClient, populated_workspace: Path,
    ) -> None:
        long_summary = "Lorem ipsum " * 400  # ~5KB
        (populated_workspace / "executive_summary.md").write_text(long_summary)

        response = client.get(f"/api/results?path={populated_workspace}")
        body = response.json()
        # Preview is bounded so the JSON payload stays small.
        assert len(body["executive_summary_preview"]) <= 2000

    def test_returns_404_for_missing_workspace(
        self, client: TestClient, tmp_path: Path,
    ) -> None:
        response = client.get(f"/api/results?path={tmp_path / 'nope'}")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Cross-cutting
# ---------------------------------------------------------------------------


class TestPathTraversalDefense:
    def test_workspace_endpoint_rejects_relative_traversal(
        self, client: TestClient, tmp_path: Path,
    ) -> None:
        # We don't allow traversal outside the resolved path even via
        # ../ tricks — but importantly we also don't error for legit
        # relative paths. The real defense is that we resolve+stat
        # before opening. This test just locks in that an obviously
        # bad value returns a 4xx instead of 5xx.
        response = client.get("/api/workspace?path=/../../etc")
        assert 400 <= response.status_code < 500
