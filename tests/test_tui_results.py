"""Tests for the Results screen (Screen 9).

Post-run summary: stats, executive summary preview, output file
paths, keybinds to open.
"""

from __future__ import annotations

from pathlib import Path

from textual.app import App, ComposeResult
from textual.widgets import Static


class TestResultsScreen:
    async def test_mounts_with_stats(self, tmp_path: Path) -> None:
        from recon.tui.screens.results import ResultsScreen

        (tmp_path / "executive_summary.md").write_text(
            "# Executive Summary\n\nThe market is competitive.\n"
        )
        themes_dir = tmp_path / "themes"
        themes_dir.mkdir()
        (themes_dir / "theme_one.md").write_text("# Theme One\n")

        class _App(App):
            CSS = "Screen { background: #000000; }"

            def compose(self) -> ComposeResult:
                yield Static("")

            def on_mount(self_app) -> None:
                self_app.push_screen(ResultsScreen(
                    workspace_root=tmp_path,
                    competitor_count=12,
                    section_count=5,
                    theme_count=4,
                    total_cost=24.85,
                    elapsed="35:12",
                ))

        app = _App()
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.pause()
            assert isinstance(app.screen, ResultsScreen)

    async def test_shows_executive_summary_preview(self, tmp_path: Path) -> None:
        from recon.tui.screens.results import ResultsScreen

        (tmp_path / "executive_summary.md").write_text(
            "# Executive Summary\n\n"
            "The desktop additive manufacturing space is experiencing\n"
            "three convergent pressures.\n"
        )

        class _App(App):
            CSS = "Screen { background: #000000; }"

            def compose(self) -> ComposeResult:
                yield Static("")

            def on_mount(self_app) -> None:
                self_app.push_screen(ResultsScreen(
                    workspace_root=tmp_path,
                    competitor_count=5,
                    section_count=3,
                    theme_count=2,
                    total_cost=10.0,
                    elapsed="10:00",
                ))

        app = _App()
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.pause()
            statics = app.screen.query(Static)
            all_text = " ".join(str(s.render()) for s in statics)
            assert "additive" in all_text.lower() or "convergent" in all_text.lower()

    async def test_shows_output_files(self, tmp_path: Path) -> None:
        from recon.tui.screens.results import ResultsScreen

        themes_dir = tmp_path / "themes"
        themes_dir.mkdir()
        (themes_dir / "price_compression.md").write_text("# Price\n")
        (tmp_path / "executive_summary.md").write_text("# Summary\n")

        class _App(App):
            CSS = "Screen { background: #000000; }"

            def compose(self) -> ComposeResult:
                yield Static("")

            def on_mount(self_app) -> None:
                self_app.push_screen(ResultsScreen(
                    workspace_root=tmp_path,
                    competitor_count=5,
                    section_count=3,
                    theme_count=1,
                    total_cost=5.0,
                    elapsed="5:00",
                ))

        app = _App()
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.pause()
            statics = app.screen.query(Static)
            all_text = " ".join(str(s.render()) for s in statics)
            assert "Executive Summary" in all_text or "executive_summary" in all_text
            assert "Price" in all_text or "price_compression" in all_text
