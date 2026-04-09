"""Integration tests for the recon pipeline.

Exercises the full workflow with mocked LLM responses: workspace init ->
add competitors -> research -> enrich -> index -> themes -> tag ->
synthesis -> distill -> summarize. Tests that modules integrate correctly
through their public APIs.
"""

from __future__ import annotations

from pathlib import Path  # noqa: TCH003 -- used at runtime
from unittest.mock import AsyncMock, patch

import frontmatter
import numpy as np
import pytest
import yaml

from recon.cost import CostTracker, ModelPricing
from recon.deliver import Distiller, MetaSynthesizer
from recon.enrichment import EnrichmentOrchestrator, EnrichmentPass
from recon.incremental import IncrementalIndexer
from recon.index import IndexManager, chunk_markdown
from recon.llm import LLMResponse
from recon.pipeline import Pipeline, PipelineConfig, PipelineStage
from recon.research import ResearchOrchestrator
from recon.state import RunStatus, StateStore
from recon.synthesis import PassResult, SynthesisEngine, SynthesisMode, SynthesisResult
from recon.tag import Tagger
from recon.themes import ThemeDiscovery
from recon.wizard import DecisionContext, WizardState
from recon.workspace import Workspace


def _mock_llm_client(text: str = "## Overview\n\nResearch content.\n") -> LLMResponse:
    """Build a mock LLMClient whose complete() returns a fixed LLMResponse."""
    client = AsyncMock()
    client.complete = AsyncMock(
        return_value=LLMResponse(
            text=text,
            input_tokens=500,
            output_tokens=200,
            model="claude-sonnet-4-20250514",
            stop_reason="end_turn",
        ),
    )
    return client


def _create_workspace_via_wizard(root: Path) -> Workspace:
    state = WizardState()
    state.set_identity(
        company_name="Acme Corp",
        products=["Acme CI"],
        domain="CI/CD Tools",
        decision_contexts=[DecisionContext.BUILD_VS_BUY],
    )
    state.advance()
    state.advance()
    state.advance()

    schema_dict = state.to_schema_dict()
    root.mkdir(parents=True, exist_ok=True)
    (root / "recon.yaml").write_text(yaml.dump(schema_dict, default_flow_style=False, sort_keys=False))

    return Workspace.init(root=root)


def _fill_profile_with_content(ws: Workspace, slug: str, name: str) -> None:
    path = ws.competitors_dir / f"{slug}.md"
    post = frontmatter.load(str(path))
    post.content = (
        f"## Overview\n\n{name} is a comprehensive CI/CD platform "
        f"for modern development teams. It supports 500+ integrations "
        f"and provides enterprise-grade security features.\n\n"
        f"## Capabilities\n\n"
        f"| Capability | Rating | Evidence |\n"
        f"|---|---|---|\n"
        f"| Pipeline speed | 4/5 | Sub-2-minute builds on average |\n"
        f"| Integration breadth | 5/5 | 500+ native integrations |\n"
        f"| Security scanning | 3/5 | Basic SAST, no DAST |\n\n"
        f"## Pricing\n\n"
        f"Free tier available. Pro starts at $10/user/month.\n"
    )
    post["research_status"] = "researched"
    path.write_text(frontmatter.dumps(post))


def _build_indexed_workspace(tmp_path: Path) -> tuple[Workspace, IndexManager]:
    """Create a workspace with 3 competitors, fill profiles, and index them."""
    ws = _create_workspace_via_wizard(tmp_path / "project")
    for name in ["Alpha CI", "Beta Pipeline", "Gamma Build"]:
        ws.create_profile(name)
    for slug, name in [("alpha-ci", "Alpha CI"), ("beta-pipeline", "Beta Pipeline"), ("gamma-build", "Gamma Build")]:
        _fill_profile_with_content(ws, slug, name)

    manager = IndexManager(persist_dir=str(tmp_path / "vectors"))
    for profile_meta in ws.list_profiles():
        full = ws.read_profile(profile_meta["_slug"])
        chunks = chunk_markdown(
            content=full["_content"],
            source_path=str(profile_meta["_path"]),
            frontmatter_meta={k: v for k, v in profile_meta.items() if not k.startswith("_")},
        )
        manager.add_chunks(chunks)

    return ws, manager


