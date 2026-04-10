"""Full pipeline orchestrator for recon.

Manages end-to-end runs through all stages: research -> verify -> enrich ->
index -> synthesize -> deliver. Tracks state in SQLite, supports starting
from any stage and stopping after any stage.
"""

from __future__ import annotations

import contextlib
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from recon.cost import CostTracker, ModelPricing
from recon.enrichment import EnrichmentOrchestrator, EnrichmentPass
from recon.index import IndexManager, chunk_markdown
from recon.llm import LLMClient  # noqa: TCH001
from recon.research import ResearchOrchestrator
from recon.state import RunStatus, StateStore  # noqa: TCH001
from recon.workspace import Workspace  # noqa: TCH001

ProgressCallback = Callable[[str, str], Awaitable[None]]


class PipelineStage(StrEnum):
    RESEARCH = "research"
    VERIFY = "verify"
    ENRICH = "enrich"
    INDEX = "index"
    SYNTHESIZE = "synthesize"
    DELIVER = "deliver"


_STAGE_ORDER = list(PipelineStage)


@dataclass
class PipelineConfig:
    max_research_workers: int = 5
    max_enrich_workers: int = 10
    deep_synthesis: bool = False
    verification_enabled: bool = True
    start_from: PipelineStage = PipelineStage.RESEARCH
    stop_after: PipelineStage = PipelineStage.DELIVER
    targets: list[str] | None = None


@dataclass
class Pipeline:
    """Full pipeline orchestrator."""

    workspace: Workspace
    state_store: StateStore
    llm_client: LLMClient
    config: PipelineConfig = field(default_factory=PipelineConfig)
    progress_callback: ProgressCallback | None = None

    async def _emit(self, stage: str, phase: str) -> None:
        if self.progress_callback is None:
            return
        # Never let a broken progress callback take down the pipeline
        with contextlib.suppress(Exception):
            await self.progress_callback(stage, phase)

    async def plan(self) -> str:
        """Create a run plan and return the run_id."""
        run_id = await self.state_store.create_run(
            operation="full_pipeline",
            parameters={
                "start_from": self.config.start_from.value,
                "stop_after": self.config.stop_after.value,
                "deep_synthesis": self.config.deep_synthesis,
                "verification_enabled": self.config.verification_enabled,
            },
        )
        return run_id

    async def get_plan_summary(self, run_id: str) -> dict[str, Any]:
        """Get a summary of what the pipeline will do."""
        profiles = self.workspace.list_profiles()
        schema = self.workspace.schema
        section_count = len(schema.sections) if schema else 0

        start_idx = _STAGE_ORDER.index(self.config.start_from)
        stop_idx = _STAGE_ORDER.index(self.config.stop_after)
        active_stages = _STAGE_ORDER[start_idx : stop_idx + 1]

        return {
            "run_id": run_id,
            "competitors": len(profiles),
            "sections": section_count,
            "stages": [s.value for s in active_stages],
            "deep_synthesis": self.config.deep_synthesis,
            "verification_enabled": self.config.verification_enabled,
        }

    async def execute(self, run_id: str) -> None:
        """Execute the pipeline."""
        await self.state_store.update_run_status(run_id, RunStatus.RUNNING)

        cost_tracker = CostTracker(
            model_pricing=ModelPricing(
                model_id="claude-sonnet-4-20250514",
                input_price_per_million=3.0,
                output_price_per_million=15.0,
            ),
        )

        start_idx = _STAGE_ORDER.index(self.config.start_from)
        stop_idx = _STAGE_ORDER.index(self.config.stop_after)

        try:
            for stage in _STAGE_ORDER[start_idx : stop_idx + 1]:
                await self._emit(stage.value, "start")
                await self._execute_stage(run_id, stage, cost_tracker)
                await self._emit(stage.value, "complete")

            await self.state_store.update_run_status(run_id, RunStatus.COMPLETED)
        except Exception:
            await self.state_store.update_run_status(run_id, RunStatus.FAILED)
            raise

    async def _execute_stage(
        self,
        run_id: str,
        stage: PipelineStage,
        cost_tracker: CostTracker,
    ) -> None:
        """Execute a single pipeline stage."""
        if stage == PipelineStage.RESEARCH:
            await self._stage_research(run_id, cost_tracker)
        elif stage == PipelineStage.VERIFY:
            if self.config.verification_enabled:
                await self._stage_verify(run_id, cost_tracker)
        elif stage == PipelineStage.ENRICH:
            await self._stage_enrich(run_id, cost_tracker)
        elif stage == PipelineStage.INDEX:
            await self._stage_index(run_id)
        elif stage == PipelineStage.SYNTHESIZE or stage == PipelineStage.DELIVER:
            pass

    async def _stage_research(self, run_id: str, cost_tracker: CostTracker) -> None:
        """Execute the research stage."""
        orchestrator = ResearchOrchestrator(
            workspace=self.workspace,
            llm_client=self.llm_client,
            max_workers=self.config.max_research_workers,
        )

        results = await orchestrator.research_all(targets=self.config.targets)

        total_input = sum(r.get("tokens", {}).get("input", 0) for r in results)
        total_output = sum(r.get("tokens", {}).get("output", 0) for r in results)

        if total_input > 0 or total_output > 0:
            cost = cost_tracker.record_call(total_input, total_output)
            await self.state_store.record_cost(
                run_id=run_id,
                model="claude-sonnet-4-20250514",
                input_tokens=total_input,
                output_tokens=total_output,
                cost_usd=cost,
            )

    async def _stage_verify(self, run_id: str, cost_tracker: CostTracker) -> None:
        """Execute the verification stage."""

    async def _stage_enrich(self, run_id: str, cost_tracker: CostTracker) -> None:
        """Execute all enrichment passes."""
        for enrichment_pass in EnrichmentPass:
            orchestrator = EnrichmentOrchestrator(
                workspace=self.workspace,
                llm_client=self.llm_client,
                enrichment_pass=enrichment_pass,
                max_workers=self.config.max_enrich_workers,
            )
            results = await orchestrator.enrich_all(targets=self.config.targets)

            total_input = sum(r.get("tokens", {}).get("input", 0) for r in results)
            total_output = sum(r.get("tokens", {}).get("output", 0) for r in results)

            if total_input > 0 or total_output > 0:
                cost = cost_tracker.record_call(total_input, total_output)
                await self.state_store.record_cost(
                    run_id=run_id,
                    model="claude-sonnet-4-20250514",
                    input_tokens=total_input,
                    output_tokens=total_output,
                    cost_usd=cost,
                )

    async def _stage_index(self, run_id: str) -> None:
        """Execute the indexing stage."""
        manager = IndexManager(persist_dir=str(self.workspace.root / ".vectordb"))

        profiles = self.workspace.list_profiles()
        for profile_meta in profiles:
            full = self.workspace.read_profile(profile_meta["_slug"])
            if not full or not full.get("_content", "").strip():
                continue

            chunks = chunk_markdown(
                content=full["_content"],
                source_path=str(profile_meta["_path"]),
                frontmatter_meta={k: v for k, v in profile_meta.items() if not k.startswith("_")},
            )
            manager.add_chunks(chunks)
