"""Tests for ThemeCurationScreen."""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.widgets import Button, Static

from recon.themes import DiscoveredTheme
from recon.tui.models.curation import ThemeCurationModel
from recon.tui.screens.curation import ThemeCurationScreen


def _make_themes(count: int = 5) -> list[DiscoveredTheme]:
    strengths = ["strong", "strong", "moderate", "moderate", "weak"]
    return [
        DiscoveredTheme(
            label=f"Theme {i}",
            evidence_chunks=[{"text": f"evidence {i}"}] * (count - i),
            evidence_strength=strengths[i % len(strengths)],
            suggested_queries=[f"query for theme {i}"],
            cluster_center=[0.1 * i],
        )
        for i in range(count)
    ]


class _CurationTestApp(App):
    CSS = "Screen { background: #000000; }"
    dismissed_result: list[DiscoveredTheme] | None = None

    def __init__(self, themes: list[DiscoveredTheme]) -> None:
        super().__init__()
        self._themes = themes

    def compose(self) -> ComposeResult:
        yield Static("")

    def on_mount(self) -> None:
        def on_dismiss(result: list[DiscoveredTheme] | None) -> None:
            self.dismissed_result = result

        model = ThemeCurationModel.from_themes(self._themes)
        self.push_screen(ThemeCurationScreen(model=model), on_dismiss)


class TestThemeCurationScreen:
    async def test_shows_theme_count(self) -> None:
        app = _CurationTestApp(themes=_make_themes(5))
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            title = app.screen.query_one("#curation-title", Static)
            assert "5" in str(title.content)

    async def test_shows_theme_entries(self) -> None:
        app = _CurationTestApp(themes=_make_themes(3))
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            items = app.screen.query(".theme-entry")
            assert len(items) == 3

    async def test_toggle_theme(self) -> None:
        app = _CurationTestApp(themes=_make_themes(3))
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, ThemeCurationScreen)
            screen.toggle_theme(0)
            assert not screen.model.entries[0].enabled

    async def test_done_dismisses_with_selected_themes(self) -> None:
        themes = _make_themes(5)
        app = _CurationTestApp(themes=themes)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            app.screen.query_one("#btn-done", Button).press()
            await pilot.pause()
            assert app.dismissed_result is not None
            assert len(app.dismissed_result) >= 1

    async def test_weak_themes_disabled_by_default(self) -> None:
        themes = _make_themes(5)
        app = _CurationTestApp(themes=themes)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, ThemeCurationScreen)
            weak_entries = [e for e in screen.model.entries if e.evidence_strength == "weak"]
            for entry in weak_entries:
                assert not entry.enabled
