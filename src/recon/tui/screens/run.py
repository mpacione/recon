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
from textual.binding import Binding
from textual.reactive import reactive
from textual.widgets import Static

from recon.logging import get_logger
from recon.tui.run_monitor import CompetitorGrid, WorkerPanel
from recon.tui.shell import ReconScreen
from recon.tui.widgets import format_progress_bar

_log = get_logger(__name__)

PipelineFn = Callable[["RunScreen"], Coroutine[Any, Any, None]]


class RunScreen(ReconScreen):
    """Live pipeline monitor with reactive state."""

    BINDINGS = [
        Binding("p", "pause", "pause/resume"),
        Binding("s", "stop", "stop"),
        Binding("b", "back", "back to dashboard"),
    ]

    keybind_hints = (
        "[#e0a044]p[/] pause/resume · [#e0a044]s[/] stop · "
        "[#e0a044]b[/] back · [#e0a044]q[/] quit"
    )

    DEFAULT_CSS = """
    RunScreen {
        background: #000000;
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
    """

    progress: reactive[float] = reactive(0.0)
    current_phase: reactive[str] = reactive("idle")
    cost_usd: reactive[float] = reactive(0.0)

    def __init__(self) -> None:
        super().__init__()
        self._activity: list[str] = []
        self._pipeline_fn: PipelineFn | None = None

    def on_mount(self) -> None:
        """First-time setup. Consuming the pending pipeline happens
        in :meth:`on_screen_resume` instead so it also fires on
        subsequent ``switch_mode("run")`` calls, not just the first.
        """
        _log.info("RunScreen.on_mount")
        self._consume_pending_pipeline()

    def on_screen_resume(self) -> None:
        """Fires every time the screen becomes the active screen.

        Textual caches the ``run`` mode's Screen instance after the
        first ``add_mode``, so later ``switch_mode("run")`` calls
        reuse the cached instance without re-firing ``on_mount``. The
        pending-pipeline handshake (dashboard queues a pipeline_fn on
        the app, then switches mode) must therefore consume the queue
        here, not in ``on_mount``. Without this, a user who went
        welcome → dashboard → r → 7 would see the run screen with
        Phase: Idle forever because ``_pending_pipeline_fn`` was
        queued AFTER the one-shot ``on_mount`` already fired at
        workspace-selected time.
        """
        _log.info("RunScreen.on_screen_resume")
        self._consume_pending_pipeline()

    def _consume_pending_pipeline(self) -> None:
        pending = getattr(self.app, "_pending_pipeline_fn", None)
        _log.info(
            "RunScreen._consume_pending_pipeline has_pending=%s",
            pending is not None,
        )
        if pending is not None:
            self.app._pending_pipeline_fn = None
            self.start_pipeline(pending)



    def compose_body(self) -> ComposeResult:
        # Legacy phase/progress/cost Statics for backward compat with
        # tests that query these by ID. The CompetitorGrid renders its
        # own header with the same info, so these are supplementary.
        yield Static(self._format_phase(), id="run-phase")
        yield Static(self._format_progress(), id="run-progress")
        yield Static(self._format_cost(), id="run-cost")
        yield Static("")

        # The new competitor grid — subscribes to the bus and renders
        # per-competitor ASCII progress bars in real time.
        self._grid = CompetitorGrid(
            competitor_names=self._competitor_names(),
            section_keys=self._section_keys(),
        )
        yield self._grid
        yield WorkerPanel(grid=self._grid)

    def _competitor_names(self) -> list[str]:
        """Pull competitor names from the workspace for grid init."""
        try:
            ws_path = getattr(self.app, "_workspace_path", None)
            if ws_path is None:
                return []
            from recon.workspace import Workspace

            ws = Workspace.open(ws_path)
            return [p["name"] for p in ws.list_profiles()]
        except Exception:
            return []

    def _section_keys(self) -> list[str]:
        """Pull section keys from the workspace schema for grid init."""
        try:
            ws_path = getattr(self.app, "_workspace_path", None)
            if ws_path is None:
                return []
            from recon.workspace import Workspace

            ws = Workspace.open(ws_path)
            if ws.schema and ws.schema.sections:
                return [s.key for s in ws.schema.sections]
            return []
        except Exception:
            return []

    def action_back(self) -> None:
        _log.info("RunScreen action_back")
        self.app.switch_mode("dashboard")

    def action_pause(self) -> None:
        _log.info("RunScreen action_pause")
        self._toggle_pause()

    def action_stop(self) -> None:
        _log.info("RunScreen action_stop")
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
        ``current_phase`` reactive flips to ``"paused"`` so the chrome
        header strip and the on-screen Phase widget both reflect the
        state.
        """
        pause_event = getattr(self.app, "_pipeline_pause_event", None)
        if pause_event is None:
            self.add_activity("Pause ignored: no active pipeline")
            self.app.notify(
                "No active pipeline to pause",
                severity="warning",
            )
            return

        if pause_event.is_set():
            # Currently running -> pause
            pause_event.clear()
            self.current_phase = "paused"
            self.add_activity("Pipeline paused -- press p again to resume")
            self.app.notify("Pipeline paused", severity="information")
        else:
            # Currently paused -> resume
            pause_event.set()
            self.current_phase = "running"
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
        _log.info("RunScreen.start_pipeline called")
        self._pipeline_fn = pipeline_fn
        self._execute_pipeline()

    @work(exclusive=True)
    async def _execute_pipeline(self) -> None:
        _log.info("RunScreen._execute_pipeline worker entered")
        if self._pipeline_fn is None:
            _log.warning("RunScreen._execute_pipeline: _pipeline_fn is None")
            return
        try:
            await self._pipeline_fn(self)
        except Exception:
            _log.exception("RunScreen._execute_pipeline: pipeline_fn raised")
            raise

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
