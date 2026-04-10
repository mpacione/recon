"""Tests for the full pipeline orchestrator.

The pipeline orchestrator manages end-to-end runs: research -> verify ->
enrich -> index -> discover themes -> retrieve -> synthesize -> distill -> meta-synthesis.
It tracks state via the StateStore and supports incremental/resumable runs.
"""

from pathlib import Path
from unittest.mock import AsyncMock

from recon.llm import LLMResponse
from recon.pipeline import Pipeline, PipelineConfig, PipelineStage


def _make_response(text: str = "LLM output.\n\n## Sources\n- [S](https://s.com) -- 2026-01-01") -> LLMResponse:
    return LLMResponse(
        text=text, input_tokens=200, output_tokens=100,
        model="claude-sonnet-4-20250514", stop_reason="end_turn",
    )


def _mock_llm() -> AsyncMock:
    client = AsyncMock()
    client.complete = AsyncMock(return_value=_make_response())
    client.total_input_tokens = 0
    client.total_output_tokens = 0
    client.call_count = 0
    return client


class TestPipelineConfig:
    def test_default_config(self) -> None:
        config = PipelineConfig()

        assert config.max_research_workers == 5
        assert config.max_enrich_workers == 10
        assert config.deep_synthesis is False
        assert config.verification_enabled is True

    def test_custom_config(self) -> None:
        config = PipelineConfig(
            max_research_workers=3,
            deep_synthesis=True,
            start_from=PipelineStage.INDEX,
        )

        assert config.max_research_workers == 3
        assert config.deep_synthesis is True
        assert config.start_from == PipelineStage.INDEX


class TestPipelineStages:
    def test_stage_ordering(self) -> None:
        stages = list(PipelineStage)

        assert stages.index(PipelineStage.RESEARCH) < stages.index(PipelineStage.VERIFY)
        assert stages.index(PipelineStage.VERIFY) < stages.index(PipelineStage.ENRICH)
        assert stages.index(PipelineStage.ENRICH) < stages.index(PipelineStage.INDEX)
        assert stages.index(PipelineStage.INDEX) < stages.index(PipelineStage.SYNTHESIZE)
        assert stages.index(PipelineStage.SYNTHESIZE) < stages.index(PipelineStage.DELIVER)

    def test_all_stages_present(self) -> None:
        expected = {"research", "verify", "enrich", "index", "synthesize", "deliver"}
        actual = {s.value for s in PipelineStage}
        assert expected == actual


class TestPipeline:
    async def test_creates_run_in_state_store(self, tmp_workspace: Path) -> None:
        from recon.state import StateStore
        from recon.workspace import Workspace

        ws = Workspace.open(tmp_workspace)
        store = StateStore(tmp_workspace / ".recon" / "state.db")
        await store.initialize()

        pipeline = Pipeline(
            workspace=ws,
            state_store=store,
            llm_client=_mock_llm(),
        )

        run_id = await pipeline.plan()

        assert run_id is not None
        run = await store.get_run(run_id)
        assert run is not None
        assert run["operation"] == "full_pipeline"

    async def test_plan_returns_stage_summary(self, tmp_workspace: Path) -> None:
        from recon.state import StateStore
        from recon.workspace import Workspace

        ws = Workspace.open(tmp_workspace)
        ws.create_profile("Alpha")
        store = StateStore(tmp_workspace / ".recon" / "state.db")
        await store.initialize()

        pipeline = Pipeline(
            workspace=ws,
            state_store=store,
            llm_client=_mock_llm(),
        )

        run_id = await pipeline.plan()
        summary = await pipeline.get_plan_summary(run_id)

        assert "stages" in summary
        assert len(summary["stages"]) > 0

    async def test_execute_runs_research_stage(self, tmp_workspace: Path) -> None:
        from recon.state import StateStore
        from recon.workspace import Workspace

        ws = Workspace.open(tmp_workspace)
        ws.create_profile("Alpha")
        store = StateStore(tmp_workspace / ".recon" / "state.db")
        await store.initialize()

        llm = _mock_llm()

        pipeline = Pipeline(
            workspace=ws,
            state_store=store,
            llm_client=llm,
            config=PipelineConfig(
                verification_enabled=False,
                start_from=PipelineStage.RESEARCH,
                stop_after=PipelineStage.RESEARCH,
            ),
        )

        run_id = await pipeline.plan()
        await pipeline.execute(run_id)

        run = await store.get_run(run_id)
        assert run["status"] == "completed"

    async def test_targets_are_forwarded_to_research_stage(self, tmp_workspace: Path) -> None:
        from recon.state import StateStore
        from recon.workspace import Workspace

        ws = Workspace.open(tmp_workspace)
        ws.create_profile("Alpha")
        ws.create_profile("Beta")
        store = StateStore(tmp_workspace / ".recon" / "state.db")
        await store.initialize()

        llm = _mock_llm()

        pipeline = Pipeline(
            workspace=ws,
            state_store=store,
            llm_client=llm,
            config=PipelineConfig(
                verification_enabled=False,
                start_from=PipelineStage.RESEARCH,
                stop_after=PipelineStage.RESEARCH,
                targets=["Beta"],
            ),
        )

        run_id = await pipeline.plan()
        await pipeline.execute(run_id)

        alpha = ws.read_profile("alpha")
        beta = ws.read_profile("beta")
        assert alpha["research_status"] == "scaffold"
        assert beta["research_status"] == "researched"

    async def test_progress_callback_fires_for_each_stage(self, tmp_workspace: Path) -> None:
        from recon.state import StateStore
        from recon.workspace import Workspace

        ws = Workspace.open(tmp_workspace)
        ws.create_profile("Alpha")
        store = StateStore(tmp_workspace / ".recon" / "state.db")
        await store.initialize()

        events: list[tuple[str, str]] = []

        async def on_progress(stage: str, phase: str) -> None:
            events.append((stage, phase))

        pipeline = Pipeline(
            workspace=ws,
            state_store=store,
            llm_client=_mock_llm(),
            config=PipelineConfig(
                verification_enabled=False,
                start_from=PipelineStage.RESEARCH,
                stop_after=PipelineStage.ENRICH,
            ),
            progress_callback=on_progress,
        )

        run_id = await pipeline.plan()
        await pipeline.execute(run_id)

        stages_started = [stage for stage, phase in events if phase == "start"]
        stages_completed = [stage for stage, phase in events if phase == "complete"]
        assert "research" in stages_started
        assert "enrich" in stages_started
        assert "research" in stages_completed
        assert "enrich" in stages_completed

    async def test_tracks_run_cost(self, tmp_workspace: Path) -> None:
        from recon.state import StateStore
        from recon.workspace import Workspace

        ws = Workspace.open(tmp_workspace)
        ws.create_profile("Alpha")
        store = StateStore(tmp_workspace / ".recon" / "state.db")
        await store.initialize()

        pipeline = Pipeline(
            workspace=ws,
            state_store=store,
            llm_client=_mock_llm(),
            config=PipelineConfig(
                verification_enabled=False,
                start_from=PipelineStage.RESEARCH,
                stop_after=PipelineStage.RESEARCH,
            ),
        )

        run_id = await pipeline.plan()
        await pipeline.execute(run_id)

        total = await store.get_run_total_cost(run_id)
        assert total >= 0
