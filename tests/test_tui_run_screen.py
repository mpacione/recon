"""Tests for RunScreen."""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.widgets import Static

from recon.tui.screens.run import RunScreen


class _RunTestApp(App):
    CSS = "Screen { background: #000000; }"

    def compose(self) -> ComposeResult:
        yield RunScreen()


class TestRunScreen:
    async def test_mounts_with_title(self) -> None:
        app = _RunTestApp()
        async with app.run_test(size=(120, 40)):
            title = app.query_one("#run-title", Static)
            assert "RUN MONITOR" in str(title.content)

    async def test_shows_idle_phase(self) -> None:
        app = _RunTestApp()
        async with app.run_test(size=(120, 40)):
            phase = app.query_one("#run-phase", Static)
            assert "Idle" in str(phase.content)

    async def test_shows_progress_bar(self) -> None:
        app = _RunTestApp()
        async with app.run_test(size=(120, 40)):
            progress = app.query_one("#run-progress", Static)
            assert "0%" in str(progress.content)

    async def test_shows_cost(self) -> None:
        app = _RunTestApp()
        async with app.run_test(size=(120, 40)):
            cost = app.query_one("#run-cost", Static)
            assert "$0.00" in str(cost.content)

    async def test_update_phase(self) -> None:
        app = _RunTestApp()
        async with app.run_test(size=(120, 40)) as pilot:
            screen = app.query_one(RunScreen)
            screen.current_phase = "research"
            await pilot.pause()
            phase = app.query_one("#run-phase", Static)
            assert "Research" in str(phase.content)

    async def test_update_progress(self) -> None:
        app = _RunTestApp()
        async with app.run_test(size=(120, 40)) as pilot:
            screen = app.query_one(RunScreen)
            screen.progress = 0.5
            await pilot.pause()
            progress = app.query_one("#run-progress", Static)
            assert "50%" in str(progress.content)

    async def test_update_cost(self) -> None:
        app = _RunTestApp()
        async with app.run_test(size=(120, 40)) as pilot:
            screen = app.query_one(RunScreen)
            screen.cost_usd = 42.50
            await pilot.pause()
            cost = app.query_one("#run-cost", Static)
            assert "$42.50" in str(cost.content)

    async def test_add_activity(self) -> None:
        app = _RunTestApp()
        async with app.run_test(size=(120, 40)) as pilot:
            screen = app.query_one(RunScreen)
            screen.add_activity("Cursor -- Capabilities -- done")
            await pilot.pause()
            log = app.query_one("#run-activity", Static)
            assert "Cursor" in str(log.content)
