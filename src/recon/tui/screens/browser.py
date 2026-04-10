"""CompetitorBrowserScreen for recon TUI.

Browse and search profiles with verification status. Two-pane
layout: scrollable competitor list on the left, detail panel
for the selected competitor on the right.
"""

from __future__ import annotations

from textual.app import ComposeResult  # noqa: TCH002 -- used at runtime
from textual.screen import Screen
from textual.widgets import DataTable, Static

from recon.tui.models.dashboard import DashboardData  # noqa: TCH001


class CompetitorBrowserScreen(Screen):
    """Scrollable competitor list with detail panel."""

    DEFAULT_CSS = """
    CompetitorBrowserScreen {
        padding: 1 2;
    }
    #browser-table {
        height: 1fr;
        margin: 1 0;
    }
    #browser-detail {
        height: auto;
        margin: 1 0;
        padding: 1 2;
        border: solid #3a3a3a;
    }
    """

    BINDINGS = [
        ("escape", "pop_screen", "Back"),
    ]

    def __init__(self, data: DashboardData) -> None:
        super().__init__()
        self._data = data

    def compose(self) -> ComposeResult:
        yield Static(
            f"[bold #e0a044]COMPETITORS[/]  ({self._data.total_competitors})",
            id="browser-title",
        )

        if not self._data.competitor_rows:
            yield Static(
                "[#a89984]No competitors in workspace.[/]",
                id="browser-empty",
            )
        else:
            table = DataTable(id="browser-table")
            yield table
            yield Static(
                "[#a89984]Select a competitor to view details[/]",
                id="browser-detail",
            )

        yield Static("")
        yield Static(
            "[#a89984][/] Search  [F] Filter  [S] Sort  [Esc] Back[/]"
        )

    def on_mount(self) -> None:
        if not self._data.competitor_rows:
            return

        table = self.query_one(DataTable)
        table.add_columns("Name", "Type", "Status")
        table.cursor_type = "row"

        for row in self._data.competitor_rows:
            table.add_row(row["name"], row["type"], row["status"])