# ---------------------------------------------------------------------------
# 1. Wizard -> Workspace
# ---------------------------------------------------------------------------


class TestWizardToWorkspaceIntegration:
    def test_wizard_produces_parseable_schema(self, tmp_path: Path) -> None:
        ws = _create_workspace_via_wizard(tmp_path / "project")

        assert ws.schema is not None
        assert ws.schema.domain == "CI/CD Tools"
        assert ws.schema.identity.company_name == "Acme Corp"
        assert len(ws.schema.sections) > 0

    def test_workspace_has_full_structure(self, tmp_path: Path) -> None:
        ws = _create_workspace_via_wizard(tmp_path / "project")

        assert (ws.root / "competitors").is_dir()
        assert (ws.root / "themes").is_dir()
        assert (ws.root / "own-products").is_dir()
        assert (ws.root / ".recon").is_dir()
        assert (ws.root / ".gitignore").exists()

    def test_can_add_competitors_after_wizard(self, tmp_path: Path) -> None:
        ws = _create_workspace_via_wizard(tmp_path / "project")

        path_a = ws.create_profile("Alpha CI")
        path_b = ws.create_profile("Beta Pipeline")

        assert path_a.exists()
        assert path_b.exists()
        profiles = ws.list_profiles()
        assert len(profiles) == 2


# ---------------------------------------------------------------------------
# 2. Research stage through pipeline
# ---------------------------------------------------------------------------


class TestResearchPipelineIntegration:
    async def test_research_writes_content_to_profiles(self, tmp_path: Path) -> None:
        ws = _create_workspace_via_wizard(tmp_path / "project")
        ws.create_profile("Alpha CI")
        ws.create_profile("Beta Pipeline")

        client = _mock_llm_client(
            text="## Overview\n\nAlpha is a leading CI/CD platform with advanced features.\n"
        )

        orchestrator = ResearchOrchestrator(
            workspace=ws,
            llm_client=client,
            max_workers=2,
        )

        results = await orchestrator.research_all()

        assert len(results) > 0
        for result in results:
            assert "competitor" in result
            assert "section" in result
            assert result["tokens"]["input"] == 500
            assert result["tokens"]["output"] == 200

        alpha = ws.read_profile("alpha-ci")
        assert "leading CI/CD platform" in alpha["_content"]

    async def test_research_through_pipeline_records_cost(self, tmp_path: Path) -> None:
        ws = _create_workspace_via_wizard(tmp_path / "project")
        ws.create_profile("Alpha CI")

        state = StateStore(db_path=ws.root / ".recon" / "state.db")
        await state.initialize()

        client = _mock_llm_client(text="## Overview\n\nResearched content.\n")

        pipeline = Pipeline(
            workspace=ws,
            state_store=state,
            llm_client=client,
            config=PipelineConfig(
                start_from=PipelineStage.RESEARCH,
                stop_after=PipelineStage.RESEARCH,
                verification_enabled=False,
            ),
        )

        run_id = await pipeline.plan()
        await pipeline.execute(run_id)

        run = await state.get_run(run_id)
        assert run["status"] == RunStatus.COMPLETED.value

        total_cost = await state.get_run_total_cost(run_id)
        assert total_cost > 0


# ---------------------------------------------------------------------------
# 3. Enrichment stage through pipeline
# ---------------------------------------------------------------------------


