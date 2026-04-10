"""Smoke tests for recon.

Fast tests that exercise the full launch sequence to catch deadlocks,
import errors, and obvious hangs. These run in under a second each
and don't touch any real network.

Run with a timeout to catch hangs: pytest tests/test_smoke.py --timeout=10
"""

from __future__ import annotations

import asyncio
from pathlib import Path  # noqa: TCH003 -- used at runtime

from textual.widgets import Button, Input

from recon.tui.app import ReconApp
from recon.tui.screens.dashboard import DashboardScreen
from recon.tui.screens.welcome import WelcomeScreen
from recon.tui.screens.wizard import WizardScreen

_LAUNCH_TIMEOUT = 5.0


class TestTuiLaunchSmoke:
    async def test_app_launches_without_hanging(self) -> None:
        app = ReconApp()
        async def _launch() -> None:
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                assert app.is_running
                assert isinstance(app.screen, WelcomeScreen)

        await asyncio.wait_for(_launch(), timeout=_LAUNCH_TIMEOUT)

    async def test_welcome_to_wizard_does_not_hang(self, tmp_path: Path) -> None:
        app = ReconApp()
        async def _launch() -> None:
            async with app.run_test(size=(120, 50)) as pilot:
                await pilot.pause()
                app.screen.post_message(
                    WelcomeScreen.NewProjectRequested(str(tmp_path / "smoke-project"))
                )
                await pilot.pause()
                await pilot.pause()
                assert isinstance(app.screen, WizardScreen)

        await asyncio.wait_for(_launch(), timeout=_LAUNCH_TIMEOUT)

    async def test_full_wizard_to_dashboard_flow(self, tmp_path: Path) -> None:
        app = ReconApp()
        async def _launch() -> None:
            async with app.run_test(size=(120, 50)) as pilot:
                await pilot.pause()
                app.screen.post_message(
                    WelcomeScreen.NewProjectRequested(str(tmp_path / "smoke-full"))
                )
                await pilot.pause()
                await pilot.pause()

                app.screen.query_one("#input-company", Input).value = "SmokeCo"
                app.screen.query_one("#input-products", Input).value = "SmokeCI"
                app.screen.query_one("#input-domain", Input).value = "Testing"
                app.screen.query_one("#btn-continue", Button).press()
                await pilot.pause()

                app.screen.query_one("#btn-continue", Button).press()
                await pilot.pause()
                app.screen.query_one("#btn-continue", Button).press()
                await pilot.pause()

                app.screen.query_one("#input-api-key", Input).value = "sk-ant-smoke"
                app.screen.query_one("#btn-confirm", Button).press()
                await pilot.pause()
                await pilot.pause()
                await pilot.pause()

                assert app.is_running
                assert isinstance(app.screen, DashboardScreen)

        await asyncio.wait_for(_launch(), timeout=_LAUNCH_TIMEOUT * 2)

    async def test_initial_wizard_dir_mode(self, tmp_path: Path) -> None:
        app = ReconApp(initial_wizard_dir=tmp_path / "auto-wizard")
        async def _launch() -> None:
            async with app.run_test(size=(120, 50)) as pilot:
                await pilot.pause()
                await pilot.pause()
                assert isinstance(app.screen, WizardScreen)

        await asyncio.wait_for(_launch(), timeout=_LAUNCH_TIMEOUT)

    async def test_existing_workspace_goes_straight_to_dashboard(
        self, tmp_workspace: Path,
    ) -> None:
        app = ReconApp(workspace_path=tmp_workspace)
        async def _launch() -> None:
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                assert isinstance(app.screen, DashboardScreen)

        await asyncio.wait_for(_launch(), timeout=_LAUNCH_TIMEOUT)


class TestCliImports:
    def test_cli_main_imports(self) -> None:
        from recon.cli import main
        assert main is not None

    def test_all_screens_import(self) -> None:
        from recon.tui.screens.browser import CompetitorBrowserScreen
        from recon.tui.screens.curation import ThemeCurationScreen
        from recon.tui.screens.dashboard import DashboardScreen
        from recon.tui.screens.discovery import DiscoveryScreen
        from recon.tui.screens.planner import RunPlannerScreen
        from recon.tui.screens.run import RunScreen
        from recon.tui.screens.selector import CompetitorSelectorScreen
        from recon.tui.screens.welcome import WelcomeScreen
        from recon.tui.screens.wizard import WizardScreen

        screens = [
            CompetitorBrowserScreen, ThemeCurationScreen, DashboardScreen,
            DiscoveryScreen, RunPlannerScreen, RunScreen,
            CompetitorSelectorScreen, WelcomeScreen, WizardScreen,
        ]
        assert all(s is not None for s in screens)

    def test_logging_configures(self, tmp_path: Path) -> None:
        from recon.logging import configure_logging, get_logger

        log_file = tmp_path / "smoke.log"
        configure_logging(level="DEBUG", log_file=log_file)
        logger = get_logger("smoke_test")
        logger.info("smoke check")

        assert log_file.exists()
        assert "smoke check" in log_file.read_text()
