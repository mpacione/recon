"""Stage-aware run monitor for recon TUI.

Stacked layout:
- Top: run header and global progress
- Middle: worker cards packed into horizontal rows
- Bottom: competitor roster with progress and current task

The monitor lives inside the screen body, so the competitor roster
scrolls naturally with the run screen instead of fighting a faux
two-column ASCII layout.
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
    """Stacked run monitor with worker rows above the competitor list."""

    DEFAULT_CSS = """
    StageMonitor {
        height: auto;
        width: 100%;
        padding: 0 0;
        color: #DDEDC4;
        overflow-x: hidden;
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

        lines.extend(self._render_workers_section())
        lines.append("")
        lines.extend(self._render_competitor_section())

        self.update("\n".join(lines))

    def _render_competitor_section(self) -> list[str]:
        lines: list[str] = []
        lines.append(
            f"[#a59a86]COMPETITORS[/]  [#787266]·[/]  "
            f"[#DDEDC4]{len(self._state.competitors)}[/] [#787266]targets[/]"
        )

        for cs in self._state.competitors.values():
            from recon.tui.widgets import truncate_name

            name = truncate_name(cs.name, 22)
            frac = f"{cs.completed}/{cs.total}"
            pct = f"{cs.progress_fraction * 100:.0f}%"
            current_task = self._current_task_for(cs.name)

            if cs.is_complete:
                icon = "[#DDEDC4]\\u2713[/]"
                status = "[#787266]COMPLETE[/]"
            elif cs.failed > 0:
                icon = "[#fb4b4b]!![/]"
                status = "[#fb4b4b]ERROR[/]"
            elif current_task:
                icon = "[#DDEDC4]▸ [/]"
                status = f"[#DDEDC4]{str(current_task).upper()}[/]"
            elif cs.active_section:
                icon = "[#DDEDC4]▸ [/]"
                status = f"[#DDEDC4]{str(cs.active_section).upper()}[/]"
            else:
                icon = "[#3a3a3a]○ [/]"
                status = "[#787266]READY[/]"

            bar = render_progress_bar(cs.progress_fraction, 20)
            lines.append(
                f"{icon} [#DDEDC4]{name:<22s}[/] {bar} "
                f"[#DDEDC4]{frac:>5}[/] [#a59a86]{pct:>4}[/] {status}"
            )

        if not self._state.competitors:
            lines.append("[#3a3a3a]waiting...[/]")

        return lines

    def _render_workers_section(self) -> list[str]:
        lines: list[str] = []
        lines.append(
            f"[#a59a86]AGENTS[/]  [#787266]·[/]  "
            f"[#DDEDC4]{len(self._workers)}[/] [#787266]workers[/]"
        )

        cards = [self._render_worker_card(i, worker) for i, worker in enumerate(self._workers, start=1)]
        lines.extend(self._pack_card_rows(cards))
        return lines

    def _render_worker_card(self, index: int, worker: WorkerCard) -> list[str]:
        from recon.tui.widgets import truncate_name

        spinner_idx = int(time.monotonic() * 4) % len(_SPINNER_FRAMES)
        frame = _SPINNER_FRAMES[spinner_idx]
        card_w = 20
        scout_id = f"SCOUT-{index:02d}"

        if worker.idle:
            title = f"[#a59a86]{scout_id:<20}[/]"
            line1 = f"[#787266]{'idle':<20}[/]"
            line2 = f"[#3a3a3a]{'waiting for task':<20}[/]"
            line3 = f"{render_progress_bar(0.0, 8)} [#787266]IDLE[/]"
        else:
            title = f"[#a59a86]{scout_id:<20}[/]"
            target = truncate_name(worker.competitor, 20)
            task = str(worker.task or "active").upper()[:10]
            elapsed = worker.elapsed_str or ""
            pulse_pos = int(time.monotonic() * 4) % 8
            pulse = "".join(
                "\u2593" if abs(pulse_pos - j) < 2 else "\u2591"
                for j in range(8)
            )
            line1 = f"[#DDEDC4]{target:<20}[/]"
            task_line = f"{task} {elapsed}".strip()
            line2 = f"[#a59a86]{task_line:<20}[/]"
            line3 = f"[#DDEDC4]{pulse}[/] [#a59a86]BUSY {frame}[/]"

        return [
            f"[#3a3a3a]┌{'─' * card_w}┐[/]",
            f"[#3a3a3a]│[/]{self._pad_markup(title, card_w)}[#3a3a3a]│[/]",
            f"[#3a3a3a]│[/]{self._pad_markup(line1, card_w)}[#3a3a3a]│[/]",
            f"[#3a3a3a]│[/]{self._pad_markup(line2, card_w)}[#3a3a3a]│[/]",
            f"[#3a3a3a]│[/]{self._pad_markup(line3, card_w)}[#3a3a3a]│[/]",
            f"[#3a3a3a]└{'─' * card_w}┘[/]",
        ]

    def _pack_card_rows(self, cards: list[list[str]]) -> list[str]:
        if not cards:
            return ["[#3a3a3a]waiting...[/]"]

        card_width = len(self._strip_markup(cards[0][0]))
        gap = 2
        available_width = max(80, self.size.width or 120)
        columns = max(1, min(len(cards), (available_width + gap) // (card_width + gap)))
        lines: list[str] = []

        for start in range(0, len(cards), columns):
            row_cards = cards[start:start + columns]
            row_height = max(len(card) for card in row_cards)
            for line_idx in range(row_height):
                row_parts = []
                for card in row_cards:
                    row_parts.append(card[line_idx])
                lines.append((" " * gap).join(row_parts))
            if start + columns < len(cards):
                lines.append("")

        return lines

    def _current_task_for(self, competitor_name: str) -> str | None:
        for worker in self._workers:
            if not worker.idle and worker.competitor == competitor_name:
                return worker.task
        return None

    @classmethod
    def _pad_markup(cls, text: str, width: int) -> str:
        visible_len = len(cls._strip_markup(text))
        return text + (" " * max(0, width - visible_len))

    @staticmethod
    def _strip_markup(text: str) -> str:
        """Remove Rich markup tags for length calculation."""
        import re
        return re.sub(r"\[/?[^\]]*\]", "", text)
