"""Tests for DashboardScreen."""

from __future__ import annotations

from pathlib import Path  # noqa: TCH003 -- used at runtime in fixtures

from textual.app import App, ComposeResult
from textual.widgets import Button, Static

from recon.tui.models.dashboard import DashboardData
from recon.tui.screens.dashboard import DashboardScreen


def _make_dashboard_data(
    total_competitors: int = 0,
    status_counts: dict[str, int] | None = None,
) -> DashboardData:
    return DashboardData(
        domain="Developer Tools",
        company_name="Acme Corp",
        total_competitors=total_competitors,
        status_counts=status_counts or {},
        competitor_rows=[],
    )


class _DashboardTestApp(App):
    CSS = "Screen { background: #000000; }"

    def __init__(self, data: DashboardData, workspace_path: Path) -> None:
        super().__init__()
        self._data = data
        self._workspace_path = workspace_path

    def compose(self) -> ComposeResult:
        yield DashboardScreen(data=self._data, workspace_path=self._workspace_path)


class TestDashboardScreen:
    def test_workspace_context_prefers_workspace_folder_name(self, tmp_path: Path) -> None:
        from recon.tui.shell import WorkspaceContext
        from recon.workspace import Workspace

        workspace_root = tmp_path / "lululemon"
        workspace_root.mkdir()
        (workspace_root / "recon.yaml").write_text(
            """
domain: athletic leisure and apparel brand
identity:
  company_name: athletic
  products: []
  decision_context: []
rating_scales: {}
sections: []
""".strip()
        )

        ws = Workspace.open(workspace_root)
        ctx = WorkspaceContext.from_workspace(ws)
        assert ctx.company_name == "lululemon"
        assert ctx.domain == "athletic leisure and apparel brand"

    async def test_shows_workspace_path(self, tmp_path: Path) -> None:
        """The workspace path lives in the persistent ReconHeaderBar
        chrome strip, not on the dashboard screen itself.
        """
        from recon.tui.shell import ReconHeaderBar, WorkspaceContext

        data = _make_dashboard_data(total_competitors=5)
        app = _DashboardTestApp(data, tmp_path)
        # The chrome reads workspace_context from the app.
        app.workspace_context = WorkspaceContext(
            workspace_path=tmp_path,
            domain="Developer Tools",
            company_name="Acme Corp",
        )
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            header = app.query_one(ReconHeaderBar)
            header.set_workspace_context(app.workspace_context)
            content = header._render_context(app.workspace_context)
            assert tmp_path.name in content

    async def test_shows_domain_and_company(self, tmp_path: Path) -> None:
        from recon.tui.shell import ReconHeaderBar, WorkspaceContext

        data = _make_dashboard_data(total_competitors=5)
        app = _DashboardTestApp(data, tmp_path)
        app.workspace_context = WorkspaceContext(
            workspace_path=tmp_path,
            domain="Developer Tools",
            company_name="Acme Corp",
        )
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            header = app.query_one(ReconHeaderBar)
            content = header._render_context(app.workspace_context)
            assert "Acme Corp" in content
            assert "Developer Tools" in content

    async def test_shows_competitor_count(self, tmp_path: Path) -> None:
        data = _make_dashboard_data(
            total_competitors=47,
            status_counts={"verified": 35, "researched": 12},
        )
        app = _DashboardTestApp(data, tmp_path)
        async with app.run_test(size=(120, 40)):
            stats = app.query_one("#competitor-stats", Static)
            assert "47" in str(stats.content)

    async def test_renders_only_next_planning_button(self, tmp_path: Path) -> None:
        data = _make_dashboard_data(total_competitors=5)
        app = _DashboardTestApp(data, tmp_path)
        async with app.run_test(size=(120, 40)):
            assert app.query_one("#dashboard-next", Button)
            assert not app.query("#dashboard-run")
            assert not app.query("#dashboard-discover")
            assert not app.query("#dashboard-browse")
            assert not app.query("#dashboard-schema")

    async def test_does_not_render_duplicate_company_domain_summary(
        self, tmp_path: Path
    ) -> None:
        data = _make_dashboard_data(total_competitors=5)
        app = _DashboardTestApp(data, tmp_path)
        async with app.run_test(size=(120, 40)):
            assert not app.query("#dashboard-summary")

    async def test_empty_workspace_shows_prompt(self, tmp_path: Path) -> None:
        data = _make_dashboard_data(total_competitors=0)
        app = _DashboardTestApp(data, tmp_path)
        async with app.run_test(size=(120, 40)):
            assert app.query_one("#empty-prompt")

    async def test_empty_workspace_does_not_render_action_buttons(
        self, tmp_path: Path
    ) -> None:
        """Empty-state CTAs ("Start Discovery" / "Add Manually") are
        replaced by keybind-driven actions and an instructional Static.
        """
        data = _make_dashboard_data(total_competitors=0)
        app = _DashboardTestApp(data, tmp_path)
        async with app.run_test(size=(120, 40)):
            assert not app.query("#btn-empty-discover")
            assert not app.query("#btn-empty-manual")

    async def test_populated_workspace_hides_empty_prompt(self, tmp_path: Path) -> None:
        data = _make_dashboard_data(total_competitors=10)
        app = _DashboardTestApp(data, tmp_path)
        async with app.run_test(size=(120, 40)):
            empty_prompts = app.query("#empty-prompt")
            assert len(empty_prompts) == 0

    async def test_shows_status_breakdown(self, tmp_path: Path) -> None:
        data = _make_dashboard_data(
            total_competitors=47,
            status_counts={"verified": 35, "researched": 12},
        )
        app = _DashboardTestApp(data, tmp_path)
        async with app.run_test(size=(120, 40)):
            breakdown = app.query_one("#status-breakdown", Static)
            content = str(breakdown.content)
            assert "verified" in content
            assert "35" in content


