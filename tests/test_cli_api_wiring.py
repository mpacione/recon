"""Tests for CLI commands that require API key wiring.

Tests that commands fail gracefully without API key and that they
construct correct engine components when the key is available.
"""

from __future__ import annotations

from pathlib import Path  # noqa: TCH003 -- used at runtime
from unittest.mock import AsyncMock, patch

import frontmatter
import pytest  # noqa: TCH002 -- used at runtime for MonkeyPatch type
import yaml
from click.testing import CliRunner

from recon.cli import main
from recon.workspace import Workspace

MINIMAL_SCHEMA = {
    "domain": "Developer Tools",
    "identity": {
        "company_name": "Acme Corp",
        "products": ["Acme IDE"],
        "decision_context": [],
    },
    "rating_scales": {},
    "sections": [
        {
            "key": "overview",
            "title": "Overview",
            "description": "High-level summary.",
            "allowed_formats": ["prose"],
            "preferred_format": "prose",
        },
    ],
}


def _setup_workspace(ws_dir: Path) -> None:
    ws_dir.mkdir(exist_ok=True)
    (ws_dir / "competitors").mkdir(exist_ok=True)
    (ws_dir / ".recon").mkdir(exist_ok=True)
    (ws_dir / ".recon" / "logs").mkdir(exist_ok=True)
    (ws_dir / "recon.yaml").write_text(yaml.dump(MINIMAL_SCHEMA))

    ws = Workspace.open(ws_dir)
    ws.create_profile("Alpha")
    path = ws.competitors_dir / "alpha.md"
    post = frontmatter.load(str(path))
    post.content = "## Overview\n\nAlpha is an AI code tool.\n"
    post["research_status"] = "researched"
    path.write_text(frontmatter.dumps(post))


