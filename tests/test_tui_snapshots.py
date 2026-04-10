"""Visual snapshot tests for TUI screens.

Uses pytest-textual-snapshot to capture SVG screenshots of each screen
in a known state. Run `pytest --snapshot-update` to regenerate baselines.
"""

from __future__ import annotations

from pathlib import Path  # noqa: TCH003 -- used at runtime

from textual.app import App, ComposeResult
from textual.widgets import Static

from recon.discovery import CompetitorTier, DiscoveryCandidate, DiscoveryState
from recon.themes import DiscoveredTheme
from recon.tui.models.curation import ThemeCurationModel
from recon.tui.models.dashboard import DashboardData, SectionStatus
from recon.tui.screens.browser import CompetitorBrowserScreen
from recon.tui.screens.curation import ThemeCurationScreen
from recon.tui.screens.dashboard import DashboardScreen
from recon.tui.screens.discovery import DiscoveryScreen
from recon.tui.screens.planner import RunPlannerScreen
from recon.tui.screens.run import RunScreen
from recon.tui.screens.selector import CompetitorSelectorScreen
from recon.tui.screens.welcome import RecentProjectsManager, WelcomeScreen
from recon.tui.theme import RECON_CSS

# ---------------------------------------------------------------------------
# Test fixture apps -- each wraps one screen in a minimal app
# ---------------------------------------------------------------------------


class _WelcomeApp(App):
    CSS = RECON_CSS

    def __init__(self, recent_path: Path) -> None:
        super().__init__()
        self._recent_path = recent_path

    def compose(self) -> ComposeResult:
        yield WelcomeScreen(recent_projects_path=self._recent_path)


class _WelcomeWithRecentsApp(App):
    CSS = RECON_CSS

    def __init__(self, recent_path: Path) -> None:
        super().__init__()
        self._recent_path = recent_path

    def compose(self) -> ComposeResult:
        yield WelcomeScreen(recent_projects_path=self._recent_path)


class _DashboardEmptyApp(App):
    CSS = RECON_CSS

    def __init__(self, workspace_path: Path) -> None:
        super().__init__()
        self._workspace_path = workspace_path

    def compose(self) -> ComposeResult:
        data = DashboardData(
            domain="Developer Tools",
            company_name="Acme Corp",
            total_competitors=0,
            status_counts={},
            competitor_rows=[],
        )
        yield DashboardScreen(data=data, workspace_path=self._workspace_path)


class _DashboardPopulatedApp(App):
    CSS = RECON_CSS

    def __init__(self, workspace_path: Path) -> None:
        super().__init__()
        self._workspace_path = workspace_path

    def compose(self) -> ComposeResult:
        data = DashboardData(
            domain="Developer Tools",
            company_name="Acme Corp",
            total_competitors=47,
            status_counts={"verified": 35, "researched": 12},
            competitor_rows=[
                {"name": "Cursor", "type": "competitor", "status": "verified", "slug": "cursor"},
                {"name": "Linear", "type": "competitor", "status": "verified", "slug": "linear"},
                {"name": "GitHub Actions", "type": "competitor", "status": "researched", "slug": "github-actions"},
            ],
            section_statuses=[
                SectionStatus(key="overview", title="Overview", completed=47, total=47),
                SectionStatus(key="capabilities", title="Capabilities", completed=47, total=47),
                SectionStatus(key="pricing", title="Pricing", completed=45, total=47),
                SectionStatus(key="developer_love", title="Developer Love", completed=40, total=47),
            ],
            total_sections=4,
            theme_count=7,
            themes_selected=5,
            total_cost=142.30,
            last_run_cost=48.20,
            run_count=3,
        )
        yield DashboardScreen(data=data, workspace_path=self._workspace_path)


class _DiscoveryApp(App):
    CSS = RECON_CSS

    def compose(self) -> ComposeResult:
        yield Static("")

    def on_mount(self) -> None:
        state = DiscoveryState()
        state.add_round([
            DiscoveryCandidate(
                name="Cursor", url="https://cursor.com",
                blurb="AI-powered code editor with deep codebase understanding",
                provenance="G2 category leader, 3x alternatives lists",
                suggested_tier=CompetitorTier.ESTABLISHED,
            ),
            DiscoveryCandidate(
                name="Linear", url="https://linear.app",
                blurb="Project management for modern software teams",
                provenance="HN mentions, ProductHunt #1",
                suggested_tier=CompetitorTier.ESTABLISHED,
            ),
            DiscoveryCandidate(
                name="Earthly", url="https://earthly.dev",
                blurb="Repeatable build automation. YC W21 batch",
                provenance="alternatives to Bazel",
                suggested_tier=CompetitorTier.EMERGING,
                accepted=False,
            ),
        ])
        self.push_screen(DiscoveryScreen(state=state, domain="Developer Tools"))


class _PlannerApp(App):
    CSS = RECON_CSS

    def compose(self) -> ComposeResult:
        yield Static("")

    def on_mount(self) -> None:
        self.push_screen(RunPlannerScreen(competitor_count=47, section_count=8))


class _RunIdleApp(App):
    CSS = RECON_CSS

    def compose(self) -> ComposeResult:
        yield RunScreen()


class _RunActiveApp(App):
    CSS = RECON_CSS

    def compose(self) -> ComposeResult:
        yield RunScreen()

    def on_mount(self) -> None:
        screen = self.query_one(RunScreen)
        screen.current_phase = "research"
        screen.progress = 0.51
        screen.cost_usd = 18.40
        screen.add_activity("14:32  CircleCI -- Capabilities -- done")
        screen.add_activity("14:31  Jenkins -- Capabilities -- done")
        screen.add_activity("14:31  Drone -- Capabilities -- done")


