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
            self._toggle_pause()
        elif button_id == "btn-stop":
            self._request_stop()

    def _request_stop(self) -> None:
        """Set the cancel event the TUI runner stored on the app, if any."""
        cancel_event = getattr(self.app, "_pipeline_cancel_event", None)
        if cancel_event is None:
            self.add_activity("Stop ignored: no active pipeline")
            self.app.notify("No active pipeline to stop", severity="warning")
            return
        cancel_event.set()
        # Make sure a paused pipeline doesn't get wedged behind the
        # pause event after the user asks for stop -- unblock it so it
        # can observe the cancel.
        pause_event = getattr(self.app, "_pipeline_pause_event", None)
        if pause_event is not None and not pause_event.is_set():
            pause_event.set()
        self.current_phase = "stopping"
        self.add_activity("Stop requested -- waiting for current stage to finish")
        self.app.notify("Stop requested", severity="warning")

    def _toggle_pause(self) -> None:
        """Pause / resume the active pipeline.

        Pause is implemented by clearing an asyncio.Event the worker
        pool waits on before each task. Resume sets it again. The
        button label flips between "Pause" and "Resume" so the user
        can see the current state.
        """
        pause_event = getattr(self.app, "_pipeline_pause_event", None)
        if pause_event is None:
            self.add_activity("Pause ignored: no active pipeline")
            self.app.notify(
                "No active pipeline to pause",
                severity="warning",
            )
            return

        pause_button = self.query_one("#btn-pause", Button)
        if pause_event.is_set():
            # Currently running -> pause
            pause_event.clear()
            pause_button.label = "Resume"
            self.current_phase = "paused"
            self.add_activity("Pipeline paused -- click Resume to continue")
            self.app.notify("Pipeline paused", severity="information")
        else:
            # Currently paused -> resume
            pause_event.set()
            pause_button.label = "Pause"
            self.add_activity("Pipeline resumed")
            self.app.notify("Pipeline resumed", severity="information")

    def watch_current_phase(self, value: str) -> None:
        with contextlib.suppress(Exception):
            self.query_one("#run-phase", Static).update(self._format_phase())
        # Phase changes the bar color/state, so refresh the bar too
        with contextlib.suppress(Exception):
            self.query_one("#run-progress", Static).update(self._format_progress())

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

    _STATE_KEYWORDS = ("idle", "running", "paused", "stopping", "done", "cancelled", "error")

    def _format_phase(self) -> str:
        return f"[#efe5c0]Phase:[/] {self.current_phase.capitalize()}"

    def _bar_state(self) -> str:
        """Map current_phase to a progress-bar visual state."""
        phase = (self.current_phase or "").lower()
        for keyword in self._STATE_KEYWORDS:
            if keyword in phase:
                return keyword
        # Default: any non-special phase ("research", "synthesize", ...)
        # is a "running" state.
        return "running"

    def _format_progress(self) -> str:
        return format_progress_bar(self.progress, state=self._bar_state())

    def _format_cost(self) -> str:
        return f"[#efe5c0]Cost:[/] ${self.cost_usd:.2f}"
