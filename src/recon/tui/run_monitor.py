"""Run monitor widgets for the recon TUI.

The ``CompetitorGrid`` renders a per-competitor progress display with
full section names and ASCII shaded progress bars. The ``WorkerPanel``
shows a compact summary of active workers. Both subscribe to the
engine's event bus and update in real time as sections start,
complete, or fail.

Layout (as rendered in the RunScreen body)::

    ── RESEARCH MONITOR ──    00:04:32    $0.42    Workers: 3/5
    ──────────────────────────────────────────────────────────────

    Dell Technologies     ████████████████░░░░░░░░  5/8   62%
    HP Inc.               ████████░░░░░░░░░░░░░░░░  3/8   37%  >> Pricing
    Lenovo Group          ██████████████████████░░  7/8   87%
    Apple Inc.            ████████████████████████  8/8  100%  ✓
    ASUS                  ████████████████░░░░░░░░  5/8   62%  >> Integration
    MSI                   ████████████░░░░░░░░░░░░  4/8   50%
    ...

    WORKERS [3 active]
    [1] HP Inc. · Pricing        [2] ASUS · Integration      [3] idle
"""

from __future__ import annotations

import contextlib
import time
from collections import OrderedDict
from dataclasses import dataclass, field

from textual.widgets import Static

from recon.events import (
    CostRecorded,
    Event,
    RunCancelled,
    RunCompleted,
    RunFailed,
    RunStageStarted,
    RunStarted,
    SectionFailed,
    SectionResearched,
    SectionRetrying,
    SectionStarted,
    get_bus,
)
from recon.logging import get_logger

_log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

# Per-section status
WAITING = "--"
QUEUED = ".."
ACTIVE = ">>"
RETRYING = "~>"
DONE = "ok"
FAILED = "!!"


@dataclass
class CompetitorStatus:
    """Tracks per-section progress for one competitor."""

    name: str
    sections: OrderedDict[str, str] = field(default_factory=OrderedDict)
    failure_errors: dict[str, str] = field(default_factory=dict)

    @property
    def total(self) -> int:
        return len(self.sections)

    @property
    def completed(self) -> int:
        return sum(1 for s in self.sections.values() if s == DONE)

    @property
    def failed(self) -> int:
        return sum(1 for s in self.sections.values() if s == FAILED)

    @property
    def active_section(self) -> str | None:
        for key, status in self.sections.items():
            if status == ACTIVE:
                return key
        return None

    @property
    def progress_fraction(self) -> float:
        if self.total == 0:
            return 0.0
        return self.completed / self.total

    @property
    def is_complete(self) -> bool:
        return self.completed == self.total and self.total > 0


@dataclass
class RunMonitorState:
    """Aggregate state for the run monitor grid."""

    competitors: OrderedDict[str, CompetitorStatus] = field(
        default_factory=OrderedDict,
    )
    section_keys: list[str] = field(default_factory=list)
    started_at: float | None = None
    total_cost: float = 0.0
    active_workers: int = 0
    max_workers: int = 5
    current_stage: str = ""

    def get_or_create(self, name: str) -> CompetitorStatus:
        if name not in self.competitors:
            cs = CompetitorStatus(name=name)
            for key in self.section_keys:
                cs.sections[key] = WAITING
            self.competitors[name] = cs
        return self.competitors[name]

    @property
    def total_sections(self) -> int:
        return sum(c.total for c in self.competitors.values())

    @property
    def completed_sections(self) -> int:
        return sum(c.completed for c in self.competitors.values())

    @property
    def active_section_names(self) -> list[tuple[str, str]]:
        """Return (competitor_name, section_key) for all in-flight sections."""
        result = []
        for cs in self.competitors.values():
            for key, status in cs.sections.items():
                if status == ACTIVE:
                    result.append((cs.name, key))
        return result

    @property
    def elapsed_str(self) -> str:
        if self.started_at is None:
            return "0:00"
        seconds = int(time.monotonic() - self.started_at)
        minutes, secs = divmod(seconds, 60)
        if minutes >= 60:
            hours, minutes = divmod(minutes, 60)
            return f"{hours}:{minutes:02d}:{secs:02d}"
        return f"{minutes}:{secs:02d}"

    @property
    def progress_fraction(self) -> float:
        total = self.total_sections
        if total == 0:
            return 0.0
        return self.completed_sections / total


# ---------------------------------------------------------------------------
# ASCII progress bar renderer
# ---------------------------------------------------------------------------

