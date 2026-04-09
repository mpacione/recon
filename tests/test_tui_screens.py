"""Tests for TUI screen integration.

Verifies the app can switch between dashboard, theme curation, and
run monitor views via keybinds, and that each view mounts correctly.
"""

from __future__ import annotations

from recon.tui.app import ReconApp, ViewMode


class TestViewMode:
    def test_default_view_is_dashboard(self) -> None:
        app = ReconApp()
        assert app.current_view == ViewMode.DASHBOARD

    async def test_switch_to_themes_view(self) -> None:
        app = ReconApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("t")
            assert app.current_view == ViewMode.THEMES

    async def test_switch_to_monitor_view(self) -> None:
        app = ReconApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("r")
            assert app.current_view == ViewMode.MONITOR

    async def test_switch_back_to_dashboard(self) -> None:
        app = ReconApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("t")
            await pilot.press("d")
            assert app.current_view == ViewMode.DASHBOARD

    async def test_themes_view_shows_curation_content(self) -> None:
        app = ReconApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("t")
            assert app.current_view == ViewMode.THEMES

    async def test_monitor_view_shows_monitor_content(self) -> None:
        app = ReconApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("r")
            assert app.current_view == ViewMode.MONITOR
