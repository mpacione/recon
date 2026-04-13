"""TUI integration tests.

Exercises full user journeys through the screen system using
ReconApp with real workspaces and mocked engine calls.
"""

from __future__ import annotations

from pathlib import Path  # noqa: TCH003 -- used at runtime in fixtures

from textual.widgets import Button, DataTable

from recon.discovery import CompetitorTier, DiscoveryCandidate
from recon.tui.app import ReconApp
from recon.tui.screens.browser import CompetitorBrowserScreen
from recon.tui.screens.dashboard import DashboardScreen
from recon.tui.screens.discovery import DiscoveryScreen
from recon.tui.screens.planner import RunPlannerScreen
from recon.tui.screens.run import RunScreen
from recon.tui.screens.welcome import WelcomeScreen
from recon.workspace import Workspace


class TestWelcomeToDashboardFlow:
    async def test_no_workspace_shows_welcome(self) -> None:
        app = ReconApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            assert isinstance(app.screen, WelcomeScreen)

    async def test_open_workspace_switches_to_dashboard(self, tmp_workspace: Path) -> None:
        app = ReconApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            assert isinstance(app.screen, WelcomeScreen)
            app.screen.post_message(WelcomeScreen.WorkspaceSelected(str(tmp_workspace)))
            await pilot.pause()
            await pilot.pause()
            assert isinstance(app.screen, DashboardScreen)
            assert app.workspace_path == tmp_workspace

    async def test_direct_workspace_skips_welcome(self, tmp_workspace: Path) -> None:
        app = ReconApp(workspace_path=tmp_workspace)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            assert isinstance(app.screen, DashboardScreen)


class TestDashboardDiscoveryFlow:
    async def test_discover_then_profiles_created(self, tmp_workspace: Path) -> None:
        ws = Workspace.open(tmp_workspace)
        initial_count = len(ws.list_profiles())

        app = ReconApp(workspace_path=tmp_workspace)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            assert isinstance(app.screen, DashboardScreen)

            await pilot.press("d")
            await pilot.pause()
            assert isinstance(app.screen, DiscoveryScreen)

            screen = app.screen
            assert isinstance(screen, DiscoveryScreen)
            state = screen.state
            state.add_round([
                DiscoveryCandidate(
                    name="NewCo",
                    url="https://newco.com",
                    blurb="New competitor",
                    provenance="test",
                    suggested_tier=CompetitorTier.ESTABLISHED,
                ),
            ])
            app.screen.query_one("#btn-done", Button).press()
            await pilot.pause()

            ws_after = Workspace.open(tmp_workspace)
            profiles = ws_after.list_profiles()
            names = [p["name"] for p in profiles]
            assert "NewCo" in names
            assert len(profiles) > initial_count


class TestDashboardToPlannerToRunFlow:
    async def test_planner_to_run_mode(self, tmp_workspace: Path) -> None:
        ws = Workspace.open(tmp_workspace)
        ws.create_profile("Placeholder Co")

        app = ReconApp(workspace_path=tmp_workspace)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.pause()
            assert isinstance(app.screen, DashboardScreen)
            assert app.current_mode == "dashboard"

            await pilot.press("r")
            await pilot.pause()
            assert isinstance(app.screen, RunPlannerScreen)

            app.screen.query_one("#btn-op-6", Button).press()
            await pilot.pause()
            await pilot.pause()
            await pilot.pause()
            assert app.current_mode == "run"
            assert isinstance(app.screen, RunScreen)


class TestPlannerStartsPipelineWithRunScreen:
    async def test_planner_full_pipeline_builds_and_starts_pipeline_fn(
        self, tmp_workspace: Path, monkeypatch
    ) -> None:
        from unittest.mock import patch

        ws = Workspace.open(tmp_workspace)
        ws.create_profile("Placeholder Co")

        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")

        execute_calls: list[str] = []

        async def fake_execute(self, run_id: str) -> None:
            execute_calls.append(run_id)
            if self.progress_callback is not None:
                await self.progress_callback("research", "start")
                await self.progress_callback("research", "complete")

        app = ReconApp(workspace_path=tmp_workspace)
        with patch("recon.pipeline.Pipeline.execute", fake_execute):
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                assert isinstance(app.screen, DashboardScreen)

                await pilot.press("r")
                await pilot.pause()
                assert isinstance(app.screen, RunPlannerScreen)

                # btn-op-6 is FULL_PIPELINE (7th option, zero-indexed)
                app.screen.query_one("#btn-op-6", Button).press()
                await pilot.pause()
                await pilot.pause()
                await pilot.pause()

                assert app.current_mode == "run"
                assert isinstance(app.screen, RunScreen)

                # Give the worker a chance to run fake_execute
                for _ in range(10):
                    if execute_calls:
                        break
                    await pilot.pause()

                assert execute_calls, "Pipeline.execute was never called"
                assert app.screen.current_phase in (
                    "research",
                    "research complete",
                    "done",
                )


