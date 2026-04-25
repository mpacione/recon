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

from rich.text import Text
from textual.message import Message
from textual.widgets import Static

from recon.tui.models.curation import ThemeCurationModel  # noqa: TCH001
from recon.tui.models.monitor import RunMonitorModel, WorkerStatus  # noqa: TCH001


def button_label(label: str, hotkey: str | None = None) -> Text:
    """Return a literal button label with an optional bracketed hotkey."""
    if hotkey:
        return Text(f"{label} [{hotkey}]")
    return Text(label)


# ---------------------------------------------------------------------------
# Shared selection widgets
# ---------------------------------------------------------------------------


class ChecklistItem(Static):
    """Compact 1-line toggleable checkbox row.

    Click to toggle. Amber [x] when selected, dim [ ] when not.
    Emits a ``Toggled`` message on click.
    """

    class Toggled(Message):
        def __init__(self, index: int, selected: bool) -> None:
            super().__init__()
            self.index = index
            self.selected = selected

    DEFAULT_CSS = """
    ChecklistItem {
        height: 1;
        width: 100%;
        padding: 0 1;
    }
    ChecklistItem:hover {
        background: #2e2b27;
    }
    """

    def __init__(
        self,
        label: str,
        description: str = "",
        selected: bool = False,
        index: int = 0,
    ) -> None:
        self._label = label
        self._description = description
        self._selected = selected
        self._index = index
        super().__init__()

    def render(self) -> str:
        # v4 glyphs: filled square (▣) for selected, dashed square (▢)
        # for empty — mirrors the web UI's Lucide square-check /
        # square-dashed pair so both surfaces read identically.
        marker = "[#DDEDC4]\u25a3[/]" if self._selected else "[#3a3a3a]\u25a2[/]"
        desc = f"  [#3a3a3a]{self._description}[/]" if self._description else ""
        color = "#DDEDC4" if self._selected else "#a59a86"
        return f"{marker} [{color}]{self._label}[/]{desc}"

    @property
    def selected(self) -> bool:
        return self._selected

    def toggle(self) -> None:
        self._selected = not self._selected
        self.refresh()

    def on_click(self) -> None:
        self.toggle()
        self.post_message(self.Toggled(self._index, self._selected))


class RadioItem(Static):
    """Compact 1-line radio option row.

    Click to select. Amber bullet when selected, dim circle when not.
    Emits a ``Selected`` message on click.
    """

    class Selected(Message):
        def __init__(self, index: int) -> None:
            super().__init__()
            self.index = index

    DEFAULT_CSS = """
    RadioItem {
        height: 1;
        width: 100%;
        padding: 0 1;
    }
    RadioItem:hover {
        background: #2e2b27;
    }
    """

    def __init__(
        self,
        label: str,
        selected: bool = False,
        index: int = 0,
    ) -> None:
        self._label = label
        self._selected = selected
        self._index = index
        super().__init__()

    def render(self) -> str:
        # v4 glyphs: filled square for selected, dashed square for not.
        # Mirrors the web UI's radio rendering (which uses the same
        # square-check / square-dashed pair as the checkbox primitive
        # so the whole interface reads as one consistent vocabulary).
        marker = "[#DDEDC4]\u25a3[/]" if self._selected else "[#3a3a3a]\u25a2[/]"
        color = "#DDEDC4" if self._selected else "#a59a86"
        return f"{marker} [{color}]{self._label}[/]"

    @property
    def selected(self) -> bool:
        return self._selected

    def set_selected(self, value: bool) -> None:
        self._selected = value
        self.refresh()

    def on_click(self) -> None:
        self.post_message(self.Selected(self._index))


def truncate_name(name: str, max_width: int = 24) -> str:
    """Truncate a competitor name smartly.

    Drops parenthetical suffixes first ("Amazon Q Developer (formerly
    CodeWhisperer)" → "Amazon Q Developer"), then truncates with
    ellipsis if still too long.
    """
    import re

    if len(name) <= max_width:
        return name

    # Drop parenthetical suffix first
    short = re.sub(r"\s*\(.*\)\s*$", "", name)
    if len(short) <= max_width:
        return short

    return short[: max_width - 1] + "\u2026"


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
    """Format a v4 ``▓▒░`` shaded-block progress bar.

    ``state`` controls the visual treatment. Matches the web + CLI
    bars: full cells are ``▓``, a single half-cell ``▒`` at the fill
    boundary, ``░`` for empty. Errors substitute ``X`` for empties so
    a broken run reads distinctly.

    Valid states: ``idle``, ``running``, ``done``, ``paused``,
    ``stopping``, ``cancelled``, ``error``.

    The outer brackets are escaped (``\\[`` / ``\\]``) so Textual
    markup parsing doesn't try to interpret them as color tags.
    """
    progress = max(0.0, min(1.0, progress))
    exact = progress * width
    filled = int(exact)
    half = 1 if (exact - filled) >= 0.5 else 0
    empty = max(0, width - filled - half)
    pct = f"{progress * 100:.0f}%"

    FULL, HALF, DOT = "▓", "▒", "░"

    if state in ("error", "cancelled"):
        bar = f"[#fb4b4b]{FULL * filled}{HALF * half}{'X' * empty}[/]"
        pct_colored = f"[#fb4b4b]{pct}[/]"
    elif state == "stopping":
        bar = f"[#a59a86]{FULL * filled}{HALF * half}[/][#3a3a3a]{DOT * empty}[/]"
        pct_colored = f"[#a59a86]{pct}[/]"
    elif state == "paused":
        bar = f"[#a59a86]{FULL * filled}{HALF * half}[/][#3a3a3a]{DOT * empty}[/]"
        pct_colored = f"[#a59a86]{pct}[/]"
    elif state == "done":
        bar = f"[#DDEDC4]{FULL * width}[/]"
        pct_colored = f"[#DDEDC4]{pct}[/]"
    elif state == "idle":
        bar = f"[#3a3a3a]{DOT * width}[/]"
        pct_colored = f"[#787266]{pct}[/]"
    else:  # running
        bar = f"[#DDEDC4]{FULL * filled}{HALF * half}[/][#3a3a3a]{DOT * empty}[/]"
        pct_colored = f"[#DDEDC4]{pct}[/]"

    return f"\\[{bar}\\] {pct_colored}"
