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
from textual.containers import Vertical
from textual.widgets import Input, Static

from recon.logging import get_logger
from recon.tui.models.dashboard import DashboardData  # noqa: TCH001 -- used at runtime
from recon.tui.primitives import CardStack, TerminalBox
from recon.tui.shell import ReconScreen

_log = get_logger(__name__)


class DashboardScreen(ReconScreen):
    """Workspace status dashboard — v4 RECON home tab."""

    tab_key = "recon"

    BINDINGS = [
        Binding("r", "run", "run pipeline"),
        Binding("d", "discover", "discover competitors"),
        Binding("b", "browse", "browse competitors"),
        Binding("m", "add_manually", "add manually"),
        Binding("e", "edit_schema", "edit schema"),
        Binding("y", "start_discovery", "Yes, discover", show=False),
    ]

    keybind_hints = (
        "[#DDEDC4]r[/] run · [#DDEDC4]d[/] discover · [#DDEDC4]b[/] browse · "
        "[#DDEDC4]e[/] edit schema · [#DDEDC4]q[/] quit · [#DDEDC4]?[/] help"
    )

    DEFAULT_CSS = """
    DashboardScreen {
        background: #000000;
    }
    #dashboard-header {
        height: auto;
    }
    #workspace-path {
        height: auto;
        color: #a59a86;
    }
    #competitor-stats {
        height: auto;
        margin: 1 0 0 0;
    }
    #status-breakdown {
        height: auto;
        margin: 0 0 1 0;
    }
    #empty-prompt {
        height: auto;
        margin: 1 0;
        padding: 0 1;
        border: solid #3a3a3a;
    }
    """

    def __init__(self, data: DashboardData, workspace_path: Path) -> None:
        super().__init__()
        self._data = data
        self._workspace_path = workspace_path

    def compose_body(self) -> ComposeResult:
        yield Static(
            f"[#DDEDC4]{self._data.company_name}[/] [#787266]·[/] "
            f"[#a59a86]{self._data.domain}[/]",
            id="dashboard-summary",
        )
        if self._data.total_competitors == 0:
            yield from self._compose_empty_prompt()
        else:
            yield from self._compose_workspace_status()

    def _compose_empty_prompt(self):
        with Vertical(id="empty-prompt"):
            yield Static("[#DDEDC4]No competitors yet.[/]")
            yield Static("")
            yield Static(
                "Press [#DDEDC4]d[/] to discover competitors via web search,\n"
                "or press [#DDEDC4]m[/] to add them manually by name.",
                classes="dim",
            )

    def _compose_workspace_status(self):
        from recon.tui.primitives import Card

        with CardStack(id="dashboard-stack"):
            yield from self._compose_competitors_card(Card)
            if self._data.section_statuses:
                yield from self._compose_sections_card(Card)
            if self._data.theme_count > 0:
                yield from self._compose_themes_card(Card)
            if self._data.total_cost > 0 or self._data.run_count > 0:
                yield from self._compose_cost_card(Card)

    def _compose_competitors_card(self, Card):
        meta = f"{self._data.total_competitors} total"
        with Card(title="COMPETITORS", meta=meta, id="competitors-card"):
            if self._data.status_counts:
                parts = [
                    f"[#a59a86]{status}[/] [#DDEDC4]{count}[/]"
                    for status, count in sorted(self._data.status_counts.items())
                ]
                yield Static(
                    "  " + "  [#3a3a3a]·[/]  ".join(parts),
                    id="status-breakdown",
                )
            else:
                yield Static("[#a59a86]no status breakdown[/]")
            yield Static(
                f"[#787266]total:[/] [#DDEDC4]{self._data.total_competitors}[/]",
                id="competitor-stats",
                classes="hidden-legacy",
            )

    def _compose_sections_card(self, Card):
        meta = f"{self._data.total_sections} defined"
        with Card(title="SECTIONS", meta=meta, id="sections-card"):
            for ss in self._data.section_statuses:
                dots = "·" * max(1, 24 - len(ss.title))
                if ss.completed == ss.total and ss.total > 0:
                    progress = "[#DDEDC4]complete[/]"
                elif ss.completed == 0:
                    progress = f"[#787266]{ss.completed}/{ss.total}[/]"
                else:
                    progress = f"[#DDEDC4]{ss.completed}/{ss.total}[/]"
                yield Static(
                    f"[#DDEDC4]{ss.title}[/] [#686359]{dots}[/] {progress}",
                )

    def _compose_themes_card(self, Card):
        meta = (
            f"{self._data.theme_count} discovered  ·  "
            f"{self._data.themes_selected} selected"
        )
        # Body intentionally empty — the card acts as a stat header.
        yield Card(title="THEMES", meta=meta, id="themes-card")

    def _compose_cost_card(self, Card):
        run_word = "run" if self._data.run_count == 1 else "runs"
        meta = f"${self._data.total_cost:.2f} across {self._data.run_count} {run_word}"
        with Card(title="COST", meta=meta, id="cost-card"):
            if self._data.last_run_cost > 0:
                yield Static(
                    f"[#a59a86]last run:[/] [#DDEDC4]${self._data.last_run_cost:.2f}[/]",
                )
            else:
                yield Static("[#787266]no run history yet[/]")

    def on_screen_resume(self) -> None:
        """Re-read workspace state every time the dashboard becomes
        active. Catches changes from modals (discovery added profiles,
        wizard rewrote the schema, etc) that didn't wait on refresh.
        """
        from recon.tui.models.dashboard import build_dashboard_data
        from recon.workspace import Workspace

        _log.info(
            "DashboardScreen.on_screen_resume refreshing from %s",
            self._workspace_path,
        )
        try:
            ws = Workspace.open(self._workspace_path)
            new_data = build_dashboard_data(ws)
            self.refresh_data(new_data)
        except Exception:
            # Logging the exception used to be a bare `pass`, which
            # meant a broken workspace (deleted, corrupt recon.yaml)
            # would silently freeze the dashboard at stale data. Now
            # we log the traceback so users and maintainers can see
            # what failed.
            _log.exception("DashboardScreen.on_screen_resume failed")

    def refresh_data(self, data: DashboardData) -> None:
        self._data = data
        self._do_recompose()

    @work
    async def _do_recompose(self) -> None:
        await self.recompose()

    def action_start_discovery(self) -> None:
        if self._data.total_competitors == 0:
            self._push_discovery()

    def action_run(self) -> None:
        _log.info(
            "DashboardScreen action_run competitors=%d", self._data.total_competitors,
        )
        if self._data.total_competitors == 0:
            self.app.notify(
                "No competitors yet. Discover or add some first.",
                title="Nothing to run",
                severity="warning",
            )
            return
        self._push_planner()

    def action_edit_schema(self) -> None:
        """Open ``recon.yaml`` in the user's ``$EDITOR``.

        Suspends the TUI while the editor is open, then refreshes the
        dashboard data on return (in case sections changed).
        """
        import os
        import subprocess

        schema_path = self._workspace_path / "recon.yaml"
        if not schema_path.exists():
            self.app.notify(
                "No recon.yaml found in this workspace.",
                severity="warning",
            )
            return

        editor = os.environ.get("EDITOR", os.environ.get("VISUAL", "vim"))
        _log.info("action_edit_schema editor=%s path=%s", editor, schema_path)

        with self.app.suspend():
            subprocess.run([editor, str(schema_path)], check=False)

        # Refresh dashboard to pick up any schema changes
        from recon.tui.models.dashboard import build_dashboard_data
        from recon.workspace import Workspace

        try:
            ws = Workspace.open(self._workspace_path)
            self.refresh_data(build_dashboard_data(ws))
            self.app.notify("Schema reloaded", severity="information")
        except Exception:
            _log.exception("failed to reload schema after edit")

    def action_discover(self) -> None:
        _log.info("DashboardScreen action_discover")
        self._push_discovery()

    def action_browse(self) -> None:
        _log.info("DashboardScreen action_browse")
        if self._data.total_competitors == 0:
            self.app.notify(
                "No competitors to browse yet. Discover or add some first.",
                title="Nothing to browse",
                severity="warning",
            )
            return
        self._push_browser()

    def action_add_manually(self) -> None:
        _log.info("DashboardScreen action_add_manually")
        if self._data.total_competitors > 0:
            self.app.notify(
                "Manual add only works on an empty workspace; "
                "use the discovery flow instead.",
                severity="information",
            )
            return
        self._show_manual_add_input()

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

        try:
            client = create_llm_client(model="claude-sonnet-4-5", api_key=api_key)
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
        from recon.tui.models.dashboard import build_dashboard_data
        from recon.workspace import Workspace

        try:
            ws = Workspace.open(self._workspace_path)
            for candidate in candidates:
                with contextlib.suppress(FileExistsError):
                    ws.create_profile(candidate.name)
            # Refresh our local view so the next action_run sees the
            # new competitor count instead of bailing with "Nothing to
            # run". The modal dismissal lifecycle doesn't always fire
            # on_screen_resume reliably.
            self.refresh_data(build_dashboard_data(ws))
        except Exception:
            _log.exception("handle_discovery_result failed")

    def _push_planner(self) -> None:
        from recon.tui.screens.planner import RunPlannerScreen
        from recon.workspace import Workspace

        section_count = self._data.total_sections
        try:
            ws = Workspace.open(self._workspace_path)
            estimated_cost = _estimate_full_run_cost(ws)
        except Exception:
            estimated_cost = 0.0

        self.app.push_screen(
            RunPlannerScreen(
                competitor_count=self._data.total_competitors,
                section_count=section_count,
                estimated_full_run_cost=estimated_cost,
            ),
            self.handle_planner_result,
        )

    def handle_planner_result(self, operation: object | None) -> None:
        _log.info(
            "DashboardScreen.handle_planner_result operation=%r",
            operation,
        )
        if operation is None:
            return

        from recon.tui.pipeline_runner import (
            OPERATIONS_REQUIRING_SELECTION,
        )
        from recon.tui.screens.planner import Operation

        if not isinstance(operation, Operation):
            _log.warning(
                "handle_planner_result: operation not an Operation instance: %s",
                type(operation).__name__,
            )
            return

        if operation == Operation.ADD_NEW:
            self._push_discovery_then_start_pipeline()
            return

        if operation in OPERATIONS_REQUIRING_SELECTION:
            self._push_selector_then_start(operation)
            return

        self._start_pipeline_for_operation(operation, targets=None)

    def _push_discovery_then_start_pipeline(self) -> None:
        """ADD_NEW handoff: discover candidates, create profiles, then run.

        Pushes :class:`DiscoveryScreen` like :meth:`_push_discovery`, but
        the dismiss handler creates the chosen profiles and immediately
        starts a pipeline run scoped to just those new names. This is
        the only planner operation that pre-discovers before research.
        """
        import contextlib

        from recon.discovery import DiscoveryState
        from recon.tui.screens.discovery import DiscoveryScreen
        from recon.tui.screens.planner import Operation
        from recon.workspace import Workspace

        state = DiscoveryState()
        screen = DiscoveryScreen(state=state, domain=self._data.domain)

        agent = self._build_discovery_agent()
        if agent is not None:
            screen.set_search_fn(agent.search)
        else:
            self.app.notify(
                "No API key configured. Add one via .env to enable search.",
                title="Add new (manual only)",
                severity="warning",
            )

        def handle(candidates: object | None) -> None:
            if not isinstance(candidates, list) or not candidates:
                self.app.notify(
                    "No candidates selected; add new cancelled.",
                    severity="information",
                )
                return

            try:
                ws = Workspace.open(self._workspace_path)
            except Exception:
                _log.exception("could not open workspace for ADD_NEW")
                return

            new_names: list[str] = []
            for candidate in candidates:
                name = getattr(candidate, "name", None)
                if not name:
                    continue
                with contextlib.suppress(FileExistsError):
                    ws.create_profile(name)
                    new_names.append(name)

            if not new_names:
                self.app.notify(
                    "All selected candidates already exist; nothing to research.",
                    severity="warning",
                )
                return

            # Refresh dashboard data so the next return shows them
            from recon.tui.models.dashboard import build_dashboard_data

            self.refresh_data(build_dashboard_data(ws))

            # Now run the pipeline scoped to just the new competitors
            self._start_pipeline_for_operation(
                Operation.UPDATE_SPECIFIC, targets=new_names,
            )

        self.app.push_screen(screen, handle)

    def _start_pipeline_for_operation(
        self, operation: object, targets: list[str] | None
    ) -> None:
        _log.info(
            "_start_pipeline_for_operation operation=%r targets=%s",
            operation, targets,
        )
        from recon.tui.pipeline_runner import build_pipeline_fn
        from recon.tui.screens.planner import Operation

        if not isinstance(operation, Operation):
            return

        pipeline_fn = build_pipeline_fn(
            workspace_path=self._workspace_path,
            operation=operation,
            targets=targets,
        )

        # Delegate the run-mode handshake to the single launcher entry
        # point on the app. It owns the queue + mode switch + resume
        # handshake so screens never have to touch
        # ``app._pending_pipeline_fn`` directly.
        self.app.launch_pipeline(pipeline_fn)

    def _push_selector_then_start(self, operation: object) -> None:
        from recon.tui.screens.planner import Operation
        from recon.tui.screens.selector import CompetitorSelectorScreen

        if not isinstance(operation, Operation):
            return

        competitors = [row.get("name", "") for row in self._data.competitor_rows if row.get("name")]
        if not competitors:
            self.app.notify(
                "No competitors available to select.",
                severity="warning",
            )
            return

        def handle(selection: object | None) -> None:
            if not isinstance(selection, list) or not selection:
                self.app.notify(
                    "No competitors selected; run cancelled.",
                    severity="information",
                )
                return
            self._start_pipeline_for_operation(operation, targets=list(selection))

        self.app.push_screen(
            CompetitorSelectorScreen(competitors=competitors),
            handle,
        )

    def _api_key_status(self) -> str:
        env_path = self._workspace_path / ".env"
        if env_path.exists() and "ANTHROPIC_API_KEY" in env_path.read_text():
            return "[#DDEDC4]API key: configured[/]"
        if os.environ.get("ANTHROPIC_API_KEY"):
            return "[#DDEDC4]API key: set in environment[/]"
        return "[#fb4b4b]API key: not configured[/]"


