"""Results screen for recon TUI (Screen 9).

Post-run summary showing stats, executive summary preview,
output file paths with keybinds to open.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static

from recon.logging import get_logger

_log = get_logger(__name__)

_PREVIEW_LINES = 6


class ResultsScreen(ModalScreen[None]):
    """Post-run results with exec summary preview and file links."""

    BINDINGS = [
        Binding("v", "view_summary", "View full summary", show=False),
        Binding("o", "open_folder", "Open output folder", show=False),
        Binding("b", "back", "Back", show=False),
        Binding("escape", "back", "Back", show=False),
        Binding("q", "quit_app", "Quit", show=False),
    ]

    DEFAULT_CSS = """
    ResultsScreen {
        align: center middle;
    }
    #results-container {
        width: 90;
        max-height: 38;
        background: #1d1d1d;
        border: round #3a3a3a;
        padding: 1 2;
        overflow-y: auto;
    }
    """

    def __init__(
        self,
        workspace_root: Path,
        competitor_count: int,
        section_count: int,
        theme_count: int,
        total_cost: float,
        elapsed: str,
    ) -> None:
        super().__init__()
        self._workspace_root = workspace_root
        self._competitor_count = competitor_count
        self._section_count = section_count
        self._theme_count = theme_count
        self._total_cost = total_cost
        self._elapsed = elapsed

    def compose(self) -> ComposeResult:
        with Vertical(id="results-container"):
            yield Static(self._render_content())

    def _render_content(self) -> str:
        lines = [
            f"[bold #e0a044]── RESEARCH COMPLETE ──[/]  "
            f"[#a89984]{self._elapsed}[/]  "
            f"[#e0a044]${self._total_cost:.2f}[/]",
            "",
            f"[#efe5c0]{self._competitor_count} competitors researched[/] · "
            f"[#efe5c0]{self._section_count} sections each[/] · "
            f"[#efe5c0]{self._theme_count} themes synthesized[/]",
            "",
        ]

        # Executive summary preview
        summary_path = self._workspace_root / "executive_summary.md"
        if summary_path.exists():
            try:
                content = summary_path.read_text()
                preview_lines = [
                    l for l in content.splitlines()
                    if l.strip() and not l.startswith("#")
                ][:_PREVIEW_LINES]
                if preview_lines:
                    lines.append(
                        "[bold #e0a044]── EXECUTIVE SUMMARY (preview) ──[/]"
                    )
                    for pl in preview_lines:
                        lines.append(f"[#efe5c0]{pl}[/]")
                    if len(content.splitlines()) > _PREVIEW_LINES + 2:
                        lines.append(
                            "[#a89984]...truncated — press v to view full[/]"
                        )
                    lines.append("")
            except Exception:
                pass

        # Output files
        output_files = self._collect_files()
        if output_files:
            lines.append("[bold #e0a044]── OUTPUT FILES ──[/]")
            for i, (label, path) in enumerate(output_files):
                lines.append(
                    f"  [#a89984]{i + 1}.[/] [#efe5c0]{label:30s}[/]  "
                    f"[#3a3a3a]{path}[/]"
                )
            lines.append("")

        lines.append(
            "[#a89984]v[/] [#e0a044]view summary[/] · "
            "[#a89984]o[/] [#e0a044]open folder[/] · "
            "[#a89984]b[/] [#e0a044]back to dashboard[/] · "
            "[#a89984]q[/] [#e0a044]quit[/]"
        )

        return "\n".join(lines)

    def _collect_files(self) -> list[tuple[str, str]]:
        files: list[tuple[str, str]] = []

        summary_path = self._workspace_root / "executive_summary.md"
        if summary_path.exists():
            files.append(("Executive Summary", str(summary_path)))

        themes_dir = self._workspace_root / "themes"
        if themes_dir.is_dir():
            for f in sorted(themes_dir.glob("*.md")):
                label = f"Theme: {f.stem.replace('_', ' ').title()}"
                files.append((label, str(f)))

        distilled_dir = self._workspace_root / "themes" / "distilled"
        if distilled_dir.is_dir():
            for f in sorted(distilled_dir.glob("*.md")):
                label = f"Distilled: {f.stem.replace('_', ' ').title()}"
                files.append((label, str(f)))

        return files

    def action_view_summary(self) -> None:
        summary_path = self._workspace_root / "executive_summary.md"
        if not summary_path.exists():
            self.app.notify("No executive summary found", severity="warning")
            return
        editor = _get_editor()
        try:
            subprocess.Popen([editor, str(summary_path)])  # noqa: S603
        except Exception as exc:
            self.app.notify(f"Could not open editor: {exc}", severity="error")

    def action_open_folder(self) -> None:
        try:
            if sys.platform == "darwin":
                subprocess.Popen(["open", str(self._workspace_root)])  # noqa: S603, S607
            else:
                subprocess.Popen(["xdg-open", str(self._workspace_root)])  # noqa: S603, S607
        except Exception as exc:
            self.app.notify(f"Could not open folder: {exc}", severity="error")

    def action_back(self) -> None:
        self.dismiss(None)

    def action_quit_app(self) -> None:
        self.app.exit()


def _get_editor() -> str:
    import os
    return os.environ.get("EDITOR", "less")
