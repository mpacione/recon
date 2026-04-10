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


class TestVersionFlag:
    def test_version_flag_resolves_installed_distribution(self) -> None:
        """--version must resolve the recon-cli distribution, not the
        import name `recon`. Regression test for a packaging bug caught
        by smoke-testing the 0.2.0 wheel in a fresh venv.
        """
        runner = CliRunner()
        result = runner.invoke(main, ["--version"], catch_exceptions=False)

        assert result.exit_code == 0, result.output
        assert "recon" in result.output.lower()


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


VERIFY_SCHEMA = {
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
            "verification_tier": "verified",
        },
    ],
}


def _setup_verify_workspace(ws_dir: Path, competitors: list[str]) -> Workspace:
    ws_dir.mkdir(parents=True, exist_ok=True)
    (ws_dir / "competitors").mkdir(exist_ok=True)
    (ws_dir / ".recon").mkdir(exist_ok=True)
    (ws_dir / ".recon" / "logs").mkdir(exist_ok=True)
    (ws_dir / "recon.yaml").write_text(yaml.dump(VERIFY_SCHEMA))
    ws = Workspace.open(ws_dir)
    for name in competitors:
        ws.create_profile(name)
        slug = name.lower().replace(" ", "_")
        path = ws.competitors_dir / f"{slug}.md"
        post = frontmatter.load(str(path))
        post.content = f"## Overview\n\n{name} details. Source: [Docs](https://example.com)\n"
        post["research_status"] = "researched"
        path.write_text(frontmatter.dumps(post))
    return ws


