"""CompetitorBrowserScreen for recon TUI.

Browse and search profiles with verification status. Two-pane
layout: scrollable competitor list on the left, detail panel
for the selected competitor on the right.
"""

from __future__ import annotations

from textual.app import ComposeResult  # noqa: TCH002 -- used at runtime
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import DataTable, Static

from recon.logging import get_logger
from recon.tui.models.dashboard import DashboardData  # noqa: TCH001
from recon.tui.shell import ReconScreen

_log = get_logger(__name__)


class CompetitorBrowserScreen(ReconScreen):
    """Scrollable competitor list — v4 COMP'S tab (shares key with Discovery)."""

    tab_key = "comps"

    keybind_hints = (
        "[#DDEDC4]b[/] back · [#DDEDC4]esc[/] back · "
        "[#DDEDC4]↑↓[/] navigate · [#DDEDC4]q[/] quit"
    )

    DEFAULT_CSS = """
    CompetitorBrowserScreen {
        background: #000000;
    }
    #browser-container {
        width: 100%;
        height: 1fr;
        padding: 1 2;
        overflow-y: auto;
    }
    #browser-table {
        height: 1fr;
    }
    #browser-detail {
        height: auto;
        padding: 0 1;
    }
    """

    show_log_pane = False
    show_activity_feed = False
    show_run_status_bar = False

    BINDINGS = [
        Binding("b", "back", "back"),
        Binding("escape", "back", "back"),
    ]

    def __init__(self, data: DashboardData) -> None:
        super().__init__()
        self._data = data

    def compose_body(self) -> ComposeResult:
        from recon.tui.primitives import Card

        count = self._data.total_competitors
        meta = f"{count} competitor{'s' if count != 1 else ''}"
        if self._data.domain:
            meta = f"{self._data.domain}   ·   {meta}"

        with Vertical(id="browser-container"):
            with Card(title="COMPETITORS", meta=meta, id="browser-card"):
                if not self._data.competitor_rows:
                    yield Static(
                        "[#a59a86]No competitors in workspace.[/]\n\n"
                        "[#787266]Press[/] [#DDEDC4]d[/] [#787266]on the dashboard to run "
                        "discovery, or [/][#DDEDC4]m[/][#787266] to add one manually.[/]",
                        id="browser-empty",
                    )
                else:
                    yield DataTable(id="browser-table")
                    yield Static(
                        "[#a59a86]Select a competitor to view details[/]",
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
                f"[bold #DDEDC4]{row['name']}[/]\n"
                f"[#a59a86]Type:[/] {row['type']}  "
                f"[#a59a86]Status:[/] {row['status']}"
            )
