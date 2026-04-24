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
        color: #DDEDC4;
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
            eta_str = f"  [#a59a86]~{eta_min}:{eta_sec:02d} remaining[/]"

        # Header
        lines.append(
            f"[bold #DDEDC4]── {stage} ──[/]  "
            f"[#a59a86]{elapsed}[/]  "
            f"[#DDEDC4]{cost}[/]  "
            f"[#a59a86]Workers:[/] [#DDEDC4]{active_count}[/]"
            f"{eta_str}"
        )

        # Global progress bar
        if total > 0:
            bar = render_progress_bar(s.progress_fraction, 60)
            lines.append(f"{bar}  [#DDEDC4]{done}[/][#a59a86]/{total}[/]  [#DDEDC4]{pct}[/]")
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
        lines.append("[#a59a86]COMPETITORS[/]")

        for cs in self._state.competitors.values():
            from recon.tui.widgets import truncate_name

            name = truncate_name(cs.name, 24)
            frac = f"{cs.completed}/{cs.total}"
            pct = f"{cs.progress_fraction * 100:.0f}%"

            if cs.is_complete:
                icon = "[#DDEDC4]\\u2713[/]"
            elif cs.failed > 0:
                icon = "[#fb4b4b]!![/]"
            elif cs.active_section:
                icon = "[#DDEDC4]▸ [/]"
            else:
                icon = "[#3a3a3a]○ [/]"

            lines.append(f"{icon} [#DDEDC4]{name:24s}[/] [#a59a86]{frac:>5} {pct:>4}[/]")

        if not self._state.competitors:
            lines.append("[#3a3a3a]waiting...[/]")

        return lines

    def _render_right_column(self) -> list[str]:
        """Per-worker compact card, matching the web UI mockup:

            ┌─ SCOUT-01 ─────── RESEARCH ─┐
            │ AcmeCorp · Positioning      │
            │ ▓▓▓▓░░░░ BUSY          [·] │
            └──────────────────────────────┘

        Idle workers collapse to a single dim line so the active
        work stands out visually.
        """
        lines: list[str] = []
        lines.append("[#a59a86]WORKERS[/]")

        spinner_idx = int(time.monotonic() * 4) % len(_SPINNER_FRAMES)
        frame = _SPINNER_FRAMES[spinner_idx]

        card_w = 36  # inner width in visible cells

        for i, w in enumerate(self._workers, start=1):
            scout_id = f"SCOUT-{i:02d}"
            if w.idle:
                lines.append(f"[#3a3a3a]· {scout_id} · idle[/]")
                continue

            # Top border — scout id on the left, role tag on the right,
            # both overlaid on the border rule.
            role = (w.task or "active").upper()[:16]
            title = f"─ {scout_id} "
            role_chunk = f" {role} ─"
            fill = max(1, card_w - len(title) - len(role_chunk))
            lines.append(
                f"[#3a3a3a]┌{title}"
                f"{'─' * fill}{role_chunk}┐[/]"
            )

            # Body row 1 — competitor + current task context.
            target = f"{w.competitor}"[:card_w - 2]
            lines.append(
                f"[#3a3a3a]│[/] [#DDEDC4]{target:<{card_w - 2}}[/] [#3a3a3a]│[/]"
            )

            # Body row 2 — progress bar + BUSY + spinner tail.
            # No per-worker progress model today; show an indeterminate
            # pulse instead (animated via the frame index) so the bar
            # reads as "in flight" without pretending to be accurate.
            pulse_pos = int(time.monotonic() * 4) % 8
            pulse = [
                "\u2593" if abs(pulse_pos - j) < 2 else "\u2591"
                for j in range(8)
            ]
            bar = "".join(pulse)
            elapsed = w.elapsed_str.rjust(6)
            busy = f"[#DDEDC4]{bar}[/] [#a59a86]BUSY[/] {frame}"
            tail_right = f"[#3a3a3a]{elapsed}[/]"
            # Pad between the busy chunk and the tail_right timestamp
            # so the card stays a fixed width.
            visible = len(bar) + 1 + len("BUSY") + 1 + 1 + 1 + len(elapsed)
            pad = max(1, card_w - 2 - visible)
            lines.append(
                f"[#3a3a3a]│[/] {busy}{' ' * pad}{tail_right} [#3a3a3a]│[/]"
            )

            # Bottom border.
            lines.append(f"[#3a3a3a]└{'─' * card_w}┘[/]")

        return lines

    @staticmethod
    def _strip_markup(text: str) -> str:
        """Remove Rich markup tags for length calculation."""
        import re
        return re.sub(r"\[/?[^\]]*\]", "", text)
