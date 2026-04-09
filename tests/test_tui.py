"""Tests for the TUI layer.

The TUI uses Textual with a warm amber retro terminal aesthetic
(cyberspace.online reference). Tests verify the app bootstraps,
renders screens, and responds to key events.
"""


from textual.app import App

from recon.tui.app import ReconApp
from recon.tui.theme import RECON_THEME


class TestReconTheme:
    def test_theme_has_required_colors(self) -> None:
        assert "background" in RECON_THEME
        assert "foreground" in RECON_THEME
        assert "accent" in RECON_THEME
        assert "dim" in RECON_THEME
        assert "border" in RECON_THEME

    def test_background_is_pure_black(self) -> None:
        assert RECON_THEME["background"] == "#000000"

    def test_foreground_is_warm_parchment(self) -> None:
        assert RECON_THEME["foreground"] == "#efe5c0"

    def test_accent_is_warm_amber(self) -> None:
        assert RECON_THEME["accent"] == "#e0a044"


class TestReconApp:
    async def test_app_instantiates(self) -> None:
        app = ReconApp()
        assert isinstance(app, App)

    async def test_app_has_title(self) -> None:
        app = ReconApp()
        assert app.title == "recon"

    async def test_app_mounts(self) -> None:
        app = ReconApp()
        async with app.run_test(size=(120, 40)):
            assert app.is_running

    async def test_app_shows_header(self) -> None:
        app = ReconApp()
        async with app.run_test(size=(120, 40)):
            header = app.query_one("Header")
            assert header is not None

    async def test_app_shows_footer(self) -> None:
        app = ReconApp()
        async with app.run_test(size=(120, 40)):
            footer = app.query_one("Footer")
            assert footer is not None

    async def test_quit_binding(self) -> None:
        app = ReconApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("q")
            assert not app.is_running