class _CurationApp(App):
    CSS = RECON_CSS

    def compose(self) -> ComposeResult:
        yield Static("")

    def on_mount(self) -> None:
        themes = [
            DiscoveredTheme(
                label="Platform Consolidation",
                evidence_chunks=[{"text": "e"}] * 38,
                evidence_strength="strong",
                suggested_queries=["platform expansion"],
                cluster_center=[0.1],
            ),
            DiscoveredTheme(
                label="Agentic Shift",
                evidence_chunks=[{"text": "e"}] * 31,
                evidence_strength="strong",
                suggested_queries=["agent workflows"],
                cluster_center=[0.2],
            ),
            DiscoveredTheme(
                label="Developer Experience",
                evidence_chunks=[{"text": "e"}] * 45,
                evidence_strength="strong",
                suggested_queries=["DX quality"],
                cluster_center=[0.3],
            ),
            DiscoveredTheme(
                label="Pricing Race",
                evidence_chunks=[{"text": "e"}] * 29,
                evidence_strength="moderate",
                suggested_queries=["pricing pressure"],
                cluster_center=[0.4],
            ),
            DiscoveredTheme(
                label="Vertical Specialization",
                evidence_chunks=[{"text": "e"}] * 12,
                evidence_strength="weak",
                suggested_queries=["niche markets"],
                cluster_center=[0.5],
            ),
        ]
        model = ThemeCurationModel.from_themes(themes)
        self.push_screen(ThemeCurationScreen(model=model))


class _BrowserApp(App):
    CSS = RECON_CSS

    def compose(self) -> ComposeResult:
        yield Static("")

    def on_mount(self) -> None:
        data = DashboardData(
            domain="Developer Tools",
            company_name="Acme Corp",
            total_competitors=5,
            status_counts={"verified": 3, "researched": 2},
            competitor_rows=[
                {"name": "Cursor", "type": "competitor", "status": "verified", "slug": "cursor"},
                {"name": "Linear", "type": "competitor", "status": "verified", "slug": "linear"},
                {"name": "GitHub Actions", "type": "competitor", "status": "verified", "slug": "github-actions"},
                {"name": "Buildkite", "type": "competitor", "status": "researched", "slug": "buildkite"},
                {"name": "Earthly", "type": "competitor", "status": "researched", "slug": "earthly"},
            ],
        )
        self.push_screen(CompetitorBrowserScreen(data=data))


class _SelectorApp(App):
    CSS = RECON_CSS

    def compose(self) -> ComposeResult:
        yield Static("")

    def on_mount(self) -> None:
        self.push_screen(
            CompetitorSelectorScreen(
                competitors=["Cursor", "Linear", "GitHub Actions", "Buildkite", "Earthly"]
            )
        )


# ---------------------------------------------------------------------------
# Snapshot tests
# ---------------------------------------------------------------------------

_SIZE = (100, 40)


class TestWelcomeSnapshots:
    def test_welcome_empty(self, snap_compare, tmp_path: Path) -> None:
        assert snap_compare(
            _WelcomeApp(recent_path=tmp_path / "recent.json"),
            terminal_size=_SIZE,
        )

    def test_welcome_with_recents(self, snap_compare, tmp_path: Path) -> None:
        json_path = tmp_path / "recent.json"
        manager = RecentProjectsManager(json_path)
        manager.add(Path("/home/user/projects/acme-ci"), "Acme CI Research")
        manager.add(Path("/home/user/projects/fintech"), "Fintech Scan")
        manager.add(Path("/home/user/projects/devtools"), "DevTools Landscape")

        assert snap_compare(
            _WelcomeWithRecentsApp(recent_path=json_path),
            terminal_size=_SIZE,
        )


class TestDashboardSnapshots:
    def test_dashboard_empty(self, snap_compare, tmp_path: Path) -> None:
        assert snap_compare(
            _DashboardEmptyApp(workspace_path=tmp_path),
            terminal_size=_SIZE,
        )

    def test_dashboard_populated(self, snap_compare, tmp_path: Path) -> None:
        assert snap_compare(
            _DashboardPopulatedApp(workspace_path=tmp_path),
            terminal_size=_SIZE,
        )


class TestDiscoverySnapshots:
    def test_discovery_with_candidates(self, snap_compare) -> None:
        assert snap_compare(_DiscoveryApp(), terminal_size=_SIZE)


class TestPlannerSnapshots:
    def test_planner_menu(self, snap_compare) -> None:
        assert snap_compare(_PlannerApp(), terminal_size=_SIZE)


class TestRunSnapshots:
    def test_run_idle(self, snap_compare) -> None:
        assert snap_compare(_RunIdleApp(), terminal_size=_SIZE)

    def test_run_active(self, snap_compare) -> None:
        assert snap_compare(_RunActiveApp(), terminal_size=_SIZE)


class TestCurationSnapshots:
    def test_curation_with_themes(self, snap_compare) -> None:
        assert snap_compare(_CurationApp(), terminal_size=_SIZE)


class TestBrowserSnapshots:
    def test_browser_with_competitors(self, snap_compare) -> None:
        assert snap_compare(_BrowserApp(), terminal_size=_SIZE)


class TestSelectorSnapshots:
    def test_selector_with_competitors(self, snap_compare) -> None:
        assert snap_compare(_SelectorApp(), terminal_size=_SIZE)