class TestEnrichmentPipelineIntegration:
    async def test_enrichment_updates_profile_content(self, tmp_path: Path) -> None:
        ws = _create_workspace_via_wizard(tmp_path / "project")
        ws.create_profile("Alpha CI")
        _fill_profile_with_content(ws, "alpha-ci", "Alpha CI")

        enriched_text = (
            "## Overview\n\nAlpha CI is a comprehensive CI/CD platform "
            "with enriched sentiment data.\n\n"
            "## Developer Sentiment\n\nPositive reception on HN.\n"
        )
        client = _mock_llm_client(text=enriched_text)

        orchestrator = EnrichmentOrchestrator(
            workspace=ws,
            llm_client=client,
            enrichment_pass=EnrichmentPass.SENTIMENT,
            max_workers=2,
        )

        results = await orchestrator.enrich_all()

        assert len(results) == 1
        assert results[0]["competitor"] == "Alpha CI"
        assert results[0]["pass"] == "sentiment"

        alpha = ws.read_profile("alpha-ci")
        assert "enriched sentiment data" in alpha["_content"]

    async def test_enrichment_through_pipeline_runs_all_passes(self, tmp_path: Path) -> None:
        ws = _create_workspace_via_wizard(tmp_path / "project")
        ws.create_profile("Alpha CI")
        _fill_profile_with_content(ws, "alpha-ci", "Alpha CI")

        state = StateStore(db_path=ws.root / ".recon" / "state.db")
        await state.initialize()

        client = _mock_llm_client(text="## Enriched\n\nEnriched content.\n")

        pipeline = Pipeline(
            workspace=ws,
            state_store=state,
            llm_client=client,
            config=PipelineConfig(
                start_from=PipelineStage.ENRICH,
                stop_after=PipelineStage.ENRICH,
                verification_enabled=False,
            ),
        )

        run_id = await pipeline.plan()
        await pipeline.execute(run_id)

        run = await state.get_run(run_id)
        assert run["status"] == RunStatus.COMPLETED.value

        assert client.complete.call_count == 3


# ---------------------------------------------------------------------------
# 4. Theme discovery -> Tag flow
# ---------------------------------------------------------------------------


class TestThemeToTagIntegration:
    def test_discovered_themes_can_tag_profiles(self, tmp_path: Path) -> None:
        ws, manager = _build_indexed_workspace(tmp_path)

        all_chunks = _build_chunks_with_embeddings(ws)

        discovery = ThemeDiscovery()
        themes = discovery.discover(all_chunks, n_themes=3)

        assert len(themes) > 0
        for theme in themes:
            assert theme.label
            assert len(theme.suggested_queries) > 0

        tagger = Tagger(index=manager, workspace=ws)
        assignments = tagger.tag(themes=themes, threshold=0.0, top_n=10)

        assert len(assignments) > 0

    def test_tag_apply_writes_to_frontmatter(self, tmp_path: Path) -> None:
        ws, manager = _build_indexed_workspace(tmp_path)

        all_chunks = _build_chunks_with_embeddings(ws)
        discovery = ThemeDiscovery()
        themes = discovery.discover(all_chunks, n_themes=2)

        tagger = Tagger(index=manager, workspace=ws)
        assignments = tagger.tag(themes=themes, threshold=0.0, top_n=10)

        tagger.apply(assignments)

        tagged_slugs = {a.competitor_slug for a in assignments}
        for slug in tagged_slugs:
            profile = ws.read_profile(slug)
            assert "themes" in frontmatter.load(str(profile["_path"])).metadata

    def test_themes_to_tag_end_to_end_preserves_competitor_names(self, tmp_path: Path) -> None:
        ws, manager = _build_indexed_workspace(tmp_path)

        all_chunks = _build_chunks_with_embeddings(ws)
        discovery = ThemeDiscovery()
        themes = discovery.discover(all_chunks, n_themes=2)
        tagger = Tagger(index=manager, workspace=ws)
        assignments = tagger.tag(themes=themes, threshold=0.0, top_n=10)

        valid_slugs = {p["_slug"] for p in ws.list_profiles()}
        for assignment in assignments:
            assert assignment.competitor_slug in valid_slugs


