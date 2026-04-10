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
    async def test_shows_workspace_path(self, tmp_path: Path) -> None:
        data = _make_dashboard_data(total_competitors=5)
        app = _DashboardTestApp(data, tmp_path)
        async with app.run_test(size=(120, 40)):
            path_label = app.query_one("#workspace-path", Static)
            assert str(tmp_path) in str(path_label.content)

    async def test_shows_domain_and_company(self, tmp_path: Path) -> None:
        data = _make_dashboard_data(total_competitors=5)
        app = _DashboardTestApp(data, tmp_path)
        async with app.run_test(size=(120, 40)):
            header = app.query_one("#dashboard-header", Static)
            content = str(header.content)
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

    async def test_shows_action_buttons(self, tmp_path: Path) -> None:
        data = _make_dashboard_data(total_competitors=5)
        app = _DashboardTestApp(data, tmp_path)
        async with app.run_test(size=(120, 40)):
            assert app.query_one("#btn-run", Button)
            assert app.query_one("#btn-discover", Button)
            assert app.query_one("#btn-browse", Button)

    async def test_empty_workspace_shows_prompt(self, tmp_path: Path) -> None:
        data = _make_dashboard_data(total_competitors=0)
        app = _DashboardTestApp(data, tmp_path)
        async with app.run_test(size=(120, 40)):
            prompt = app.query_one("#empty-prompt", Static)
            assert "No competitors" in str(prompt.content)

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


class TestDashboardButtonWiring:
    async def test_browse_button_pushes_browser_screen(self, tmp_path: Path) -> None:
        from recon.tui.screens.browser import CompetitorBrowserScreen

        data = _make_dashboard_data(total_competitors=5, status_counts={"scaffold": 5})
        app = _DashboardTestApp(data, tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            app.query_one("#btn-browse", Button).press()
            await pilot.pause()
            assert isinstance(app.screen, CompetitorBrowserScreen)

    async def test_discover_button_pushes_discovery_screen(self, tmp_path: Path) -> None:
        from recon.tui.screens.discovery import DiscoveryScreen

        data = _make_dashboard_data(total_competitors=5)
        app = _DashboardTestApp(data, tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            app.query_one("#btn-discover", Button).press()
            await pilot.pause()
            assert isinstance(app.screen, DiscoveryScreen)

    async def test_run_button_pushes_planner_screen(self, tmp_path: Path) -> None:
        from recon.tui.screens.planner import RunPlannerScreen

        data = _make_dashboard_data(total_competitors=10, status_counts={"scaffold": 10})
        app = _DashboardTestApp(data, tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            app.query_one("#btn-run", Button).press()
            await pilot.pause()
            assert isinstance(app.screen, RunPlannerScreen)

    async def test_y_key_on_empty_workspace_pushes_discovery(self, tmp_path: Path) -> None:
        from recon.tui.screens.discovery import DiscoveryScreen

        data = _make_dashboard_data(total_competitors=0)
        app = _DashboardTestApp(data, tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("y")
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
