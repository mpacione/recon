"""Tests for CompetitorSelectorScreen."""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.widgets import Button, Static

from recon.tui.screens.selector import CompetitorSelectorScreen


class _SelectorTestApp(App):
    CSS = "Screen { background: #000000; }"
    dismissed_result: list[str] | None = None

    def __init__(self, competitors: list[str]) -> None:
        super().__init__()
        self._competitors = competitors

    def compose(self) -> ComposeResult:
        yield Static("")

    def on_mount(self) -> None:
        def on_dismiss(result: list[str] | None) -> None:
            self.dismissed_result = result

        self.push_screen(
            CompetitorSelectorScreen(competitors=self._competitors),
            on_dismiss,
        )


class TestCompetitorSelectorScreen:
    async def test_shows_all_competitors(self) -> None:
        app = _SelectorTestApp(["Cursor", "Linear", "GitLab"])
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            items = app.screen.query(".selector-item")
            assert len(items) == 3

    async def test_all_selected_by_default(self) -> None:
        app = _SelectorTestApp(["Cursor", "Linear"])
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, CompetitorSelectorScreen)
            assert screen.selected == ["Cursor", "Linear"]

    async def test_toggle_deselects(self) -> None:
        app = _SelectorTestApp(["Cursor", "Linear"])
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, CompetitorSelectorScreen)
            screen.toggle(0)
            assert screen.selected == ["Linear"]

    async def test_done_dismisses_with_selected(self) -> None:
        app = _SelectorTestApp(["Cursor", "Linear", "GitLab"])
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, CompetitorSelectorScreen)
            screen.toggle(1)
            app.screen.query_one("#btn-done", Button).press()
            await pilot.pause()
            assert app.dismissed_result == ["Cursor", "GitLab"]

    async def test_select_all_selects_all(self) -> None:
        app = _SelectorTestApp(["Cursor", "Linear", "GitLab"])
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, CompetitorSelectorScreen)
            screen.toggle(0)
            screen.toggle(1)
            assert len(screen.selected) == 1
            screen.select_all()
            assert len(screen.selected) == 3

    async def test_item_button_click_toggles(self) -> None:
        app = _SelectorTestApp(["Cursor", "Linear"])
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            app.screen.query_one("#selector-0", Button).press()
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, CompetitorSelectorScreen)
            assert screen.selected == ["Linear"]

    async def test_cancel_button_dismisses_empty(self) -> None:
        app = _SelectorTestApp(["Cursor", "Linear"])
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            app.screen.query_one("#btn-cancel", Button).press()
            await pilot.pause()
            assert app.dismissed_result == []
