"""Tests for the discovery CLI command."""

from __future__ import annotations

import json
from pathlib import Path  # noqa: TCH003 -- used in test signatures
from unittest.mock import AsyncMock, patch

from click.testing import CliRunner

from recon.cli import main


def _init_workspace(tmp_path: Path) -> None:
    """Create a minimal workspace for testing."""
    from recon.workspace import Workspace

    Workspace.init(
        root=tmp_path, domain="Developer Tools",
        company_name="Acme", products=["Acme CI"],
    )


def _candidates_response() -> str:
    return json.dumps({"candidates": [
        {
            "name": "Cursor",
            "url": "https://cursor.com",
            "blurb": "AI-first code editor",
            "provenance": "G2 category leader",
            "suggested_tier": "established",
        },
        {
            "name": "Linear",
            "url": "https://linear.app",
            "blurb": "Project tracking",
            "provenance": "YC batch",
            "suggested_tier": "emerging",
        },
    ]})


class TestDiscoverCommand:
    def test_dry_run_shows_plan(self, tmp_path: Path) -> None:
        _init_workspace(tmp_path)
        runner = CliRunner()

        result = runner.invoke(main, [
            "discover", "--workspace", str(tmp_path), "--dry-run",
        ])

        assert result.exit_code == 0
        assert "discovery" in result.output.lower()

    def test_discover_requires_api_key(self, tmp_path: Path) -> None:
        _init_workspace(tmp_path)
        runner = CliRunner()

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": ""}, clear=False):
            result = runner.invoke(main, [
                "discover", "--workspace", str(tmp_path),
                "--batch-size", "1", "--rounds", "1",
            ])

        assert "ANTHROPIC_API_KEY" in result.output

    def test_discover_creates_profiles(self, tmp_path: Path) -> None:
        _init_workspace(tmp_path)
        runner = CliRunner()

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-test"}, clear=False), \
             patch("recon.discovery.DiscoveryAgent.search", new_callable=AsyncMock) as mock_search:
            from recon.discovery import parse_candidates_response
            mock_search.return_value = parse_candidates_response(_candidates_response())

            result = runner.invoke(main, [
                "discover", "--workspace", str(tmp_path),
                "--rounds", "1", "--auto-accept",
            ])

        assert result.exit_code == 0
        assert "Cursor" in result.output
        profiles = list((tmp_path / "competitors").glob("*.md"))
        assert len(profiles) >= 2
