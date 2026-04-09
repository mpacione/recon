"""Main Textual application for recon."""

from __future__ import annotations

import os
from enum import StrEnum
from pathlib import Path  # noqa: TCH003 -- used at runtime

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import Footer, Header, Input, Static

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
        yield Static("[#a89984]No active pipeline run.[/]", classes="dim")
        yield Static("")
        yield Static("[#a89984][P] Pause  [S] Stop  [K] Skip  [R] Retry  [Esc] Back[/]")


class _WorkspaceDashboard(Vertical):
    """Interactive dashboard with workspace data and action controls."""

    DEFAULT_CSS = """
    _WorkspaceDashboard {
        padding: 1 2;
    }
    #activity-log {
        height: auto;
        max-height: 12;
        margin: 1 0;
    }
    #add-input {
        margin: 1 0;
        display: none;
    }
    #add-input.visible {
        display: block;
    }
    """

    def __init__(self, data: object, workspace_path: Path) -> None:
        super().__init__()
        self._data = data
        self._workspace_path = workspace_path

    def compose(self) -> ComposeResult:
        from recon.tui.widgets import StatusPanel

        yield StatusPanel(self._data)
        yield Static("")
        yield Static(self._api_key_status())
        yield Static("")
        yield Static(
            "[bold #e0a044]ACTIONS[/]  "
            "[#efe5c0][A][/][#a89984] Add competitor  [/]"
            "[#efe5c0][R][/][#a89984] Research all  [/]"
            "[#efe5c0][I][/][#a89984] Index profiles  [/]"
            "[#efe5c0][Q][/][#a89984] Quit[/]"
        )
        yield Input(placeholder="Competitor name (Enter to add, Esc to cancel)", id="add-input")
        yield Static("")
        yield Static("[bold #e0a044]ACTIVITY[/]", id="activity-header")
        yield Static("[#a89984]Ready.[/]", id="activity-log")

    def on_mount(self) -> None:
        """Restore activity messages from the app."""
        app = self.app
        if hasattr(app, "_activity_messages") and app._activity_messages:
            log = self.query_one("#activity-log", Static)
            log.update("\n".join(app._activity_messages[-10:]))

    def _api_key_status(self) -> str:
        env_path = self._workspace_path / ".env"
        if env_path.exists() and "ANTHROPIC_API_KEY" in env_path.read_text():
            return "[#98971a]API key: configured[/]"
        if os.environ.get("ANTHROPIC_API_KEY"):
            return "[#98971a]API key: set in environment[/]"
        return "[#cc241d]API key: not configured -- set ANTHROPIC_API_KEY or re-run init[/]"


