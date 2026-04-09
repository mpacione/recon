"""Custom widgets for the recon TUI.

Retro-styled widgets with warm amber aesthetic.
"""

from __future__ import annotations

from textual.app import ComposeResult  # noqa: TCH002 -- used at runtime
from textual.containers import Vertical
from textual.widgets import DataTable, Static

from recon.tui.curation import ThemeCurationModel  # noqa: TCH001
from recon.tui.screens import DashboardData  # noqa: TCH001


class StatusPanel(Vertical):
    """Workspace status summary panel."""

    DEFAULT_CSS = """
    StatusPanel {
        height: auto;
        padding: 1 2;
        border: solid #3a3a3a;
        margin: 1;
    }
    """

    def __init__(self, data: DashboardData) -> None:
        super().__init__()
        self._data = data

    def compose(self) -> ComposeResult:
        yield Static(f"[bold #e0a044]WORKSPACE[/]  {self._data.domain}")
        yield Static(f"[#a89984]Company:[/] {self._data.company_name}")
        yield Static(f"[#a89984]Profiles:[/] {self._data.total_competitors}")
        yield Static("")
        if self._data.status_counts:
            lines = [f"  {status}: {count}" for status, count in sorted(self._data.status_counts.items())]
            yield Static("[bold #e0a044]STATUS BREAKDOWN[/]")
            for line in lines:
                yield Static(line)
        else:
            yield Static("[#a89984]No profiles yet. Run [bold]recon add <name>[/bold] to add competitors.[/]")


class CompetitorTable(Vertical):
    """DataTable showing all competitors and their status."""

    DEFAULT_CSS = """
    CompetitorTable {
        height: 1fr;
        padding: 0 1;
        margin: 0 1;
    }
    """

    def __init__(self, data: DashboardData) -> None:
        super().__init__()
        self._data = data

    def compose(self) -> ComposeResult:
        table = DataTable(id="competitor-table")
        yield table

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("Name", "Type", "Status")
        table.cursor_type = "row"

        for row in self._data.competitor_rows:
            table.add_row(
                row["name"],
                row["type"],
                row["status"],
            )


class ProgressBar(Static):
    """Retro ASCII progress bar."""

    DEFAULT_CSS = """
    ProgressBar {
        height: 1;
        margin: 0 2;
    }
    """

    def __init__(self, progress: float = 0.0, width: int = 40) -> None:
        self._progress = max(0.0, min(1.0, progress))
        self._bar_width = width
        super().__init__(self._render_bar())

    def _render_bar(self) -> str:
        filled = int(self._progress * self._bar_width)
        empty = self._bar_width - filled
        bar = f"[#e0a044]{'=' * filled}[/][#3a3a3a]{'-' * empty}[/]"
        pct = f"{self._progress * 100:.0f}%"
        return f"[{bar}] {pct}"

    def update_progress(self, progress: float) -> None:
        self._progress = max(0.0, min(1.0, progress))
        self.update(self._render_bar())


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


class ThemeCurationPanel(Vertical):
    """Interactive theme curation panel for the TUI."""

    DEFAULT_CSS = """
    ThemeCurationPanel {
        height: auto;
        padding: 1 2;
        border: solid #3a3a3a;
        margin: 1;
    }
    """

    def __init__(self, model: ThemeCurationModel) -> None:
        super().__init__()
        self._model = model

    def compose(self) -> ComposeResult:
        yield Static("[bold #e0a044]THEME DISCOVERY[/]")
        yield Static(f"[#a89984]{len(self._model.entries)} themes discovered, "
                      f"{self._model.selected_count} selected[/]")
        yield Static("")

        lines = format_theme_list(self._model)
        for line in lines:
            yield Static(line)

        yield Static("")
        yield Static(
            "[#a89984][Space] Toggle  [E] Edit name  [V] View evidence  "
            "[D] Done -- synthesize selected[/]"
        )