_MAX_ERROR_DISPLAY_LEN = 30


def _truncate_error(error: str) -> str:
    """Extract a short, meaningful error hint from an exception message."""
    cleaned = error.strip().split("\n")[0]
    if len(cleaned) > _MAX_ERROR_DISPLAY_LEN:
        return cleaned[:_MAX_ERROR_DISPLAY_LEN] + "..."
    return cleaned


_FULL_BLOCK = "\u2588"  # █
_LIGHT_SHADE = "\u2591"  # ░


def render_progress_bar(fraction: float, width: int = 24) -> str:
    """Render a shaded ASCII progress bar.

    Uses Unicode block elements for a smooth visual:
    ``████████████░░░░░░░░░░░░``
    """
    filled = int(fraction * width)
    empty = width - filled

    if fraction >= 1.0:
        return f"[#98971a]{_FULL_BLOCK * width}[/]"
    if filled == 0:
        return f"[#3a3a3a]{_LIGHT_SHADE * width}[/]"
    return (
        f"[#e0a044]{_FULL_BLOCK * filled}[/]"
        f"[#3a3a3a]{_LIGHT_SHADE * empty}[/]"
    )


# ---------------------------------------------------------------------------
# CompetitorGrid widget
# ---------------------------------------------------------------------------


class CompetitorGrid(Static):
    """Per-competitor progress grid with ASCII shaded bars.

    Subscribes to the engine's event bus on mount and updates in
    real time as sections start, complete, or fail. Uses
    ``set_interval`` for elapsed-time ticking (same pattern as
    LogPane and RunStatusBar).
    """

    DEFAULT_CSS = """
    CompetitorGrid {
        height: auto;
        width: 100%;
        padding: 0 0;
        color: #efe5c0;
    }
    """

    def __init__(
        self,
        competitor_names: list[str] | None = None,
        section_keys: list[str] | None = None,
    ) -> None:
        super().__init__("", markup=True)
        self._state = RunMonitorState(
            section_keys=list(section_keys or []),
        )
        if competitor_names:
            for name in competitor_names:
                self._state.get_or_create(name)
        self._subscriber = self._on_event
        self._dirty = True

    @property
    def state(self) -> RunMonitorState:
        return self._state

    def on_mount(self) -> None:
        get_bus().subscribe(self._subscriber)
        self._render_grid()
        self.set_interval(1.0, self._tick, name="grid-tick")

    def on_unmount(self) -> None:
        with contextlib.suppress(Exception):
            get_bus().unsubscribe(self._subscriber)

    def _tick(self) -> None:
        if self._dirty or self._state.started_at is not None:
            self._render_grid()

    # -- event handling ----------------------------------------------------

    def _on_event(self, event: Event) -> None:
        try:
            self.app.call_from_thread(self._handle, event)
        except Exception:
            self._handle(event)

    def _handle(self, event: Event) -> None:
        if isinstance(event, RunStarted):
            self._state.started_at = time.monotonic()
            self._state.total_cost = 0.0
            self._state.current_stage = ""
            self._dirty = True
        elif isinstance(event, RunStageStarted):
            self._state.current_stage = event.stage
            self._dirty = True
        elif isinstance(event, SectionStarted):
            cs = self._state.get_or_create(event.competitor_name)
            cs.sections[event.section_key] = ACTIVE
            self._state.active_workers = len(
                self._state.active_section_names,
            )
            self._dirty = True
        elif isinstance(event, SectionResearched):
            cs = self._state.get_or_create(event.competitor_name)
            cs.sections[event.section_key] = DONE
            self._state.active_workers = len(
                self._state.active_section_names,
            )
            self._dirty = True
        elif isinstance(event, SectionRetrying):
            cs = self._state.get_or_create(event.competitor_name)
            cs.sections[event.section_key] = RETRYING
            self._dirty = True
        elif isinstance(event, SectionFailed):
            cs = self._state.get_or_create(event.competitor_name)
            cs.sections[event.section_key] = FAILED
            if event.error:
                cs.failure_errors[event.section_key] = event.error
            self._state.active_workers = len(
                self._state.active_section_names,
            )
            self._dirty = True
        elif isinstance(event, CostRecorded):
            self._state.total_cost += event.cost_usd
            self._dirty = True
        elif isinstance(event, (RunCompleted, RunFailed, RunCancelled)):
            self._state.current_stage = ""
            self._dirty = True

        if self._dirty:
            self._render_grid()

    # -- rendering ---------------------------------------------------------

    def _render_grid(self) -> None:
        self._dirty = False
        lines: list[str] = []

        s = self._state

        # Header line
        elapsed = s.elapsed_str
        cost = f"${s.total_cost:.2f}"
        workers = len(s.active_section_names)
        total = s.total_sections
        done = s.completed_sections
        pct = f"{s.progress_fraction * 100:.0f}%" if total > 0 else "0%"

        lines.append(
            f"[bold #e0a044]── RESEARCH MONITOR ──[/]  "
            f"[#a89984]{elapsed}[/]  "
            f"[#e0a044]{cost}[/]  "
            f"[#a89984]Workers:[/] [#e0a044]{workers}[/]"
        )
        lines.append("")

        if not s.competitors:
            lines.append("[#a89984]waiting for pipeline...[/]")
            self.update("\n".join(lines))
            return

        # Find the longest competitor name for alignment
        max_name = max(len(cs.name) for cs in s.competitors.values())
        name_width = min(max_name, 28)
        bar_width = 24

        # Per-competitor rows
        for cs in s.competitors.values():
            name_padded = cs.name[:name_width].ljust(name_width)
            bar = render_progress_bar(cs.progress_fraction, bar_width)
            count = f"{cs.completed}/{cs.total}"
            pct_str = f"{cs.progress_fraction * 100:.0f}%"

            # Status indicator on the right
            retrying = sum(1 for v in cs.sections.values() if v == RETRYING)
            if cs.is_complete:
                indicator = "  [#98971a]\\[ok][/]"
            elif cs.failed > 0:
                first_error = next(iter(cs.failure_errors.values()), "")
                error_hint = _truncate_error(first_error) if first_error else ""
                error_suffix = f": {error_hint}" if error_hint else ""
                indicator = f"  [#cc241d]{cs.failed} failed{error_suffix}[/]"
            elif retrying > 0:
                indicator = f"  [#d79921]~> retrying[/]"
            elif cs.active_section:
                indicator = f"  [#e0a044]>> {cs.active_section}[/]"
            else:
                indicator = ""

            lines.append(
                f"[#efe5c0]{name_padded}[/]  "
                f"{bar}  "
                f"[#a89984]{count:>5}[/]  "
                f"[#a89984]{pct_str:>4}[/]"
                f"{indicator}"
            )

        # Summary bar
        lines.append("")
        global_bar = render_progress_bar(s.progress_fraction, 40)
        lines.append(
            f"{global_bar}  "
            f"[#e0a044]{done}[/][#a89984]/{total} sections[/]  "
            f"[#e0a044]{pct}[/]"
        )

        self.update("\n".join(lines))


