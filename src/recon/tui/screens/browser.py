"""CompetitorBrowserScreen for recon TUI.

Browse and search profiles with verification status. Two-pane
layout: scrollable competitor list on the left, detail panel
for the selected competitor on the right.
"""

from __future__ import annotations

from textual.app import ComposeResult  # noqa: TCH002 -- used at runtime
from textual.binding import Binding
from textual.widgets import DataTable, Static

from recon.logging import get_logger
from recon.tui.models.dashboard import DashboardData  # noqa: TCH001
from recon.tui.shell import ReconScreen

_log = get_logger(__name__)


class CompetitorBrowserScreen(ReconScreen):
    """Scrollable competitor list with detail panel."""

    keybind_hints = (
        "[#e0a044]b[/] back · [#e0a044]esc[/] back · "
        "[#e0a044]↑↓[/] navigate · [#e0a044]q[/] quit"
    )

    DEFAULT_CSS = """
    CompetitorBrowserScreen {
        background: #000000;
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
        Binding("b", "back", "back"),
        Binding("escape", "back", "back"),
    ]

    def __init__(self, data: DashboardData) -> None:
        super().__init__()
        self._data = data

    def compose_body(self) -> ComposeResult:
        yield Static(
            f"[bold #e0a044]── COMPETITORS ── ({self._data.total_competitors})[/]",
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

    def action_back(self) -> None:
        _log.info("CompetitorBrowserScreen action_back")
        self.app.pop_screen()

    def on_mount(self) -> None:
        if not self._data.competitor_rows:
            return

        table = self.query_one(DataTable)
        table.add_columns("Name", "Type", "Status")
        table.cursor_type = "row"

        for row in self._data.competitor_rows:
            table.add_row(row["name"], row["type"], row["status"])

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.row_key is None:
            return
        row_index = event.cursor_row
        if 0 <= row_index < len(self._data.competitor_rows):
            row = self._data.competitor_rows[row_index]
            detail = self.query_one("#browser-detail", Static)
            detail.update(
                f"[bold #e0a044]{row['name']}[/]\n"
                f"[#a89984]Type:[/] {row['type']}  "
                f"[#a89984]Status:[/] {row['status']}"
            )
