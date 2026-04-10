"""DashboardScreen for recon TUI.

Home base showing workspace status: competitors, sections, themes,
index stats, cost history. Shows workspace path. Auto-prompts on
empty workspace.
"""

from __future__ import annotations

import contextlib
import os
from pathlib import Path  # noqa: TCH003 -- used at runtime

from textual import work
from textual.app import ComposeResult  # noqa: TCH002 -- used at runtime
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Input, Static

from recon.logging import get_logger
from recon.tui.models.dashboard import DashboardData  # noqa: TCH001 -- used at runtime

_log = get_logger(__name__)


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
    .empty-actions {
        height: auto;
        margin: 1 0 0 0;
    }
    .empty-actions Button {
        margin: 0 1 0 0;
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
            yield from self._compose_empty_prompt()
        else:
            yield from self._compose_workspace_status()

        with Horizontal(classes="action-bar"):
            yield Button("Run", id="btn-run", variant="primary")
            yield Button("Discover", id="btn-discover")
            yield Button("Browse", id="btn-browse")
            yield Button("Quit", id="btn-quit", variant="error")

    def _compose_empty_prompt(self):
        with Vertical(id="empty-prompt"):
            yield Static("[#efe5c0]No competitors yet.[/]")
            yield Static("")
            yield Static(
                "Search the web for competitors in this domain,\n"
                "or add them manually by name.",
                classes="dim",
            )
            yield Static("")
            with Horizontal(classes="empty-actions"):
                yield Button(
                    "Start Discovery",
                    id="btn-empty-discover",
                    variant="primary",
                )
                yield Button(
                    "Add Manually",
                    id="btn-empty-manual",
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

        if self._data.section_statuses:
            yield Static("")
            yield Static(
                f"[bold #e0a044]SECTIONS[/]  {self._data.total_sections} defined",
                id="section-stats",
            )
            for ss in self._data.section_statuses:
                dots = "." * max(1, 20 - len(ss.title))
                progress = "complete" if ss.completed == ss.total else f"{ss.completed}/{ss.total}"
                yield Static(f"  {ss.title} {dots} {progress}")

        if self._data.theme_count > 0:
            yield Static("")
            yield Static(
                f"[bold #e0a044]THEMES[/]  {self._data.theme_count} discovered, "
                f"{self._data.themes_selected} selected",
            )

        if self._data.total_cost > 0:
            yield Static("")
            yield Static(
                f"[bold #e0a044]COST[/]  ${self._data.total_cost:.2f} "
                f"across {self._data.run_count} runs",
            )

    def on_screen_resume(self) -> None:
        from recon.tui.models.dashboard import build_dashboard_data
        from recon.workspace import Workspace

        try:
            ws = Workspace.open(self._workspace_path)
            new_data = build_dashboard_data(ws)
            self.refresh_data(new_data)
        except Exception:
            pass

    def refresh_data(self, data: DashboardData) -> None:
        self._data = data
        self._do_recompose()

    @work
    async def _do_recompose(self) -> None:
        await self.recompose()

    def action_start_discovery(self) -> None:
        if self._data.total_competitors == 0:
            self._push_discovery()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        _log.info(
            "DashboardScreen button pressed id=%s competitors=%d",
            button_id,
            self._data.total_competitors,
        )
        if button_id in ("btn-browse", "btn-empty-browse"):
            self._push_browser()
        elif button_id in ("btn-discover", "btn-empty-discover"):
            self._push_discovery()
        elif button_id == "btn-empty-manual":
            self._show_manual_add_input()
        elif button_id == "btn-run":
            if self._data.total_competitors == 0:
                self.app.notify(
                    "No competitors yet. Discover or add some first.",
                    title="Nothing to run",
                    severity="warning",
                )
                return
            self._push_planner()
        elif button_id == "btn-quit":
            self.app.exit()

    def _push_browser(self) -> None:
        from recon.tui.screens.browser import CompetitorBrowserScreen

        self.app.push_screen(CompetitorBrowserScreen(data=self._data))

    def _push_discovery(self) -> None:
        from recon.discovery import DiscoveryState
        from recon.tui.screens.discovery import DiscoveryScreen

        state = DiscoveryState()
        screen = DiscoveryScreen(state=state, domain=self._data.domain)

        agent = self._build_discovery_agent()
        if agent is not None:
            _log.info("discovery agent built; wiring search fn")
            screen.set_search_fn(agent.search)
        else:
            _log.warning("discovery agent unavailable; search disabled")
            self.app.notify(
                "No API key configured. Add one via .env to enable search.",
                title="Discovery (manual only)",
                severity="warning",
            )

        self.app.push_screen(screen, self.handle_discovery_result)

    def _build_discovery_agent(self):
        from recon.client_factory import ClientCreationError, create_llm_client
        from recon.discovery import DiscoveryAgent

        api_key = self._load_api_key()
        if not api_key:
            _log.warning("no API key found; discovery will be manual only")
            return None

        os.environ["ANTHROPIC_API_KEY"] = api_key
        try:
            client = create_llm_client(model="claude-sonnet-4-5")
        except ClientCreationError as exc:
            _log.warning("create_llm_client failed: %s", exc)
            return None
        except Exception:
            _log.exception("unexpected error creating LLM client")
            return None

        _log.info(
            "built DiscoveryAgent model=%s domain=%s",
            "claude-sonnet-4-5",
            self._data.domain,
        )
        return DiscoveryAgent(
            llm_client=client,
            domain=self._data.domain,
        )

    def _load_api_key(self) -> str | None:
        env_path = self._workspace_path / ".env"
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if line.startswith("ANTHROPIC_API_KEY="):
                    return line.split("=", 1)[1].strip()
        return os.environ.get("ANTHROPIC_API_KEY")

    def _show_manual_add_input(self) -> None:
        existing = self.query("#manual-add-input")
        if existing:
            return
        try:
            prompt_container = self.query_one("#empty-prompt", Vertical)
        except Exception:
            return
        add_input = Input(
            placeholder="Competitor name (Enter to add, Esc to cancel)",
            id="manual-add-input",
        )
        prompt_container.mount(add_input)
        add_input.focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "manual-add-input":
            return
        name = event.value.strip()
        if not name:
            event.input.remove()
            return
        from recon.workspace import Workspace

        try:
            ws = Workspace.open(self._workspace_path)
            ws.create_profile(name)
            _log.info("manually added competitor name=%s", name)
            self.app.notify(f"Added: {name}", title="Competitor added")
            event.input.remove()
            from recon.tui.models.dashboard import build_dashboard_data

            self.refresh_data(build_dashboard_data(ws))
        except FileExistsError:
            self.app.notify(f"{name} already exists", severity="warning")
        except Exception as exc:
            _log.exception("failed to add competitor")
            self.app.notify(str(exc), severity="error")

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
            ),
            self.handle_planner_result,
        )

    def handle_planner_result(self, operation: object | None) -> None:
        if operation is None:
            return
        self.app.switch_mode("run")

    def _api_key_status(self) -> str:
        env_path = self._workspace_path / ".env"
        if env_path.exists() and "ANTHROPIC_API_KEY" in env_path.read_text():
            return "[#98971a]API key: configured[/]"
        if os.environ.get("ANTHROPIC_API_KEY"):
            return "[#98971a]API key: set in environment[/]"
        return "[#cc241d]API key: not configured[/]"