class TestDashboardKeybindings:
    async def test_action_browse_pushes_browser_screen(self, tmp_path: Path) -> None:
        from recon.tui.screens.browser import CompetitorBrowserScreen

        data = _make_dashboard_data(total_competitors=5, status_counts={"scaffold": 5})
        app = _DashboardTestApp(data, tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            screen = app.query_one(DashboardScreen)
            screen.action_browse()
            await pilot.pause()
            assert isinstance(app.screen, CompetitorBrowserScreen)

    async def test_action_discover_pushes_discovery_screen(self, tmp_path: Path) -> None:
        from recon.tui.screens.discovery import DiscoveryScreen

        data = _make_dashboard_data(total_competitors=5)
        app = _DashboardTestApp(data, tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            screen = app.query_one(DashboardScreen)
            screen.action_discover()
            await pilot.pause()
            assert isinstance(app.screen, DiscoveryScreen)

    async def test_action_run_pushes_planner_screen(self, tmp_path: Path) -> None:
        from recon.tui.screens.planner import RunPlannerScreen

        data = _make_dashboard_data(total_competitors=10, status_counts={"scaffold": 10})
        app = _DashboardTestApp(data, tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            screen = app.query_one(DashboardScreen)
            screen.action_run()
            await pilot.pause()
            assert isinstance(app.screen, RunPlannerScreen)

    async def test_action_run_on_empty_workspace_notifies_instead_of_pushing(
        self, tmp_path: Path
    ) -> None:
        from unittest.mock import patch

        from recon.tui.screens.planner import RunPlannerScreen

        data = _make_dashboard_data(total_competitors=0)
        app = _DashboardTestApp(data, tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            screen = app.query_one(DashboardScreen)
            notes: list[str] = []
            with patch.object(
                type(app), "notify", lambda self, msg, **kw: notes.append(msg),
            ):
                screen.action_run()
                await pilot.pause()
            assert any("Nothing to run" in n or "No competitors" in n for n in notes)
            assert not isinstance(app.screen, RunPlannerScreen)

    async def test_action_add_manually_mounts_input_on_empty_workspace(
        self, tmp_path: Path
    ) -> None:
        from textual.widgets import Input

        data = _make_dashboard_data(total_competitors=0)
        app = _DashboardTestApp(data, tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            screen = app.query_one(DashboardScreen)
            screen.action_add_manually()
            await pilot.pause()
            assert app.query_one("#manual-add-input", Input) is not None

    async def test_keybind_hints_mention_top_nav_routes(
        self, tmp_path: Path
    ) -> None:
        data = _make_dashboard_data(total_competitors=5)
        app = _DashboardTestApp(data, tmp_path)
        async with app.run_test(size=(120, 40)):
            screen = app.query_one(DashboardScreen)
            hints = screen.keybind_hints
            assert "2" in hints
            assert "3" in hints
            assert "4" in hints
            assert "6" in hints
            assert "next planning" in hints


class TestDashboardWiring:

    async def test_action_start_discovery_pushes_discovery_on_empty(
        self, tmp_path: Path
    ) -> None:
        """The hidden ``y`` binding routes through ``action_start_discovery``
        which only fires on empty workspaces. The action method is
        unit-tested directly here; an end-to-end ``pilot.press("y")``
        check lives in the integration suite, where ReconApp pushes
        DashboardScreen as a real active screen and the binding
        traversal works normally.
        """
        from recon.tui.screens.discovery import DiscoveryScreen

        data = _make_dashboard_data(total_competitors=0)
        app = _DashboardTestApp(data, tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            screen = app.query_one(DashboardScreen)
            screen.action_start_discovery()
            await pilot.pause()
            assert isinstance(app.screen, DiscoveryScreen)

    async def test_refresh_updates_data(self, tmp_path: Path) -> None:
        data = _make_dashboard_data(total_competitors=5, status_counts={"scaffold": 5})
        app = _DashboardTestApp(data, tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            screen = app.query_one(DashboardScreen)
            new_data = _make_dashboard_data(
                total_competitors=10,
                status_counts={"scaffold": 5, "researched": 5},
            )
            screen.refresh_data(new_data)
            await pilot.pause()
            stats = app.query_one("#competitor-stats", Static)
            assert "10" in str(stats.content)

    async def test_planner_result_switches_to_run_mode(self, tmp_workspace: Path) -> None:
        from recon.tui.app import ReconApp
        from recon.tui.screens.planner import Operation

        app = ReconApp(workspace_path=tmp_workspace)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, DashboardScreen)
            screen.handle_planner_result(Operation.FULL_PIPELINE)
            await pilot.pause()
            await pilot.pause()
            await pilot.pause()
            assert app.current_mode == "run"

    async def test_discovery_dismiss_creates_profiles(self, tmp_workspace: Path) -> None:
        from recon.discovery import CompetitorTier, DiscoveryCandidate
        from recon.workspace import Workspace

        data = _make_dashboard_data(total_competitors=0)
        app = _DashboardTestApp(data, tmp_workspace)
        async with app.run_test(size=(120, 40)) as pilot:
            screen = app.query_one(DashboardScreen)
            candidates = [
                DiscoveryCandidate(
                    name="TestCo",
                    url="https://testco.com",
                    blurb="A test company",
                    provenance="test",
                    suggested_tier=CompetitorTier.ESTABLISHED,
                    accepted=True,
                ),
            ]
            screen.handle_discovery_result(candidates)
            await pilot.pause()

            ws = Workspace.open(tmp_workspace)
            profiles = ws.list_profiles()
            names = [p["name"] for p in profiles]
            assert "TestCo" in names
