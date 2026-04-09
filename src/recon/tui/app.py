"""Main Textual application for recon."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path  # noqa: TCH003 -- used at runtime

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import Footer, Header, Static

from recon.tui.theme import RECON_CSS


class ViewMode(StrEnum):
    DASHBOARD = "dashboard"
    THEMES = "themes"
    MONITOR = "monitor"


class DashboardView(Vertical):
    """Main dashboard showing workspace status."""

    def compose(self) -> ComposeResult:
        yield Static("[b]recon[/b] -- competitive intelligence", classes="title")
        yield Static("")
        yield Static("No workspace loaded. Run [b]recon init[/b] to get started.", classes="dim")


class ThemesView(Vertical):
    """Theme curation view."""

    def compose(self) -> ComposeResult:
        yield Static("[bold #e0a044]THEME CURATION[/]", classes="title")
        yield Static("")
        yield Static("[#a89984]No themes discovered yet. Run the pipeline to discover themes.[/]", classes="dim")
        yield Static("")
        yield Static("[#a89984][Space] Toggle  [E] Edit name  [D] Done  [Esc] Back[/]")


class MonitorView(Vertical):
    """Run monitor view."""

    def compose(self) -> ComposeResult:
        yield Static("[bold #e0a044]RUN MONITOR[/]", classes="title")
        yield Static("")
        yield Static("[#a89984]No active pipeline run. Start one with [b]recon run[/b].[/]", classes="dim")
        yield Static("")
        yield Static("[#a89984][P] Pause  [S] Stop  [K] Skip  [R] Retry  [Esc] Back[/]")


class ReconApp(App):
    """The recon TUI application."""

    TITLE = "recon"
    CSS = RECON_CSS

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("?", "help", "Help"),
        Binding("d", "switch_dashboard", "Dashboard"),
        Binding("t", "switch_themes", "Themes"),
        Binding("r", "switch_monitor", "Monitor"),
    ]

    def __init__(self, workspace_path: Path | None = None) -> None:
        super().__init__()
        self._workspace_path = workspace_path
        self.current_view = ViewMode.DASHBOARD

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        container = Vertical(id="view-container")
        container.can_focus = False
        yield container
        yield Footer()

    def on_mount(self) -> None:
        self._switch_view(ViewMode.DASHBOARD)

    def _switch_view(self, mode: ViewMode) -> None:
        self.current_view = mode
        container = self.query_one("#view-container", Vertical)
        container.remove_children()
        container.mount(self._build_view(mode))

    def _build_view(self, mode: ViewMode) -> Vertical:
        if mode == ViewMode.THEMES:
            return ThemesView()
        if mode == ViewMode.MONITOR:
            return MonitorView()
        if self._workspace_path:
            return self._build_workspace_dashboard()
        return DashboardView()

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
            return DashboardView()

    @property
    def title(self) -> str:
        return self.TITLE

    @title.setter
    def title(self, value: str) -> None:
        self.TITLE = value

    def action_help(self) -> None:
        self.notify(
            "d=Dashboard  t=Themes  r=Monitor  q=Quit",
            title="Help",
        )

    def action_switch_dashboard(self) -> None:
        self._switch_view(ViewMode.DASHBOARD)

    def action_switch_themes(self) -> None:
        self._switch_view(ViewMode.THEMES)

    def action_switch_monitor(self) -> None:
        self._switch_view(ViewMode.MONITOR)