class ReconApp(App):
    """The recon TUI application."""

    TITLE = "recon"
    CSS = RECON_CSS

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("?", "help", "Help"),
        Binding("d", "switch_dashboard", "Dashboard"),
        Binding("t", "switch_themes", "Themes"),
        Binding("a", "add_competitor", "Add"),
        Binding("r", "run_research", "Research"),
        Binding("i", "run_index", "Index"),
    ]

    def __init__(self, workspace_path: Path | None = None) -> None:
        super().__init__()
        self._workspace_path = workspace_path
        self.current_view = ViewMode.DASHBOARD
        self._adding = False
        self._activity_messages: list[str] = []

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
        from recon.workspace import Workspace

        try:
            ws = Workspace.open(self._workspace_path)
            data = build_dashboard_data(ws)
            return _WorkspaceDashboard(data, self._workspace_path)
        except (FileNotFoundError, Exception):
            return DashboardView()

    def _log_activity(self, message: str) -> None:
        """Append a message to the activity log."""
        self._activity_messages.append(message)
        try:
            log = self.query_one("#activity-log", Static)
            log.update("\n".join(self._activity_messages[-10:]))
        except Exception:
            pass

    def _load_api_key(self) -> str | None:
        """Load API key from .env file or environment."""
        if self._workspace_path:
            env_path = self._workspace_path / ".env"
            if env_path.exists():
                for line in env_path.read_text().splitlines():
                    if line.startswith("ANTHROPIC_API_KEY="):
                        return line.split("=", 1)[1].strip()
        return os.environ.get("ANTHROPIC_API_KEY")

    @property
    def title(self) -> str:
        return self.TITLE

    @title.setter
    def title(self, value: str) -> None:
        self.TITLE = value

    def action_help(self) -> None:
        self.notify(
            "A=Add  R=Research  I=Index  D=Dashboard  T=Themes  Q=Quit",
            title="Keybinds",
        )

    def action_switch_dashboard(self) -> None:
        self._switch_view(ViewMode.DASHBOARD)

    def action_switch_themes(self) -> None:
        self._switch_view(ViewMode.THEMES)

    def action_add_competitor(self) -> None:
        """Show the add-competitor input."""
        if self.current_view != ViewMode.DASHBOARD:
            return
        try:
            add_input = self.query_one("#add-input", Input)
            add_input.add_class("visible")
            add_input.focus()
            self._adding = True
        except Exception:
            self.notify("Open the dashboard first (press D)", severity="warning")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Enter on the add-competitor input."""
        if event.input.id != "add-input":
            return

        name = event.value.strip()
        if not name:
            self._hide_add_input()
            return

        from recon.workspace import Workspace

        try:
            ws = Workspace.open(self._workspace_path)
            ws.create_profile(name)
            self._log_activity(f"Added: {name}")
            event.input.value = ""
            self._hide_add_input()
            self._switch_view(ViewMode.DASHBOARD)
        except FileExistsError:
            self.notify(f"{name} already exists", severity="warning")
            event.input.value = ""
        except Exception as e:
            self.notify(str(e), severity="error")

    def on_key(self, event) -> None:
        """Handle Escape to cancel add input."""
        if event.key == "escape" and self._adding:
            self._hide_add_input()
            event.prevent_default()

    def _hide_add_input(self) -> None:
        try:
            add_input = self.query_one("#add-input", Input)
            add_input.remove_class("visible")
            add_input.value = ""
            self._adding = False
        except Exception:
            pass

    def action_run_research(self) -> None:
        """Kick off research on all scaffold profiles."""
        api_key = self._load_api_key()
        if not api_key:
            self.notify("API key not configured. Re-run recon init or set ANTHROPIC_API_KEY.", severity="error")
            return

        if not self._workspace_path:
            self.notify("No workspace loaded.", severity="error")
            return

        self._log_activity("Starting research...")
        self._do_research(api_key)

    @work(thread=True)
    def _do_research(self, api_key: str) -> None:
        """Run research in a background thread."""
        import asyncio

        from recon.llm import LLMClient
        from recon.research import ResearchOrchestrator
        from recon.workspace import Workspace

        async def run() -> list[dict]:
            import anthropic

            client = LLMClient(
                client=anthropic.AsyncAnthropic(api_key=api_key),
                model="claude-sonnet-4-20250514",
            )
            ws = Workspace.open(self._workspace_path)
            orchestrator = ResearchOrchestrator(workspace=ws, llm_client=client, max_workers=5)
            return await orchestrator.research_all()

        try:
            results = asyncio.run(run())
            total_input = sum(r.get("tokens", {}).get("input", 0) for r in results)
            total_output = sum(r.get("tokens", {}).get("output", 0) for r in results)
            self.call_from_thread(
                self._log_activity,
                f"Research complete: {len(results)} sections. Tokens: {total_input} in, {total_output} out.",
            )
            self.call_from_thread(self._switch_view, ViewMode.DASHBOARD)
        except Exception as e:
            self.call_from_thread(self._log_activity, f"Research failed: {e}")
            self.call_from_thread(self.notify, str(e), severity="error")

    def action_run_index(self) -> None:
        """Index all profiles into the vector database."""
        if not self._workspace_path:
            self.notify("No workspace loaded.", severity="error")
            return

        self._log_activity("Indexing profiles...")
        self._do_index()

    @work(thread=True)
    def _do_index(self) -> None:
        """Run indexing in a background thread."""
        import asyncio

        from recon.incremental import IncrementalIndexer
        from recon.index import IndexManager
        from recon.state import StateStore
        from recon.workspace import Workspace

        async def run():
            ws = Workspace.open(self._workspace_path)
            manager = IndexManager(persist_dir=str(ws.root / ".vectordb"))
            state = StateStore(db_path=ws.root / ".recon" / "state.db")
            await state.initialize()
            indexer = IncrementalIndexer(workspace=ws, index_manager=manager, state_store=state)
            return await indexer.index()

        try:
            result = asyncio.run(run())
            self.call_from_thread(
                self._log_activity,
                f"Indexed {result.indexed} files ({result.total_chunks} chunks), skipped {result.skipped} unchanged.",
            )
            self.call_from_thread(self._switch_view, ViewMode.DASHBOARD)
        except Exception as e:
            self.call_from_thread(self._log_activity, f"Index failed: {e}")
            self.call_from_thread(self.notify, str(e), severity="error")
