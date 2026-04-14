"""Stage-aware run monitor for recon TUI (v2).

Two-column layout:
- Left (30%): Scrollable competitor list with progress fractions
- Right (70%): Worker cards showing per-worker activity

Adapts to pipeline stages: research shows sections, enrich shows
passes, synthesize shows themes, deliver shows distillation.
"""

from __future__ import annotations

import contextlib
import time
from collections import OrderedDict
from dataclasses import dataclass, field

from textual.widgets import Static

from recon.events import (
    CostRecorded,
    DeliveryCompleted,
    DeliveryStarted,
    EnrichmentCompleted,
    EnrichmentStarted,
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
    SynthesisCompleted,
    SynthesisStarted,
    get_bus,
)
from recon.logging import get_logger
from recon.tui.run_monitor import (
    ACTIVE,
    DONE,
    FAILED,
    RETRYING,
    WAITING,
    CompetitorStatus,
    RunMonitorState,
    render_progress_bar,
)

_log = get_logger(__name__)

_MAX_WORKER_CARDS = 8
_LEFT_COL_WIDTH = 32
_WORKER_ACTIVITY_LINES = 3


_SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]


@dataclass
class WorkerCard:
    """Tracks one active worker's current task and recent activity."""

    worker_id: int
    competitor: str = ""
    task: str = ""
    cost: float = 0.0
    activity: list[str] = field(default_factory=list)
    idle: bool = True
    started_at: float = 0.0

    @property
    def elapsed_str(self) -> str:
        if self.idle or self.started_at == 0.0:
            return ""
        seconds = int(time.monotonic() - self.started_at)
        return f"{seconds}s"

    def add_activity(self, line: str) -> None:
        self.activity.append(line)
        if len(self.activity) > _WORKER_ACTIVITY_LINES:
            self.activity = self.activity[-_WORKER_ACTIVITY_LINES:]


