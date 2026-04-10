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

            app.screen.query_one("#btn-discover", Button).press()
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

            app.screen.query_one("#btn-run", Button).press()
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

                app.screen.query_one("#btn-run", Button).press()
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

                app.screen.query_one("#btn-run", Button).press()
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

                app.screen.query_one("#btn-run", Button).press()
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


class TestDashboardBrowserFlow:
    async def test_browse_and_return(self, tmp_workspace: Path) -> None:
        ws = Workspace.open(tmp_workspace)
        ws.create_profile("Alpha Corp")
        ws.create_profile("Beta Inc")

        app = ReconApp(workspace_path=tmp_workspace)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            assert isinstance(app.screen, DashboardScreen)

            app.screen.query_one("#btn-browse", Button).press()
            await pilot.pause()
            assert isinstance(app.screen, CompetitorBrowserScreen)

            table = app.screen.query_one(DataTable)
            assert table.row_count == 2

            app.pop_screen()
            await pilot.pause()
            assert isinstance(app.screen, DashboardScreen)


class TestNewProjectFullFlow:
    async def test_welcome_new_project_wizard_to_dashboard(self, tmp_path: Path) -> None:
        from textual.widgets import Input

        from recon.tui.screens.wizard import WizardScreen

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
            assert isinstance(app.screen, WizardScreen)
            assert app.is_running

            app.screen.query_one("#input-company", Input).value = "Acme Corp"
            app.screen.query_one("#input-products", Input).value = "Acme CI"
            app.screen.query_one("#input-domain", Input).value = "CI/CD Tools"
            app.screen.query_one("#btn-continue", Button).press()
            await pilot.pause()

            app.screen.query_one("#btn-continue", Button).press()
            await pilot.pause()

            app.screen.query_one("#btn-continue", Button).press()
            await pilot.pause()

            app.screen.query_one("#input-api-key", Input).value = "sk-ant-test"
            app.screen.query_one("#btn-confirm", Button).press()
            await pilot.pause()
            await pilot.pause()
            await pilot.pause()

            assert app.is_running
            assert isinstance(app.screen, DashboardScreen)
            assert app.workspace_path == new_path
            assert (new_path / "recon.yaml").exists()
            assert (new_path / ".env").exists()


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
