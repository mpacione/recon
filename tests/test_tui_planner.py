"""Tests for RunPlannerScreen."""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.widgets import Button, Static

from recon.tui.screens.planner import Operation, RunPlannerScreen


class _PlannerTestApp(App):
    CSS = "Screen { background: #000000; }"
    selected_operation: Operation | None = None

    def __init__(self, competitor_count: int = 10, section_count: int = 8) -> None:
        super().__init__()
        self._competitor_count = competitor_count
        self._section_count = section_count

    def compose(self) -> ComposeResult:
        yield Static("")

    def on_mount(self) -> None:
        def on_dismiss(result: Operation | None) -> None:
            self.selected_operation = result

        self.push_screen(
            RunPlannerScreen(
                competitor_count=self._competitor_count,
                section_count=self._section_count,
            ),
            on_dismiss,
        )


class TestRunPlannerScreen:
    async def test_shows_workspace_stats(self) -> None:
        app = _PlannerTestApp(competitor_count=47, section_count=8)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            stats = app.screen.query_one("#planner-stats", Static)
            content = str(stats.content)
            assert "47" in content
            assert "8" in content

    async def test_shows_all_seven_operations(self) -> None:
        app = _PlannerTestApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            items = app.screen.query(".operation-button")
            assert len(items) == 7

    async def test_operation_button_dismisses_with_selection(self) -> None:
        app = _PlannerTestApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            app.screen.query_one("#btn-op-6", Button).press()
            await pilot.pause()
            assert app.selected_operation == Operation.FULL_PIPELINE

    async def test_back_dismisses_with_none(self) -> None:
        app = _PlannerTestApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            app.screen.query_one("#btn-back", Button).press()
            await pilot.pause()
            assert app.selected_operation is None

    async def test_all_operations_defined(self) -> None:
        assert len(Operation) == 7

    async def test_number_key_selects_and_confirms(self) -> None:
        app = _PlannerTestApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.press("7")
            await pilot.pause()
            assert app.selected_operation == Operation.FULL_PIPELINE
