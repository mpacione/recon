"""Reusable formatters for the recon TUI.

This used to be a collection of widget classes (StatusPanel,
CompetitorTable, ProgressBar, ThemeCurationPanel, RunMonitorPanel)
plus three formatting helpers. Every screen ended up rendering its
own widgets directly with Static, so the classes were never adopted.
They were removed as part of the Option U cleanup. The three
formatting helpers are still used by RunScreen, the curation tests,
and the monitor tests, so they remain here.
"""

from __future__ import annotations

from recon.tui.models.curation import ThemeCurationModel  # noqa: TCH001
from recon.tui.models.monitor import RunMonitorModel, WorkerStatus  # noqa: TCH001


def format_theme_list(model: ThemeCurationModel) -> list[str]:
    """Format the theme curation model as displayable lines."""
    lines: list[str] = []
    for i, entry in enumerate(model.entries):
        checkbox = "[x]" if entry.enabled else "[ ]"
        lines.append(
            f"{checkbox} {i + 1}. {entry.label}  "
            f"({entry.chunk_count} chunks, {entry.evidence_strength})"
        )
    return lines


def format_worker_list(model: RunMonitorModel) -> list[str]:
    """Format worker status lines for the run monitor."""
    lines: list[str] = []
    for w in model.workers:
        status_display = w.status.value
        if w.status == WorkerStatus.COMPLETE:
            status_display = "Y complete"
        elif w.status == WorkerStatus.FAILED:
            status_display = "X failed"
        lines.append(f"  {w.worker_id}  {w.competitor} ... {status_display}")
    return lines


def format_progress_bar(progress: float, width: int = 40) -> str:
    """Format an ASCII progress bar string."""
    progress = max(0.0, min(1.0, progress))
    filled = int(progress * width)
    empty = width - filled
    pct = f"{progress * 100:.0f}%"
    return f"[{'=' * filled}{'-' * empty}] {pct}"
