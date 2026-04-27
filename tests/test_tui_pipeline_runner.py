"""Tests for the TUI pipeline runner glue.

The runner bridges a RunPlannerScreen Operation to a pipeline_fn that
RunScreen.start_pipeline() can consume. It owns the Pipeline lifecycle:
opening workspace/state store, creating the LLMClient, configuring the
PipelineConfig based on the operation, and streaming progress updates
back into the RunScreen's reactive attributes.
"""

from __future__ import annotations

from pathlib import Path  # noqa: TCH003 -- used at runtime
from unittest.mock import patch

import yaml
from textual.app import App, ComposeResult

from recon.tui.pipeline_runner import (
    SUPPORTED_OPERATIONS,
    build_pipeline_fn,
    pipeline_config_for_operation,
)
from recon.tui.screens.planner import Operation
from recon.tui.screens.run import RunScreen

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


def _setup_workspace(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    (path / "competitors").mkdir(exist_ok=True)
    (path / ".recon").mkdir(exist_ok=True)
    (path / ".recon" / "logs").mkdir(exist_ok=True)
    (path / "recon.yaml").write_text(yaml.dump(MINIMAL_SCHEMA))
    return path


class _RunTestApp(App):
    CSS = "Screen { background: #000000; }"

    def compose(self) -> ComposeResult:
        yield RunScreen()


class TestPipelineConfigForOperation:
    def test_full_pipeline_runs_all_stages(self) -> None:
        from recon.pipeline import PipelineStage

        config = pipeline_config_for_operation(Operation.FULL_PIPELINE)
        assert config.start_from == PipelineStage.RESEARCH
        assert config.stop_after == PipelineStage.DELIVER

    def test_update_all_runs_research_stage(self) -> None:
        from recon.pipeline import PipelineStage

        config = pipeline_config_for_operation(Operation.UPDATE_ALL)
        assert config.start_from == PipelineStage.RESEARCH
        assert config.stop_after == PipelineStage.RESEARCH

    def test_unsupported_operation_raises(self) -> None:
        import pytest

        # ADD_NEW is the only operation that doesn't yet map to a
        # PipelineConfig (it needs a discovery round + selection flow
        # before any pipeline stage runs).
        with pytest.raises(NotImplementedError):
            pipeline_config_for_operation(Operation.ADD_NEW)

    def test_supported_operations_listed(self) -> None:
        assert Operation.FULL_PIPELINE in SUPPORTED_OPERATIONS
        assert Operation.UPDATE_ALL in SUPPORTED_OPERATIONS
        assert Operation.DIFF_ALL in SUPPORTED_OPERATIONS
        assert Operation.DIFF_SPECIFIC in SUPPORTED_OPERATIONS
        assert Operation.RERUN_FAILED in SUPPORTED_OPERATIONS

    def test_diff_all_sets_stale_only(self) -> None:
        config = pipeline_config_for_operation(Operation.DIFF_ALL)
        assert config.stale_only is True
        assert config.failed_only is False

    def test_diff_specific_sets_stale_only(self) -> None:
        config = pipeline_config_for_operation(Operation.DIFF_SPECIFIC)
        assert config.stale_only is True

    def test_rerun_failed_sets_failed_only(self) -> None:
        config = pipeline_config_for_operation(Operation.RERUN_FAILED)
        assert config.failed_only is True
        assert config.stale_only is False


class TestBuildPipelineFn:
    async def test_pipeline_fn_forwards_verification_mode_to_pipeline_config(
        self, tmp_path: Path, monkeypatch,
    ) -> None:
        ws_dir = _setup_workspace(tmp_path / "ws")
        from recon.workspace import Workspace

        Workspace.open(ws_dir).create_profile("Alpha")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")

        async def fake_execute(self, run_id: str) -> None:
            assert self.config.verification_enabled is True
            assert self.config.verification_tier == "deep"
            await self.progress_callback("research", "start")  # type: ignore[misc]

        with patch("recon.pipeline.Pipeline.execute", fake_execute):
            pipeline_fn = build_pipeline_fn(
                workspace_path=ws_dir,
                operation=Operation.FULL_PIPELINE,
                verification_mode="deep",
            )

            app = _RunTestApp()
            async with app.run_test(size=(120, 40)) as pilot:
                screen = app.query_one(RunScreen)
                screen.start_pipeline(pipeline_fn)
                await pilot.pause()
                await pilot.pause()

    async def test_pipeline_fn_updates_phase_and_progress(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        ws_dir = _setup_workspace(tmp_path / "ws")
        from recon.workspace import Workspace

        Workspace.open(ws_dir).create_profile("Alpha")

        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")

        # Stub Pipeline.execute so we don't actually hit the mock LLM chain
        async def fake_execute(self, run_id: str) -> None:
            assert self.progress_callback is not None
            await self.progress_callback("research", "start")
            await self.progress_callback("research", "complete")

        with patch("recon.pipeline.Pipeline.execute", fake_execute):
            pipeline_fn = build_pipeline_fn(
                workspace_path=ws_dir,
                operation=Operation.FULL_PIPELINE,
            )

            app = _RunTestApp()
            async with app.run_test(size=(120, 40)) as pilot:
                screen = app.query_one(RunScreen)
                screen.start_pipeline(pipeline_fn)
                await pilot.pause()
                await pilot.pause()
                await pilot.pause()

            assert screen.current_phase in ("research", "complete", "done")
            assert screen.progress >= 0.0

    async def test_pipeline_fn_without_api_key_notifies_and_exits(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        ws_dir = _setup_workspace(tmp_path / "ws")
        from recon.workspace import Workspace

        Workspace.open(ws_dir).create_profile("Alpha")

        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        pipeline_fn = build_pipeline_fn(
            workspace_path=ws_dir,
            operation=Operation.FULL_PIPELINE,
        )

        notifications: list[str] = []

        async def fake_notify(self, message: str, **kwargs) -> None:
            notifications.append(message)

        app = _RunTestApp()
        async with app.run_test(size=(120, 40)) as pilot:
            screen = app.query_one(RunScreen)
            with patch.object(type(app), "notify", lambda self, msg, **kw: notifications.append(msg)):
                screen.start_pipeline(pipeline_fn)
                await pilot.pause()
                await pilot.pause()

            assert any("API key" in m for m in notifications)
            assert screen.current_phase in ("error", "idle")

    async def test_pipeline_fn_unsupported_operation_notifies(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        ws_dir = _setup_workspace(tmp_path / "ws")
        from recon.workspace import Workspace

        Workspace.open(ws_dir).create_profile("Alpha")

        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")

        pipeline_fn = build_pipeline_fn(
            workspace_path=ws_dir,
            operation=Operation.ADD_NEW,
        )

        notifications: list[str] = []

        app = _RunTestApp()
        async with app.run_test(size=(120, 40)) as pilot:
            screen = app.query_one(RunScreen)
            with patch.object(
                type(app),
                "notify",
                lambda self, msg, **kw: notifications.append(msg),
            ):
                screen.start_pipeline(pipeline_fn)
                await pilot.pause()
                await pilot.pause()

            assert any("not implemented" in m.lower() or "not yet" in m.lower() for m in notifications)

    def test_collect_output_files_finds_theme_and_summary(
        self, tmp_path: Path
    ) -> None:
        from recon.tui.pipeline_runner import _collect_output_files

        ws_root = tmp_path / "ws"
        ws_root.mkdir()
        (ws_root / "executive_summary.md").write_text("# Summary")
        themes_dir = ws_root / "themes"
        themes_dir.mkdir()
        (themes_dir / "platform_consolidation.md").write_text("# Theme")
        (themes_dir / "open_source_moats.md").write_text("# Theme")
        distilled = themes_dir / "distilled"
        distilled.mkdir()
        (distilled / "platform_consolidation.md").write_text("# Distilled")

        files = _collect_output_files(ws_root)

        labels = [f["label"] for f in files]
        assert "Executive Summary" in labels
        assert any("Platform Consolidation" in l for l in labels)
        assert any("Open Source Moats" in l for l in labels)
        assert any("Distilled" in l for l in labels)

    def test_collect_output_files_empty_workspace(self, tmp_path: Path) -> None:
        from recon.tui.pipeline_runner import _collect_output_files

        ws_root = tmp_path / "empty"
        ws_root.mkdir()

        files = _collect_output_files(ws_root)

        assert files == []

    async def test_pipeline_fn_auto_accepts_themes_without_gate(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Themes auto-synthesize without a curation gate. The pipeline
        should run with theme_curation_callback=None so discovered themes
        flow directly to synthesis without pausing for user input."""
        ws_dir = _setup_workspace(tmp_path / "ws")
        from recon.workspace import Workspace

        Workspace.open(ws_dir).create_profile("Alpha")

        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")

        captured_callback: list = []

        async def fake_execute(self, run_id: str) -> None:
            captured_callback.append(self.theme_curation_callback)

        with patch("recon.pipeline.Pipeline.execute", fake_execute):
            pipeline_fn = build_pipeline_fn(
                workspace_path=ws_dir,
                operation=Operation.FULL_PIPELINE,
            )

            app = _RunTestApp()
            async with app.run_test(size=(120, 40)) as pilot:
                screen = app.query_one(RunScreen)
                screen.start_pipeline(pipeline_fn)
                await pilot.pause()
                await pilot.pause()

        assert len(captured_callback) == 1
        assert captured_callback[0] is None, (
            "Themes should auto-synthesize without a curation gate. "
            "The callback should be None so the pipeline keeps all themes."
        )

    async def test_pipeline_fn_calls_pipeline_execute_with_progress(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        ws_dir = _setup_workspace(tmp_path / "ws")
        from recon.workspace import Workspace

        Workspace.open(ws_dir).create_profile("Alpha")

        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")

        captured_callbacks: list = []

        async def fake_execute(self, run_id: str) -> None:
            captured_callbacks.append(self.progress_callback)
            if self.progress_callback is not None:
                await self.progress_callback("research", "start")
                await self.progress_callback("research", "complete")

        with patch("recon.pipeline.Pipeline.execute", fake_execute):
            pipeline_fn = build_pipeline_fn(
                workspace_path=ws_dir,
                operation=Operation.UPDATE_ALL,
            )

            app = _RunTestApp()
            async with app.run_test(size=(120, 40)) as pilot:
                screen = app.query_one(RunScreen)
                screen.start_pipeline(pipeline_fn)
                await pilot.pause()
                await pilot.pause()

        assert len(captured_callbacks) == 1
        assert captured_callbacks[0] is not None
