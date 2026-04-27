"""ResultsScreen — the v4 OUTPUT tab.

Two-pane layout mirroring the web UI's OUTPUT tab:

- **Left**: grouped file browser for dossiers, summaries, and themes.
- **Right**: Markdown preview of the currently-selected file, with
  a reveal-in-Finder action and a fallback stats panel for empty
  workspaces.

Keyboard contract (matches the web UI and the sibling tabs):

    ↑ / ↓ / j / k  walk files
    Enter           open / reveal in Finder
    l               open the workspace folder in Finder
    esc / b         back to dashboard
"""

from __future__ import annotations

import contextlib
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Markdown, Static

from recon.logging import get_logger
from recon.tui.shell import ReconScreen
from recon.tui.widgets import action_button

_log = get_logger(__name__)


@dataclass(frozen=True)
class _FileEntry:
    """One file in the tree. Pre-computed so rendering + preview
    lookup both use the same list with a single index.
    """

    label: str        # display label ("executive_summary.md")
    path: Path        # absolute path on disk
    group: str        # "competitors" / "output" / "themes" / "themes/distilled"


class ResultsScreen(ReconScreen):
    """Post-run results — v4 OUTPUT tab."""

    tab_key = "output"

    BINDINGS = [
        # File nav — ↑↓ + j/k walk the tree.
        Binding("j", "cursor_down", "down", show=False),
        Binding("k", "cursor_up", "up", show=False),
        Binding("down", "cursor_down", "down", show=False),
        Binding("up", "cursor_up", "up", show=False),
        # Enter reveals the selected file in Finder (the web UI calls
        # this "REVEAL [↲]"). `l` opens the workspace root instead —
        # useful when you want to browse everything, not just one file.
        Binding("enter", "reveal", "reveal", show=False),
        Binding("space", "next", "next", show=False),
        Binding("l", "open_folder", "open dir", show=False),
        Binding("v", "view_summary", "View full summary", show=False),
        Binding("b", "back", "Back", show=False),
        Binding("escape", "back", "Back", show=False),
    ]

    keybind_hints = (
        "[#DDEDC4]↑↓[/] nav · [#DDEDC4]↲[/] reveal · "
        "[#DDEDC4]l[/] open dir · [#DDEDC4]space[/] next · [#DDEDC4]esc[/] back · [#DDEDC4]q[/] quit"
    )

    DEFAULT_CSS = """
    ResultsScreen {
        background: #000000;
    }
    #results-container {
        width: 100%;
        height: 1fr;
        padding: 0;
    }
    #results-card {
        height: 1fr;
    }
    #results-panes {
        height: 1fr;
        layout: horizontal;
    }
    #results-tree {
        width: 38;
        height: 100%;
        padding: 0 1;
        border-right: solid #3a3a3a;
        overflow-y: auto;
        scrollbar-background: #000000;
        scrollbar-color: #6B7866;
        scrollbar-color-hover: #6B7866;
        scrollbar-color-active: #6B7866;
    }
    #results-tree .is-cursor {
        background: #2e2b27;
        color: #DDEDC4;
    }
    #results-preview {
        width: 1fr;
        height: 100%;
        padding: 0 1 0 2;
        overflow-y: auto;
        scrollbar-background: #000000;
        scrollbar-color: #6B7866;
        scrollbar-color-hover: #6B7866;
        scrollbar-color-active: #6B7866;
    }
    #results-preview-empty {
        height: auto;
        color: #787266;
        padding: 1 0;
    }
    #results-actions {
        dock: bottom;
        height: 3;
        padding: 0 2;
        layout: horizontal;
        background: #000000;
    }
    #results-actions Button {
        margin: 0 1 0 0;
    }
    Markdown#results-markdown {
        padding: 0;
        background: #000000;
        scrollbar-background: #000000;
        scrollbar-color: #6B7866;
        scrollbar-color-hover: #6B7866;
        scrollbar-color-active: #6B7866;
    }
    """

    show_log_pane = False
    show_activity_feed = False
    show_run_status_bar = False
    # The left OUTPUT pane is narrow once padding + the divider are
    # accounted for. Keep labels conservative so the ASCII tree never
    # wraps and breaks the branch rendering.
    _TREE_LABEL_WIDTH = 24

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
        self._files: list[_FileEntry] = self._collect_files()
        # Default selection prefers the executive summary so users
        # land on the headline artifact without scrolling.
        self._cursor: int = self._default_cursor_index()

    # -- compose ----------------------------------------------------------

    def compose_body(self) -> ComposeResult:
        from recon.tui.primitives import Card

        files_meta = (
            f"{len(self._files)} file{'s' if len(self._files) != 1 else ''}"
            f"   ·   {self._elapsed}   ·   ${self._total_cost:.2f}"
        )
        if not self._files:
            files_meta = (
                f"no outputs yet   ·   "
                f"{self._competitor_count} competitors · "
                f"{self._section_count} sections"
            )

        with Vertical(id="results-container"):
            with Card(title="OUTPUTS", meta=files_meta, id="results-card"):
                with Horizontal(id="results-panes"):
                    with Vertical(id="results-tree"):
                        yield from self._compose_tree_rows()
                    with Vertical(id="results-preview"):
                        yield from self._compose_preview()

        with Horizontal(id="results-actions"):
            yield action_button("BACK", "Esc", button_id="btn-back")
            yield action_button("OPEN FOLDER", "L", button_id="btn-open-folder", variant="primary")
            yield action_button("VIEW SUMMARY", "V", button_id="btn-view-summary")
            yield Static("", classes="action-spacer")
            yield action_button("NEXT", "Space", button_id="btn-next")

    def _compose_tree_rows(self) -> ComposeResult:
        if not self._files:
            yield Static(
                "[#787266]No outputs yet.[/]\n\n"
                "[#a59a86]Go to[/] [#DDEDC4]AGENTS[/] [#a59a86]and run the workflow first.[/]",
            )
            return

        # Workspace name at the tree root — same aesthetic as the web
        # UI's tree prefix rendering, but keep the list itself simple
        # so long filenames don't destroy ASCII branch alignment.
        root_label = self._truncate_tree_label(f"{self._workspace_root.name}/")
        yield Static(f"[#DDEDC4]{root_label}[/]")

        prev_group = ""
        for i, entry in enumerate(self._files):
            if entry.group != prev_group:
                yield Static(f"[#787266]  {entry.group}/[/]")
                prev_group = entry.group
            yield Static(
                self._render_tree_row(i, selected=(i == self._cursor)),
                id=f"tree-row-{i}",
            )

    def _render_tree_row(self, index: int, selected: bool) -> str:
        entry = self._files[index]
        marker = "[#DDEDC4]▌[/]" if selected else "[#3a3a3a] [/]"
        name = self._truncate_tree_label(entry.label)
        color = "#DDEDC4" if selected else "#a59a86"
        return f"{marker} [#787266]    [/][{color}]{name}[/]"

    @classmethod
    def _truncate_tree_label(cls, label: str) -> str:
        if len(label) <= cls._TREE_LABEL_WIDTH:
            return label
        if cls._TREE_LABEL_WIDTH <= 3:
            return label[:cls._TREE_LABEL_WIDTH]
        return label[: cls._TREE_LABEL_WIDTH - 3] + "..."

    def _compose_preview(self) -> ComposeResult:
        if not self._files:
            yield Static(
                "[#787266]Select a file on the left to preview its contents.[/]",
                id="results-preview-empty",
            )
            return
        # Header strip with the current filename + meta.
        yield Static(self._preview_header(), id="results-preview-header")
        # Textual's Markdown widget renders inline, reflows on resize,
        # and follows the theme's markdown.* styles from cli_ui/theme.
        yield Markdown(
            self._preview_markdown_source(),
            id="results-markdown",
        )

    # -- keyboard ---------------------------------------------------------

    def action_cursor_down(self) -> None:
        if not self._files:
            return
        self._cursor = (self._cursor + 1) % len(self._files)
        self._refresh_cursor()
        self._refresh_preview()

    def action_cursor_up(self) -> None:
        if not self._files:
            return
        self._cursor = (self._cursor - 1) % len(self._files)
        self._refresh_cursor()
        self._refresh_preview()

    def action_reveal(self) -> None:
        """Reveal the selected file in Finder (macOS) / file manager."""
        if not self._files:
            return
        path = self._files[self._cursor].path
        try:
            if sys.platform == "darwin":
                subprocess.Popen(["open", "-R", str(path)])  # noqa: S603, S607
            else:
                subprocess.Popen(["xdg-open", str(path.parent)])  # noqa: S603, S607
        except Exception as exc:
            self.app.notify(f"Could not reveal: {exc}", severity="error")

    # -- existing actions preserved for backwards compat -----------------

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
        # Dismiss for backwards-compat with existing push_screen_wait
        # callers. If we're on the screen stack, pop back; else
        # switch_mode('dashboard').
        try:
            self.dismiss(None)
        except Exception:
            with contextlib.suppress(Exception):
                self.app.switch_mode("dashboard")

    def action_next(self) -> None:
        with contextlib.suppress(Exception):
            self.app.action_goto_tab("recon")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id == "btn-view-summary":
            self.action_view_summary()
        elif button_id == "btn-open-folder":
            self.action_open_folder()
        elif button_id == "btn-back":
            self.action_back()
        elif button_id == "btn-next":
            self.action_next()

    # -- refresh helpers --------------------------------------------------

    def _refresh_cursor(self) -> None:
        for i in range(len(self._files)):
            try:
                static = self.query_one(f"#tree-row-{i}", Static)
            except Exception:
                continue
            static.update(self._render_tree_row(i, selected=(i == self._cursor)))

    def _refresh_preview(self) -> None:
        try:
            header = self.query_one("#results-preview-header", Static)
            header.update(self._preview_header())
        except Exception:
            pass
        try:
            md = self.query_one("#results-markdown", Markdown)
            # ``update`` accepts a coroutine on Textual >=0.50; wrap in
            # a no-exception call so older versions still work via the
            # sync fallback.
            with contextlib.suppress(Exception):
                md.update(self._preview_markdown_source())
        except Exception:
            pass

    def _preview_header(self) -> str:
        if not self._files:
            return ""
        entry = self._files[self._cursor]
        rel = entry.path.relative_to(self._workspace_root)
        return (
            f"[#DDEDC4]▌[/] [#DDEDC4]{entry.label}[/]  "
            f"[#787266]{rel}[/]"
        )

    def _preview_markdown_source(self) -> str:
        """Read the current file for the Markdown widget.

        Returns a plain string (not markup) — Markdown handles its own
        theme styling via markdown.* theme keys. Files missing or
        unreadable fall back to a placeholder so the pane never goes
        completely blank on the user.
        """
        if not self._files:
            return "*Select a file to preview.*"
        entry = self._files[self._cursor]
        try:
            text = entry.path.read_text()
        except OSError as exc:
            return f"*Could not read file: {exc}*"
        # Strip frontmatter if present — it's noise in a preview.
        if text.startswith("---"):
            end = text.find("\n---", 3)
            if end != -1:
                text = text[end + 4 :].lstrip("\n")
        return text or "*File is empty.*"

    # -- file discovery ---------------------------------------------------

    def _collect_files(self) -> list[_FileEntry]:
        """Walk the workspace once and return the flat list the tree +
        preview share. Groups are emitted in display order (dossiers →
        output → themes → themes/distilled) so ``_compose_tree_rows``
        can detect group transitions with a single comparison.
        """
        files: list[_FileEntry] = []

        competitors_dir = self._workspace_root / "competitors"
        if competitors_dir.is_dir():
            for f in sorted(competitors_dir.glob("*.md")):
                files.append(
                    _FileEntry(label=f.name, path=f, group="competitors"),
                )

        # output/ — executive summary + any top-level files.
        output_dir = self._workspace_root / "output"
        if output_dir.is_dir():
            for f in sorted(output_dir.glob("*.md")):
                files.append(
                    _FileEntry(label=f.name, path=f, group="output"),
                )
        # Top-level executive_summary.md (older workspaces store it here).
        legacy_summary = self._workspace_root / "executive_summary.md"
        if legacy_summary.exists() and not any(
            f.path.name == "executive_summary.md" for f in files
        ):
            files.append(
                _FileEntry(
                    label="executive_summary.md",
                    path=legacy_summary,
                    group="output",
                ),
            )

        # themes/*.md
        themes_dir = self._workspace_root / "themes"
        if themes_dir.is_dir():
            for f in sorted(themes_dir.glob("*.md")):
                files.append(
                    _FileEntry(label=f.name, path=f, group="themes"),
                )

        # themes/distilled/*.md
        distilled_dir = self._workspace_root / "themes" / "distilled"
        if distilled_dir.is_dir():
            for f in sorted(distilled_dir.glob("*.md")):
                files.append(
                    _FileEntry(
                        label=f.name,
                        path=f,
                        group="themes/distilled",
                    ),
                )

        return files

    def _default_cursor_index(self) -> int:
        for i, entry in enumerate(self._files):
            if entry.label == "executive_summary.md":
                return i
        return 0


def _get_editor() -> str:
    import os

    return os.environ.get("EDITOR", "less")
