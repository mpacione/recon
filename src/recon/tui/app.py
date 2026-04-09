"""Main Textual application for recon."""

from __future__ import annotations

from pathlib import Path  # noqa: TCH003 -- used at runtime

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import Footer, Header, Static

from recon.tui.theme import RECON_CSS


class DashboardScreen(Vertical):
    """Main dashboard showing workspace status."""

    def compose(self) -> ComposeResult:
        yield Static("[b]recon[/b] -- competitive intelligence", classes="title")
        yield Static("")
        yield Static("No workspace loaded. Run [b]recon init[/b] to get started.", classes="dim")


class ReconApp(App):
    """The recon TUI application."""

    TITLE = "recon"
    CSS = RECON_CSS

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("?", "help", "Help"),
        Binding("d", "dashboard", "Dashboard"),
    ]

    def __init__(self, workspace_path: Path | None = None) -> None:
        super().__init__()
        self._workspace_path = workspace_path

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        if self._workspace_path:
            yield self._build_workspace_dashboard()
        else:
            yield DashboardScreen()
        yield Footer()

    def _build_workspace_dashboard(self) -> Vertical:
        """Build dashboard with real workspace data."""
        from recon.tui.screens import build_dashboard_data
        from recon.tui.widgets import CompetitorTable, StatusPanel
        from recon.workspace import Workspace

        try:
            ws = Workspace.open(self._workspace_path)
            data = build_dashboard_data(ws)
            container = Vertical()
            container._nodes = [StatusPanel(data), CompetitorTable(data)]
            return container
        except (FileNotFoundError, Exception):
            return DashboardScreen()

    @property
    def title(self) -> str:
        return self.TITLE

    @title.setter
    def title(self, value: str) -> None:
        self.TITLE = value

    def action_help(self) -> None:
        self.notify("Press q to quit. More keybinds coming soon.", title="Help")

    def action_dashboard(self) -> None:
        self.notify("Dashboard view", title="Navigation")
