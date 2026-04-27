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
from textual.containers import Horizontal
from textual.reactive import reactive
from textual.widgets import Button, Static

from recon.logging import get_logger
from recon.events import RunPaused, RunResumed, publish
from recon.tui.shell import ReconScreen
from recon.tui.stage_monitor import StageMonitor
from recon.tui.widgets import action_button, format_progress_bar

_log = get_logger(__name__)

PipelineFn = Callable[["RunScreen"], Coroutine[Any, Any, None]]


class RunScreen(ReconScreen):
    """Live pipeline monitor — v4 AGENTS tab."""

    tab_key = "agents"
    show_activity_feed = False

    BINDINGS = [
        Binding("enter", "run", "run", show=False),
        Binding("space", "next", "next", show=False),
        Binding("r", "run", "run", show=False),
        Binding("p", "pause", "pause/resume"),
        Binding("s", "stop", "stop"),
        Binding("b", "back", "back to dashboard"),
        # `esc` matches the "back" hotkey on every other tab so the
        # whole TUI reads with a single mental model: esc = go up.
        Binding("escape", "back", "back", show=False),
        # `o` — jump straight to OUTPUT tab. Matches the web UI which
        # auto-navigates there once a run completes.
        Binding("o", "goto_output", "output", show=False),
    ]

    keybind_hints = (
        "[#DDEDC4]↲[/] run · [#DDEDC4]p[/] pause/resume · [#DDEDC4]s[/] stop · "
        "[#DDEDC4]space[/] next · [#DDEDC4]esc[/] back · [#DDEDC4]q[/] quit"
    )

    DEFAULT_CSS = """
    RunScreen {
        background: #000000;
    }
    #run-header {
        height: auto;
        margin: 0 0 1 0;
    }
    #run-actions {
        height: 3;
        margin: 0 0 1 0;
        layout: horizontal;
    }
    #run-actions Button {
        margin: 0 1 0 0;
        min-width: 15;
    }
    #run-empty-state {
        height: auto;
        margin: 0 0 1 0;
        color: #a59a86;
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
    .hidden-legacy {
        display: none;
    }
    """

    progress: reactive[float] = reactive(0.0)
    current_phase: reactive[str] = reactive("idle")
    cost_usd: reactive[float] = reactive(0.0)

    def __init__(self) -> None:
        super().__init__()
        self._activity: list[str] = []
        self._pipeline_fn: PipelineFn | None = None
        self._run_summary: list[dict[str, str]] = []

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
        with Horizontal(id="run-actions"):
            yield action_button("BACK", "Esc", button_id="run-back")
            yield action_button("RUN", "Enter", button_id="run-start", variant="primary")
            yield action_button("PAUSE/RESUME", "P", button_id="run-pause")
            yield action_button("STOP", "S", button_id="run-stop")
            yield Static("", classes="action-spacer")
            yield action_button("NEXT", "Space", button_id="run-next")

        yield Static(self._render_ready_state(), id="run-empty-state")

        self._monitor = StageMonitor(
            competitor_names=self._competitor_names(),
            section_keys=self._section_keys(),
            verification_mode=self._verification_mode(),
        )
        yield self._monitor

        # Legacy IDs kept as hidden placeholders so existing tests
        # that query by ID don't crash. They're updated by watchers
        # but not visible to the user.
        yield Static(self._format_phase(), id="run-phase", classes="hidden-legacy")
        yield Static(self._format_progress(), id="run-progress", classes="hidden-legacy")
        yield Static(self._format_cost(), id="run-cost", classes="hidden-legacy")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "run-start":
            self.action_run()
        elif button_id == "run-pause":
            self.action_pause()
        elif button_id == "run-stop":
            self.action_stop()
        elif button_id == "run-back":
            self.action_back()
        elif button_id == "run-next":
            self.action_next()
        else:
            return
        event.stop()

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

    def _verification_mode(self) -> str:
        try:
            settings_loader = getattr(self.app, "_load_plan_settings", None)
            if callable(settings_loader):
                settings = settings_loader()
                if isinstance(settings, dict):
                    return str(settings.get("verification_mode", "standard"))
        except Exception:
            pass
        return "standard"

    def _configured_workers(self) -> int:
        try:
            settings_loader = getattr(self.app, "_load_plan_settings", None)
            if callable(settings_loader):
                settings = settings_loader()
                if isinstance(settings, dict):
                    return int(settings.get("workers", 5))
        except Exception:
            pass
        return 5

    def action_back(self) -> None:
        _log.info("RunScreen action_back")
        self.app.switch_mode("dashboard")

    def action_run(self) -> None:
        _log.info("RunScreen action_run")
        with contextlib.suppress(Exception):
            self.app.launch_pipeline_from_plan()

    def action_goto_output(self) -> None:
        """Jump to the OUTPUT tab — matches the web UI's post-run flow.

        The app-level ``goto_tab('output')`` handler rebuilds the
        dashboard in ``output`` mode. Safe to call while a run is
        mid-flight; the RunScreen instance stays alive in the ``run``
        mode and the user can press ``4`` / ``agents`` to return.
        """
        _log.info("RunScreen action_goto_output")
        with contextlib.suppress(Exception):
            self.app.action_goto_tab("output")

    def action_next(self) -> None:
        self.action_goto_output()

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
        with contextlib.suppress(Exception):
            self._monitor.freeze_clock()
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
            with contextlib.suppress(Exception):
                self._monitor.pause_clock()
            with contextlib.suppress(Exception):
                publish(RunPaused())
            self.add_activity("Pipeline paused -- press p again to resume")
            self.app.notify("Pipeline paused", severity="information")
        else:
            # Currently paused -> resume
            pause_event.set()
            self.current_phase = "running"
            with contextlib.suppress(Exception):
                self._monitor.resume_clock()
            with contextlib.suppress(Exception):
                publish(RunResumed())
            self.add_activity("Pipeline resumed")
            self.app.notify("Pipeline resumed", severity="information")

    def watch_current_phase(self, value: str) -> None:
        with contextlib.suppress(Exception):
            self.query_one("#run-phase", Static).update(self._format_phase())
        with contextlib.suppress(Exception):
            self.query_one("#run-empty-state", Static).update(self._render_ready_state())
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
        return f"[#DDEDC4]Phase:[/] {self.current_phase.capitalize()}"

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
        return f"[#DDEDC4]Cost:[/] ${self.cost_usd:.2f}"

    def set_run_summary(self, output_files: list[dict[str, str]]) -> None:
        """Display a post-run summary with output file paths.

        Also posts a notification pointing at the OUTPUT tab —
        matches the web UI's "Research complete · SEE OUTPUTS [↲]"
        modal. The TUI uses the lightweight notification instead of
        a blocking modal so the user can keep scrolling the activity
        log or hit ``o`` to switch tabs whenever they're ready.
        """
        self._run_summary = output_files
        self._render_run_summary()
        with contextlib.suppress(Exception):
            self.app.notify(
                "Press [o] to view outputs, [esc] to return to dashboard.",
                title="Research complete",
                severity="information",
                timeout=10,
            )

    def _render_run_summary(self) -> None:
        if not self._run_summary:
            return

        lines = [
            "",
            "[bold #DDEDC4]▒ RUN COMPLETE ▒[/]",
            "",
            "[#DDEDC4]Output files:[/]",
        ]
        for i, entry in enumerate(self._run_summary):
            lines.append(
                f"  [#a59a86]{i + 1}.[/] [#DDEDC4]{entry['label']}[/]  "
                f"[#3a3a3a]{entry['path']}[/]"
            )

        lines.append("")
        lines.append(
            "[#a59a86]press [/][#DDEDC4]b[/][#a59a86] to return to dashboard[/]"
        )

        self.add_activity("\n".join(lines))

    def _render_ready_state(self) -> str:
        competitors = self._competitor_names()
        sections = self._section_keys()
        workers = self._configured_workers()
        verification = self._verification_mode()
        verification_text = (
            f"[#DDEDC4]{verification}[/]" if verification != "standard" else "[#787266]off[/]"
        )
        if not competitors:
            return (
                f"[#a59a86]{len(sections)} sections[/] [#787266]·[/] "
                f"[#a59a86]verification[/] {verification_text} [#787266]·[/] "
                f"[#a59a86]{workers} workers[/]\n"
                "[#787266]No accepted companies yet.[/]\n"
                "[#a59a86]Go to[/] [#DDEDC4]COMPANIES[/] [#a59a86]and discover or add companies before starting a run.[/]"
            )
        if not sections:
            return (
                f"[#a59a86]{len(competitors)} companies[/] [#787266]·[/] "
                f"[#a59a86]verification[/] {verification_text} [#787266]·[/] "
                f"[#a59a86]{workers} workers[/]\n"
                "[#787266]No schema sections selected yet.[/]\n"
                "[#a59a86]Go to[/] [#DDEDC4]SCHEMA[/] [#a59a86]and select at least one section first.[/]"
            )
        if self.current_phase in ("idle", "", "done", "cancelled", "error"):
            return (
                f"[#DDEDC4]Ready to run[/] [#787266]·[/] "
                f"[#a59a86]{len(competitors)} companies[/] [#787266]·[/] "
                f"[#a59a86]{len(sections)} sections[/] [#787266]·[/] "
                f"[#a59a86]verification[/] {verification_text} [#787266]·[/] "
                f"[#a59a86]{workers} workers[/]\n"
                "[#787266]Launch from this screen with[/] [#DDEDC4]RUN [R][/][#787266].[/]"
            )
        return (
            f"[#DDEDC4]{(self.current_phase or 'running').upper()}[/] [#787266]·[/] "
            f"[#a59a86]{len(competitors)} companies[/] [#787266]·[/] "
            f"[#a59a86]{len(sections)} sections[/] [#787266]·[/] "
            f"[#a59a86]verification[/] {verification_text} [#787266]·[/] "
            f"[#a59a86]{workers} workers[/]"
        )
