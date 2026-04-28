"""Main Textual application for recon.

Top-level navigation is section-based:
- MAIN: global project browser
- PROJECT: project brief + run settings
- SCHEMA: section/template editor
- COMPANIES: discovery and roster management
- PIPELINE: live pipeline execution monitor
- OUTPUT: generated artifacts
"""

from __future__ import annotations

import asyncio
import contextlib
from pathlib import Path  # noqa: TCH003 -- used at runtime

import yaml
from textual.app import App, ComposeResult
from textual.binding import Binding

from recon.logging import get_logger
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
        # v4 numbered-tab hotkeys.
        # 0 = MAIN, 1-5 = PROJECT / SCHEMA / COMPANIES / PIPELINE / OUTPUT.
        Binding("0", "goto_tab('recon')",  "Main",   show=False, priority=True),
        Binding("1", "goto_tab('plan')",   "Project",   show=False, priority=True),
        Binding("2", "goto_tab('schema')", "Schema", show=False, priority=True),
        Binding("3", "goto_tab('comps')",  "Companies",  show=False, priority=True),
        Binding("4", "goto_tab('agents')", "Pipeline", show=False, priority=True),
        Binding("5", "goto_tab('output')", "Output", show=False, priority=True),
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

    async def _recover_interrupted_workspace_runs(self, workspace_path: Path) -> None:
        """Recover old non-terminal runs when a workspace is opened."""
        from recon.state import StateStore

        try:
            store = StateStore(workspace_path / ".recon" / "state.db")
            await store.initialize()
            recovered = await store.recover_interrupted_runs(max_age_seconds=60)
        except Exception:
            _log.exception("failed to recover interrupted runs")
            return
        if recovered:
            _log.info("recovered interrupted runs: %s", ",".join(recovered))
            self.refresh_workspace_context()

    def _schedule_interrupted_run_recovery(self) -> None:
        if self._workspace_path is None:
            return
        try:
            asyncio.create_task(
                self._recover_interrupted_workspace_runs(self._workspace_path),
            )
        except RuntimeError:
            _log.exception("could not schedule interrupted run recovery")

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

    def _make_dashboard_screen(self) -> WelcomeScreen:
        """MAIN is always the global project browser root."""
        return WelcomeScreen()

    def compose(self) -> ComposeResult:
        return ()

    def on_mount(self) -> None:
        _log.info("ReconApp.on_mount -- registering modes")
        # Subscribe to engine events so the chrome stays live
        from recon.events import get_bus

        get_bus().subscribe(self._event_subscriber)
        # Make sure we have a context populated for any screen that
        # mounts via the constructor (e.g. ReconApp(workspace_path=...))
        if self._workspace_path is not None:
            self._schedule_interrupted_run_recovery()
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
        self._workspace_path = Path(event.path).expanduser()
        self._record_recent_project(self._workspace_path)
        self._schedule_interrupted_run_recovery()
        self.refresh_workspace_context()
        self._rebuild_dashboard_mode()
        self.action_goto_tab("plan")
        _log.info("workspace loaded, plan tab active")

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
        try:
            from recon.tui.screens.run import RunScreen

            if self.current_mode == "run" and isinstance(self.screen, RunScreen):
                _log.info("ReconApp.launch_pipeline starting immediately on active run screen")
                self.screen.start_pipeline(pipeline_fn)
                return
        except Exception:
            _log.exception("failed immediate run-screen pipeline start; falling back to queue")
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

        output_dir = Path(event.path).expanduser()
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

        # New projects land in PLAN so the brief, settings, and schema
        # can be reviewed before discovery starts.
        self.action_goto_tab("plan")
        self._kickoff_discovery_prewarm()

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

        state = self._load_discovery_state() or DiscoveryState()
        screen = DiscoveryScreen(state=state, domain=domain)
        screen.set_state_change_fn(self._save_discovery_state_and_sync)

        # Wire up the search function if API key is available
        self._wire_discovery_search(screen, domain)
        self.push_screen(screen)

    def _wire_discovery_search(self, screen, domain: str) -> None:  # noqa: ANN001
        """Wire the best available search backend into the discovery screen.

        Priority:
        1. Gemini with Google Search grounding (if Google AI key available)
        2. Anthropic with web_search tool (if Anthropic key available)
        3. No search (manual add only)

        Gemini is preferred because Google Search grounding produces
        better competitor discovery results than Anthropic's web_search.
        """
        search_fn = self._build_discovery_search_fn(domain)
        if search_fn is None:
            _log.warning("no API keys available for discovery search")
            return
        screen.set_search_fn(search_fn)

    def _build_discovery_search_fn(self, domain: str):  # noqa: ANN001
        """Build the best available discovery search coroutine."""
        import os

        from recon.api_keys import load_api_keys

        if self._workspace_path is None:
            return None

        keys = load_api_keys(workspace_root=self._workspace_path)

        # Build both agents where keys are available
        google_key = keys.get("google_ai")
        api_key = keys.get("anthropic") or os.environ.get("ANTHROPIC_API_KEY")

        gemini_agent = None
        anthropic_agent = None

        if google_key:
            try:
                from recon.gemini_discovery import GeminiDiscoveryAgent
                from recon.provenance import ProvenanceRecorder

                gemini_agent = GeminiDiscoveryAgent(
                    api_key=google_key,
                    domain=domain,
                    provenance=(
                        ProvenanceRecorder.for_discovery(self._workspace_path)
                        if self._workspace_path is not None else None
                    ),
                )
            except Exception:
                _log.exception("failed to create Gemini agent")

        if api_key:
            from recon.client_factory import create_llm_client
            from recon.discovery import DiscoveryAgent
            from recon.provenance import ProvenanceRecorder

            client = create_llm_client(api_key=api_key)
            anthropic_agent = DiscoveryAgent(
                llm_client=client,
                domain=domain,
                provenance=(
                    ProvenanceRecorder.for_discovery(self._workspace_path)
                    if self._workspace_path is not None else None
                ),
            )

        if gemini_agent is None and anthropic_agent is None:
            return None

        async def search_with_fallback(state):  # noqa: ANN001
            """Try Gemini first, fall back to Anthropic on any error."""
            if gemini_agent is not None:
                try:
                    result = await gemini_agent.search(state)
                    if result:
                        return result
                except Exception as exc:
                    error_msg = str(exc)
                    if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
                        short = "Gemini rate limit hit"
                    elif "403" in error_msg or "PERMISSION" in error_msg:
                        short = "Gemini API key invalid or restricted"
                    else:
                        short = "Gemini search failed"
                    _log.warning("%s, falling back to Anthropic: %s", short, exc)
                    if anthropic_agent is not None:
                        screen.app.notify(
                            f"{short} — trying Anthropic instead",
                            severity="warning",
                            timeout=5,
                        )

            if anthropic_agent is not None:
                return await anthropic_agent.search(state)

            return []

        primary = "Gemini" if gemini_agent else "Anthropic"
        fallback = " (Anthropic fallback)" if gemini_agent and anthropic_agent else ""
        _log.info("discovery wired to %s%s", primary, fallback)
        return search_with_fallback

    def _kickoff_discovery_prewarm(self) -> None:
        """Start one background discovery round for a newly-created project."""
        if self._workspace_path is None:
            return
        with contextlib.suppress(Exception):
            self.run_worker(
                self._prewarm_discovery_once(),
                exclusive=False,
                group="discovery-prewarm",
                description="Prewarm company discovery",
            )

    async def _prewarm_discovery_once(self) -> None:
        """Seed COMPANIES with one discovery round while the user is in setup."""
        from recon.discovery import DiscoveryState
        from recon.workspace import Workspace

        ws_path = self._workspace_path
        if ws_path is None:
            return
        state = self._load_discovery_state() or DiscoveryState()
        if state.all_candidates:
            return
        try:
            ws = Workspace.open(ws_path)
            domain = ws.schema.domain if ws.schema else "unknown"
        except Exception:
            domain = "unknown"
        search_fn = self._build_discovery_search_fn(domain)
        if search_fn is None:
            return
        try:
            candidates = await search_fn(state)
        except Exception:
            _log.exception("background discovery prewarm failed")
            return
        if not candidates:
            _log.info("background discovery prewarm returned no candidates")
            return
        state.add_round(candidates)
        self._save_discovery_state_and_sync(state)
        _log.info("background discovery prewarm saved %d candidates", len(candidates))

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

        # Default 5-6 sections on, rest off. The LLM selection (Phase a)
        # would be smarter, but this gives a reasonable starting point.
        always_on = {
            "overview",
            "pricing",
            "distribution_gtm",
            "brand_market",
            "customer_segments",
        }
        sections = [
            {**s, "selected": s["key"] in always_on}
            for s in SECTION_POOL
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

        # Persist the full editable pool and write the selected subset
        self._update_schema_sections(result.sections)

        # Push confirm screen
        from recon.tui.screens.confirm import ConfirmScreen

        self.push_screen(
            ConfirmScreen(
                competitor_count=competitor_count,
                section_count=len(selected),
                section_names=[s["title"] for s in selected],
            ),
            self._handle_v2_confirm_result,
        )

    def _update_schema_sections(self, sections: list[dict]) -> None:
        """Persist the editable schema pool and selected active sections."""

        if self._workspace_path is None:
            return

        schema_path = self._workspace_path / "recon.yaml"
        if not schema_path.exists():
            return

        try:
            schema_dict = yaml.safe_load(schema_path.read_text()) or {}
            pool_path = self._workspace_state_path("schema_sections.yaml")
            if pool_path is not None:
                pool_path.parent.mkdir(parents=True, exist_ok=True)
                pool_path.write_text(yaml.safe_dump(sections, sort_keys=False))
            schema_dict["sections"] = [
                {
                    "key": s["key"],
                    "title": s["title"],
                    "description": s.get("description", ""),
                    "allowed_formats": list(s.get("allowed_formats", ["prose"])),
                    "preferred_format": s.get("preferred_format", "prose"),
                    **({"when_relevant": s["when_relevant"]} if s.get("when_relevant") else {}),
                }
                for s in sections
                if s.get("selected")
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
            verification_mode=result.verification_mode,
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
        self.action_goto_tab("plan")
        self._kickoff_discovery_prewarm()
        _log.info("switched to plan tab after wizard")

    def action_help(self) -> None:
        self.notify("Q=Quit  ?=Help  1-6=Tabs", title="Keybinds")

    def _workspace_state_path(self, *parts: str) -> Path | None:
        if self._workspace_path is None:
            return None
        path = self._workspace_path / ".recon"
        for part in parts:
            path = path / part
        return path

    def _load_plan_settings(self) -> dict[str, object]:
        path = self._workspace_state_path("plan.yaml")
        defaults: dict[str, object] = {
            "model_name": "sonnet",
            "workers": 5,
            "verification_mode": "standard",
        }
        if path is None or not path.exists():
            return dict(defaults)
        try:
            data = yaml.safe_load(path.read_text()) or {}
            if isinstance(data, dict):
                return {
                    "model_name": str(data.get("model_name", defaults["model_name"])),
                    "workers": int(data.get("workers", defaults["workers"])),
                    "verification_mode": str(
                        data.get("verification_mode", defaults["verification_mode"])
                    ),
                }
        except Exception:
            _log.exception("failed to load plan settings")
        return dict(defaults)

    def _save_plan_settings(
        self,
        model_name: str,
        workers: int,
        verification_mode: str = "standard",
    ) -> None:
        path = self._workspace_state_path("plan.yaml")
        if path is None:
            return
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                yaml.safe_dump(
                    {
                        "model_name": model_name,
                        "workers": workers,
                        "verification_mode": verification_mode,
                    },
                    sort_keys=False,
                )
            )
        except Exception:
            _log.exception("failed to save plan settings")

    def _load_discovery_state(self):
        from recon.discovery import DiscoveryState

        path = self._workspace_state_path("discovery", "state.yaml")
        if path is None or not path.exists():
            return None
        try:
            data = yaml.safe_load(path.read_text()) or {}
            return DiscoveryState.from_dict(data if isinstance(data, dict) else None)
        except Exception:
            _log.exception("failed to load discovery state")
            return None

    def _save_discovery_state_and_sync(self, state) -> None:  # noqa: ANN001
        from recon.discovery import DiscoveryState
        from recon.tui.screens.discovery import DiscoveryScreen
        from recon.workspace import Workspace

        if not isinstance(state, DiscoveryState):
            return
        path = self._workspace_state_path("discovery", "state.yaml")
        if path is None or self._workspace_path is None:
            return
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(yaml.safe_dump(state.to_dict(), sort_keys=False))
        except Exception:
            _log.exception("failed to save discovery state")

        try:
            ws = Workspace.open(self._workspace_path)
            existing = {str(p.get("name", "")).strip() for p in ws.list_profiles()}
            for candidate in state.accepted_candidates:
                name = candidate.name.strip()
                if not name or name in existing:
                    continue
                try:
                    ws.create_profile(name)
                    existing.add(name)
                except FileExistsError:
                    existing.add(name)
                except Exception:
                    _log.exception("failed to sync profile for %s", name)
            self.refresh_workspace_context()
        except Exception:
            _log.exception("failed to sync discovery state into workspace")

        try:
            if isinstance(self.screen, DiscoveryScreen):
                self.screen.load_state(state)
        except Exception:
            _log.exception("failed to refresh active discovery screen")

    def _persist_current_screen_state(self) -> None:
        try:
            from recon.tui.screens.discovery import DiscoveryScreen

            if isinstance(self.screen, DiscoveryScreen):
                self._save_discovery_state_and_sync(self.screen.state)
        except Exception:
            _log.exception("failed to persist current screen state")

    def _workspace_schema_dict(self, ws_path: Path) -> dict:
        schema_path = ws_path / "recon.yaml"
        if not schema_path.exists():
            return {}
        try:
            data = yaml.safe_load(schema_path.read_text()) or {}
            return data if isinstance(data, dict) else {}
        except Exception:
            _log.exception("failed to load workspace schema dict")
            return {}

    def _project_brief(self, ws_path: Path) -> str:
        schema = self._workspace_schema_dict(ws_path)
        brief = schema.get("project_brief")
        if isinstance(brief, str) and brief.strip():
            return brief.strip()
        domain = schema.get("domain")
        return domain.strip() if isinstance(domain, str) else ""

    def _update_project_brief(self, description: str) -> None:
        if self._workspace_path is None:
            return
        schema_path = self._workspace_path / "recon.yaml"
        schema = self._workspace_schema_dict(self._workspace_path)
        parsed = _description_to_schema(description)
        schema["domain"] = parsed.get("domain", schema.get("domain", ""))
        schema["identity"] = parsed.get("identity", schema.get("identity", {}))
        schema["project_brief"] = description.strip()
        try:
            schema_path.write_text(yaml.safe_dump(schema, sort_keys=False))
            self.refresh_workspace_context()
        except Exception:
            _log.exception("failed to update project brief")

    def _handle_plan_describe_result(self, result: object | None) -> None:
        from recon.tui.screens.describe import DescribeResult

        if not isinstance(result, DescribeResult):
            return
        self._update_project_brief(result.description)
        self._refresh_plan_screen()
        self.notify("Project brief updated", severity="information")

    def _handle_plan_settings_result(self, result: object | None) -> None:
        from recon.tui.screens.confirm import ConfirmResult

        if not isinstance(result, ConfirmResult):
            return
        self._save_plan_settings(
            model_name=result.model_name,
            workers=result.workers,
            verification_mode=result.verification_mode,
        )
        self._refresh_plan_screen()
        self.notify("Plan settings saved", severity="information")

    def _refresh_plan_screen(self) -> None:
        """Refresh the mounted PLAN screen after a brief/settings edit."""
        from recon.tui.screens.plan import PlanScreen

        if self._workspace_path is None:
            return
        if not isinstance(self.screen, PlanScreen):
            return

        self.refresh_workspace_context()
        self.screen.reload(
            project_brief=self._project_brief(self._workspace_path),
            competitor_count=len(self._list_competitors(self._workspace_path)),
            section_count=len(self._section_names(self._workspace_path)),
            plan_settings=self._load_plan_settings(),
            total_cost=float(self.workspace_context.total_cost),
            run_count=int(self.workspace_context.run_count),
        )

    def launch_pipeline_from_plan(self) -> None:
        from recon.tui.pipeline_runner import Operation, build_pipeline_fn

        ws_path = self._workspace_path
        if ws_path is None:
            self.notify("Open a project first", severity="warning")
            return
        competitors = self._list_competitors(ws_path)
        sections = self._section_names(ws_path)
        if not competitors:
            self.notify(
                "Go to COMPANIES and accept at least one company first.",
                severity="warning",
            )
            return
        if not sections:
            self.notify(
                "Go to SCHEMA and select at least one section first.",
                severity="warning",
            )
            return
        settings = self._load_plan_settings()
        pipeline_fn = build_pipeline_fn(
            workspace_path=ws_path,
            operation=Operation.FULL_PIPELINE,
            model_name=str(settings.get("model_name", "sonnet")),
            worker_count=int(settings.get("workers", 5)),
            verification_mode=str(settings.get("verification_mode", "standard")),
        )
        self.launch_pipeline(pipeline_fn)

    def _list_competitors(self, ws_path: Path) -> list[dict]:
        """Best-effort competitor fetch for the OUTPUT tab's meta."""
        try:
            from recon.workspace import Workspace

            return Workspace.open(ws_path).list_profiles()
        except Exception:
            return []

    def _count_schema_sections(self, ws_path: Path) -> int:
        """Best-effort section count for the OUTPUT tab's meta."""
        try:
            from recon.workspace import Workspace

            ws = Workspace.open(ws_path)
            if ws.schema and ws.schema.sections:
                return len(ws.schema.sections)
        except Exception:
            pass
        return 0

    def _section_names(self, ws_path: Path) -> list[str]:
        """Human-readable section titles from the loaded schema.

        Feeds ConfirmScreen's "Sections: A, B, C" preview so the user
        can see what the run will cover before paying for it.
        """
        try:
            from recon.workspace import Workspace

            ws = Workspace.open(ws_path)
            if ws.schema and ws.schema.sections:
                return [s.title for s in ws.schema.sections]
        except Exception:
            pass
        return []

    def _schema_sections(self, ws_path: Path) -> tuple[list[dict], str]:
        """Full section library + selected flags for TemplateScreen."""
        try:
            from recon.section_library import merge_with_selected
            from recon.workspace import Workspace

            ws = Workspace.open(ws_path)
            if not ws.schema:
                return ([], "")
            state_path = self._workspace_state_path("schema_sections.yaml")
            if state_path is not None and state_path.exists():
                try:
                    data = yaml.safe_load(state_path.read_text()) or []
                    if isinstance(data, list):
                        sections = [dict(section) for section in data if isinstance(section, dict)]
                        return (sections, ws.schema.domain or "")
                except Exception:
                    _log.exception("failed to load schema section pool state")

            selected = [
                {
                    "key": s.key,
                    "title": s.title,
                    "description": s.description or "",
                    "allowed_formats": list(s.allowed_formats),
                    "preferred_format": s.preferred_format,
                    "selected": True,
                }
                for s in ws.schema.sections
            ]
            sections = merge_with_selected(selected)
            return (sections, ws.schema.domain or "")
        except Exception:
            return ([], "")

    def action_goto_tab(self, tab_key: str) -> None:
        """Jump to the v4 tab identified by ``tab_key``.

        MAIN is always available. The other sections are workspace-scoped
        and sit on top of the MAIN root screen.
        """
        if (
            tab_key != "recon"
            and getattr(self, "_workspace_path", None) is None
            and self.workspace_context.workspace_path is None
        ):
            return

        self._persist_current_screen_state()

        def reset_to_dashboard_root() -> None:
            with contextlib.suppress(Exception):
                self.switch_mode("dashboard")
            with contextlib.suppress(Exception):
                while len(self.screen_stack) > 1:
                    self.pop_screen()

        if tab_key == "recon":
            reset_to_dashboard_root()
            return

        current_key = getattr(self.screen, "tab_key", None)
        if current_key == tab_key:
            return

        ws_path = getattr(self, "_workspace_path", None)

        if tab_key == "plan":
            if ws_path is None:
                return
            reset_to_dashboard_root()
            from recon.tui.screens.plan import PlanScreen

            with contextlib.suppress(Exception):
                self.push_screen(
                    PlanScreen(
                        workspace_root=ws_path,
                        project_brief=self._project_brief(ws_path),
                        competitor_count=len(self._list_competitors(ws_path)),
                        section_count=len(self._section_names(ws_path)),
                        plan_settings=self._load_plan_settings(),
                        total_cost=self.workspace_context.total_cost,
                        run_count=self.workspace_context.run_count,
                    ),
                )
            return
        if tab_key == "schema":
            if ws_path is None:
                return
            reset_to_dashboard_root()
            from recon.tui.screens.template import TemplateScreen

            sections, domain = self._schema_sections(ws_path)
            with contextlib.suppress(Exception):
                self.push_screen(
                    TemplateScreen(sections=sections, domain=domain, next_tab="comps"),
                )
            return
        if tab_key == "comps":
            from recon.discovery import DiscoveryState
            from recon.tui.screens.discovery import DiscoveryScreen
            from recon.workspace import Workspace

            if ws_path is None:
                return
            reset_to_dashboard_root()
            try:
                ws = Workspace.open(ws_path)
                domain = ws.schema.domain if ws.schema else ""
            except Exception:
                domain = ""
            state = self._load_discovery_state() or DiscoveryState()
            screen = DiscoveryScreen(state=state, domain=domain)
            screen.set_state_change_fn(self._save_discovery_state_and_sync)
            self._wire_discovery_search(screen, domain)
            with contextlib.suppress(Exception):
                self.push_screen(screen)
            return
        if tab_key == "agents":
            with contextlib.suppress(Exception):
                self.switch_mode("run")
            return
        if tab_key == "output":
            from recon.tui.screens.results import ResultsScreen

            if ws_path is None:
                return
            reset_to_dashboard_root()
            ctx = self.workspace_context
            with contextlib.suppress(Exception):
                self.push_screen(
                    ResultsScreen(
                        workspace_root=ws_path,
                        competitor_count=len(self._list_competitors(ws_path)),
                        section_count=self._count_schema_sections(ws_path),
                        theme_count=0,
                        total_cost=ctx.total_cost,
                        elapsed="—",
                    ),
                )
            return


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
    schema["project_brief"] = description.strip()

    return schema