class TestResearchCommand:
    def test_without_api_key_shows_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        ws_dir = tmp_path / "ws"
        _setup_workspace(ws_dir)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.chdir(ws_dir)

        runner = CliRunner()
        result = runner.invoke(main, ["research", "--all"], catch_exceptions=False)

        assert result.exit_code == 0
        assert "ANTHROPIC_API_KEY" in result.output

    def test_with_api_key_runs_orchestrator(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        ws_dir = tmp_path / "ws"
        _setup_workspace(ws_dir)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")
        monkeypatch.chdir(ws_dir)

        mock_orchestrator = AsyncMock()
        mock_orchestrator.research_all = AsyncMock(return_value=[
            {"competitor": "Alpha", "section": "overview", "tokens": {"input": 100, "output": 50}},
        ])

        with patch("recon.research.ResearchOrchestrator", return_value=mock_orchestrator):
            runner = CliRunner()
            result = runner.invoke(main, ["research", "--all"], catch_exceptions=False)

        assert result.exit_code == 0
        assert "complete" in result.output.lower()

    def test_target_argument_passes_single_competitor(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        ws_dir = tmp_path / "ws"
        _setup_workspace(ws_dir)
        ws = Workspace.open(ws_dir)
        ws.create_profile("Beta")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")
        monkeypatch.chdir(ws_dir)

        mock_orchestrator = AsyncMock()
        mock_orchestrator.research_all = AsyncMock(return_value=[])

        with patch("recon.research.ResearchOrchestrator", return_value=mock_orchestrator):
            runner = CliRunner()
            result = runner.invoke(main, ["research", "Beta"], catch_exceptions=False)

        assert result.exit_code == 0
        assert "Beta" in result.output
        mock_orchestrator.research_all.assert_awaited_once()
        call_kwargs = mock_orchestrator.research_all.await_args.kwargs
        assert call_kwargs["targets"] == ["Beta"]

    def test_unknown_target_shows_error_and_does_not_call_orchestrator(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        ws_dir = tmp_path / "ws"
        _setup_workspace(ws_dir)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")
        monkeypatch.chdir(ws_dir)

        mock_orchestrator = AsyncMock()

        with patch("recon.research.ResearchOrchestrator", return_value=mock_orchestrator):
            runner = CliRunner()
            result = runner.invoke(main, ["research", "Nonexistent"], catch_exceptions=False)

        assert result.exit_code == 0
        assert "Unknown competitor" in result.output
        mock_orchestrator.research_all.assert_not_awaited()

    def test_no_target_and_no_all_shows_usage_hint(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        ws_dir = tmp_path / "ws"
        _setup_workspace(ws_dir)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")
        monkeypatch.chdir(ws_dir)

        runner = CliRunner()
        result = runner.invoke(main, ["research"], catch_exceptions=False)

        assert result.exit_code == 0
        assert "--all" in result.output


class TestEnrichCommand:
    def test_without_api_key_shows_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        ws_dir = tmp_path / "ws"
        _setup_workspace(ws_dir)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.chdir(ws_dir)

        runner = CliRunner()
        result = runner.invoke(main, ["enrich", "--all", "--pass", "cleanup"], catch_exceptions=False)

        assert result.exit_code == 0
        assert "ANTHROPIC_API_KEY" in result.output

    def test_with_api_key_runs_orchestrator(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        ws_dir = tmp_path / "ws"
        _setup_workspace(ws_dir)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")
        monkeypatch.chdir(ws_dir)

        mock_orchestrator = AsyncMock()
        mock_orchestrator.enrich_all = AsyncMock(return_value=[
            {"competitor": "Alpha", "pass": "cleanup", "tokens": {"input": 100, "output": 50}},
        ])

        with patch("recon.enrichment.EnrichmentOrchestrator", return_value=mock_orchestrator):
            runner = CliRunner()
            result = runner.invoke(
                main, ["enrich", "--all", "--pass", "cleanup"],
                catch_exceptions=False,
            )

        assert result.exit_code == 0
        assert "complete" in result.output.lower()

    def test_target_argument_passes_single_competitor(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        ws_dir = tmp_path / "ws"
        _setup_workspace(ws_dir)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")
        monkeypatch.chdir(ws_dir)

        mock_orchestrator = AsyncMock()
        mock_orchestrator.enrich_all = AsyncMock(return_value=[])

        with patch("recon.enrichment.EnrichmentOrchestrator", return_value=mock_orchestrator):
            runner = CliRunner()
            result = runner.invoke(
                main, ["enrich", "Alpha", "--pass", "cleanup"],
                catch_exceptions=False,
            )

        assert result.exit_code == 0
        mock_orchestrator.enrich_all.assert_awaited_once()
        call_kwargs = mock_orchestrator.enrich_all.await_args.kwargs
        assert call_kwargs["targets"] == ["Alpha"]


class TestSynthesizeCommand:
    def test_without_api_key_shows_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        ws_dir = tmp_path / "ws"
        _setup_workspace(ws_dir)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.chdir(ws_dir)

        runner = CliRunner()
        result = runner.invoke(main, ["synthesize", "--theme", "AI"], catch_exceptions=False)

        assert result.exit_code == 0
        assert "ANTHROPIC_API_KEY" in result.output


class TestDistillCommand:
    def test_without_api_key_shows_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        ws_dir = tmp_path / "ws"
        _setup_workspace(ws_dir)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.chdir(ws_dir)

        runner = CliRunner()
        result = runner.invoke(main, ["distill", "--theme", "AI"], catch_exceptions=False)

        assert result.exit_code == 0
        assert "ANTHROPIC_API_KEY" in result.output


class TestSummarizeCommand:
    def test_without_api_key_shows_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        ws_dir = tmp_path / "ws"
        _setup_workspace(ws_dir)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.chdir(ws_dir)

        runner = CliRunner()
        result = runner.invoke(main, ["summarize"], catch_exceptions=False)

        assert result.exit_code == 0
        assert "ANTHROPIC_API_KEY" in result.output


class TestRunCommand:
    def test_without_api_key_shows_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        ws_dir = tmp_path / "ws"
        _setup_workspace(ws_dir)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.chdir(ws_dir)

        runner = CliRunner()
        result = runner.invoke(main, ["run"], catch_exceptions=False)

        assert result.exit_code == 0
        assert "ANTHROPIC_API_KEY" in result.output
