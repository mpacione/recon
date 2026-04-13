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
        Binding("ctrl+c", "quit", "Quit", show=False, priority=True),
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
        """Handle the user picking a workspace from the welcome screen."""
        _log.info("WorkspaceSelected path=%s", event.path)
        self._workspace_path = Path(event.path)
        self._record_recent_project(self._workspace_path)
        self.refresh_workspace_context()
        self._rebuild_dashboard_mode()
        _log.info("workspace loaded, dashboard mode active")

    def _rebuild_dashboard_mode(self) -> None:
        """Re-register the dashboard mode with a factory that captures
        the current ``self._workspace_path``.

        Shared by the workspace-selected and wizard-completed handlers
        because both need to switch the dashboard from "welcome state"
        to "loaded workspace state" without touching the run mode.
        Textual refuses to remove the active mode, so we briefly
        switch to a dedicated ``_loading`` holding mode, rebuild
        dashboard, then switch back to dashboard.

        The previous implementation used ``switch_mode("run")`` as the
        holding mode, which had a subtle side effect: the early
        ``switch_mode("run")`` instantiated the cached RunScreen and
        fired its ``on_mount`` BEFORE any pipeline had been queued. A
        later ``launch_pipeline()`` call through the normal flow then
        hit a stale one-shot lifecycle and the pipeline silently
        refused to start. Using a dedicated ``_loading`` mode avoids
        touching the run mode at all -- its cached instance stays
        uninstantiated until the user actually wants a pipeline.
        """
        from textual.screen import Screen

        if "_loading" not in self._modes:
            self.add_mode("_loading", Screen)
        self.switch_mode("_loading")
        self.remove_mode("dashboard")
        self.add_mode("dashboard", self._make_dashboard_screen)
        self.switch_mode("dashboard")

    def launch_pipeline(self, pipeline_fn) -> None:  # noqa: ANN001 -- PipelineFn from run.py
        """Start a pipeline run and activate the run mode.

        This is the canonical way to launch a pipeline from any
        screen. Replaces the fragile ``app._pending_pipeline_fn``
        handshake that relied on :meth:`RunScreen.on_mount` or
        :meth:`on_screen_resume` picking up state at just the right
        lifecycle event.

        The flow:

        1. Queue the ``pipeline_fn`` on the app (a simple attribute,
           but owned by this single entry point so the contract is
           legible).
        2. ``switch_mode("run")`` activates the cached RunScreen.
        3. RunScreen's ``on_screen_resume`` hook fires and consumes
           the queue.

        The reason we still queue rather than calling
        ``screen.start_pipeline`` directly is that the RunScreen
        instance isn't accessible before the mode switch -- Textual
        lazily instantiates it on first activation. The queue bridges
        the "before first activation" and "after" states cleanly.
        """
        _log.info("ReconApp.launch_pipeline queuing pipeline_fn")
        self._pending_pipeline_fn = pipeline_fn
        self.switch_mode("run")

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
        from recon.tui.screens.describe import DescribeScreen

        output_dir = Path(event.path)
        self.push_screen(
            DescribeScreen(output_dir=output_dir),
            self._handle_describe_result,
        )

    def _handle_describe_result(self, result: object | None) -> None:
        from recon.tui.screens.describe import DescribeResult

        _log.info("describe dismissed result=%s", type(result).__name__ if result else "None")
        if not isinstance(result, DescribeResult):
            _log.info("describe cancelled")
            return

        self._create_workspace_from_description(result)

    def _create_workspace_from_description(self, result: object) -> None:
        import yaml

        from recon.tui.screens.describe import DescribeResult
        from recon.workspace import Workspace

        if not isinstance(result, DescribeResult):
            return

        _log.info("creating workspace at %s from description", result.output_dir)
        try:
            result.output_dir.mkdir(parents=True, exist_ok=True)

            competitors_dir = result.output_dir / "competitors"
            if competitors_dir.exists():
                existing = list(competitors_dir.glob("*.md"))
                if existing:
                    _log.info("cleaning %d existing profiles", len(existing))
                    for p in existing:
                        p.unlink()

            # Parse description into structured schema fields
            schema_dict = _description_to_schema(result.description)

            (result.output_dir / "recon.yaml").write_text(
                yaml.dump(schema_dict, default_flow_style=False, sort_keys=False)
            )

            # Save API keys to .env
            for key_name, key_value in result.api_keys.items():
                from recon.api_keys import save_api_key
                save_api_key(key_name, key_value, workspace_root=result.output_dir)

            Workspace.init(root=result.output_dir)
            _log.info("workspace created from description")
        except Exception as exc:
            _log.exception("failed to create workspace from description")
            self.notify(f"Failed to create workspace: {exc}", severity="error")
            return

        self._workspace_path = result.output_dir
        self._record_recent_project(result.output_dir)
        self.refresh_workspace_context()
        self._rebuild_dashboard_mode()

        # v2 flow: auto-start discovery after workspace creation
        self._start_v2_discovery()

    def _start_v2_discovery(self) -> None:
        """Push discovery screen to start finding competitors."""
        from recon.discovery import DiscoveryState
        from recon.tui.screens.discovery import DiscoveryScreen
        from recon.workspace import Workspace

        if self._workspace_path is None:
            return

        try:
            ws = Workspace.open(self._workspace_path)
            domain = ws.schema.domain if ws.schema else "unknown"
        except Exception:
            domain = "unknown"

        state = DiscoveryState()
        screen = DiscoveryScreen(state=state, domain=domain)

        # Wire up the search function if API key is available
        self._wire_discovery_search(screen, domain)

        self.push_screen(screen, self._handle_v2_discovery_result)

    def _wire_discovery_search(self, screen, domain: str) -> None:  # noqa: ANN001
        """Wire the LLM search function into the discovery screen."""
        import os

        from recon.api_keys import load_api_keys

        if self._workspace_path is None:
            return

        keys = load_api_keys(workspace_root=self._workspace_path)
        api_key = keys.get("anthropic") or os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            return

        from recon.client_factory import create_llm_client
        from recon.discovery import DiscoveryAgent

        os.environ["ANTHROPIC_API_KEY"] = api_key
        client = create_llm_client()
        agent = DiscoveryAgent(llm_client=client, domain=domain)

        async def search_fn(state):  # noqa: ANN001
            return await agent.search(state)

        screen.set_search_fn(search_fn)

    def _handle_v2_discovery_result(self, result: object | None) -> None:
        """After discovery, create profiles and push template screen."""
        from recon.discovery import DiscoveryCandidate
        from recon.workspace import Workspace

        if self._workspace_path is None:
            return

        if not isinstance(result, list):
            _log.info("discovery cancelled")
            return

        accepted = [c for c in result if isinstance(c, DiscoveryCandidate)]
        if not accepted:
            _log.info("no candidates accepted")
            return

        # Create profiles for accepted candidates
        ws = Workspace.open(self._workspace_path)
        for candidate in accepted:
            try:
                ws.create_profile(candidate.name)
            except Exception:
                _log.exception("failed to create profile for %s", candidate.name)

        self.refresh_workspace_context()

        # Push template screen
        self._start_v2_template(len(accepted))

    def _start_v2_template(self, competitor_count: int) -> None:
        """Push the template screen for section selection."""
        from recon.schema_designer import SECTION_POOL
        from recon.tui.screens.template import TemplateScreen
        from recon.workspace import Workspace

        if self._workspace_path is None:
            return

        try:
            ws = Workspace.open(self._workspace_path)
            domain = ws.schema.domain if ws.schema else "unknown"
        except Exception:
            domain = "unknown"

        # Use default selections for now (Phase a LLM selection is wired
        # but requires an async call — for now use sensible defaults)
        always_on = {"overview", "pricing_business", "market_position", "head_to_head"}
        sections = [
            {**s, "selected": s["key"] in always_on}
            for s in SECTION_POOL[:10]
        ]

        self.push_screen(
            TemplateScreen(sections=sections, domain=domain),
            lambda result: self._handle_v2_template_result(result, competitor_count),
        )

    def _handle_v2_template_result(self, result: object | None, competitor_count: int) -> None:
        """After template, push cost confirmation screen."""
        from recon.tui.screens.template import TemplateResult

        if not isinstance(result, TemplateResult):
            _log.info("template cancelled")
            return

        selected = [s for s in result.sections if s.get("selected")]
        if not selected:
            self.notify("No sections selected", severity="warning")
            return

        # Update schema with selected sections
        self._update_schema_sections(selected)

        # Push confirm screen
        from recon.tui.screens.confirm import ConfirmScreen

        self.push_screen(
            ConfirmScreen(
                competitor_count=competitor_count,
                section_count=len(selected),
            ),
            self._handle_v2_confirm_result,
        )

    def _update_schema_sections(self, sections: list[dict]) -> None:
        """Update the workspace's recon.yaml with the selected sections."""
        import yaml

        if self._workspace_path is None:
            return

        schema_path = self._workspace_path / "recon.yaml"
        if not schema_path.exists():
            return

        try:
            schema_dict = yaml.safe_load(schema_path.read_text()) or {}
            schema_dict["sections"] = [
                {
                    "key": s["key"],
                    "title": s["title"],
                    "description": s.get("description", ""),
                    "allowed_formats": ["prose"],
                    "preferred_format": "prose",
                }
                for s in sections
            ]
            schema_path.write_text(
                yaml.dump(schema_dict, default_flow_style=False, sort_keys=False)
            )
        except Exception:
            _log.exception("failed to update schema sections")

    def _handle_v2_confirm_result(self, result: object | None) -> None:
        """After confirmation, launch the pipeline."""
        from recon.tui.screens.confirm import ConfirmResult

        if not isinstance(result, ConfirmResult):
            _log.info("confirm cancelled")
            return

        # Build pipeline function with the chosen model and workers
        from recon.tui.pipeline_runner import Operation, build_pipeline_fn

        pipeline_fn = build_pipeline_fn(
            workspace_path=self._workspace_path,
            operation=Operation.FULL_PIPELINE,
            model_name=result.model_name,
            worker_count=result.workers,
        )
        self.launch_pipeline(pipeline_fn)

    # Keep the old wizard handler for backward compatibility (CLI --wizard flag)
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

            # Guard: if the target directory already has competitor
            # profiles from a previous project, wipe them so the new
            # project starts clean. Without this, discovery results
            # from project A bleed into project B when the user reuses
            # the same directory name.
            competitors_dir = result.output_dir / "competitors"
            if competitors_dir.exists():
                existing = list(competitors_dir.glob("*.md"))
                if existing:
                    _log.info(
                        "cleaning %d existing competitor profiles from %s",
                        len(existing),
                        competitors_dir,
                    )
                    for p in existing:
                        p.unlink()
                    self.notify(
                        f"Cleaned {len(existing)} existing profiles from "
                        f"previous project in this directory.",
                        severity="information",
                    )

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
        self._rebuild_dashboard_mode()
        _log.info("switched to dashboard mode after wizard")

    def action_help(self) -> None:
        self.notify("Q=Quit  ?=Help", title="Keybinds")


