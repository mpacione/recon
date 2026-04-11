"""Main Textual application for recon.

Uses Textual Modes for top-level navigation:
- dashboard: workspace status, discovery, planning, browsing
- run: live pipeline execution monitor

WelcomeScreen is pushed on mount when no workspace is specified.
"""

from __future__ import annotations

import contextlib
from pathlib import Path  # noqa: TCH003 -- used at runtime

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header

from recon.logging import get_logger
from recon.tui.screens.dashboard import DashboardScreen
from recon.tui.screens.run import RunScreen
from recon.tui.screens.welcome import WelcomeScreen
from recon.tui.shell import WorkspaceContext
from recon.tui.theme import RECON_CSS


def contextlib_suppress():
    return contextlib.suppress(Exception)

_log = get_logger(__name__)


class ReconApp(App):
    """The recon TUI application with Modes-based navigation."""

    TITLE = "recon"
    CSS = RECON_CSS

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("?", "help", "Help"),
    ]

    def __init__(
        self,
        workspace_path: Path | None = None,
        initial_wizard_dir: Path | None = None,
    ) -> None:
        super().__init__()
        self._workspace_path = workspace_path
        self._initial_wizard_dir = initial_wizard_dir
        self.workspace_context = WorkspaceContext.empty()
        self._event_subscriber = self._on_engine_event
        _log.info(
            "ReconApp.__init__ workspace_path=%s initial_wizard_dir=%s",
            workspace_path,
            initial_wizard_dir,
        )

    def _on_engine_event(self, event) -> None:  # noqa: ANN001 -- Event isinstance below
        """Translate an engine bus event into a workspace_context update.

        The chrome's header strip reflects run_state, run_phase,
        total_cost, and run_count. Each event mutates the relevant
        field and pushes the change to the visible ReconScreen.
        """
        from recon.events import (
            CostRecorded,
            ProfileCreated,
            RunCancelled,
            RunCompleted,
            RunFailed,
            RunPaused,
            RunResumed,
            RunStageStarted,
            RunStarted,
        )

        ctx = self.workspace_context
        changed = False

        if isinstance(event, RunStarted):
            ctx.run_state = "running"
            ctx.run_phase = ""
            changed = True
        elif isinstance(event, RunStageStarted):
            ctx.run_state = "running"
            ctx.run_phase = event.stage
            changed = True
        elif isinstance(event, RunCompleted):
            ctx.run_state = "done"
            ctx.run_phase = ""
            ctx.run_count += 1
            changed = True
        elif isinstance(event, RunFailed):
            ctx.run_state = "error"
            changed = True
        elif isinstance(event, RunCancelled):
            ctx.run_state = "cancelled"
            ctx.run_count += 1
            changed = True
        elif isinstance(event, RunPaused):
            ctx.run_state = "paused"
            changed = True
        elif isinstance(event, RunResumed):
            ctx.run_state = "running"
            changed = True
        elif isinstance(event, CostRecorded):
            ctx.total_cost += event.cost_usd
            changed = True
        elif isinstance(event, ProfileCreated):
            # No header field, but a refresh is cheap and useful
            changed = True

        if changed:
            self._schedule_chrome_refresh()

    def _schedule_chrome_refresh(self) -> None:
        """Push a chrome refresh onto the message loop.

        Engine events arrive from any thread. ``call_from_thread`` is
        the safe path when we're off-thread, but it raises
        ``RuntimeError`` if invoked from the message loop's own thread.
        Try the inline path first; only fall back to ``call_from_thread``
        when the inline path raises (worker-thread case).
        """
        from recon.tui.shell import ReconScreen

        try:
            screen = self.screen
        except Exception:
            return
        if not isinstance(screen, ReconScreen):
            return
        try:
            screen.refresh_chrome()
        except Exception:
            with contextlib.suppress(Exception):
                self.call_from_thread(screen.refresh_chrome)

    def refresh_workspace_context(self) -> None:
        """Rebuild ``self.workspace_context`` from the current workspace.

        Called whenever a meaningful state change happens (workspace
        opened, run finished, profile added). Also pushes the new
        context into any visible :class:`ReconScreen` so its header
        bar updates immediately.
        """
        from recon.tui.shell import ReconScreen
        from recon.workspace import Workspace

        if self._workspace_path is None:
            self.workspace_context = WorkspaceContext.empty()
        else:
            try:
                ws = Workspace.open(self._workspace_path)
                self.workspace_context = WorkspaceContext.from_workspace(ws)
            except Exception:
                _log.exception("refresh_workspace_context failed")
                self.workspace_context = WorkspaceContext.empty()

        # Push the update to whatever full screen is currently visible
        try:
            if isinstance(self.screen, ReconScreen):
                self.screen.refresh_chrome()
        except Exception:
            pass

    @property
    def workspace_path(self) -> Path | None:
        return self._workspace_path

    @workspace_path.setter
    def workspace_path(self, value: Path) -> None:
        self._workspace_path = value

    @property
    def title(self) -> str:
        return self.TITLE

    @title.setter
    def title(self, value: str) -> None:
        self.TITLE = value

    def _make_dashboard_screen(self) -> DashboardScreen | WelcomeScreen:
        if self._workspace_path is None:
            return WelcomeScreen()
        return self._build_workspace_dashboard()

    def _build_workspace_dashboard(self) -> DashboardScreen:
        from recon.tui.models.dashboard import build_dashboard_data
        from recon.workspace import Workspace

        try:
            ws = Workspace.open(self._workspace_path)
            data = build_dashboard_data(ws)
        except Exception:
            from recon.tui.models.dashboard import DashboardData

            data = DashboardData(
                domain="Unknown",
                company_name="Unknown",
                total_competitors=0,
                status_counts={},
                competitor_rows=[],
            )
        return DashboardScreen(data=data, workspace_path=self._workspace_path)

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield Footer()

    def on_mount(self) -> None:
        _log.info("ReconApp.on_mount -- registering modes")
        # Subscribe to engine events so the chrome stays live
        from recon.events import get_bus

        get_bus().subscribe(self._event_subscriber)
        # Make sure we have a context populated for any screen that
        # mounts via the constructor (e.g. ReconApp(workspace_path=...))
        if self._workspace_path is not None:
            self.refresh_workspace_context()
        self.add_mode("dashboard", self._make_dashboard_screen)
        self.add_mode("run", RunScreen)
        self.switch_mode("dashboard")
        _log.info("ReconApp.on_mount -- switched to dashboard mode")

        if self._initial_wizard_dir is not None:
            _log.info(
                "ReconApp.on_mount -- pushing wizard for %s",
                self._initial_wizard_dir,
            )
            from recon.tui.screens.wizard import WizardScreen

            self.push_screen(
                WizardScreen(output_dir=self._initial_wizard_dir),
                self._handle_wizard_result,
            )

    def on_unmount(self) -> None:
        with contextlib_suppress():
            from recon.events import get_bus

            get_bus().unsubscribe(self._event_subscriber)

    def on_welcome_screen_workspace_selected(self, event: WelcomeScreen.WorkspaceSelected) -> None:
        _log.info("WorkspaceSelected path=%s", event.path)
        self._workspace_path = Path(event.path)
        self._record_recent_project(self._workspace_path)
        self.refresh_workspace_context()
        self.switch_mode("run")
        self.remove_mode("dashboard")
        self.add_mode("dashboard", self._make_dashboard_screen)
        self.switch_mode("dashboard")
        _log.info("workspace loaded, dashboard mode active")

    def _record_recent_project(self, workspace_path: Path) -> None:
        """Append the opened workspace to ~/.recon/recent.json so the
        welcome screen can show it next time. Silent on failure.
        """
        try:
            from recon.tui.screens.welcome import (
                _DEFAULT_RECENT_PATH,
                RecentProjectsManager,
            )

            manager = RecentProjectsManager(_DEFAULT_RECENT_PATH)
            manager.add(workspace_path, workspace_path.name)
            _log.info("recorded recent project path=%s", workspace_path)
        except Exception:
            _log.exception("failed to record recent project")

    def on_welcome_screen_new_project_requested(self, event: WelcomeScreen.NewProjectRequested) -> None:
        _log.info("NewProjectRequested path=%s", event.path)
        from recon.tui.screens.wizard import WizardScreen

        output_dir = Path(event.path)
        self.push_screen(
            WizardScreen(output_dir=output_dir),
            self._handle_wizard_result,
        )

    def _handle_wizard_result(self, result: object | None) -> None:
        from recon.tui.screens.wizard import WizardResult

        _log.info("wizard dismissed result=%s", type(result).__name__)
        if not isinstance(result, WizardResult) or result.schema is None:
            _log.info("wizard cancelled or empty result")
            return

        self._create_workspace_from_wizard(result)

    def _create_workspace_from_wizard(self, result: object) -> None:
        import yaml

        from recon.tui.screens.wizard import WizardResult
        from recon.workspace import Workspace

        if not isinstance(result, WizardResult) or result.schema is None:
            return

        _log.info("creating workspace at %s", result.output_dir)
        try:
            result.output_dir.mkdir(parents=True, exist_ok=True)
            (result.output_dir / "recon.yaml").write_text(
                yaml.dump(result.schema, default_flow_style=False, sort_keys=False)
            )
            if result.api_key:
                env_path = result.output_dir / ".env"
                env_path.write_text(f"ANTHROPIC_API_KEY={result.api_key}\n")
            Workspace.init(root=result.output_dir)
            _log.info("workspace created successfully")
        except Exception as exc:
            _log.exception("failed to create workspace")
            self.notify(f"Failed to create workspace: {exc}", severity="error")
            return

        self._workspace_path = result.output_dir
        self._record_recent_project(result.output_dir)
        self.refresh_workspace_context()
        self.switch_mode("run")
        self.remove_mode("dashboard")
        self.add_mode("dashboard", self._make_dashboard_screen)
        self.switch_mode("dashboard")
        _log.info("switched to dashboard mode after wizard")

    def action_help(self) -> None:
        self.notify("Q=Quit  ?=Help", title="Keybinds")
