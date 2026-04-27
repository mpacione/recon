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
        assert "high-level" in section["description"].lower()

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

    def test_persists_full_section_pool_with_custom_section(
        self, client: TestClient, tmp_workspace: Path,
    ) -> None:
        response = client.put(
            "/api/template",
            json={
                "path": str(tmp_workspace),
                "sections": [
                    {
                        "key": "overview",
                        "title": "Overview",
                        "description": "Summarize the company at a high level.",
                        "selected": True,
                        "allowed_formats": ["prose"],
                        "preferred_format": "prose",
                    },
                    {
                        "key": "channel_risk",
                        "title": "Channel Risk",
                        "description": "Assess channel concentration, platform dependency, and partner risk.",
                        "selected": False,
                        "allowed_formats": ["prose"],
                        "preferred_format": "prose",
                    },
                ],
            },
        )
        assert response.status_code == 200, response.text

        raw = yaml.safe_load((tmp_workspace / "recon.yaml").read_text())
        assert [s["key"] for s in raw["sections"]] == ["overview"]

        pool = yaml.safe_load((tmp_workspace / ".recon" / "schema_sections.yaml").read_text())
        assert [s["key"] for s in pool] == ["overview", "channel_risk"]
        assert pool[1]["selected"] is False

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

    def test_uses_saved_plan_settings_for_defaults_and_breakdown(
        self, client: TestClient, workspace_with_competitors: Path,
    ) -> None:
        patch = client.patch(
            "/api/plan-settings",
            json={
                "path": str(workspace_with_competitors),
                "model_name": "opus",
                "workers": 7,
                "verification_mode": "deep",
            },
        )
        assert patch.status_code == 200, patch.text

        response = client.get(f"/api/confirm?path={workspace_with_competitors}")
        body = response.json()
        assert body["default_model"] == "opus"
        assert body["default_workers"] == 7
        assert body["default_verification_mode"] == "deep"
        assert body["estimate_competitor_count"] == 2
        assert body["research_per_company"] > 0
        assert body["enrichment_per_company"] > 0
        assert body["fixed_total"] > 0
        assert body["verification_uplift_per_company"] >= 0

    def test_404_for_missing_workspace(
        self, client: TestClient, tmp_path: Path,
    ) -> None:
        response = client.get(f"/api/confirm?path={tmp_path / 'nope'}")
        assert response.status_code == 404


class TestPlanSettings:
    def test_get_returns_defaults_when_no_plan_yaml_exists(
        self, client: TestClient, tmp_workspace: Path,
    ) -> None:
        response = client.get(f"/api/plan-settings?path={tmp_workspace}")
        assert response.status_code == 200
        assert response.json() == {
            "model_name": "sonnet",
            "workers": 5,
            "verification_mode": "standard",
        }

    def test_patch_persists_workspace_plan_settings(
        self, client: TestClient, tmp_workspace: Path,
    ) -> None:
        response = client.patch(
            "/api/plan-settings",
            json={
                "path": str(tmp_workspace),
                "model_name": "haiku",
                "workers": 3,
                "verification_mode": "verified",
            },
        )
        assert response.status_code == 200, response.text
        assert response.json() == {
            "model_name": "haiku",
            "workers": 3,
            "verification_mode": "verified",
        }

        get_response = client.get(f"/api/plan-settings?path={tmp_workspace}")
        assert get_response.status_code == 200
        assert get_response.json() == response.json()