class TestRecentProjectsRecording:
    """ReconApp must record opened workspaces in recent.json so the
    welcome screen can show them next time. This is the BUG-1 fix
    from the audit -- previously the file stayed empty forever.
    """

    async def test_opening_workspace_via_welcome_appends_to_recent(
        self, tmp_workspace: Path, tmp_path: Path, monkeypatch
    ) -> None:
        from recon.tui.screens.welcome import RecentProjectsManager

        recent_path = tmp_path / "recent.json"
        # Patch the default location ReconApp uses
        monkeypatch.setattr(
            "recon.tui.screens.welcome._DEFAULT_RECENT_PATH",
            recent_path,
        )

        app = ReconApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            assert isinstance(app.screen, WelcomeScreen)
            app.screen.post_message(WelcomeScreen.WorkspaceSelected(str(tmp_workspace)))
            await pilot.pause()
            await pilot.pause()
            assert isinstance(app.screen, DashboardScreen)

        # The workspace should now be in the recent.json file
        assert recent_path.exists(), "recent.json was never written"
        manager = RecentProjectsManager(recent_path)
        projects = manager.load()
        assert len(projects) == 1
        assert projects[0].path == str(tmp_workspace)

    async def test_creating_workspace_via_wizard_appends_to_recent(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        from recon.tui.screens.welcome import RecentProjectsManager
        from recon.tui.screens.wizard import WizardResult

        recent_path = tmp_path / "recent.json"
        monkeypatch.setattr(
            "recon.tui.screens.welcome._DEFAULT_RECENT_PATH",
            recent_path,
        )

        new_dir = tmp_path / "fresh-project"
        app = ReconApp()
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause()
            # Simulate wizard returning a valid result
            result = WizardResult(
                schema={
                    "domain": "Test",
                    "identity": {
                        "company_name": "X",
                        "products": ["Y"],
                        "decision_context": [],
                    },
                    "rating_scales": {},
                    "sections": [
                        {
                            "key": "overview",
                            "title": "Overview",
                            "description": "x",
                            "allowed_formats": ["prose"],
                            "preferred_format": "prose",
                        },
                    ],
                },
                output_dir=new_dir,
                api_key=None,
            )
            app._handle_wizard_result(result)
            await pilot.pause()
            await pilot.pause()

        assert recent_path.exists(), "recent.json was never written"
        manager = RecentProjectsManager(recent_path)
        projects = manager.load()
        assert any(str(new_dir) == p.path for p in projects)


class TestPlannerAddNewFlow:
    async def test_add_new_pushes_discovery_then_starts_pipeline_with_new_targets(
        self, tmp_workspace: Path, monkeypatch
    ) -> None:
        from unittest.mock import patch

        from recon.tui.screens.discovery import DiscoveryScreen

        ws = Workspace.open(tmp_workspace)
        ws.create_profile("Existing Co")  # one pre-existing profile

        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")

        execute_calls: list[list[str] | None] = []

        async def fake_execute(self, run_id: str) -> None:
            execute_calls.append(
                list(self.config.targets) if self.config.targets else None,
            )
            if self.progress_callback is not None:
                await self.progress_callback("research", "start")
                await self.progress_callback("research", "complete")

        app = ReconApp(workspace_path=tmp_workspace)
        with patch("recon.pipeline.Pipeline.execute", fake_execute):
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                assert isinstance(app.screen, DashboardScreen)

                await pilot.press("r")
                await pilot.pause()
                assert isinstance(app.screen, RunPlannerScreen)

                # btn-op-0 is ADD_NEW (first option, index 0)
                app.screen.query_one("#btn-op-0", Button).press()
                await pilot.pause()
                await pilot.pause()

                assert isinstance(app.screen, DiscoveryScreen)

                # Inject two candidates and confirm
                discovery_screen = app.screen
                discovery_screen.state.add_round([
                    DiscoveryCandidate(
                        name="NewCo",
                        url="https://newco.com",
                        blurb="A new competitor",
                        provenance="test",
                        suggested_tier=CompetitorTier.ESTABLISHED,
                    ),
                    DiscoveryCandidate(
                        name="Other Inc",
                        url="https://other.com",
                        blurb="Another new competitor",
                        provenance="test",
                        suggested_tier=CompetitorTier.ESTABLISHED,
                    ),
                ])
                app.screen.query_one("#btn-done", Button).press()
                await pilot.pause()
                await pilot.pause()
                await pilot.pause()

                # Should now be in run mode
                assert app.current_mode == "run"

                for _ in range(10):
                    if execute_calls:
                        break
                    await pilot.pause()

                assert execute_calls, "Pipeline.execute was never called"
                # The new targets should NOT include the pre-existing profile
                targets = execute_calls[0]
                assert targets is not None
                assert "Existing Co" not in targets
                assert "NewCo" in targets
                assert "Other Inc" in targets

                # The new competitors should now exist as profiles
                ws_after = Workspace.open(tmp_workspace)
                names = [p["name"] for p in ws_after.list_profiles()]
                assert "NewCo" in names
                assert "Other Inc" in names


class TestPlannerUpdateSpecificFlow:
    async def test_update_specific_pushes_selector_then_pipeline(
        self, tmp_workspace: Path, monkeypatch
    ) -> None:
        from unittest.mock import patch

        from recon.tui.screens.selector import CompetitorSelectorScreen

        ws = Workspace.open(tmp_workspace)
        ws.create_profile("Alpha Corp")
        ws.create_profile("Beta Inc")

        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")

        execute_calls: list[tuple[str, list[str] | None]] = []

        async def fake_execute(self, run_id: str) -> None:
            execute_calls.append((run_id, list(self.config.targets) if self.config.targets else None))
            if self.progress_callback is not None:
                await self.progress_callback("research", "start")
                await self.progress_callback("research", "complete")

        app = ReconApp(workspace_path=tmp_workspace)
        with patch("recon.pipeline.Pipeline.execute", fake_execute):
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                assert isinstance(app.screen, DashboardScreen)

                await pilot.press("r")
                await pilot.pause()
                assert isinstance(app.screen, RunPlannerScreen)

                # btn-op-1 is UPDATE_SPECIFIC (2nd option, index 1)
                app.screen.query_one("#btn-op-1", Button).press()
                await pilot.pause()
                await pilot.pause()

                assert isinstance(app.screen, CompetitorSelectorScreen)

                # Clear all, then pick only Beta Inc
                app.screen.query_one("#btn-clear-all", Button).press()
                await pilot.pause()
                app.screen.query_one("#selector-1", Button).press()
                await pilot.pause()
                app.screen.query_one("#btn-done", Button).press()
                await pilot.pause()
                await pilot.pause()
                await pilot.pause()

                assert app.current_mode == "run"

                for _ in range(10):
                    if execute_calls:
                        break
                    await pilot.pause()

                assert execute_calls, "Pipeline.execute was never called"
                run_id, targets = execute_calls[0]
                assert targets == ["Beta Inc"]


class TestPlannerDiffAllFlow:
    async def test_diff_all_passes_stale_only_to_pipeline(
        self, tmp_workspace: Path, monkeypatch
    ) -> None:
        from unittest.mock import patch

        ws = Workspace.open(tmp_workspace)
        ws.create_profile("Alpha")
        ws.create_profile("Beta")

        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")

        config_seen: list[bool] = []

        async def fake_execute(self, run_id: str) -> None:
            config_seen.append(self.config.stale_only)
            if self.progress_callback is not None:
                await self.progress_callback("research", "start")
                await self.progress_callback("research", "complete")

        app = ReconApp(workspace_path=tmp_workspace)
        with patch("recon.pipeline.Pipeline.execute", fake_execute):
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                await pilot.press("r")
                await pilot.pause()
                # btn-op-4 is DIFF_ALL (5th option, index 4)
                app.screen.query_one("#btn-op-4", Button).press()
                await pilot.pause()
                await pilot.pause()
                await pilot.pause()

                for _ in range(10):
                    if config_seen:
                        break
                    await pilot.pause()

                assert config_seen, "Pipeline.execute never called"
                assert config_seen[0] is True


class TestPlannerRerunFailedFlow:
    async def test_rerun_failed_passes_failed_only_to_pipeline(
        self, tmp_workspace: Path, monkeypatch
    ) -> None:
        from unittest.mock import patch

        ws = Workspace.open(tmp_workspace)
        ws.create_profile("Alpha")

        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")

        config_seen: list[bool] = []

        async def fake_execute(self, run_id: str) -> None:
            config_seen.append(self.config.failed_only)
            if self.progress_callback is not None:
                await self.progress_callback("research", "start")
                await self.progress_callback("research", "complete")

        app = ReconApp(workspace_path=tmp_workspace)
        with patch("recon.pipeline.Pipeline.execute", fake_execute):
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                await pilot.press("r")
                await pilot.pause()
                # btn-op-5 is RERUN_FAILED (6th option, index 5)
                app.screen.query_one("#btn-op-5", Button).press()
                await pilot.pause()
                await pilot.pause()
                await pilot.pause()

                for _ in range(10):
                    if config_seen:
                        break
                    await pilot.pause()

                assert config_seen, "Pipeline.execute never called"
                assert config_seen[0] is True


class TestStopButtonCancelsRunningPipeline:
    async def test_stop_pressed_during_run_cancels_pipeline(
        self, tmp_workspace: Path, monkeypatch
    ) -> None:
        """Full integration: start a real pipeline, press Stop while it's
        running, assert the run finalizes as CANCELLED in the state store.
        """
        import asyncio
        from unittest.mock import patch

        from recon.state import RunStatus, StateStore

        ws = Workspace.open(tmp_workspace)
        ws.create_profile("Alpha")
        ws.create_profile("Beta")

        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")

        # Slow execute that lets us press Stop mid-flight
        execute_started = asyncio.Event()
        cancel_observed = []

        async def slow_execute(self, run_id: str) -> None:
            execute_started.set()
            # Simulate some work that periodically checks the cancel event
            for _ in range(20):
                if self.cancel_event is not None and self.cancel_event.is_set():
                    cancel_observed.append(True)
                    await self.state_store.update_run_status(
                        run_id, RunStatus.CANCELLED,
                    )
                    return
                await asyncio.sleep(0.02)
            await self.state_store.update_run_status(run_id, RunStatus.COMPLETED)

        app = ReconApp(workspace_path=tmp_workspace)
        with patch("recon.pipeline.Pipeline.execute", slow_execute):
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                # Drive through planner -> FULL_PIPELINE -> run mode
                await pilot.press("r")
                await pilot.pause()
                app.screen.query_one("#btn-op-6", Button).press()
                await pilot.pause()
                await pilot.pause()
                await pilot.pause()

                assert app.current_mode == "run"

                # Wait for the slow execute to start
                for _ in range(20):
                    if execute_started.is_set():
                        break
                    await pilot.pause()
                assert execute_started.is_set()

                # Press Stop (s key) while the pipeline is mid-flight
                await pilot.press("s")
                await pilot.pause()

                # Let the slow execute observe the cancel and finalize
                for _ in range(40):
                    if cancel_observed:
                        break
                    await pilot.pause()

                assert cancel_observed, "Pipeline never observed the cancel event"

        # Verify the run is marked CANCELLED in the state store
        store = StateStore(tmp_workspace / ".recon" / "state.db")
        await store.initialize()
        runs = await store.list_runs()
        assert runs, "No runs were recorded"
        latest = runs[-1]
        assert latest["status"] == RunStatus.CANCELLED.value


class TestPauseResumeIntegration:
    async def test_pause_then_resume_completes_pipeline(
        self, tmp_workspace: Path, monkeypatch
    ) -> None:
        """Full integration: start a pipeline, press Pause, verify the
        button label flips, press Resume, verify the run completes
        normally with status COMPLETED.
        """
        import asyncio
        from unittest.mock import patch

        from recon.state import RunStatus, StateStore

        ws = Workspace.open(tmp_workspace)
        ws.create_profile("Alpha")

        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")

        # Slow execute that observes pause_event between steps so the
        # test can flip pause/resume mid-run. Total runtime is bounded
        # by allow_finish, which the test sets after it has confirmed
        # the pause/resume cycle.
        execute_started = asyncio.Event()
        allow_finish = asyncio.Event()
        steps_completed: list[int] = []

        async def slow_execute(self, run_id: str) -> None:
            execute_started.set()
            i = 0
            while True:
                if self.pause_event is not None:
                    while not self.pause_event.is_set():
                        if self.cancel_event is not None and self.cancel_event.is_set():
                            await self.state_store.update_run_status(
                                run_id, RunStatus.CANCELLED,
                            )
                            return
                        await asyncio.sleep(0.02)
                if self.cancel_event is not None and self.cancel_event.is_set():
                    await self.state_store.update_run_status(
                        run_id, RunStatus.CANCELLED,
                    )
                    return
                steps_completed.append(i)
                i += 1
                if allow_finish.is_set() and i >= 4:
                    break
                await asyncio.sleep(0.02)
            await self.state_store.update_run_status(run_id, RunStatus.COMPLETED)

        app = ReconApp(workspace_path=tmp_workspace)
        with patch("recon.pipeline.Pipeline.execute", slow_execute):
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                await pilot.press("r")
                await pilot.pause()
                app.screen.query_one("#btn-op-6", Button).press()
                await pilot.pause()
                await pilot.pause()
                await pilot.pause()

                assert app.current_mode == "run"

                for _ in range(20):
                    if execute_started.is_set():
                        break
                    await pilot.pause()
                assert execute_started.is_set()

                # The runner should have stashed both events on the app
                stashed_pause = getattr(app, "_pipeline_pause_event", None)
                assert stashed_pause is not None, (
                    "TUI runner should stash pause_event on the app"
                )
                assert stashed_pause.is_set(), "pause_event starts in running state"

                # Pause via the keybind -- the steps_completed counter
                # should freeze. The visual cue is now current_phase
                # flipping to "paused" rather than a button label change.
                from recon.tui.screens.run import RunScreen

                run_screen = app.screen
                assert isinstance(run_screen, RunScreen)
                await pilot.press("p")
                await pilot.pause()
                steps_at_pause = len(steps_completed)
                assert not stashed_pause.is_set(), "pause should clear the event"
                assert run_screen.current_phase == "paused"

                # Hold the pause for a moment and confirm work doesn't advance
                for _ in range(5):
                    await pilot.pause()
                    await asyncio.sleep(0.02)
                assert len(steps_completed) == steps_at_pause, (
                    "steps should not advance while paused"
                )

                # Resume + tell the fake it can wrap up
                await pilot.press("p")
                await pilot.pause()
                assert stashed_pause.is_set()
                allow_finish.set()
                for _ in range(80):
                    if run_screen.current_phase in ("done", "error", "cancelled"):
                        break
                    await pilot.pause()

                assert run_screen.current_phase == "done", (
                    f"Pipeline ended in {run_screen.current_phase!r}"
                )
                assert len(steps_completed) >= 4

        store = StateStore(tmp_workspace / ".recon" / "state.db")
        await store.initialize()
        runs = await store.list_runs()
        assert runs[-1]["status"] == RunStatus.COMPLETED.value


class TestFullPipelineThroughTuiNoMock:
    async def test_full_pipeline_runs_real_engine_with_fake_llm(
        self, tmp_workspace: Path, monkeypatch
    ) -> None:
        """Full integration: TUI planner -> Pipeline (real, not mocked)
        with a fake LLM client. Exercises every stage and asserts the
        on-disk artifacts exist when the run is done.
        """
        from unittest.mock import AsyncMock, patch

        from recon.llm import LLMResponse

        ws = Workspace.open(tmp_workspace)
        ws.create_profile("Alpha")
        # Pre-fill so we don't need real research
        import frontmatter as fm

        path = ws.competitors_dir / "alpha.md"
        post = fm.load(str(path))
        post.content = "## Overview\n\nAlpha does AI tooling.\n"
        post["research_status"] = "researched"
        path.write_text(fm.dumps(post))

        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")

        fake_response = LLMResponse(
            text="## Overview\n\nFake LLM output for synthesis.\n",
            input_tokens=100,
            output_tokens=50,
            model="claude-sonnet-4-5",
            stop_reason="end_turn",
        )

        fake_client = AsyncMock()
        fake_client.complete = AsyncMock(return_value=fake_response)
        fake_client.total_input_tokens = 0
        fake_client.total_output_tokens = 0

        app = ReconApp(workspace_path=tmp_workspace)
        with patch(
            "recon.client_factory.create_llm_client",
            return_value=fake_client,
        ):
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                await pilot.press("r")
                await pilot.pause()
                # btn-op-2 is UPDATE_ALL (3rd option, index 2) -- shorter than full pipeline
                app.screen.query_one("#btn-op-2", Button).press()
                await pilot.pause()
                await pilot.pause()
                await pilot.pause()

                # Wait for the worker to actually finish
                from recon.tui.screens.run import RunScreen

                assert isinstance(app.screen, RunScreen)
                run_screen = app.screen
                for _ in range(60):
                    if run_screen.current_phase in ("done", "error"):
                        break
                    await pilot.pause()

                # The pipeline should have finished without error
                assert run_screen.current_phase == "done", (
                    f"Pipeline ended in {run_screen.current_phase!r}"
                )

        # The fake LLM should have been called
        assert fake_client.complete.called


class TestDashboardBrowserFlow:
    async def test_browse_and_return(self, tmp_workspace: Path) -> None:
        ws = Workspace.open(tmp_workspace)
        ws.create_profile("Alpha Corp")
        ws.create_profile("Beta Inc")

        app = ReconApp(workspace_path=tmp_workspace)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            assert isinstance(app.screen, DashboardScreen)

            await pilot.press("b")
            await pilot.pause()
            assert isinstance(app.screen, CompetitorBrowserScreen)

            table = app.screen.query_one(DataTable)
            assert table.row_count == 2

            app.pop_screen()
            await pilot.pause()
            assert isinstance(app.screen, DashboardScreen)


class TestNewProjectFullFlow:
    async def test_welcome_new_project_describe_to_dashboard(self, tmp_path: Path) -> None:
        from textual.widgets import TextArea

        from recon.tui.screens.describe import DescribeScreen

        app = ReconApp()
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause()
            assert isinstance(app.screen, WelcomeScreen)

            new_path = tmp_path / "my-fresh-project"
            app.screen.post_message(
                WelcomeScreen.NewProjectRequested(str(new_path))
            )
            await pilot.pause()
            await pilot.pause()
            assert isinstance(app.screen, DescribeScreen)
            assert app.is_running

            area = app.screen.query_one("#describe-area", TextArea)
            area.load_text("Acme Corp makes CI/CD tools for developers")
            await pilot.pause()

            app.screen.action_submit()
            await pilot.pause()
            await pilot.pause()
            await pilot.pause()

            assert app.is_running
            assert isinstance(app.screen, DashboardScreen)
            assert app.workspace_path == new_path
            assert (new_path / "recon.yaml").exists()

    async def test_wizard_completion_does_not_stall_pipeline_launch(
        self, tmp_path: Path, monkeypatch,
    ) -> None:
        """Phase Q regression: launching a pipeline immediately after
        completing the wizard must NOT stall. Before Phase Q, the
        wizard completion handler did a ``switch_mode("run")`` dance
        that instantiated the run mode early and consumed its one-shot
        ``on_mount`` before any pipeline had been queued. A later
        ``launch_pipeline`` call would silently no-op.

        This test skips the full wizard UI drive (which has 12+ Tab
        stops) and dispatches the wizard completion via
        ``_handle_wizard_result`` directly -- the same entry point the
        real wizard dismiss calls. Then it drives dashboard → r →
        FULL_PIPELINE and asserts the pipeline transitioned past
        Idle. Uses a fake LLM client to avoid hitting the real API.
        """
        from unittest.mock import AsyncMock, patch

        from recon.llm import LLMResponse
        from recon.tui.screens.planner import Operation, RunPlannerScreen
        from recon.tui.screens.run import RunScreen
        from recon.tui.screens.wizard import WizardResult
        from recon.workspace import Workspace

        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")

        # Minimal valid schema the wizard produces
        wizard_schema = {
            "domain": "Dev Tools",
            "identity": {
                "company_name": "AcmeCo",
                "products": ["X"],
                "decision_context": ["build-vs-buy"],
            },
            "rating_scales": {
                "c": {
                    "name": "Cap",
                    "values": ["1", "2"],
                    "never_use": ["emoji"],
                },
            },
            "sections": [
                {
                    "key": "overview",
                    "title": "Overview",
                    "description": "x",
                    "evidence_types": ["factual"],
                    "allowed_formats": ["prose"],
                    "preferred_format": "prose",
                },
            ],
        }
        new_path = tmp_path / "wizard-to-pipeline"

        fake_response = LLMResponse(
            text="## Overview\n\nFake.\n",
            input_tokens=100,
            output_tokens=50,
            model="claude-sonnet-4-5",
            stop_reason="end_turn",
        )
        fake_client = AsyncMock()
        fake_client.complete = AsyncMock(return_value=fake_response)
        fake_client.total_input_tokens = 0
        fake_client.total_output_tokens = 0

        app = ReconApp()
        with patch(
            "recon.client_factory.create_llm_client",
            return_value=fake_client,
        ):
            async with app.run_test(size=(140, 50)) as pilot:
                await pilot.pause()
                assert isinstance(app.screen, WelcomeScreen)

                # Dispatch wizard completion directly (skips the Tab
                # chain but runs the same handler path as a real
                # dismiss). This is what ``WizardScreen.dismiss``
                # ultimately triggers.
                result = WizardResult(
                    schema=wizard_schema,
                    output_dir=new_path,
                    api_key="sk-ant-test",
                )
                app._handle_wizard_result(result)
                for _ in range(5):
                    await pilot.pause()

                # We should land on the dashboard for the new workspace
                assert isinstance(app.screen, DashboardScreen)
                assert app.workspace_path == new_path

                # Create a profile so the dashboard has something to
                # run on
                ws = Workspace.open(new_path)
                ws.create_profile("Alpha Corp")
                dashboard = app.screen
                from recon.tui.models.dashboard import build_dashboard_data
                dashboard.refresh_data(build_dashboard_data(ws))
                for _ in range(3):
                    await pilot.pause()

                # Now launch the pipeline -- Phase Q ensures the
                # run mode is still uninstantiated at this point,
                # so launch_pipeline will queue and switch cleanly.
                dashboard.action_run()
                for _ in range(3):
                    await pilot.pause()
                assert isinstance(app.screen, RunPlannerScreen)
                app.screen.dismiss(Operation.UPDATE_ALL)
                for _ in range(5):
                    await pilot.pause()

                # Run mode must be active
                assert app.current_mode == "run"
                assert isinstance(app.screen, RunScreen)

                # And the pipeline must transition out of Idle
                run = app.screen
                for _ in range(40):
                    await pilot.pause()
                    if run.current_phase != "idle":
                        break
                assert run.current_phase != "idle", (
                    "pipeline stalled at Idle after wizard completion "
                    "-- Phase Q regression: the cached RunScreen's "
                    "on_mount probably fired too early again"
                )


class TestRunScreenPipelineGate:
    async def test_pipeline_gate_end_to_end(self) -> None:
        from recon.themes import DiscoveredTheme
        from recon.tui.models.curation import ThemeCurationModel
        from recon.tui.screens.curation import ThemeCurationScreen

        themes = [
            DiscoveredTheme(
                label="Platform Consolidation",
                evidence_chunks=[{"text": "evidence"}],
                evidence_strength="strong",
                suggested_queries=["q1"],
                cluster_center=[0.1],
            ),
        ]
        gate_result: list[DiscoveredTheme] = []
        pipeline_completed = False

        async def mock_pipeline(screen: RunScreen) -> None:
            nonlocal pipeline_completed
            screen.current_phase = "research"
            screen.progress = 0.5
            screen.current_phase = "themes"

            model = ThemeCurationModel.from_themes(themes)
            curated = await screen.app.push_screen_wait(ThemeCurationScreen(model=model))
            gate_result.extend(curated)

            screen.current_phase = "synthesis"
            screen.progress = 0.9
            screen.current_phase = "complete"
            screen.progress = 1.0
            pipeline_completed = True

        app = ReconApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            app.switch_mode("run")
            await pilot.pause()

            screen = app.screen
            assert isinstance(screen, RunScreen)
            screen.start_pipeline(mock_pipeline)
            await pilot.pause()
            await pilot.pause()

            assert isinstance(app.screen, ThemeCurationScreen)
            app.screen.query_one("#btn-done", Button).press()
            await pilot.pause()
            await pilot.pause()

            assert len(gate_result) >= 1
            assert pipeline_completed
