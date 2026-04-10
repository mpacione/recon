"""Pipeline runner glue for the recon TUI.

Bridges a RunPlannerScreen :class:`Operation` to a pipeline_fn that
:meth:`RunScreen.start_pipeline` can consume. This is where the TUI
finally talks to the real engine pipeline.

Supported operations:
- ``FULL_PIPELINE`` -- research → deliver
- ``UPDATE_ALL`` -- research every section
- ``UPDATE_SPECIFIC`` -- research only selected competitors (requires
  a :class:`CompetitorSelectorScreen` push first)
- ``DIFF_ALL`` -- re-research sections older than the staleness window
- ``DIFF_SPECIFIC`` -- same, scoped to selected competitors
- ``RERUN_FAILED`` -- only re-research sections marked ``failed`` or
  never successfully researched
"""

from __future__ import annotations

import contextlib
import os
from collections.abc import Callable, Coroutine
from pathlib import Path  # noqa: TCH003 -- used at runtime
from typing import TYPE_CHECKING, Any

from recon.logging import get_logger
from recon.pipeline import PipelineConfig, PipelineStage
from recon.tui.screens.planner import Operation

if TYPE_CHECKING:
    from recon.tui.screens.run import RunScreen

_log = get_logger(__name__)

PipelineFn = Callable[["RunScreen"], Coroutine[Any, Any, None]]


SUPPORTED_OPERATIONS: set[Operation] = {
    Operation.FULL_PIPELINE,
    Operation.UPDATE_ALL,
    Operation.UPDATE_SPECIFIC,
    Operation.DIFF_ALL,
    Operation.DIFF_SPECIFIC,
    Operation.RERUN_FAILED,
}

OPERATIONS_REQUIRING_SELECTION: set[Operation] = {
    Operation.UPDATE_SPECIFIC,
    Operation.DIFF_SPECIFIC,
}


_STAGE_PROGRESS: dict[str, float] = {
    "research": 0.15,
    "verify": 0.3,
    "enrich": 0.45,
    "index": 0.55,
    "themes": 0.65,
    "synthesize": 0.85,
    "deliver": 0.95,
}


def pipeline_config_for_operation(operation: Operation) -> PipelineConfig:
    """Map a planner Operation to a PipelineConfig.

    Raises NotImplementedError for operations that don't yet have a
    pipeline shape.
    """
    if operation == Operation.FULL_PIPELINE:
        return PipelineConfig(
            start_from=PipelineStage.RESEARCH,
            stop_after=PipelineStage.DELIVER,
            verification_enabled=False,
        )
    if operation in (Operation.UPDATE_ALL, Operation.UPDATE_SPECIFIC):
        return PipelineConfig(
            start_from=PipelineStage.RESEARCH,
            stop_after=PipelineStage.RESEARCH,
            verification_enabled=False,
        )
    if operation in (Operation.DIFF_ALL, Operation.DIFF_SPECIFIC):
        return PipelineConfig(
            start_from=PipelineStage.RESEARCH,
            stop_after=PipelineStage.RESEARCH,
            verification_enabled=False,
            stale_only=True,
        )
    if operation == Operation.RERUN_FAILED:
        return PipelineConfig(
            start_from=PipelineStage.RESEARCH,
            stop_after=PipelineStage.RESEARCH,
            verification_enabled=False,
            failed_only=True,
        )
    msg = f"Operation not yet implemented: {operation.value}"
    raise NotImplementedError(msg)


def _load_api_key_from_workspace(workspace_path: Path) -> str | None:
    env_path = workspace_path / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("ANTHROPIC_API_KEY="):
                return line.split("=", 1)[1].strip()
    return os.environ.get("ANTHROPIC_API_KEY")


