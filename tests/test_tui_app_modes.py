"""Tests for ReconApp Modes-based architecture."""

from __future__ import annotations

from pathlib import Path  # noqa: TCH003 -- used at runtime in fixtures

from recon.tui.app import ReconApp
from recon.tui.screens.dashboard import DashboardScreen
from recon.tui.screens.run import RunScreen


class TestReconAppModes:
    async def test_default_mode_is_dashboard(self) -> None:
        app = ReconApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            assert app.current_mode == "dashboard"

    async def test_dashboard_screen_is_active(self, tmp_workspace: Path) -> None:
        app = ReconApp(workspace_path=tmp_workspace)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            assert isinstance(app.screen, DashboardScreen)

    async def test_no_workspace_shows_welcome(self) -> None:
        app = ReconApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            from recon.tui.screens.welcome import WelcomeScreen

            assert isinstance(app.screen, WelcomeScreen)

    async def test_switch_to_run_mode(self, tmp_workspace: Path) -> None:
        app = ReconApp(workspace_path=tmp_workspace)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            app.switch_mode("run")
            await pilot.pause()
            assert app.current_mode == "run"
            assert isinstance(app.screen, RunScreen)

    async def test_switch_back_to_dashboard(self, tmp_workspace: Path) -> None:
        app = ReconApp(workspace_path=tmp_workspace)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            app.switch_mode("run")
            await pilot.pause()
            app.switch_mode("dashboard")
            await pilot.pause()
            assert app.current_mode == "dashboard"

    async def test_workspace_path_accessible(self, tmp_workspace: Path) -> None:
        app = ReconApp(workspace_path=tmp_workspace)
        assert app.workspace_path == tmp_workspace
