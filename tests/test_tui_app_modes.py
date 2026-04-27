"""Tests for ReconApp Modes-based architecture."""

from __future__ import annotations

from pathlib import Path  # noqa: TCH003 -- used at runtime in fixtures

from recon.workspace import Workspace
from recon.discovery import CompetitorTier, DiscoveryCandidate
from recon.tui.app import ReconApp
from textual.widgets import Button, DataTable

from recon.tui.screens.describe import DescribeScreen
from recon.tui.screens.confirm import ConfirmResult
from recon.tui.screens.discovery import DiscoveryScreen
from recon.tui.screens.plan import PlanScreen
from recon.tui.screens.results import ResultsScreen
from recon.tui.screens.run import RunScreen
from recon.tui.screens.welcome import WelcomeScreen


class TestReconAppModes:
    async def test_default_mode_is_dashboard(self) -> None:
        app = ReconApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            assert app.current_mode == "dashboard"

    async def test_home_screen_is_active(self, tmp_workspace: Path) -> None:
        app = ReconApp(workspace_path=tmp_workspace)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            assert isinstance(app.screen, WelcomeScreen)

    async def test_no_workspace_shows_welcome(self) -> None:
        app = ReconApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            from recon.tui.screens.welcome import WelcomeScreen

            assert isinstance(app.screen, WelcomeScreen)

    async def test_switch_to_run_mode(self, tmp_workspace: Path) -> None:
        app = ReconApp(workspace_path=tmp_workspace)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            app.switch_mode("run")
            await pilot.pause()
            assert app.current_mode == "run"
            assert isinstance(app.screen, RunScreen)

    async def test_switch_back_to_dashboard(self, tmp_workspace: Path) -> None:
        app = ReconApp(workspace_path=tmp_workspace)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            app.switch_mode("run")
            await pilot.pause()
            app.switch_mode("dashboard")
            await pilot.pause()
            assert app.current_mode == "dashboard"

    async def test_number_hotkeys_switch_between_tabs(self, tmp_workspace: Path) -> None:
        app = ReconApp(workspace_path=tmp_workspace)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            assert isinstance(app.screen, WelcomeScreen)

            await pilot.press("1")
            await pilot.pause()
            assert isinstance(app.screen, PlanScreen)

            await pilot.press("4")
            await pilot.pause()
            assert app.current_mode == "run"
            assert isinstance(app.screen, RunScreen)

            await pilot.press("5")
            await pilot.pause()
            assert isinstance(app.screen, ResultsScreen)

            await pilot.press("0")
            await pilot.pause()
            assert app.current_mode == "dashboard"
            assert isinstance(app.screen, WelcomeScreen)

    async def test_number_hotkeys_work_even_with_action_buttons_present(
        self, tmp_workspace: Path,
    ) -> None:
        app = ReconApp(workspace_path=tmp_workspace)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()

            await pilot.press("4")
            await pilot.pause()
            assert isinstance(app.screen, RunScreen)

            pause_button = app.screen.query_one("#run-pause", Button)
            pause_button.focus()
            await pilot.pause()

            await pilot.press("5")
            await pilot.pause()
            assert isinstance(app.screen, ResultsScreen)

            await pilot.press("0")
            await pilot.pause()
            assert isinstance(app.screen, WelcomeScreen)

    async def test_space_advances_between_top_level_workflow_screens(
        self, tmp_workspace: Path,
    ) -> None:
        app = ReconApp(workspace_path=tmp_workspace)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()

            await pilot.press("1")
            await pilot.pause()
            assert isinstance(app.screen, PlanScreen)

            await pilot.press("space")
            await pilot.pause()
            from recon.tui.screens.template import TemplateScreen

            assert isinstance(app.screen, TemplateScreen)

            await pilot.press("3")
            await pilot.pause()
            assert isinstance(app.screen, DiscoveryScreen)

            await pilot.press("space")
            await pilot.pause()
            assert isinstance(app.screen, RunScreen)

            await pilot.press("space")
            await pilot.pause()
            assert isinstance(app.screen, ResultsScreen)

            await pilot.press("space")
            await pilot.pause()
            assert isinstance(app.screen, WelcomeScreen)

    async def test_home_hotkey_pops_back_from_comps_screen(self, tmp_workspace: Path) -> None:
        app = ReconApp(workspace_path=tmp_workspace)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            assert isinstance(app.screen, WelcomeScreen)

            await pilot.press("3")
            await pilot.pause()
            assert isinstance(app.screen, DiscoveryScreen)

            await pilot.press("0")
            await pilot.pause()
            assert app.current_mode == "dashboard"
            assert isinstance(app.screen, WelcomeScreen)

    async def test_workspace_path_accessible(self, tmp_workspace: Path) -> None:
        app = ReconApp(workspace_path=tmp_workspace)
        assert app.workspace_path == tmp_workspace

    async def test_workspace_selected_sets_path_and_switches(self, tmp_workspace: Path) -> None:
        from recon.tui.screens.welcome import WelcomeScreen

        app = ReconApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            assert isinstance(app.screen, WelcomeScreen)
            app.screen.post_message(
                WelcomeScreen.WorkspaceSelected(str(tmp_workspace))
            )
            await pilot.pause()
            await pilot.pause()
            assert app.workspace_path == tmp_workspace
            assert isinstance(app.screen, PlanScreen)

    async def test_new_project_pushes_describe_screen(self, tmp_path: Path) -> None:
        from recon.tui.screens.welcome import WelcomeScreen

        app = ReconApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            assert isinstance(app.screen, WelcomeScreen)
            new_path = tmp_path / "brand-new-project"
            app.screen.post_message(
                WelcomeScreen.NewProjectRequested(str(new_path))
            )
            await pilot.pause()
            await pilot.pause()
            assert app.is_running
            assert isinstance(app.screen, DescribeScreen)

    async def test_new_project_expands_tilde_path(self, tmp_path: Path, monkeypatch) -> None:
        from recon.tui.screens.welcome import WelcomeScreen

        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setenv("HOME", str(fake_home))

        app = ReconApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            assert isinstance(app.screen, WelcomeScreen)

            app.screen.post_message(
                WelcomeScreen.NewProjectRequested("~/recon-workspaces/test-project")
            )
            await pilot.pause()
            await pilot.pause()

            assert isinstance(app.screen, DescribeScreen)
            assert app.screen._output_dir == fake_home / "recon-workspaces" / "test-project"

    async def test_new_project_completion_lands_in_plan(self, tmp_path: Path) -> None:
        from recon.tui.screens.describe import DescribeResult

        app = ReconApp()
        new_path = tmp_path / "new-project"
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            app._handle_describe_result(
                DescribeResult(
                    output_dir=new_path,
                    description="Novalab makes infra-red light therapy devices",
                    api_keys={},
                )
            )
            await pilot.pause()
            await pilot.pause()
            assert app.workspace_path == new_path
            assert isinstance(app.screen, PlanScreen)

    async def test_new_project_prewarms_discovery_in_background(self, tmp_path: Path) -> None:
        from recon.tui.screens.describe import DescribeResult

        app = ReconApp()
        new_path = tmp_path / "prewarm-project"
        captured: list[str] = []

        async def fake_search(_state):
            return [
                DiscoveryCandidate(
                    name="Therabody",
                    url="https://www.therabody.com",
                    blurb="Light therapy adjacent recovery brand",
                    provenance="test",
                    suggested_tier=CompetitorTier.ESTABLISHED,
                )
            ]

        def capture_state(state) -> None:
            captured.extend(candidate.name for candidate in state.all_candidates)

        app._build_discovery_search_fn = lambda _domain: fake_search  # type: ignore[method-assign]
        app._save_discovery_state_and_sync = capture_state  # type: ignore[method-assign]

        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            app._handle_describe_result(
                DescribeResult(
                    output_dir=new_path,
                    description="Novalab makes infra-red light therapy devices",
                    api_keys={},
                )
            )
            await pilot.pause()
            await pilot.pause()
            assert isinstance(app.screen, PlanScreen)
            assert "Therabody" in captured

    async def test_plan_screen_refreshes_after_settings_save(self, tmp_workspace: Path) -> None:
        Workspace.open(tmp_workspace).create_profile("Therabody")

        app = ReconApp(workspace_path=tmp_workspace)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.press("1")
            await pilot.pause()
            assert isinstance(app.screen, PlanScreen)

            before = str(app.screen.query_one("#plan-cost").render())
            assert "Total cost per company" in before
            assert "Fixed overhead" in before

            app._handle_plan_settings_result(
                ConfirmResult(model_name="opus", workers=8, verification_mode="deep")
            )
            await pilot.pause()

            settings = str(app.screen.query_one("#plan-settings").render())
            after = str(app.screen.query_one("#plan-cost").render())

            assert "opus" in settings.lower()
            assert "8" in settings
            assert "deep" in settings.lower()
            assert "Total cost per company" in after
            assert "Verification uplift" in after
            assert "Projected full run" in after
            assert after != before

    async def test_plan_screen_shows_nominal_projection_with_zero_companies(
        self, tmp_workspace: Path,
    ) -> None:
        app = ReconApp(workspace_path=tmp_workspace)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.press("1")
            await pilot.pause()
            assert isinstance(app.screen, PlanScreen)

            cost = str(app.screen.query_one("#plan-cost").render())
            assert "nominal 10-company run" in cost
            assert "Estimated time:" in cost
            assert "Projected full run (nominal 10-company run): ~$1.07" in cost

    async def test_plan_screen_direct_controls_update_settings_and_cost(
        self, tmp_workspace: Path,
    ) -> None:
        Workspace.open(tmp_workspace).create_profile("Therabody")

        app = ReconApp(workspace_path=tmp_workspace)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.press("1")
            await pilot.pause()
            assert isinstance(app.screen, PlanScreen)

            before_settings = str(app.screen.query_one("#plan-settings").render())
            before_cost = str(app.screen.query_one("#plan-cost").render())

            await pilot.press("m", "v", "+")
            await pilot.pause()

            after_settings = str(app.screen.query_one("#plan-settings").render())
            after_cost = str(app.screen.query_one("#plan-cost").render())

            assert after_settings != before_settings
            assert "opus" in after_settings.lower()
            assert "verified" in after_settings.lower()
            assert "6" in after_settings
            assert after_cost != before_cost

    async def test_companies_screen_refreshes_when_background_discovery_arrives(
        self, tmp_workspace: Path,
    ) -> None:
        from recon.discovery import DiscoveryState

        app = ReconApp(workspace_path=tmp_workspace)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.press("3")
            await pilot.pause()
            assert isinstance(app.screen, DiscoveryScreen)

            state = DiscoveryState()
            state.add_round(
                [
                    DiscoveryCandidate(
                        name="Therabody",
                        url="https://www.therabody.com",
                        blurb="Light therapy adjacent recovery brand",
                        provenance="test",
                        suggested_tier=CompetitorTier.ESTABLISHED,
                    )
                ]
            )
            app._save_discovery_state_and_sync(state)
            await pilot.pause()
            await pilot.pause()

            table = app.screen.query_one("#discovery-table", DataTable)
            assert table.row_count == 1

    async def test_run_hotkey_starts_pipeline_when_already_on_agents(
        self, tmp_workspace: Path,
    ) -> None:
        app = ReconApp(workspace_path=tmp_workspace)
        started: list[str] = []

        async def fake_pipeline(_screen):
            started.append("started")

        def fake_launch_from_plan() -> None:
            app.launch_pipeline(fake_pipeline)

        app.launch_pipeline_from_plan = fake_launch_from_plan  # type: ignore[method-assign]

        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.press("4")
            await pilot.pause()
            assert isinstance(app.screen, RunScreen)

            await pilot.press("r")
            await pilot.pause()
            await pilot.pause()

            assert started == ["started"]
