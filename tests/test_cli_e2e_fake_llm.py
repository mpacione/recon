"""End-to-end CLI tests with a fake in-memory LLM client.

These tests drive the CLI entrypoints the way a user would -- via
``CliRunner.invoke(main, ...)`` -- with the Anthropic client mocked
out at ``recon.client_factory.create_llm_client``. They are the
regression safety net that would have caught bugs like:

- ``recon research <target>`` silently ignoring its argument
- ``recon run`` passing an ``index_manager`` kwarg that Pipeline doesn't accept
- Research never marking profiles as ``researched``
"""

from __future__ import annotations

from pathlib import Path  # noqa: TCH003 -- used at runtime
from unittest.mock import AsyncMock, patch

import frontmatter
import pytest  # noqa: TCH002 -- used at runtime for MonkeyPatch
import yaml
from click.testing import CliRunner

from recon.cli import main
from recon.llm import LLMResponse
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


def _setup_workspace(ws_dir: Path, competitors: list[str]) -> Workspace:
    ws_dir.mkdir(parents=True, exist_ok=True)
    (ws_dir / "competitors").mkdir(exist_ok=True)
    (ws_dir / ".recon").mkdir(exist_ok=True)
    (ws_dir / ".recon" / "logs").mkdir(exist_ok=True)
    (ws_dir / "recon.yaml").write_text(yaml.dump(MINIMAL_SCHEMA))
    ws = Workspace.open(ws_dir)
    for name in competitors:
        ws.create_profile(name)
    return ws


def _fake_llm_client(text: str = "## Overview\n\nFake research output.\n") -> AsyncMock:
    client = AsyncMock()
    client.complete = AsyncMock(
        return_value=LLMResponse(
            text=text,
            input_tokens=100,
            output_tokens=50,
            model="claude-sonnet-4-5",
            stop_reason="end_turn",
        )
    )
    client.total_input_tokens = 0
    client.total_output_tokens = 0
    return client


class TestResearchCliE2E:
    def test_research_all_updates_every_profile(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        ws_dir = tmp_path / "ws"
        _setup_workspace(ws_dir, ["Alpha", "Beta"])
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        monkeypatch.chdir(ws_dir)

        fake = _fake_llm_client(text="## Overview\n\nResearch results here.\n")
        with patch("recon.client_factory.create_llm_client", return_value=fake):
            runner = CliRunner()
            result = runner.invoke(main, ["research", "--all"], catch_exceptions=False)

        assert result.exit_code == 0, result.output

        ws = Workspace.open(ws_dir)
        alpha = ws.read_profile("alpha")
        beta = ws.read_profile("beta")
        assert alpha["research_status"] == "researched"
        assert beta["research_status"] == "researched"
        assert "Research results here" in alpha["_content"]
        assert "Research results here" in beta["_content"]

    def test_research_single_target_only_updates_that_profile(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        ws_dir = tmp_path / "ws"
        _setup_workspace(ws_dir, ["Alpha", "Beta", "Gamma"])
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        monkeypatch.chdir(ws_dir)

        fake = _fake_llm_client()
        with patch("recon.client_factory.create_llm_client", return_value=fake):
            runner = CliRunner()
            result = runner.invoke(main, ["research", "Beta"], catch_exceptions=False)

        assert result.exit_code == 0, result.output

        ws = Workspace.open(ws_dir)
        assert ws.read_profile("alpha")["research_status"] == "scaffold"
        assert ws.read_profile("beta")["research_status"] == "researched"
        assert ws.read_profile("gamma")["research_status"] == "scaffold"
        # Only Beta's overview section was researched, so only 1 LLM call
        assert fake.complete.call_count == 1


class TestEnrichCliE2E:
    def test_enrich_all_updates_every_eligible_profile(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        ws_dir = tmp_path / "ws"
        ws = _setup_workspace(ws_dir, ["Alpha", "Beta"])
        # Populate profiles with content so they're eligible for enrichment
        for slug in ["alpha", "beta"]:
            path = ws.competitors_dir / f"{slug}.md"
            post = frontmatter.load(str(path))
            post.content = "## Overview\n\nSome existing research.\n"
            post["research_status"] = "researched"
            path.write_text(frontmatter.dumps(post))

        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        monkeypatch.chdir(ws_dir)

        fake = _fake_llm_client(
            text="## Overview\n\nCleaner research with standardized headings.\n"
        )
        with patch("recon.client_factory.create_llm_client", return_value=fake):
            runner = CliRunner()
            result = runner.invoke(
                main, ["enrich", "--all", "--pass", "cleanup"], catch_exceptions=False,
            )

        assert result.exit_code == 0, result.output
        # Both profiles should have been rewritten
        ws = Workspace.open(ws_dir)
        for slug in ["alpha", "beta"]:
            profile = ws.read_profile(slug)
            assert "Cleaner research" in profile["_content"]

    def test_enrich_single_target_only_enriches_that_profile(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        ws_dir = tmp_path / "ws"
        ws = _setup_workspace(ws_dir, ["Alpha", "Beta"])
        for slug, name in [("alpha", "Alpha"), ("beta", "Beta")]:
            path = ws.competitors_dir / f"{slug}.md"
            post = frontmatter.load(str(path))
            post.content = f"## Overview\n\n{name} has existing research.\n"
            post["research_status"] = "researched"
            path.write_text(frontmatter.dumps(post))

        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        monkeypatch.chdir(ws_dir)

        fake = _fake_llm_client(text="## Overview\n\nEnriched only.\n")
        with patch("recon.client_factory.create_llm_client", return_value=fake):
            runner = CliRunner()
            result = runner.invoke(
                main, ["enrich", "Alpha", "--pass", "cleanup"], catch_exceptions=False,
            )

        assert result.exit_code == 0, result.output
        ws = Workspace.open(ws_dir)
        assert "Enriched only" in ws.read_profile("alpha")["_content"]
        assert "Enriched only" not in ws.read_profile("beta")["_content"]


class TestRunCliE2E:
    def test_run_command_executes_pipeline_without_errors(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        ws_dir = tmp_path / "ws"
        _setup_workspace(ws_dir, ["Alpha"])
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        monkeypatch.chdir(ws_dir)

        fake = _fake_llm_client(text="## Overview\n\nPipeline output.\n")
        with patch("recon.client_factory.create_llm_client", return_value=fake):
            runner = CliRunner()
            result = runner.invoke(
                main, ["run", "--from", "research"], catch_exceptions=False,
            )

        assert result.exit_code == 0, result.output
        assert "Run ID" in result.output or "complete" in result.output.lower()

        ws = Workspace.open(ws_dir)
        alpha = ws.read_profile("alpha")
        assert alpha["research_status"] == "researched"