# ---------------------------------------------------------------------------
# WorkerPanel widget
# ---------------------------------------------------------------------------


class WorkerPanel(Static):
    """Compact display of active workers.

    Shows one line per in-flight section, formatted as:
    ``WORKERS [3 active]``
    ``[1] HP Inc. · Pricing    [2] ASUS · Integration    [3] idle``
    """

    DEFAULT_CSS = """
    WorkerPanel {
        height: auto;
        width: 100%;
        padding: 0 0;
        margin: 1 0 0 0;
        color: #a89984;
        border-top: solid #3a3a3a;
    }
    """

    def __init__(self, grid: CompetitorGrid, max_display: int = 5) -> None:
        super().__init__("", markup=True)
        self._grid = grid
        self._max_display = max_display

    def on_mount(self) -> None:
        self.set_interval(0.5, self._refresh, name="worker-panel-tick")

    def _refresh(self) -> None:
        active = self._grid.state.active_section_names
        count = len(active)

        if count == 0:
            self.update(
                "[#a89984]WORKERS[/]  [#3a3a3a]none active[/]",
            )
            return

        label = f"[#a89984]WORKERS[/]  [#e0a044]{count}[/] [#a89984]active[/]"
        slots: list[str] = []
        for i, (comp, section) in enumerate(active[: self._max_display]):
            slots.append(
                f"[#3a3a3a]\\[[/][#e0a044]{i + 1}[/][#3a3a3a]\\][/] "
                f"[#efe5c0]{comp}[/] [#3a3a3a]·[/] [#a89984]{section}[/]"
            )

        if count > self._max_display:
            slots.append(
                f"[#3a3a3a]...+{count - self._max_display} more[/]",
            )

        self.update(f"{label}\n" + "  ".join(slots))