def build_pipeline_fn(
    *,
    workspace_path: Path,
    operation: Operation,
    targets: list[str] | None = None,
) -> PipelineFn:
    """Create a pipeline_fn bound to a workspace + operation.

    The returned function is what RunScreen.start_pipeline() expects:
    an async callable that takes a RunScreen and returns None. It owns
    the Pipeline lifecycle, pushes progress updates into the screen's
    reactive attributes, and notifies on errors.

    ``targets`` is used for operations that narrow the pipeline to
    specific competitors (e.g. UPDATE_SPECIFIC).
    """

    async def pipeline_fn(screen: RunScreen) -> None:  # pragma: no branch -- closure
        try:
            if operation not in SUPPORTED_OPERATIONS:
                screen.current_phase = "error"
                screen.app.notify(
                    f"Operation not yet implemented: {operation.value}",
                    title="Run",
                    severity="warning",
                )
                _log.warning("pipeline_fn: unsupported operation %s", operation.value)
                return

            api_key = _load_api_key_from_workspace(workspace_path)
            if not api_key:
                screen.current_phase = "error"
                screen.app.notify(
                    "No API key configured. Add ANTHROPIC_API_KEY to .env.",
                    title="Run",
                    severity="error",
                )
                _log.warning("pipeline_fn: no API key for workspace %s", workspace_path)
                return

            os.environ["ANTHROPIC_API_KEY"] = api_key

            # Defer heavy imports until we're actually going to run the pipeline
            from recon.client_factory import ClientCreationError, create_llm_client
            from recon.pipeline import Pipeline
            from recon.state import StateStore
            from recon.workspace import Workspace

            try:
                client = create_llm_client(model="claude-sonnet-4-5")
            except ClientCreationError as exc:
                screen.current_phase = "error"
                screen.app.notify(
                    f"Could not create LLM client: {exc}",
                    title="Run",
                    severity="error",
                )
                _log.warning("pipeline_fn: client creation failed: %s", exc)
                return

            ws = Workspace.open(workspace_path)
            store = StateStore(db_path=workspace_path / ".recon" / "state.db")
            await store.initialize()

            config = pipeline_config_for_operation(operation)
            if targets is not None:
                from dataclasses import replace

                config = replace(config, targets=list(targets))

            async def on_progress(stage: str, phase: str) -> None:
                screen.current_phase = f"{stage} {phase}" if phase != "start" else stage
                screen.add_activity(f"{stage}: {phase}")
                if phase == "start":
                    progress = _STAGE_PROGRESS.get(stage, 0.0)
                    if progress > screen.progress:
                        screen.progress = progress

            async def curate_themes(themes: list) -> list:
                """Push ThemeCurationScreen as a gate and return the user's choices."""
                from recon.themes import DiscoveredTheme
                from recon.tui.models.curation import ThemeCurationModel
                from recon.tui.screens.curation import ThemeCurationScreen

                if not themes:
                    return []
                try:
                    model = ThemeCurationModel.from_themes(themes)
                    curated = await screen.app.push_screen_wait(
                        ThemeCurationScreen(model=model),
                    )
                except Exception:  # noqa: BLE001 -- fall back to auto-accept on any error
                    _log.exception("theme curation gate failed; keeping all themes")
                    return themes
                if not isinstance(curated, list):
                    return themes
                # Re-attach full DiscoveredTheme objects when the curation
                # screen returned labels or partial objects
                if curated and isinstance(curated[0], DiscoveredTheme):
                    return curated
                kept_labels = {
                    c.label if hasattr(c, "label") else str(c) for c in curated
                }
                return [t for t in themes if t.label in kept_labels]

            pipeline = Pipeline(
                workspace=ws,
                state_store=store,
                llm_client=client,
                config=config,
                progress_callback=on_progress,
                theme_curation_callback=curate_themes,
            )

            screen.current_phase = "planning"
            screen.add_activity("Planning run...")
            run_id = await pipeline.plan()

            screen.add_activity(f"Run {run_id} started")
            await pipeline.execute(run_id)

            screen.current_phase = "done"
            screen.progress = 1.0
            screen.add_activity("Pipeline complete")

            total_cost = await store.get_run_total_cost(run_id)
            screen.cost_usd = float(total_cost)
        except Exception as exc:  # noqa: BLE001 -- surface any pipeline failure to the user
            _log.exception("pipeline_fn failed")
            screen.current_phase = "error"
            with contextlib.suppress(Exception):
                screen.app.notify(
                    f"Pipeline failed: {exc}",
                    title="Run",
                    severity="error",
                )

    return pipeline_fn