def _description_to_schema(description: str) -> dict:
    """Parse a freeform description into a minimal schema dict.

    Extracts company_name (first capitalized phrase or first sentence
    subject), domain (the space described), and products (anything
    that looks like a product mention). Returns a schema with
    default sections — the Template screen (Phase 2.3) will refine
    these later via LLM.
    """
    import re

    words = description.strip().split()
    company_name = ""
    domain = description.strip()
    products: list[str] = []

    # Heuristic: first 1-3 capitalized words are likely the company name
    caps: list[str] = []
    for word in words:
        cleaned = re.sub(r"[^a-zA-Z0-9]", "", word)
        if cleaned and cleaned[0].isupper():
            caps.append(word.rstrip(".,;:"))
        else:
            break
    if caps:
        company_name = " ".join(caps)

    # Heuristic: text after "in" or "competing in" is the domain
    domain_match = re.search(
        r"(?:competing\s+in|in\s+(?:the\s+)?|for\s+(?:the\s+)?)"
        r"([^.]+?)(?:\.|$)",
        description,
        re.IGNORECASE,
    )
    if domain_match:
        domain = domain_match.group(1).strip()

    if not company_name:
        company_name = words[0] if words else "My Company"

    from recon.workspace import _make_default_schema

    schema = _make_default_schema(
        company_name=company_name,
        products=products,
        domain=domain,
    )

    return schema
