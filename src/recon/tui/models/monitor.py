"""Run monitor data model for recon TUI.

Tracks live pipeline execution state: current phase, section progress,
per-worker status, cost accumulation, activity feed, and errors.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

_MAX_ACTIVITY = 50


class WorkerStatus(StrEnum):
    IDLE = "idle"
    SEARCHING = "searching"
    WRITING = "writing"
    VALIDATING = "validating"
    RETRYING = "retrying"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class WorkerState:
    worker_id: str
    competitor: str
    status: WorkerStatus


@dataclass
class RunMonitorModel:
    """Live state of a pipeline run for TUI rendering."""

    run_id: str
    total_competitors: int
    total_sections: int

    current_phase: str = "idle"
    current_section: str = ""
    section_index: int = 0
    _total_sections_in_phase: int = 0

    progress: float = 0.0
    cost_usd: float = 0.0

    workers: list[WorkerState] = field(default_factory=list)
    activity: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def set_phase(
        self,
        phase: str,
        section: str = "",
        section_index: int = 0,
        total_sections: int = 0,
    ) -> None:
        self.current_phase = phase
        self.current_section = section
        self.section_index = section_index
        self._total_sections_in_phase = total_sections

    def update_progress(self, completed: int, total: int) -> None:
        self.progress = completed / total if total > 0 else 0.0

    def update_worker(
        self,
        worker_id: str,
        competitor: str,
        status: WorkerStatus,
    ) -> None:
        for w in self.workers:
            if w.worker_id == worker_id:
                w.competitor = competitor
                w.status = status
                return

        self.workers.append(WorkerState(
            worker_id=worker_id,
            competitor=competitor,
            status=status,
        ))

    def add_activity(self, message: str) -> None:
        self.activity.append(message)
        if len(self.activity) > _MAX_ACTIVITY:
            self.activity = self.activity[-_MAX_ACTIVITY:]

    def add_error(self, message: str) -> None:
        self.errors.append(message)

    def record_cost(self, amount_usd: float) -> None:
        self.cost_usd += amount_usd

    @property
    def active_worker_count(self) -> int:
        active_statuses = {WorkerStatus.SEARCHING, WorkerStatus.WRITING, WorkerStatus.VALIDATING, WorkerStatus.RETRYING}
        return sum(1 for w in self.workers if w.status in active_statuses)

    def summary_line(self) -> str:
        pct = f"{self.progress * 100:.0f}%"
        parts = [f"Phase: {self.current_phase.capitalize()}"]
        if self.current_section:
            parts.append(f"Section: {self.current_section.capitalize()}")
        parts.append(f"Progress: {pct}")
        return "  ".join(parts)
