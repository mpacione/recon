"""Tests for RunScreen."""

from __future__ import annotations

from unittest.mock import patch

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Button, Static

from recon.tui.screens.run import RunScreen


class _RunTestApp(App):
    CSS = "Screen { background: #000000; }"

    def compose(self) -> ComposeResult:
        yield RunScreen()


class TestRunScreen:
    async def test_mounts_with_monitor_heading(self) -> None:
        from recon.tui.stage_monitor import StageMonitor

        app = _RunTestApp()
        async with app.run_test(size=(120, 40)):
            monitor = app.query_one(StageMonitor)
            content = str(monitor.render())
            assert "MONITOR" in content or "waiting" in content.lower()

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

    async def test_add_activity_appends_to_internal_log(self) -> None:
        app = _RunTestApp()
        async with app.run_test(size=(120, 40)) as pilot:
            screen = app.query_one(RunScreen)
            screen.add_activity("Cursor -- Capabilities -- done")
            await pilot.pause()
            assert "Cursor" in screen._activity[-1]

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

    async def test_action_stop_sets_app_cancel_event(self) -> None:
        import asyncio

        app = _RunTestApp()
        async with app.run_test(size=(120, 40)) as pilot:
            event = asyncio.Event()
            app._pipeline_cancel_event = event

            screen = app.query_one(RunScreen)
            screen.action_stop()
            await pilot.pause()

            assert event.is_set()
            assert screen.current_phase == "stopping"

    async def test_action_pause_toggles_pause_event_and_phase(self) -> None:
        import asyncio

        app = _RunTestApp()
        async with app.run_test(size=(120, 40)) as pilot:
            event = asyncio.Event()
            event.set()
            app._pipeline_pause_event = event

            screen = app.query_one(RunScreen)

            # First press: pause -> event cleared, phase = paused
            screen.action_pause()
            await pilot.pause()
            assert not event.is_set()
            assert screen.current_phase == "paused"

            # Second press: resume -> event set, phase != paused
            screen.action_pause()
            await pilot.pause()
            assert event.is_set()
            assert screen.current_phase != "paused"

    async def test_action_pause_with_no_active_pipeline_notifies(self) -> None:
        app = _RunTestApp()
        async with app.run_test(size=(120, 40)) as pilot:
            screen = app.query_one(RunScreen)

            notifications: list[str] = []
            with patch.object(
                type(app),
                "notify",
                lambda self, msg, **kw: notifications.append(msg),
            ):
                screen.action_pause()
                await pilot.pause()

            assert any("No active pipeline" in m for m in notifications)

    async def test_action_stop_unblocks_paused_pipeline(self) -> None:
        """Stop while paused should release the pause so the worker
        can observe the cancel and exit cleanly.
        """
        import asyncio

        app = _RunTestApp()
        async with app.run_test(size=(120, 40)) as pilot:
            cancel = asyncio.Event()
            pause = asyncio.Event()  # cleared = paused
            app._pipeline_cancel_event = cancel
            app._pipeline_pause_event = pause

            screen = app.query_one(RunScreen)
            screen.action_stop()
            await pilot.pause()

            assert cancel.is_set()
            assert pause.is_set(), "Stop should release the pause event"

    async def test_action_stop_with_no_active_pipeline_notifies(self) -> None:
        app = _RunTestApp()
        async with app.run_test(size=(120, 40)) as pilot:
            screen = app.query_one(RunScreen)

            notifications: list[str] = []
            with patch.object(
                type(app),
                "notify",
                lambda self, msg, **kw: notifications.append(msg),
            ):
                screen.action_stop()
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


class TestRunScreenKeybindings:
    """RunScreen exposes pause/stop/back via keybindings.

    The visible controls mirror the key bindings: pressing p/s/b/o
    fires the same ``action_*`` methods as clicking the buttons.
    """

    async def test_screen_declares_pause_stop_back_keybindings(self) -> None:
        app = _RunTestApp()
        async with app.run_test(size=(120, 40)):
            screen = app.query_one(RunScreen)
            keys = {b.key for b in screen.BINDINGS if isinstance(b, Binding)}
            assert "p" in keys
            assert "s" in keys
            assert "b" in keys

    async def test_renders_run_control_buttons(self) -> None:
        app = _RunTestApp()
        async with app.run_test(size=(120, 40)):
            assert app.query_one("#run-pause", Button)
            assert app.query_one("#run-stop", Button)
            assert app.query_one("#run-output", Button)
            assert app.query_one("#run-back", Button)

    async def test_action_back_switches_to_dashboard_mode(self) -> None:
        switch_calls: list[str] = []

        app = _RunTestApp()
        async with app.run_test(size=(120, 40)) as pilot:
            screen = app.query_one(RunScreen)
            with patch.object(
                type(app),
                "switch_mode",
                lambda self, name: switch_calls.append(name),
            ):
                screen.action_back()
                await pilot.pause()
            assert switch_calls == ["dashboard"]

    async def test_keybind_hints_mention_pause_stop_back(self) -> None:
        app = _RunTestApp()
        async with app.run_test(size=(120, 40)):
            screen = app.query_one(RunScreen)
            hints = screen.keybind_hints
            assert "p" in hints
            assert "s" in hints
            assert "b" in hints
            assert "pause" in hints
            assert "stop" in hints

    async def test_pause_phase_indicator_reflects_paused_state(self) -> None:
        """The visual cue that used to come from the button label
        flipping to "Resume" now lives in the phase status: when
        paused, current_phase is set to ``paused`` and the chrome /
        run-phase widget renders that.
        """
        import asyncio

        app = _RunTestApp()
        async with app.run_test(size=(120, 40)) as pilot:
            event = asyncio.Event()
            event.set()
            app._pipeline_pause_event = event

            screen = app.query_one(RunScreen)
            screen.action_pause()
            await pilot.pause()
            assert screen.current_phase == "paused"
            phase_static = app.query_one("#run-phase", Static)
            assert "Paused" in str(phase_static.content)
