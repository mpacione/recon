"""Integration tests for the recon pipeline.

Exercises the full workflow with mocked LLM responses: workspace init ->
add competitors -> research -> enrich -> index -> pipeline orchestration.
Tests that modules integrate correctly through their public APIs.
"""

from __future__ import annotations

from pathlib import Path  # noqa: TCH003 -- used at runtime
from unittest.mock import AsyncMock

import frontmatter
import pytest
import yaml

from recon.cost import CostTracker, ModelPricing
from recon.index import IndexManager, chunk_markdown
from recon.pipeline import Pipeline, PipelineConfig, PipelineStage
from recon.state import RunStatus, StateStore
from recon.wizard import DecisionContext, WizardState
from recon.workspace import Workspace


def _mock_llm_client() -> AsyncMock:
    client = AsyncMock()
    client.query = AsyncMock(return_value={
        "content": "## Overview\n\nAlpha is a CI/CD platform for modern teams.\n",
        "tokens": {"input": 500, "output": 200},
    })
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


class TestResearchToIndexIntegration:
    def test_researched_profiles_can_be_indexed(self, tmp_path: Path) -> None:
        ws = _create_workspace_via_wizard(tmp_path / "project")
        ws.create_profile("Alpha CI")
        ws.create_profile("Beta Pipeline")

        _fill_profile_with_content(ws, "alpha-ci", "Alpha CI")
        _fill_profile_with_content(ws, "beta-pipeline", "Beta Pipeline")

        manager = IndexManager()
        for profile_meta in ws.list_profiles():
            full = ws.read_profile(profile_meta["_slug"])
            chunks = chunk_markdown(
                content=full["_content"],
                source_path=str(profile_meta["_path"]),
                frontmatter_meta={k: v for k, v in profile_meta.items() if not k.startswith("_")},
            )
            manager.add_chunks(chunks)

        results = manager.retrieve("CI/CD capabilities", n_results=5)
        assert len(results) > 0

    def test_index_preserves_metadata(self, tmp_path: Path) -> None:
        ws = _create_workspace_via_wizard(tmp_path / "project")
        ws.create_profile("Alpha CI")
        _fill_profile_with_content(ws, "alpha-ci", "Alpha CI")

        manager = IndexManager(persist_dir=str(tmp_path / "vectors"))
        full = ws.read_profile("alpha-ci")
        chunks = chunk_markdown(
            content=full["_content"],
            source_path=str(ws.competitors_dir / "alpha-ci.md"),
            frontmatter_meta={"name": "Alpha CI", "type": "competitor"},
        )
        manager.add_chunks(chunks)

        results = manager.retrieve("capabilities", n_results=1)

        assert results[0]["metadata"]["name"] == "Alpha CI"


class TestStateStoreIntegration:
    async def test_pipeline_records_run_state(self, tmp_path: Path) -> None:
        ws = _create_workspace_via_wizard(tmp_path / "project")
        ws.create_profile("Alpha CI")
        _fill_profile_with_content(ws, "alpha-ci", "Alpha CI")

        state = StateStore(db_path=ws.root / ".recon" / "state.db")
        await state.initialize()

        run_id = await state.create_run(operation="research")
        task_id = await state.create_task(
            run_id=run_id,
            competitor_slug="alpha-ci",
            section_key="overview",
        )
        await state.record_verification(
            task_id=task_id,
            competitor_slug="alpha-ci",
            section_key="overview",
            claim_text="Alpha CI has 500+ integrations",
            agent="agent_b",
            status="confirmed",
            evidence_summary="Verified via official docs",
        )
        await state.record_cost(
            run_id=run_id,
            model="claude-sonnet-4-20250514",
            input_tokens=500,
            output_tokens=200,
            cost_usd=0.005,
        )

        run = await state.get_run(run_id)
        assert run is not None
        assert run["operation"] == "research"

        verifications = await state.get_verification_results(task_id=task_id)
        assert len(verifications) == 1

        total_cost = await state.get_run_total_cost(run_id)
        assert total_cost == pytest.approx(0.005)


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


class TestPipelineOrchestration:
    async def test_pipeline_runs_research_and_index_stages(self, tmp_path: Path) -> None:
        ws = _create_workspace_via_wizard(tmp_path / "project")
        ws.create_profile("Alpha CI")
        _fill_profile_with_content(ws, "alpha-ci", "Alpha CI")

        state = StateStore(db_path=ws.root / ".recon" / "state.db")
        await state.initialize()

        client = _mock_llm_client()

        pipeline = Pipeline(
            workspace=ws,
            state_store=state,
            llm_client=client,
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
        from unittest.mock import patch

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
        f"| Security scanning | 3/5 | Basic SAST, no DAST |\n"
    )
    post["research_status"] = "researched"
    path.write_text(frontmatter.dumps(post))
