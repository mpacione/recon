"""Tests for the Cost Confirmation screen (Screen 6).

Shows cost breakdown, model selection, worker count adjustment.
Explicit gate before spending money.
"""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.widgets import Static


class _ConfirmTestApp(App):
    CSS = "Screen { background: #000000; }"

    def compose(self) -> ComposeResult:
        yield Static("")

    def on_mount(self) -> None:
        from recon.tui.screens.confirm import ConfirmScreen

        self.push_screen(ConfirmScreen(
            competitor_count=12,
            section_count=5,
        ))


class TestConfirmScreen:
    async def test_mounts_without_error(self) -> None:
        app = _ConfirmTestApp()
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.pause()
            from recon.tui.screens.confirm import ConfirmScreen

            assert isinstance(app.screen, ConfirmScreen)

    async def test_shows_cost_breakdown(self) -> None:
        app = _ConfirmTestApp()
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.pause()
            statics = app.screen.query(Static)
            all_text = " ".join(str(s.render()) for s in statics)
            assert "$" in all_text
            assert "Research" in all_text or "research" in all_text

    async def test_shows_model_options(self) -> None:
        app = _ConfirmTestApp()
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.pause()
            statics = app.screen.query(Static)
            all_text = " ".join(str(s.render()) for s in statics)
            assert "Sonnet" in all_text or "sonnet" in all_text

    async def test_result_contains_model_and_workers(self) -> None:
        from recon.tui.screens.confirm import ConfirmResult, ConfirmScreen

        results: list[ConfirmResult] = []

        class _App(App):
            CSS = "Screen { background: #000000; }"

            def compose(self) -> ComposeResult:
                yield Static("")

            def on_mount(self) -> None:
                def capture(result: object) -> None:
                    if isinstance(result, ConfirmResult):
                        results.append(result)

                self.push_screen(
                    ConfirmScreen(competitor_count=10, section_count=5),
                    capture,
                )

        app = _App()
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.pause()
            app.screen.action_submit()
            await pilot.pause()

        assert len(results) == 1
        assert results[0].model_name == "sonnet"
        assert results[0].workers == 5