def _estimate_full_run_cost(workspace) -> float:  # noqa: ANN001 -- runtime workspace type
    """Estimate the LLM cost of a full pipeline run on this workspace.

    Walks the schema's sections, asks ``CostTracker.estimate_section_cost``
    for each one across every profile at the section's verification
    tier, and adds a small overhead for the synthesize and deliver
    stages. Returns 0.0 if the schema isn't loaded.
    """
    from recon.cost import CostTracker, ModelPricing

    schema = getattr(workspace, "schema", None)
    if schema is None or not schema.sections:
        return 0.0

    profiles = workspace.list_profiles()
    competitor_count = len(profiles)
    if competitor_count == 0:
        return 0.0

    # claude-sonnet-4-5 default pricing -- matches Pipeline._DEFAULT_MODEL
    tracker = CostTracker(
        model_pricing=ModelPricing(
            model_id="claude-sonnet-4-20250514",
            input_price_per_million=3.0,
            output_price_per_million=15.0,
        ),
    )

    research_cost = 0.0
    for section in schema.sections:
        research_cost += tracker.estimate_section_cost(
            format_type=section.preferred_format,
            competitor_count=competitor_count,
            verification_tier=section.verification_tier.value,
        )

    # Synthesize/deliver/themes are roughly 10-15% on top of research
    return research_cost * 1.15