class StageMonitor(Static):
    """Two-column run monitor with competitor list + worker cards.

    Subscribes to the engine's event bus. Renders a compact left
    column with per-competitor progress and a right column with
    per-worker activity cards.
    """

    DEFAULT_CSS = """
    StageMonitor {
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
        max_workers: int = 5,
    ) -> None:
        super().__init__("", markup=True)
        self._state = RunMonitorState(
            section_keys=list(section_keys or []),
            max_workers=max_workers,
        )
        if competitor_names:
            for name in competitor_names:
                self._state.get_or_create(name)
        self._workers: list[WorkerCard] = [
            WorkerCard(worker_id=i + 1) for i in range(max_workers)
        ]
        self._subscriber = self._on_event
        self._dirty = True

    @property
    def state(self) -> RunMonitorState:
        return self._state

    def on_mount(self) -> None:
        get_bus().subscribe(self._subscriber)
        self._render_monitor()
        self.set_interval(1.0, self._tick, name="monitor-tick")

    def on_unmount(self) -> None:
        with contextlib.suppress(Exception):
            get_bus().unsubscribe(self._subscriber)

    def _tick(self) -> None:
        if self._dirty or self._state.started_at is not None:
            self._render_monitor()

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
            self._assign_worker(event.competitor_name, event.section_key)
            self._dirty = True
        elif isinstance(event, SectionResearched):
            cs = self._state.get_or_create(event.competitor_name)
            cs.sections[event.section_key] = DONE
            self._release_worker(event.competitor_name, event.section_key)
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
            self._release_worker(event.competitor_name, event.section_key)
            self._dirty = True
        elif isinstance(event, EnrichmentStarted):
            self._assign_worker(event.competitor_name, event.pass_name)
            self._dirty = True
        elif isinstance(event, EnrichmentCompleted):
            self._release_worker(event.competitor_name, event.pass_name)
            self._dirty = True
        elif isinstance(event, SynthesisStarted):
            self._assign_worker(event.theme_label, "writing")
            self._dirty = True
        elif isinstance(event, SynthesisCompleted):
            self._release_worker(event.theme_label, "writing")
            self._dirty = True
        elif isinstance(event, DeliveryStarted):
            self._assign_worker(event.theme_label, "distilling")
            self._dirty = True
        elif isinstance(event, DeliveryCompleted):
            self._release_worker(event.theme_label, "distilling")
            self._dirty = True
        elif isinstance(event, CostRecorded):
            self._state.total_cost += event.cost_usd
            self._dirty = True
        elif isinstance(event, (RunCompleted, RunFailed, RunCancelled)):
            self._state.current_stage = ""
            for w in self._workers:
                w.idle = True
                w.competitor = ""
                w.task = ""
            self._dirty = True

        if self._dirty:
            self._render_monitor()

    def _assign_worker(self, competitor: str, task: str) -> None:
        for w in self._workers:
            if w.idle:
                w.idle = False
                w.competitor = competitor
                w.task = task
                w.cost = 0.0
                w.started_at = time.monotonic()
                w.activity = [f"Calling API..."]
                return

    def _release_worker(self, competitor: str, task: str) -> None:
        for w in self._workers:
            if not w.idle and w.competitor == competitor and w.task == task:
                w.idle = True
                w.competitor = ""
                w.task = ""
                return

    def _render_monitor(self) -> None:
        self._dirty = False
        s = self._state

        elapsed = s.elapsed_str
        cost = f"${s.total_cost:.2f}"
        stage = s.current_stage.upper() if s.current_stage else "MONITOR"
        total = s.total_sections
        done = s.completed_sections
        pct = f"{s.progress_fraction * 100:.0f}%" if total > 0 else "0%"
        active_count = sum(1 for w in self._workers if not w.idle)

        lines: list[str] = []

        # ETA calculation
        eta_str = ""
        if done > 0 and s.started_at is not None:
            elapsed_secs = time.monotonic() - s.started_at
            remaining = total - done
            secs_per_task = elapsed_secs / done
            eta_secs = int(secs_per_task * remaining)
            eta_min, eta_sec = divmod(eta_secs, 60)
            eta_str = f"  [#a89984]~{eta_min}:{eta_sec:02d} remaining[/]"

        # Header
        lines.append(
            f"[bold #e0a044]── {stage} ──[/]  "
            f"[#a89984]{elapsed}[/]  "
            f"[#e0a044]{cost}[/]  "
            f"[#a89984]Workers:[/] [#e0a044]{active_count}[/]"
            f"{eta_str}"
        )

        # Global progress bar
        if total > 0:
            bar = render_progress_bar(s.progress_fraction, 60)
            lines.append(f"{bar}  [#e0a044]{done}[/][#a89984]/{total}[/]  [#e0a044]{pct}[/]")
        lines.append("")

        # Two columns: left = competitors, right = worker cards
        left_lines = self._render_left_column()
        right_lines = self._render_right_column()

        # Interleave columns
        max_rows = max(len(left_lines), len(right_lines))
        left_w = _LEFT_COL_WIDTH

        for i in range(max_rows):
            left = left_lines[i] if i < len(left_lines) else ""
            right = right_lines[i] if i < len(right_lines) else ""

            visible_len = len(self._strip_markup(left))
            padding = max(0, left_w - visible_len)
            lines.append(f"{left}{' ' * padding} [#3a3a3a]│[/] {right}")

        self.update("\n".join(lines))

    def _render_left_column(self) -> list[str]:
        lines: list[str] = []
        lines.append("[#a89984]COMPETITORS[/]")

        for cs in self._state.competitors.values():
            from recon.tui.widgets import truncate_name

            name = truncate_name(cs.name, 24)
            frac = f"{cs.completed}/{cs.total}"
            pct = f"{cs.progress_fraction * 100:.0f}%"

            if cs.is_complete:
                icon = "[#98971a]\\u2713[/]"
            elif cs.failed > 0:
                icon = "[#cc241d]!![/]"
            elif cs.active_section:
                icon = "[#e0a044]▸ [/]"
            else:
                icon = "[#3a3a3a]○ [/]"

            lines.append(f"{icon} [#efe5c0]{name:24s}[/] [#a89984]{frac:>5} {pct:>4}[/]")

        if not self._state.competitors:
            lines.append("[#3a3a3a]waiting...[/]")

        return lines

    def _render_right_column(self) -> list[str]:
        lines: list[str] = []
        lines.append("[#a89984]WORKERS[/]")

        spinner_idx = int(time.monotonic() * 4) % len(_SPINNER_FRAMES)
        frame = _SPINNER_FRAMES[spinner_idx]

        for w in self._workers:
            if w.idle:
                lines.append(
                    f"[#3a3a3a]· idle[/]"
                )
            else:
                elapsed = w.elapsed_str
                lines.append(
                    f"[#e0a044]▸[/] "
                    f"[#efe5c0]{w.competitor}[/] [#3a3a3a]·[/] "
                    f"[#a89984]{w.task}[/]  "
                    f"[#3a3a3a]{elapsed}[/]"
                )
                if w.activity:
                    last = w.activity[-1]
                    lines.append(
                        f"  [#3a3a3a]{last}[/]  [#e0a044]{frame}[/]"
                    )

        return lines

    @staticmethod
    def _strip_markup(text: str) -> str:
        """Remove Rich markup tags for length calculation."""
        import re
        return re.sub(r"\[/?[^\]]*\]", "", text)