# ---------------------------------------------------------------------------
# 5. Synthesis -> Distill -> Summarize chain
# ---------------------------------------------------------------------------


class TestDeliveryChainIntegration:
    async def test_synthesis_produces_result_for_distillation(self, tmp_path: Path) -> None:
        ws, manager = _build_indexed_workspace(tmp_path)

        client = _mock_llm_client(text="# Platform Consolidation\n\nKey finding: convergence trend.\n")
        engine = SynthesisEngine(llm_client=client)

        chunks = manager.retrieve("CI/CD platform capabilities", n_results=10)
        result = await engine.synthesize(theme="Platform Consolidation", chunks=chunks)

        assert result.theme == "Platform Consolidation"
        assert result.mode == SynthesisMode.SINGLE
        assert "convergence trend" in result.content
        assert result.total_input_tokens > 0

    async def test_deep_synthesis_runs_four_passes(self, tmp_path: Path) -> None:
        ws, manager = _build_indexed_workspace(tmp_path)

        call_count = 0
        pass_texts = [
            "Strategist: convergence pattern detected.",
            "Devil's advocate: but fragmentation risk exists.",
            "Gap analyst: monitoring gap identified.",
            "Executive: recommend consolidation strategy.",
        ]

        async def mock_complete(system_prompt: str, user_prompt: str, max_tokens: int = 4096) -> LLMResponse:
            nonlocal call_count
            text = pass_texts[min(call_count, len(pass_texts) - 1)]
            call_count += 1
            return LLMResponse(
                text=text, input_tokens=800, output_tokens=300,
                model="claude-opus-4-20250514", stop_reason="end_turn",
            )

        client = AsyncMock()
        client.complete = mock_complete

        engine = SynthesisEngine(llm_client=client)
        chunks = manager.retrieve("CI/CD platform", n_results=10)
        result = await engine.synthesize(theme="Platform Consolidation", chunks=chunks, mode=SynthesisMode.DEEP)

        assert result.mode == SynthesisMode.DEEP
        assert len(result.passes) == 4
        assert result.passes[0].role == "strategist"
        assert result.passes[3].role == "executive_integrator"
        assert result.total_input_tokens == 3200
        assert result.total_output_tokens == 1200

    async def test_distill_compresses_synthesis(self, tmp_path: Path) -> None:
        synthesis = SynthesisResult(
            theme="Platform Consolidation",
            mode=SynthesisMode.SINGLE,
            content="Full analysis of platform consolidation trends across 50 competitors.",
            passes=[PassResult(role="analyst", content="Full analysis content.", input_tokens=800, output_tokens=400)],
            total_input_tokens=800,
            total_output_tokens=400,
        )

        client = _mock_llm_client(text="Executive summary: consolidation accelerating. Act now.\n")
        distiller = Distiller(llm_client=client)
        result = await distiller.distill(synthesis)

        assert result.theme == "Platform Consolidation"
        assert "consolidation accelerating" in result.content
        assert result.input_tokens > 0

    async def test_meta_synthesis_combines_distilled_themes(self, tmp_path: Path) -> None:
        distilled = [
            {"theme": "Platform Consolidation", "content": "Consolidation is accelerating."},
            {"theme": "Developer Experience", "content": "DX is the new battleground."},
            {"theme": "Pricing Race", "content": "Race to bottom on pricing."},
        ]

        client = _mock_llm_client(text="# Executive Summary\n\nThree converging trends shape the landscape.\n")
        synthesizer = MetaSynthesizer(llm_client=client)
        result = await synthesizer.synthesize(distilled)

        assert result.theme_count == 3
        assert "converging trends" in result.content
        assert result.input_tokens > 0

    async def test_full_delivery_chain(self, tmp_path: Path) -> None:
        """End-to-end: synthesize -> distill -> meta-synthesize."""
        ws, manager = _build_indexed_workspace(tmp_path)
        chunks = manager.retrieve("CI/CD", n_results=10)

        synth_client = _mock_llm_client(text="Theme analysis: CI/CD consolidation trend.\n")
        engine = SynthesisEngine(llm_client=synth_client)
        synthesis = await engine.synthesize(theme="CI/CD Consolidation", chunks=chunks)

        distill_client = _mock_llm_client(text="Distilled: consolidation is real.\n")
        distiller = Distiller(llm_client=distill_client)
        distilled = await distiller.distill(synthesis)

        meta_client = _mock_llm_client(text="Executive summary across all themes.\n")
        meta = MetaSynthesizer(llm_client=meta_client)
        summary = await meta.synthesize([{"theme": distilled.theme, "content": distilled.content}])

        assert summary.theme_count == 1
        assert summary.content