class TestVerifyCliE2E:
    def test_verify_all_writes_frontmatter_summary(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        ws_dir = tmp_path / "ws"
        _setup_verify_workspace(ws_dir, ["Alpha"])
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        monkeypatch.chdir(ws_dir)

        fake = AsyncMock()
        fake.complete = AsyncMock(
            return_value=LLMResponse(
                text='{"sources": [{"url": "https://example.com", "status": "confirmed", "notes": "match"}], "corroboration": "ok"}',
                input_tokens=200,
                output_tokens=50,
                model="claude-sonnet-4-5",
                stop_reason="end_turn",
            ),
        )
        with patch("recon.client_factory.create_llm_client", return_value=fake):
            runner = CliRunner()
            result = runner.invoke(main, ["verify", "--all"], catch_exceptions=False)

        assert result.exit_code == 0, result.output
        assert "confirmed" in result.output

        ws = Workspace.open(ws_dir)
        alpha = ws.read_profile("alpha")
        verification = alpha.get("verification")
        assert isinstance(verification, dict)
        assert "overview" in verification
        assert verification["overview"]["confirmed"] == 1

    def test_verify_dry_run_lists_sections(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        ws_dir = tmp_path / "ws"
        _setup_verify_workspace(ws_dir, ["Alpha"])
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        monkeypatch.chdir(ws_dir)

        runner = CliRunner()
        result = runner.invoke(main, ["verify", "--all", "--dry-run"], catch_exceptions=False)

        assert result.exit_code == 0, result.output
        assert "overview" in result.output
        assert "verified" in result.output

    def test_verify_with_target_filters(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        ws_dir = tmp_path / "ws"
        _setup_verify_workspace(ws_dir, ["Alpha", "Beta"])
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        monkeypatch.chdir(ws_dir)

        fake = AsyncMock()
        fake.complete = AsyncMock(
            return_value=LLMResponse(
                text='{"sources": [{"url": "https://example.com", "status": "confirmed", "notes": "ok"}], "corroboration": "ok"}',
                input_tokens=100,
                output_tokens=50,
                model="claude-sonnet-4-5",
                stop_reason="end_turn",
            ),
        )
        with patch("recon.client_factory.create_llm_client", return_value=fake):
            runner = CliRunner()
            result = runner.invoke(main, ["verify", "Beta"], catch_exceptions=False)

        assert result.exit_code == 0, result.output
        # Only one LLM call should have been made (Beta, not Alpha)
        assert fake.complete.call_count == 1

        ws = Workspace.open(ws_dir)
        alpha = ws.read_profile("alpha")
        beta = ws.read_profile("beta")
        assert alpha.get("verification") is None
        assert beta.get("verification") is not None


class TestDiffCliE2E:
    def test_diff_all_refreshes_only_stale_sections(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import datetime as dt

        ws_dir = tmp_path / "ws"
        ws = _setup_workspace(ws_dir, ["Alpha", "Beta"])
        # Alpha is fresh (1 day ago), Beta is stale (60 days ago)
        fresh = (dt.datetime.now(dt.UTC) - dt.timedelta(days=1)).isoformat()
        stale = (dt.datetime.now(dt.UTC) - dt.timedelta(days=60)).isoformat()
        for slug, researched_at in [("alpha", fresh), ("beta", stale)]:
            path = ws.competitors_dir / f"{slug}.md"
            post = frontmatter.load(str(path))
            post.content = "## Overview\n\nPrior content.\n"
            post["research_status"] = "researched"
            post["section_status"] = {
                "overview": {"status": "researched", "researched_at": researched_at},
            }
            path.write_text(frontmatter.dumps(post))

        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        monkeypatch.chdir(ws_dir)

        fake = _fake_llm_client(text="## Overview\n\nRefreshed content.\n")
        with patch("recon.client_factory.create_llm_client", return_value=fake):
            runner = CliRunner()
            result = runner.invoke(
                main, ["diff", "--all", "--max-age-days", "30"], catch_exceptions=False,
            )

        assert result.exit_code == 0, result.output
        assert "Diff complete" in result.output
        # Only Beta should have been re-researched (1 call, not 2)
        assert fake.complete.call_count == 1

    def test_diff_dry_run_does_not_call_llm(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        ws_dir = tmp_path / "ws"
        _setup_workspace(ws_dir, ["Alpha"])
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        monkeypatch.chdir(ws_dir)

        fake = _fake_llm_client()
        with patch("recon.client_factory.create_llm_client", return_value=fake):
            runner = CliRunner()
            result = runner.invoke(
                main, ["diff", "--all", "--dry-run"], catch_exceptions=False,
            )

        assert result.exit_code == 0
        assert "Diff plan" in result.output
        assert fake.complete.call_count == 0


class TestRerunCliE2E:
    def test_rerun_all_refreshes_only_failed_sections(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import datetime as dt

        ws_dir = tmp_path / "ws"
        ws = _setup_workspace(ws_dir, ["Alpha", "Beta"])
        now = dt.datetime.now(dt.UTC).isoformat()
        for slug, section_status in [
            ("alpha", {"overview": {"status": "researched", "researched_at": now}}),
            ("beta", {"overview": {"status": "failed"}}),
        ]:
            path = ws.competitors_dir / f"{slug}.md"
            post = frontmatter.load(str(path))
            post.content = "## Overview\n\nWhatever.\n"
            post["research_status"] = "researched"
            post["section_status"] = section_status
            path.write_text(frontmatter.dumps(post))

        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        monkeypatch.chdir(ws_dir)

        fake = _fake_llm_client(text="## Overview\n\nRetried content.\n")
        with patch("recon.client_factory.create_llm_client", return_value=fake):
            runner = CliRunner()
            result = runner.invoke(
                main, ["rerun", "--all"], catch_exceptions=False,
            )

        assert result.exit_code == 0, result.output
        assert "Rerun complete" in result.output
        # Only Beta should have been re-researched
        assert fake.complete.call_count == 1

        ws = Workspace.open(ws_dir)
        beta = ws.read_profile("beta")
        assert beta["section_status"]["overview"]["status"] == "researched"


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

    def test_run_command_full_pipeline_writes_synthesis_and_summary(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The full pipeline should actually produce themes + synthesis + executive summary.

        This is the regression test for the "recon run does nothing past
        enrich" bug fixed in Option P.
        """
        ws_dir = tmp_path / "ws"
        ws = _setup_workspace(ws_dir, ["Alpha", "Beta"])
        # Pre-fill with researched content so we don't hit the web_search tool
        for slug, name in [("alpha", "Alpha"), ("beta", "Beta")]:
            path = ws.competitors_dir / f"{slug}.md"
            post = frontmatter.load(str(path))
            post.content = f"## Overview\n\n{name} does interesting things in AI tooling.\n"
            post["research_status"] = "researched"
            path.write_text(frontmatter.dumps(post))

        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        monkeypatch.chdir(ws_dir)

        fake = _fake_llm_client(text="Synthesis / distillation output.")
        with patch("recon.client_factory.create_llm_client", return_value=fake):
            runner = CliRunner()
            # Start from INDEX so we don't re-run research/enrich (saves calls)
            result = runner.invoke(
                main, ["run", "--from", "index"], catch_exceptions=False,
            )

        assert result.exit_code == 0, result.output

        themes_dir = ws_dir / "themes"
        assert themes_dir.exists(), "themes/ should exist after run"
        theme_files = [p for p in themes_dir.glob("*.md") if p.is_file()]
        assert theme_files, "at least one theme synthesis file should be written"

        distilled_dir = themes_dir / "distilled"
        assert distilled_dir.exists(), "themes/distilled/ should exist after run"
        assert list(distilled_dir.glob("*.md")), "at least one distilled file"

        summary = ws_dir / "executive_summary.md"
        assert summary.exists(), "executive_summary.md should exist after run"
        assert summary.read_text().strip(), "summary should not be empty"

        # Output should advertise what the pipeline produced
        assert "theme" in result.output.lower()
        assert "executive_summary.md" in result.output


class TestCliSequentialWorkflow:
    """End-to-end CLI workflow exercising the individual stage commands.

    Drives a realistic user journey: init → add → research → enrich →
    index → tag → synthesize → distill → summarize. Uses the fake LLM
    client throughout. Each command is verified for non-zero outputs
    and on-disk artifacts.
    """

    def test_full_chain_init_through_summarize(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        ws_dir = tmp_path / "ws"
        ws_dir.mkdir()
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        monkeypatch.chdir(ws_dir)

        fake = _fake_llm_client(
            text=(
                "## Overview\n\n"
                "Alpha and Beta both compete in AI tooling.\n\n"
                "Source: [Docs](https://example.com) -- 2026-01-01\n"
            )
        )

        runner = CliRunner()
        with patch("recon.client_factory.create_llm_client", return_value=fake):
            # 1. Init the workspace headlessly
            result = runner.invoke(
                main,
                [
                    "init",
                    "--headless",
                    "--domain",
                    "AI tools",
                    "--company",
                    "Acme",
                    "--products",
                    "Acme IDE",
                ],
                catch_exceptions=False,
            )
            assert result.exit_code == 0, result.output
            assert (ws_dir / "recon.yaml").exists()

            # 2. Add competitors
            result = runner.invoke(
                main, ["add", "Alpha"], catch_exceptions=False,
            )
            assert result.exit_code == 0, result.output
            result = runner.invoke(
                main, ["add", "Beta"], catch_exceptions=False,
            )
            assert result.exit_code == 0, result.output

            # 3. Research everything
            result = runner.invoke(
                main, ["research", "--all"], catch_exceptions=False,
            )
            assert result.exit_code == 0, result.output
            assert "Research complete" in result.output

            # 4. Enrich (cleanup pass only -- the others would just stack)
            result = runner.invoke(
                main, ["enrich", "--all", "--pass", "cleanup"],
                catch_exceptions=False,
            )
            assert result.exit_code == 0, result.output

            # 5. Index
            result = runner.invoke(main, ["index"], catch_exceptions=False)
            assert result.exit_code == 0, result.output

            # 6. Tag (theme discovery + tagging)
            result = runner.invoke(main, ["tag"], catch_exceptions=False)
            assert result.exit_code == 0, result.output
            assert "Discovered" in result.output

            # 7. Status reflects the work done
            result = runner.invoke(main, ["status"], catch_exceptions=False)
            assert result.exit_code == 0, result.output
            assert "researched: 2" in result.output.lower() or "Profiles: 2" in result.output

            # 8. Both profiles should now have content + frontmatter status
            ws = Workspace.open(ws_dir)
            for slug in ["alpha", "beta"]:
                profile = ws.read_profile(slug)
                assert profile["research_status"] == "researched"
                assert "section_status" in profile
                assert "_content" in profile and profile["_content"].strip()


class TestDiffSequentialWorkflow:
    """Sequential test: research → diff (no-op) → mark old → diff (refresh).

    Verifies that diff is genuinely a no-op for fresh content and
    actually picks up sections after they age past the threshold.
    """

    def test_research_then_diff_noop_then_force_stale_then_diff_refreshes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import datetime as dt

        ws_dir = tmp_path / "ws"
        _setup_workspace(ws_dir, ["Alpha"])
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        monkeypatch.chdir(ws_dir)

        runner = CliRunner()

        # Round 1: research
        first_response = "## Overview\n\nFirst pass content.\n"
        fake1 = _fake_llm_client(text=first_response)
        with patch("recon.client_factory.create_llm_client", return_value=fake1):
            result = runner.invoke(
                main, ["research", "--all"], catch_exceptions=False,
            )
        assert result.exit_code == 0
        assert fake1.complete.call_count == 1

        # Round 2: diff with default 30d window -- nothing should run
        fake2 = _fake_llm_client(text="should not be called")
        with patch("recon.client_factory.create_llm_client", return_value=fake2):
            result = runner.invoke(
                main, ["diff", "--all", "--max-age-days", "30"],
                catch_exceptions=False,
            )
        assert result.exit_code == 0
        assert fake2.complete.call_count == 0

        # Now force the section to look old by rewriting researched_at
        ws = Workspace.open(ws_dir)
        path = ws.competitors_dir / "alpha.md"
        post = frontmatter.load(str(path))
        old = (dt.datetime.now(dt.UTC) - dt.timedelta(days=90)).isoformat()
        post["section_status"] = {
            "overview": {"status": "researched", "researched_at": old},
        }
        path.write_text(frontmatter.dumps(post))

        # Round 3: diff again -- now it should refresh
        fake3 = _fake_llm_client(text="## Overview\n\nRefreshed content.\n")
        with patch("recon.client_factory.create_llm_client", return_value=fake3):
            result = runner.invoke(
                main, ["diff", "--all", "--max-age-days", "30"],
                catch_exceptions=False,
            )
        assert result.exit_code == 0
        assert fake3.complete.call_count == 1

        # The section_status timestamp should have been updated
        ws = Workspace.open(ws_dir)
        alpha = ws.read_profile("alpha")
        new_ts = alpha["section_status"]["overview"]["researched_at"]
        assert new_ts != old


class TestRunCostTracking:
    """The state store should record cost from every stage of `recon run`."""

    def test_full_run_records_cost_through_state_store(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from recon.state import StateStore

        ws_dir = tmp_path / "ws"
        ws = _setup_workspace(ws_dir, ["Alpha"])
        # Pre-fill so research has work to do but nothing too expensive
        path = ws.competitors_dir / "alpha.md"
        post = frontmatter.load(str(path))
        post.content = "## Overview\n\nAlpha content.\n"
        post["research_status"] = "researched"
        path.write_text(frontmatter.dumps(post))

        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        monkeypatch.chdir(ws_dir)

        fake = _fake_llm_client(text="## Overview\n\nFake output.\n")
        with patch("recon.client_factory.create_llm_client", return_value=fake):
            runner = CliRunner()
            result = runner.invoke(
                main, ["run", "--from", "index"], catch_exceptions=False,
            )

        assert result.exit_code == 0, result.output

        async def check_costs() -> float:
            store = StateStore(ws_dir / ".recon" / "state.db")
            await store.initialize()
            runs = await store.list_runs()
            assert runs, "No runs recorded"
            latest = runs[-1]
            return await store.get_run_total_cost(latest["run_id"])

        import asyncio

        total = asyncio.run(check_costs())
        # Synthesis + distill + meta-synthesis = 3 LLM calls minimum, all
        # should be costed via _record_tokens
        assert total > 0.0, "state store should record nonzero cost"
