"""Tests for ReconApp Modes-based architecture."""

from __future__ import annotations

from pathlib import Path  # noqa: TCH003 -- used at runtime in fixtures

from recon.tui.app import ReconApp
from textual.widgets import Button

from recon.tui.screens.dashboard import DashboardScreen
from recon.tui.screens.describe import DescribeScreen
from recon.tui.screens.results import ResultsScreen
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

    async def test_number_hotkeys_switch_between_tabs(self, tmp_workspace: Path) -> None:
        app = ReconApp(workspace_path=tmp_workspace)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            assert isinstance(app.screen, DashboardScreen)

            await pilot.press("5")
            await pilot.pause()
            assert app.current_mode == "run"
            assert isinstance(app.screen, RunScreen)

            await pilot.press("6")
            await pilot.pause()
            assert isinstance(app.screen, ResultsScreen)

            await pilot.press("1")
            await pilot.pause()
            assert app.current_mode == "dashboard"
            assert isinstance(app.screen, DashboardScreen)

    async def test_number_hotkeys_work_even_with_action_buttons_present(
        self, tmp_workspace: Path,
    ) -> None:
        app = ReconApp(workspace_path=tmp_workspace)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()

            await pilot.press("5")
            await pilot.pause()
            assert isinstance(app.screen, RunScreen)

            pause_button = app.screen.query_one("#run-pause", Button)
            pause_button.focus()
            await pilot.pause()

            await pilot.press("6")
            await pilot.pause()
            assert isinstance(app.screen, ResultsScreen)

            await pilot.press("1")
            await pilot.pause()
            assert isinstance(app.screen, DashboardScreen)

    async def test_home_hotkey_pops_back_from_comps_screen(self, tmp_workspace: Path) -> None:
        app = ReconApp(workspace_path=tmp_workspace)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            assert isinstance(app.screen, DashboardScreen)

            await pilot.press("4")
            await pilot.pause()
            assert getattr(app.screen, "tab_key", None) == "comps"

            await pilot.press("1")
            await pilot.pause()
            assert app.current_mode == "dashboard"
            assert isinstance(app.screen, DashboardScreen)

    async def test_workspace_path_accessible(self, tmp_workspace: Path) -> None:
        app = ReconApp(workspace_path=tmp_workspace)
        assert app.workspace_path == tmp_workspace

    async def test_workspace_selected_sets_path_and_switches(self, tmp_workspace: Path) -> None:
        from recon.tui.screens.welcome import WelcomeScreen

        app = ReconApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            assert isinstance(app.screen, WelcomeScreen)
            app.screen.post_message(
                WelcomeScreen.WorkspaceSelected(str(tmp_workspace))
            )
            await pilot.pause()
            await pilot.pause()
            assert app.workspace_path == tmp_workspace

    async def test_new_project_pushes_describe_screen(self, tmp_path: Path) -> None:
        from recon.tui.screens.welcome import WelcomeScreen

        app = ReconApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            assert isinstance(app.screen, WelcomeScreen)
            new_path = tmp_path / "brand-new-project"
            app.screen.post_message(
                WelcomeScreen.NewProjectRequested(str(new_path))
            )
            await pilot.pause()
            await pilot.pause()
            assert app.is_running
            assert isinstance(app.screen, DescribeScreen)

    async def test_new_project_expands_tilde_path(self, tmp_path: Path, monkeypatch) -> None:
        from recon.tui.screens.welcome import WelcomeScreen

        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setenv("HOME", str(fake_home))

        app = ReconApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            assert isinstance(app.screen, WelcomeScreen)

            app.screen.post_message(
                WelcomeScreen.NewProjectRequested("~/recon-workspaces/test-project")
            )
            await pilot.pause()
            await pilot.pause()

            assert isinstance(app.screen, DescribeScreen)
            assert app.screen._output_dir == fake_home / "recon-workspaces" / "test-project"
