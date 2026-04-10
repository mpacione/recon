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

from pathlib import Path

from recon.tui.models.curation import ThemeCurationModel  # noqa: TCH001
from recon.tui.models.monitor import RunMonitorModel, WorkerStatus  # noqa: TCH001


def humanize_path(path: Path | str, max_width: int = 64) -> str:
    """Render ``path`` as a short, terminal-friendly string.

    - Replaces ``$HOME`` with ``~`` if the path lives under the home dir.
    - Collapses macOS ``/private/var/folders/...`` temp dirs to
      ``$TMP``.
    - If the result still exceeds ``max_width``, drops middle directory
      components and replaces them with ``…``, keeping the leading
      anchor (``~`` / ``/`` / ``$TMP``) and the last 1-2 path segments.
    """
    raw = str(path)

    home = str(Path.home())
    if raw == home or raw.startswith(home + "/"):
        raw = "~" + raw[len(home):]

    # macOS temp dirs commonly look like /var/folders/zd/.../T/...
    # Collapse to $TMP for legibility.
    for prefix in ("/private/var/folders/", "/var/folders/", "/private/tmp/", "/tmp/"):
        if raw.startswith(prefix):
            tail = raw[len(prefix):]
            # Strip the noisy zd/rdn139.../T/ leading segments
            parts = tail.split("/")
            keep_from = 0
            for i, part in enumerate(parts):
                if part == "T":
                    keep_from = i + 1
                    break
            tail = "/".join(parts[keep_from:]) if keep_from else tail
            raw = "$TMP/" + tail
            break

    if len(raw) <= max_width:
        return raw

    # Still too long: collapse middle segments
    segments = raw.split("/")
    if len(segments) <= 3:
        return raw  # nothing useful to collapse
    head = segments[0] or "/"
    last = "/".join(segments[-2:])
    candidate = f"{head}/…/{last}"
    if len(candidate) <= max_width:
        return candidate
    # Last resort: just keep the leaf
    return f"{head}/…/{segments[-1]}"


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


def format_progress_bar(
    progress: float,
    width: int = 40,
    state: str = "running",
) -> str:
    """Format an ASCII progress bar string.

    ``state`` controls the visual treatment so a stopped/errored bar
    looks distinct from a happy in-progress one. Valid states:
    ``idle`` (empty bar, white), ``running`` (orange fill), ``done``
    (green fill), ``paused`` (yellow fill), ``stopping`` (gray fill),
    ``cancelled`` / ``error`` (red fill, X-marks instead of dashes).

    The outer brackets are escaped (``\\[`` / ``\\]``) so Textual
    markup parsing doesn't try to interpret them as color tags.
    """
    progress = max(0.0, min(1.0, progress))
    filled = int(progress * width)
    empty = width - filled
    pct = f"{progress * 100:.0f}%"

    if state in ("error", "cancelled"):
        bar = f"[#cc241d]{'=' * filled}{'X' * empty}[/]"
        pct_colored = f"[#cc241d]{pct}[/]"
    elif state == "stopping":
        bar = f"[#a89984]{'=' * filled}[/][#3a3a3a]{'-' * empty}[/]"
        pct_colored = f"[#a89984]{pct}[/]"
    elif state == "paused":
        bar = f"[#d79921]{'=' * filled}[/][#3a3a3a]{'-' * empty}[/]"
        pct_colored = f"[#d79921]{pct}[/]"
    elif state == "done":
        bar = f"[#98971a]{'=' * width}[/]"
        pct_colored = f"[#98971a]{pct}[/]"
    elif state == "idle":
        bar = f"[#3a3a3a]{'-' * width}[/]"
        pct_colored = f"[#a89984]{pct}[/]"
    else:  # running
        bar = f"[#e0a044]{'=' * filled}[/][#3a3a3a]{'-' * empty}[/]"
        pct_colored = f"[#e0a044]{pct}[/]"

    return f"\\[{bar}\\] {pct_colored}"
