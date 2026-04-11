"""Tests for RunStatusBar widget.

Thin 1-line bar in the persistent chrome that surfaces the active
run's stage, progress, elapsed time, and running cost. Hidden when
the workspace is idle, visible while a run is in flight.
"""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.widgets import Static


class _StatusBarTestApp(App):
    CSS = "Screen { background: #000000; }"

    def compose(self) -> ComposeResult:
        from recon.tui.shell import RunStatusBar

        yield RunStatusBar()


class TestRunStatusBarVisibility:
    async def test_hidden_when_idle(self) -> None:
        from recon.tui.shell import RunStatusBar

        app = _StatusBarTestApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            bar = app.query_one(RunStatusBar)
            assert bar.has_class("idle")

    async def test_visible_when_run_started(self) -> None:
        from recon.events import RunStarted, publish
        from recon.tui.shell import RunStatusBar

        app = _StatusBarTestApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            publish(RunStarted(run_id="r1", operation="full_pipeline"))
            await pilot.pause()
            bar = app.query_one(RunStatusBar)
            assert not bar.has_class("idle")

    async def test_hidden_again_after_run_completed(self) -> None:
        from recon.events import RunCompleted, RunStarted, publish
        from recon.tui.shell import RunStatusBar

        app = _StatusBarTestApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            publish(RunStarted(run_id="r1", operation="x"))
            await pilot.pause()
            publish(RunCompleted(run_id="r1", total_cost_usd=1.23))
            await pilot.pause()
            bar = app.query_one(RunStatusBar)
            assert bar.has_class("idle")

    async def test_hidden_after_run_failed(self) -> None:
        from recon.events import RunFailed, RunStarted, publish
        from recon.tui.shell import RunStatusBar

        app = _StatusBarTestApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            publish(RunStarted(run_id="r1", operation="x"))
            await pilot.pause()
            publish(RunFailed(run_id="r1", error="boom"))
            await pilot.pause()
            bar = app.query_one(RunStatusBar)
            assert bar.has_class("idle")

    async def test_hidden_after_run_cancelled(self) -> None:
        from recon.events import RunCancelled, RunStarted, publish
        from recon.tui.shell import RunStatusBar

        app = _StatusBarTestApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            publish(RunStarted(run_id="r1", operation="x"))
            await pilot.pause()
            publish(RunCancelled(run_id="r1"))
            await pilot.pause()
            bar = app.query_one(RunStatusBar)
            assert bar.has_class("idle")


class TestRunStatusBarContent:
    async def test_renders_stage_after_stage_started(self) -> None:
        from recon.events import RunStageStarted, RunStarted, publish
        from recon.tui.shell import RunStatusBar

        app = _StatusBarTestApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            publish(RunStarted(run_id="r1", operation="x"))
            publish(RunStageStarted(run_id="r1", stage="research"))
            await pilot.pause()
            bar = app.query_one(RunStatusBar)
            content = str(bar.render())
            assert "research" in content

    async def test_running_cost_increments_with_cost_recorded(self) -> None:
        from recon.events import CostRecorded, RunStarted, publish
        from recon.tui.shell import RunStatusBar

        app = _StatusBarTestApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            publish(RunStarted(run_id="r1", operation="x"))
            publish(
                CostRecorded(
                    run_id="r1",
                    model="claude-sonnet-4-5",
                    input_tokens=1000,
                    output_tokens=500,
                    cost_usd=0.42,
                ),
            )
            publish(
                CostRecorded(
                    run_id="r1",
                    model="claude-sonnet-4-5",
                    input_tokens=500,
                    output_tokens=200,
                    cost_usd=0.18,
                ),
            )
            await pilot.pause()
            bar = app.query_one(RunStatusBar)
            content = str(bar.render())
            # Running cost should be cumulative
            assert "$0.60" in content

    async def test_renders_elapsed_time_marker(self) -> None:
        from recon.events import RunStarted, publish
        from recon.tui.shell import RunStatusBar

        app = _StatusBarTestApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            publish(RunStarted(run_id="r1", operation="x"))
            await pilot.pause()
            bar = app.query_one(RunStatusBar)
            content = str(bar.render())
            # Elapsed time render is shaped like "0:00" or "0:01"
            assert ":" in content

    async def test_progress_bar_visible_in_render(self) -> None:
        from recon.events import RunStarted, publish
        from recon.tui.shell import RunStatusBar

        app = _StatusBarTestApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            publish(RunStarted(run_id="r1", operation="x"))
            await pilot.pause()
            bar = app.query_one(RunStatusBar)
            content = str(bar.render())
            # The bar uses bracketed dashes/equals from format_progress_bar
            assert "[" in content or "=" in content or "-" in content

    async def test_running_cost_resets_on_new_run(self) -> None:
        from recon.events import CostRecorded, RunCompleted, RunStarted, publish
        from recon.tui.shell import RunStatusBar

        app = _StatusBarTestApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            publish(RunStarted(run_id="r1", operation="x"))
            publish(
                CostRecorded(
                    run_id="r1",
                    model="claude-sonnet-4-5",
                    input_tokens=1000,
                    output_tokens=500,
                    cost_usd=0.42,
                ),
            )
            publish(RunCompleted(run_id="r1", total_cost_usd=0.42))
            await pilot.pause()
            publish(RunStarted(run_id="r2", operation="x"))
            await pilot.pause()
            bar = app.query_one(RunStatusBar)
            content = str(bar.render())
            assert "$0.42" not in content
            assert "$0.00" in content


class TestRunStatusBarSubscriptionLifecycle:
    async def test_unmount_unsubscribes_from_bus(self) -> None:
        from recon.events import RunStarted, get_bus, publish
        from recon.tui.shell import RunStatusBar

        app = _StatusBarTestApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            initial_count = len(get_bus()._subscribers)
            assert initial_count >= 1
            bar = app.query_one(RunStatusBar)
            await bar.remove()
            await pilot.pause()
            assert len(get_bus()._subscribers) < initial_count
            publish(RunStarted(run_id="r1", operation="x"))


class TestRunStatusBarChromeIntegration:
    """RunStatusBar should appear in the persistent chrome below the
    body region and above LogPane.
    """

    async def test_recon_screen_includes_status_bar(self) -> None:
        from recon.tui.shell import LogPane, ReconScreen, RunStatusBar

        class _DummyScreen(ReconScreen):
            def compose_body(self):
                yield Static("dummy")

        class _DummyApp(App):
            CSS = "Screen { background: #000000; }"

            def compose(self) -> ComposeResult:
                yield Static("")

            def on_mount(self) -> None:
                self.push_screen(_DummyScreen())

        app = _DummyApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.pause()
            screen = app.screen
            assert screen.query_one(RunStatusBar) is not None
            assert screen.query_one(LogPane) is not None
