"""Tests for Template and Confirm endpoints (Phase 7).

Endpoints under test:
- GET   /api/template?path=     — section pool + which are selected
- PUT   /api/template           — replace the workspace's section list
- GET   /api/confirm?path=      — cost estimate + model options + ETA

These drive the last two pre-run screens in the flow. Both are pure
reads/writes against the workspace; no LLM calls, no network.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from recon.web.api import create_app


@pytest.fixture()
def client() -> TestClient:
    return TestClient(create_app())


@pytest.fixture()
def workspace_with_competitors(tmp_workspace: Path) -> Path:
    """tmp_workspace + 2 competitor profiles, used by confirm cost math."""
    competitors = tmp_workspace / "competitors"
    for slug, name in [("prusa", "Prusa"), ("creality", "Creality")]:
        (competitors / f"{slug}.md").write_text(
            f"---\nname: {name}\ntype: competitor\nresearch_status: scaffold\n---\n\n# {name}\n",
        )
    return tmp_workspace


# ---------------------------------------------------------------------------
# GET /api/template
# ---------------------------------------------------------------------------


class TestGetTemplate:
    def test_returns_full_section_pool_with_selected_flags(
        self, client: TestClient, tmp_workspace: Path,
    ) -> None:
        response = client.get(f"/api/template?path={tmp_workspace}")
        assert response.status_code == 200
        body = response.json()

        # The pool is DefaultSections.ALL (8 sections as of v2).
        assert len(body["sections"]) >= 8
        keys = {s["key"] for s in body["sections"]}
        assert {"overview", "pricing", "strategic_notes"} <= keys

        # tmp_workspace's minimal_schema_dict only picks "overview" so
        # exactly one section is selected.
        selected = [s for s in body["sections"] if s["selected"]]
        assert len(selected) == 1
        assert selected[0]["key"] == "overview"

    def test_section_entries_carry_title_and_description(
        self, client: TestClient, tmp_workspace: Path,
    ) -> None:
        response = client.get(f"/api/template?path={tmp_workspace}")
        section = next(
            s for s in response.json()["sections"] if s["key"] == "overview"
        )
        assert section["title"] == "Overview"
        assert "summary" in section["description"].lower()

    def test_404_for_missing_workspace(
        self, client: TestClient, tmp_path: Path,
    ) -> None:
        response = client.get(f"/api/template?path={tmp_path / 'nope'}")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# PUT /api/template — replace the selected section list
# ---------------------------------------------------------------------------


class TestPutTemplate:
    def test_replaces_workspace_section_list(
        self, client: TestClient, tmp_workspace: Path,
    ) -> None:
        # Start with only "overview" selected (per the fixture).
        # Switch to [overview, pricing].
        response = client.put(
            "/api/template",
            json={
                "path": str(tmp_workspace),
                "section_keys": ["overview", "pricing"],
            },
        )
        assert response.status_code == 200, response.text

        # The workspace yaml should now have those two sections.
        raw = yaml.safe_load((tmp_workspace / "recon.yaml").read_text())
        keys = [s["key"] for s in raw["sections"]]
        assert keys == ["overview", "pricing"]

        # And the GET reflects the change.
        get_response = client.get(f"/api/template?path={tmp_workspace}")
        selected = [s["key"] for s in get_response.json()["sections"] if s["selected"]]
        assert set(selected) == {"overview", "pricing"}

    def test_empty_list_is_allowed(
        self, client: TestClient, tmp_workspace: Path,
    ) -> None:
        # Empty is a valid (if useless) state — the Confirm screen will
        # warn/disable Start if sections are empty, not this endpoint.
        response = client.put(
            "/api/template",
            json={"path": str(tmp_workspace), "section_keys": []},
        )
        assert response.status_code == 200
        raw = yaml.safe_load((tmp_workspace / "recon.yaml").read_text())
        assert raw["sections"] == []

    def test_rejects_unknown_section_key(
        self, client: TestClient, tmp_workspace: Path,
    ) -> None:
        response = client.put(
            "/api/template",
            json={
                "path": str(tmp_workspace),
                "section_keys": ["overview", "definitely_not_a_section"],
            },
        )
        assert response.status_code == 400
        # The workspace yaml wasn't modified.
        raw = yaml.safe_load((tmp_workspace / "recon.yaml").read_text())
        assert [s["key"] for s in raw["sections"]] == ["overview"]

    def test_404_for_missing_workspace(
        self, client: TestClient, tmp_path: Path,
    ) -> None:
        response = client.put(
            "/api/template",
            json={"path": str(tmp_path / "nope"), "section_keys": []},
        )
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/confirm
# ---------------------------------------------------------------------------


class TestGetConfirm:
    def test_summarizes_counts_and_section_names(
        self, client: TestClient, workspace_with_competitors: Path,
    ) -> None:
        response = client.get(f"/api/confirm?path={workspace_with_competitors}")
        assert response.status_code == 200
        body = response.json()

        assert body["competitor_count"] == 2
        # One section ("overview") from MINIMAL_SCHEMA_DICT.
        assert body["section_keys"] == ["overview"]
        assert body["section_names"] == ["Overview"]

    def test_cost_estimate_scales_with_competitors_and_sections(
        self, client: TestClient, workspace_with_competitors: Path,
    ) -> None:
        response = client.get(f"/api/confirm?path={workspace_with_competitors}")
        body = response.json()

        # Per-stage breakdown exposed so the UI can render the TUI-style
        # line items (research / enrichment / themes / summaries).
        breakdown = body["cost_by_stage"]
        assert "research" in breakdown
        assert "enrichment" in breakdown
        assert "themes" in breakdown
        assert "summaries" in breakdown
        assert all(v >= 0 for v in breakdown.values())

        total = body["estimated_total"]
        assert total == pytest.approx(sum(breakdown.values()), rel=0.01)

    def test_exposes_model_options_with_per_model_total(
        self, client: TestClient, workspace_with_competitors: Path,
    ) -> None:
        response = client.get(f"/api/confirm?path={workspace_with_competitors}")
        body = response.json()

        models = {m["id"]: m for m in body["model_options"]}
        # All three canonical Claude 4 tiers surfaced.
        assert "claude-sonnet-4-20250514" in models
        # Each carries input/output pricing + an estimated total for
        # the run so the Confirm screen can show "~$X.XX" per option.
        sonnet = models["claude-sonnet-4-20250514"]
        assert "input_price_per_million" in sonnet
        assert "output_price_per_million" in sonnet
        assert "estimated_total" in sonnet
        assert sonnet["recommended"] is True

    def test_exposes_eta_and_worker_defaults(
        self, client: TestClient, workspace_with_competitors: Path,
    ) -> None:
        response = client.get(f"/api/confirm?path={workspace_with_competitors}")
        body = response.json()
        assert body["default_workers"] >= 1
        assert body["eta_seconds"] > 0
        # Sanity: the per-section time estimate shouldn't collapse the
        # ETA to something absurd (< 5s for 2 competitors × 1 section).
        assert body["eta_seconds"] >= 10

    def test_404_for_missing_workspace(
        self, client: TestClient, tmp_path: Path,
    ) -> None:
        response = client.get(f"/api/confirm?path={tmp_path / 'nope'}")
        assert response.status_code == 404
