"""RunScreen for recon TUI.

Live pipeline execution monitor. Uses reactive attributes for
progress, phase, cost. Pipeline runs in a @work worker. Theme
curation gate is pushed via push_screen_wait.
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable, Coroutine
from typing import Any

from textual import work
from textual.app import ComposeResult  # noqa: TCH002 -- used at runtime
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Button, Static

from recon.logging import get_logger
from recon.tui.widgets import format_progress_bar

_log = get_logger(__name__)

PipelineFn = Callable[["RunScreen"], Coroutine[Any, Any, None]]


class RunScreen(Screen):
    """Live pipeline monitor with reactive state."""

    DEFAULT_CSS = """
    RunScreen {
        padding: 1 2;
    }
    #run-header {
        height: auto;
        margin: 0 0 1 0;
    }
    #run-workers {
        height: auto;
        margin: 1 0;
        padding: 1 2;
        border: solid #3a3a3a;
    }
    #run-activity-section {
        height: auto;
        margin: 1 0;
    }
    .action-bar {
        height: auto;
        margin: 1 0;
        layout: horizontal;
    }
    .action-bar Button {
        margin: 0 1 0 0;
    }
    """

    progress: reactive[float] = reactive(0.0)
    current_phase: reactive[str] = reactive("idle")
    cost_usd: reactive[float] = reactive(0.0)

    def __init__(self) -> None:
        super().__init__()
        self._activity: list[str] = []
        self._pipeline_fn: PipelineFn | None = None

    def on_mount(self) -> None:
        # Consume any pending pipeline queued on the app before this
        # screen existed (happens when mode is switched from another
        # screen that wants to start a pipeline here).
        pending = getattr(self.app, "_pending_pipeline_fn", None)
        if pending is not None:
            self.app._pending_pipeline_fn = None
            self.start_pipeline(pending)

    def compose(self) -> ComposeResult:
        yield Static("[bold #e0a044]RUN MONITOR[/]", id="run-title")
        yield Static("")
        yield Static(self._format_phase(), id="run-phase")
        yield Static(self._format_progress(), id="run-progress")
        yield Static(self._format_cost(), id="run-cost")
        yield Static("")
        with Vertical(id="run-activity-section"):
            yield Static("[bold #e0a044]ACTIVITY[/]")
            yield Static("[#a89984]Waiting...[/]", id="run-activity")
        yield Static("")
        with Horizontal(classes="action-bar"):
            yield Button("Pause", id="btn-pause")
            yield Button("Stop", id="btn-stop", variant="error")
            yield Button("Back to Dashboard", id="btn-back-to-dashboard", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        _log.info("RunScreen button pressed id=%s", button_id)
        if button_id == "btn-back-to-dashboard":
            self.app.switch_mode("dashboard")
        elif button_id == "btn-pause":
            self.app.notify("Pause not yet implemented", severity="warning")
        elif button_id == "btn-stop":
            self._request_stop()

    def _request_stop(self) -> None:
        """Set the cancel event the TUI runner stored on the app, if any."""
        cancel_event = getattr(self.app, "_pipeline_cancel_event", None)
        if cancel_event is None:
            self.app.notify("No active pipeline to stop", severity="warning")
            return
        cancel_event.set()
        self.current_phase = "stopping"
        self.add_activity("Stop requested -- waiting for current stage to finish")
        self.app.notify("Stop requested", severity="warning")

    def watch_current_phase(self, value: str) -> None:
        with contextlib.suppress(Exception):
            self.query_one("#run-phase", Static).update(self._format_phase())

    def watch_progress(self, value: float) -> None:
        with contextlib.suppress(Exception):
            self.query_one("#run-progress", Static).update(self._format_progress())

    def watch_cost_usd(self, value: float) -> None:
        with contextlib.suppress(Exception):
            self.query_one("#run-cost", Static).update(self._format_cost())

    def start_pipeline(self, pipeline_fn: PipelineFn) -> None:
        self._pipeline_fn = pipeline_fn
        self._execute_pipeline()

    @work(exclusive=True)
    async def _execute_pipeline(self) -> None:
        if self._pipeline_fn is None:
            return
        await self._pipeline_fn(self)

    def add_activity(self, message: str) -> None:
        self._activity.append(message)
        if len(self._activity) > 50:
            self._activity = self._activity[-50:]
        try:
            log = self.query_one("#run-activity", Static)
            log.update("\n".join(self._activity[-10:]))
        except Exception:
            pass

    def _format_phase(self) -> str:
        return f"[#efe5c0]Phase:[/] {self.current_phase.capitalize()}"

    def _format_progress(self) -> str:
        return format_progress_bar(self.progress)

    def _format_cost(self) -> str:
        return f"[#efe5c0]Cost:[/] ${self.cost_usd:.2f}"
