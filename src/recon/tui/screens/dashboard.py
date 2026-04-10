"""DashboardScreen for recon TUI.

Home base showing workspace status: competitors, sections, themes,
index stats, cost history. Shows workspace path. Auto-prompts on
empty workspace.
"""

from __future__ import annotations

import contextlib
import os
from pathlib import Path  # noqa: TCH003 -- used at runtime

from textual.app import ComposeResult  # noqa: TCH002 -- used at runtime
from textual.binding import Binding
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Button, Static

from recon.tui.models.dashboard import DashboardData  # noqa: TCH001 -- used at runtime


class DashboardScreen(Screen):
    """Workspace status dashboard."""

    BINDINGS = [
        Binding("y", "start_discovery", "Yes, discover", show=False),
    ]

    DEFAULT_CSS = """
    DashboardScreen {
        padding: 1 2;
    }
    #dashboard-header {
        height: auto;
    }
    #workspace-path {
        height: auto;
        color: #a89984;
    }
    #competitor-stats {
        height: auto;
        margin: 1 0 0 0;
    }
    #status-breakdown {
        height: auto;
        margin: 0 0 1 0;
    }
    .action-bar {
        height: auto;
        margin: 1 0;
        layout: horizontal;
    }
    .action-bar Button {
        margin: 0 1 0 0;
    }
    #empty-prompt {
        height: auto;
        margin: 1 0;
        padding: 1 2;
        border: solid #3a3a3a;
    }
    """

    def __init__(self, data: DashboardData, workspace_path: Path) -> None:
        super().__init__()
        self._data = data
        self._workspace_path = workspace_path

    def compose(self) -> ComposeResult:
        yield Static(
            f"[bold #e0a044]recon[/] // {self._data.company_name} -- {self._data.domain}",
            id="dashboard-header",
        )
        display_path = str(self._workspace_path).replace(str(Path.home()), "~")
        yield Static(f"Workspace: {display_path}", id="workspace-path")

        if self._data.total_competitors == 0:
            yield self._compose_empty_prompt()
        else:
            yield from self._compose_workspace_status()

        with Horizontal(classes="action-bar"):
            yield Button("Run", id="btn-run", variant="primary")
            yield Button("Discover", id="btn-discover")
            yield Button("Browse", id="btn-browse")
            yield Button("Quit", id="btn-quit", variant="error")

    def _compose_empty_prompt(self) -> Static:
        return Static(
            "[#efe5c0]No competitors yet.[/]\n\n"
            "Search for competitors in this domain?\n"
            "The agent will search the web and present\n"
            "candidates for you to review.\n\n"
            "[#e0a044][Y][/] Yes, start discovery  "
            "[#e0a044][N][/] No, add manually",
            id="empty-prompt",
        )

    def _compose_workspace_status(self):
        yield Static(
            f"[bold #e0a044]COMPETITORS[/]  {self._data.total_competitors} total",
            id="competitor-stats",
        )

        if self._data.status_counts:
            parts = [f"{status}: {count}" for status, count in sorted(self._data.status_counts.items())]
            yield Static(
                "  " + "  |  ".join(parts),
                id="status-breakdown",
            )

    def action_start_discovery(self) -> None:
        if self._data.total_competitors == 0:
            self._push_discovery()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-browse":
            self._push_browser()
        elif event.button.id == "btn-discover":
            self._push_discovery()
        elif event.button.id == "btn-run":
            self._push_planner()
        elif event.button.id == "btn-quit":
            self.app.exit()

    def _push_browser(self) -> None:
        from recon.tui.screens.browser import CompetitorBrowserScreen

        self.app.push_screen(CompetitorBrowserScreen(data=self._data))

    def _push_discovery(self) -> None:
        from recon.discovery import DiscoveryState
        from recon.tui.screens.discovery import DiscoveryScreen

        state = DiscoveryState()
        self.app.push_screen(
            DiscoveryScreen(state=state, domain=self._data.domain),
            self.handle_discovery_result,
        )

    def handle_discovery_result(self, candidates: list | None) -> None:
        if not candidates:
            return
        from recon.workspace import Workspace

        try:
            ws = Workspace.open(self._workspace_path)
            for candidate in candidates:
                with contextlib.suppress(FileExistsError):
                    ws.create_profile(candidate.name)
        except Exception:
            pass

    def _push_planner(self) -> None:
        from recon.tui.screens.planner import RunPlannerScreen

        section_count = 0
        self.app.push_screen(
            RunPlannerScreen(
                competitor_count=self._data.total_competitors,
                section_count=section_count,
            )
        )

    def _api_key_status(self) -> str:
        env_path = self._workspace_path / ".env"
        if env_path.exists() and "ANTHROPIC_API_KEY" in env_path.read_text():
            return "[#98971a]API key: configured[/]"
        if os.environ.get("ANTHROPIC_API_KEY"):
            return "[#98971a]API key: set in environment[/]"
        return "[#cc241d]API key: not configured[/]"