# ---------------------------------------------------------------------------
# 6. Incremental indexing
# ---------------------------------------------------------------------------


class TestIncrementalIndexingIntegration:
    async def test_unchanged_profiles_are_skipped(self, tmp_path: Path) -> None:
        ws = _create_workspace_via_wizard(tmp_path / "project")
        ws.create_profile("Alpha CI")
        _fill_profile_with_content(ws, "alpha-ci", "Alpha CI")

        manager = IndexManager(persist_dir=str(tmp_path / "vectors"))
        state = StateStore(db_path=ws.root / ".recon" / "state.db")
        await state.initialize()

        indexer = IncrementalIndexer(workspace=ws, index_manager=manager, state_store=state)

        first_run = await indexer.index()
        assert first_run.indexed == 1
        assert first_run.skipped == 0

        second_run = await indexer.index()
        assert second_run.indexed == 0
        assert second_run.skipped == 1

    async def test_modified_profiles_are_reindexed(self, tmp_path: Path) -> None:
        ws = _create_workspace_via_wizard(tmp_path / "project")
        ws.create_profile("Alpha CI")
        _fill_profile_with_content(ws, "alpha-ci", "Alpha CI")

        manager = IndexManager(persist_dir=str(tmp_path / "vectors2"))
        state = StateStore(db_path=ws.root / ".recon" / "state.db")
        await state.initialize()

        indexer = IncrementalIndexer(workspace=ws, index_manager=manager, state_store=state)
        await indexer.index()

        path = ws.competitors_dir / "alpha-ci.md"
        post = frontmatter.load(str(path))
        post.content += "\n\n## New Section\n\nAdditional content after update.\n"
        path.write_text(frontmatter.dumps(post))

        second_run = await indexer.index()
        assert second_run.indexed == 1
        assert second_run.skipped == 0

    async def test_new_profiles_added_incrementally(self, tmp_path: Path) -> None:
        ws = _create_workspace_via_wizard(tmp_path / "project")
        ws.create_profile("Alpha CI")
        _fill_profile_with_content(ws, "alpha-ci", "Alpha CI")

        manager = IndexManager(persist_dir=str(tmp_path / "vectors3"))
        state = StateStore(db_path=ws.root / ".recon" / "state.db")
        await state.initialize()

        indexer = IncrementalIndexer(workspace=ws, index_manager=manager, state_store=state)
        first_run = await indexer.index()
        assert first_run.indexed == 1

        ws.create_profile("Beta Pipeline")
        _fill_profile_with_content(ws, "beta-pipeline", "Beta Pipeline")

        second_run = await indexer.index()
        assert second_run.indexed == 1
        assert second_run.skipped == 1


# ---------------------------------------------------------------------------
# 7. Pipeline orchestration
# ---------------------------------------------------------------------------


