"""RunScreen for recon TUI.

Live pipeline execution monitor. Uses reactive attributes for
progress, phase, cost. Pipeline runs in a @work worker. Theme
curation gate is pushed via push_screen_wait.
"""

from __future__ import annotations

import contextlib

from textual.app import ComposeResult  # noqa: TCH002 -- used at runtime
from textual.containers import Vertical
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Static

from recon.tui.widgets import format_progress_bar


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
    """

    progress: reactive[float] = reactive(0.0)
    current_phase: reactive[str] = reactive("idle")
    cost_usd: reactive[float] = reactive(0.0)

    def __init__(self) -> None:
        super().__init__()
        self._activity: list[str] = []

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
        yield Static(
            "[#a89984][P] Pause  [S] Stop  [D] Dashboard[/]",
            id="run-controls",
        )

    def watch_current_phase(self, value: str) -> None:
        with contextlib.suppress(Exception):
            self.query_one("#run-phase", Static).update(self._format_phase())

    def watch_progress(self, value: float) -> None:
        with contextlib.suppress(Exception):
            self.query_one("#run-progress", Static).update(self._format_progress())

    def watch_cost_usd(self, value: float) -> None:
        with contextlib.suppress(Exception):
            self.query_one("#run-cost", Static).update(self._format_cost())

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
