"""Main Textual application for recon.

Uses Textual Modes for top-level navigation:
- dashboard: workspace status, discovery, planning, browsing
- run: live pipeline execution monitor

WelcomeScreen is pushed on mount when no workspace is specified.
"""

from __future__ import annotations

from pathlib import Path  # noqa: TCH003 -- used at runtime

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header

from recon.tui.screens.dashboard import DashboardScreen
from recon.tui.screens.run import RunScreen
from recon.tui.screens.welcome import WelcomeScreen
from recon.tui.theme import RECON_CSS


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
        self.add_mode("dashboard", self._make_dashboard_screen)
        self.add_mode("run", RunScreen)
        self.switch_mode("dashboard")

        if self._initial_wizard_dir is not None:
            from recon.tui.screens.wizard import WizardScreen

            self.push_screen(
                WizardScreen(output_dir=self._initial_wizard_dir),
                self._handle_wizard_result,
            )

    def on_welcome_screen_workspace_selected(self, event: WelcomeScreen.WorkspaceSelected) -> None:
        self._workspace_path = Path(event.path)
        self.switch_mode("run")
        self.remove_mode("dashboard")
        self.add_mode("dashboard", self._make_dashboard_screen)
        self.switch_mode("dashboard")

    def on_welcome_screen_new_project_requested(self, event: WelcomeScreen.NewProjectRequested) -> None:
        from recon.tui.screens.wizard import WizardScreen

        output_dir = Path(event.path)
        self.push_screen(
            WizardScreen(output_dir=output_dir),
            self._handle_wizard_result,
        )

    def _handle_wizard_result(self, result: object | None) -> None:
        from recon.tui.screens.wizard import WizardResult

        if not isinstance(result, WizardResult) or result.schema is None:
            return

        self._create_workspace_from_wizard(result)

    def _create_workspace_from_wizard(self, result: object) -> None:
        import yaml

        from recon.tui.screens.wizard import WizardResult
        from recon.workspace import Workspace

        if not isinstance(result, WizardResult) or result.schema is None:
            return

        try:
            result.output_dir.mkdir(parents=True, exist_ok=True)
            (result.output_dir / "recon.yaml").write_text(
                yaml.dump(result.schema, default_flow_style=False, sort_keys=False)
            )
            if result.api_key:
                env_path = result.output_dir / ".env"
                env_path.write_text(f"ANTHROPIC_API_KEY={result.api_key}\n")
            Workspace.init(root=result.output_dir)
        except Exception as exc:
            self.notify(f"Failed to create workspace: {exc}", severity="error")
            return

        self._workspace_path = result.output_dir
        self.switch_mode("run")
        self.remove_mode("dashboard")
        self.add_mode("dashboard", self._make_dashboard_screen)
        self.switch_mode("dashboard")

    def action_help(self) -> None:
        self.notify("Q=Quit  ?=Help", title="Keybinds")