class TestPipelineOrchestration:
    async def test_pipeline_runs_index_stage(self, tmp_path: Path) -> None:
        ws = _create_workspace_via_wizard(tmp_path / "project")
        ws.create_profile("Alpha CI")
        _fill_profile_with_content(ws, "alpha-ci", "Alpha CI")

        state = StateStore(db_path=ws.root / ".recon" / "state.db")
        await state.initialize()

        pipeline = Pipeline(
            workspace=ws,
            state_store=state,
            llm_client=_mock_llm_client(),
            config=PipelineConfig(
                start_from=PipelineStage.INDEX,
                stop_after=PipelineStage.INDEX,
                verification_enabled=False,
            ),
        )

        run_id = await pipeline.plan()
        await pipeline.execute(run_id)

        run = await state.get_run(run_id)
        assert run["status"] == RunStatus.COMPLETED.value

    async def test_pipeline_plan_summary(self, tmp_path: Path) -> None:
        ws = _create_workspace_via_wizard(tmp_path / "project")
        ws.create_profile("Alpha CI")
        ws.create_profile("Beta Pipeline")

        state = StateStore(db_path=ws.root / ".recon" / "state.db")
        await state.initialize()

        pipeline = Pipeline(
            workspace=ws,
            state_store=state,
            llm_client=_mock_llm_client(),
            config=PipelineConfig(
                start_from=PipelineStage.RESEARCH,
                stop_after=PipelineStage.INDEX,
            ),
        )

        run_id = await pipeline.plan()
        summary = await pipeline.get_plan_summary(run_id)

        assert summary["competitors"] == 2
        assert "research" in summary["stages"]
        assert "index" in summary["stages"]

    async def test_failed_pipeline_records_failure(self, tmp_path: Path) -> None:
        ws = _create_workspace_via_wizard(tmp_path / "project")
        ws.create_profile("Alpha CI")

        state = StateStore(db_path=ws.root / ".recon" / "state.db")
        await state.initialize()

        pipeline = Pipeline(
            workspace=ws,
            state_store=state,
            llm_client=_mock_llm_client(),
            config=PipelineConfig(
                start_from=PipelineStage.RESEARCH,
                stop_after=PipelineStage.RESEARCH,
            ),
        )

        run_id = await pipeline.plan()
        with (
            patch.object(pipeline, "_stage_research", side_effect=RuntimeError("API connection failed")),
            pytest.raises(RuntimeError),
        ):
            await pipeline.execute(run_id)

        run = await state.get_run(run_id)
        assert run["status"] == RunStatus.FAILED.value


# ---------------------------------------------------------------------------
# 8. State store integration
# ---------------------------------------------------------------------------


class TestStateStoreIntegration:
    async def test_full_state_lifecycle(self, tmp_path: Path) -> None:
        ws = _create_workspace_via_wizard(tmp_path / "project")
        state = StateStore(db_path=ws.root / ".recon" / "state.db")
        await state.initialize()

        run_id = await state.create_run(operation="research")
        task_id = await state.create_task(run_id=run_id, competitor_slug="alpha-ci", section_key="overview")

        await state.record_verification(
            task_id=task_id, competitor_slug="alpha-ci", section_key="overview",
            claim_text="Has 500+ integrations", agent="agent_b", status="confirmed",
            evidence_summary="Verified via official docs",
        )
        await state.record_cost(
            run_id=run_id, model="claude-sonnet-4-20250514",
            input_tokens=500, output_tokens=200, cost_usd=0.005,
        )

        run = await state.get_run(run_id)
        assert run["operation"] == "research"

        verifications = await state.get_verification_results(task_id=task_id)
        assert len(verifications) == 1

        total_cost = await state.get_run_total_cost(run_id)
        assert total_cost == pytest.approx(0.005)


# ---------------------------------------------------------------------------
# 9. Cost tracker integration
# ---------------------------------------------------------------------------


