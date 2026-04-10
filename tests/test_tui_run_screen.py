"""Tests for RunScreen."""

from __future__ import annotations

from unittest.mock import patch

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

    async def test_start_pipeline_updates_phase(self) -> None:
        phases_seen: list[str] = []

        async def mock_pipeline(screen: RunScreen) -> None:
            screen.current_phase = "research"
            phases_seen.append("research")
            screen.progress = 0.5
            screen.current_phase = "complete"
            phases_seen.append("complete")

        app = _RunTestApp()
        async with app.run_test(size=(120, 40)) as pilot:
            screen = app.query_one(RunScreen)
            screen.start_pipeline(mock_pipeline)
            await pilot.pause()
            await pilot.pause()
            assert "research" in phases_seen
            assert "complete" in phases_seen

    async def test_stop_button_sets_app_cancel_event(self) -> None:
        import asyncio

        from textual.widgets import Button

        app = _RunTestApp()
        async with app.run_test(size=(120, 40)) as pilot:
            event = asyncio.Event()
            app._pipeline_cancel_event = event

            screen = app.query_one(RunScreen)
            stop_btn = screen.query_one("#btn-stop", Button)
            stop_btn.press()
            await pilot.pause()

            assert event.is_set()
            assert screen.current_phase == "stopping"

    async def test_stop_button_with_no_active_pipeline_notifies(self) -> None:
        from textual.widgets import Button

        app = _RunTestApp()
        async with app.run_test(size=(120, 40)) as pilot:
            screen = app.query_one(RunScreen)

            notifications: list[str] = []
            with patch.object(
                type(app),
                "notify",
                lambda self, msg, **kw: notifications.append(msg),
            ):
                screen.query_one("#btn-stop", Button).press()
                await pilot.pause()

            assert any("No active pipeline" in m for m in notifications)

    async def test_push_theme_gate(self) -> None:
        from textual.widgets import Button

        from recon.themes import DiscoveredTheme
        from recon.tui.models.curation import ThemeCurationModel
        from recon.tui.screens.curation import ThemeCurationScreen

        themes = [
            DiscoveredTheme(
                label="Theme A",
                evidence_chunks=[{"text": "evidence"}],
                evidence_strength="strong",
                suggested_queries=["q1"],
                cluster_center=[0.1],
            ),
        ]
        gate_result: list[DiscoveredTheme] = []

        async def mock_pipeline(screen: RunScreen) -> None:
            screen.current_phase = "themes"
            model = ThemeCurationModel.from_themes(themes)
            curated = await screen.app.push_screen_wait(ThemeCurationScreen(model=model))
            gate_result.extend(curated)
            screen.current_phase = "complete"

        app = _RunTestApp()
        async with app.run_test(size=(120, 40)) as pilot:
            screen = app.query_one(RunScreen)
            screen.start_pipeline(mock_pipeline)
            await pilot.pause()
            await pilot.pause()
            assert isinstance(app.screen, ThemeCurationScreen)
            app.screen.query_one("#btn-done", Button).press()
            await pilot.pause()
            await pilot.pause()
            assert len(gate_result) >= 1
            assert screen.current_phase == "complete"