class TestCostTrackerIntegration:
    def test_cost_tracking_across_pipeline_stages(self) -> None:
        tracker = CostTracker(
            model_pricing=ModelPricing(
                model_id="claude-sonnet-4-20250514",
                input_price_per_million=3.0,
                output_price_per_million=15.0,
            ),
        )

        cost_1 = tracker.record_call(input_tokens=1000, output_tokens=500)
        cost_2 = tracker.record_call(input_tokens=2000, output_tokens=800)

        assert cost_1 > 0
        assert cost_2 > 0
        assert tracker.total_cost == pytest.approx(cost_1 + cost_2)
        assert tracker.total_input_tokens == 3000
        assert tracker.total_output_tokens == 1300


# ---------------------------------------------------------------------------
# 10. CLI end-to-end
# ---------------------------------------------------------------------------


class TestCLIEndToEnd:
    def test_init_add_index_status_flow(self, tmp_path: Path) -> None:
        import os

        from click.testing import CliRunner

        from recon.cli import main

        ws_dir = tmp_path / "e2e_project"
        runner = CliRunner()

        result = runner.invoke(
            main,
            ["init", str(ws_dir), "--wizard"],
            input="Acme Corp\nAcme CI\nCI/CD Tools\n6\nn\n\n\ny\n",
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        assert (ws_dir / "recon.yaml").exists()

        list_file = tmp_path / "competitors.txt"
        list_file.write_text("Alpha CI\nBeta Pipeline\nGamma Build\n")

        old_cwd = os.getcwd()
        os.chdir(ws_dir)
        try:
            result = runner.invoke(
                main,
                ["add", "--from-list", str(list_file)],
                catch_exceptions=False,
            )
            assert result.exit_code == 0
            assert (ws_dir / "competitors" / "alpha-ci.md").exists()
            assert (ws_dir / "competitors" / "beta-pipeline.md").exists()
            assert (ws_dir / "competitors" / "gamma-build.md").exists()

            for slug, name in [("alpha-ci", "Alpha CI"), ("beta-pipeline", "Beta Pipeline"), ("gamma-build", "Gamma Build")]:
                ws = Workspace.open(ws_dir)
                _fill_profile_with_content(ws, slug, name)

            result = runner.invoke(main, ["index"], catch_exceptions=False)
            assert result.exit_code == 0
            assert "Indexed" in result.output

            result = runner.invoke(main, ["status"], catch_exceptions=False)
            assert result.exit_code == 0
            assert "3" in result.output or "Profiles" in result.output

        finally:
            os.chdir(old_cwd)

    def test_research_dry_run(self, tmp_path: Path) -> None:
        import os

        from click.testing import CliRunner

        from recon.cli import main

        ws_dir = tmp_path / "e2e_dry"
        runner = CliRunner()
        runner.invoke(
            main,
            ["init", str(ws_dir), "--wizard"],
            input="Acme Corp\nAcme CI\nTools\n6\nn\n\n\ny\n",
            catch_exceptions=False,
        )

        old_cwd = os.getcwd()
        os.chdir(ws_dir)
        try:
            ws = Workspace.open(ws_dir)
            ws.create_profile("Alpha CI")

            result = runner.invoke(main, ["research", "--all", "--dry-run"], catch_exceptions=False)
            assert result.exit_code == 0
            assert "Plan" in result.output or "tasks" in result.output
        finally:
            os.chdir(old_cwd)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_chunks_with_embeddings(ws: Workspace) -> list[dict]:
    """Build chunks with deterministic embeddings for theme discovery."""
    all_chunks: list[dict] = []
    for profile_meta in ws.list_profiles():
        full = ws.read_profile(profile_meta["_slug"])
        if not full or not full.get("_content", "").strip():
            continue

        chunks = chunk_markdown(
            content=full["_content"],
            source_path=str(profile_meta["_path"]),
            frontmatter_meta={k: v for k, v in profile_meta.items() if not k.startswith("_")},
        )
        for chunk in chunks:
            rng = np.random.default_rng(hash(chunk.text) % (2**31))
            embedding = rng.random(64).tolist()
            all_chunks.append({
                "text": chunk.text,
                "embedding": embedding,
                "metadata": chunk.metadata,
            })

    return all_chunks
