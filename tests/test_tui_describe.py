"""Tests for the Describe screen (Screen 2).

Single freeform description field + API key status. Replaces the
4-step wizard with a one-screen experience.
"""

from __future__ import annotations

from pathlib import Path

from textual.app import App, ComposeResult
from textual.widgets import Static


class _DescribeTestApp(App):
    CSS = "Screen { background: #000000; }"

    def compose(self) -> ComposeResult:
        yield Static("")

    def on_mount(self) -> None:
        from recon.tui.screens.describe import DescribeScreen

        self.push_screen(DescribeScreen(output_dir=Path("/tmp/test-ws")))


class TestDescribeScreen:
    async def test_mounts_without_error(self) -> None:
        app = _DescribeTestApp()
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.pause()
            from recon.tui.screens.describe import DescribeScreen

            assert isinstance(app.screen, DescribeScreen)

    async def test_shows_description_input(self) -> None:
        from textual.widgets import TextArea

        app = _DescribeTestApp()
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.pause()
            areas = app.screen.query(TextArea)
            assert len(areas) >= 1

    async def test_shows_api_key_section(self) -> None:
        app = _DescribeTestApp()
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.pause()
            statics = app.screen.query(Static)
            all_text = " ".join(str(s.render()) for s in statics)
            assert "Anthropic" in all_text or "anthropic" in all_text.lower()

    async def test_result_contains_description(self) -> None:
        """When the user fills in the description and presses enter,
        the screen should dismiss with a result containing the text."""
        from recon.tui.screens.describe import DescribeResult, DescribeScreen

        results: list[DescribeResult] = []

        class _App(App):
            CSS = "Screen { background: #000000; }"

            def compose(self) -> ComposeResult:
                yield Static("")

            def on_mount(self) -> None:
                def capture(result: object) -> None:
                    if isinstance(result, DescribeResult):
                        results.append(result)

                self.push_screen(
                    DescribeScreen(output_dir=Path("/tmp/test")),
                    capture,
                )

        app = _App()
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.pause()
            from textual.widgets import TextArea

            area = app.screen.query_one(TextArea)
            area.load_text("Bambu Lab makes 3D printers")
            await pilot.pause()
            # Trigger submit
            app.screen.action_submit()
            await pilot.pause()
            await pilot.pause()

        assert len(results) == 1
        assert "Bambu Lab" in results[0].description
        assert results[0].output_dir == Path("/tmp/test")

    async def test_continue_button_submits(self) -> None:
        """The Continue button should submit the form (no keybind conflict)."""
        from textual.widgets import Button

        from recon.tui.screens.describe import DescribeResult, DescribeScreen

        results: list[DescribeResult] = []

        class _App(App):
            CSS = "Screen { background: #000000; }"

            def compose(self) -> ComposeResult:
                yield Static("")

            def on_mount(self) -> None:
                def capture(result: object) -> None:
                    if isinstance(result, DescribeResult):
                        results.append(result)

                self.push_screen(
                    DescribeScreen(output_dir=Path("/tmp/test-btn")),
                    capture,
                )

        app = _App()
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.pause()
            from textual.widgets import TextArea

            area = app.screen.query_one(TextArea)
            area.load_text("Test company description")
            await pilot.pause()
            # Click the Continue button instead of keybind
            app.screen.query_one("#btn-continue", Button).press()
            await pilot.pause()
            await pilot.pause()

        assert len(results) == 1
        assert "Test company" in results[0].description

    async def test_edit_keys_button_shows_inputs(self) -> None:
        """Edit API Keys button should reveal the key input fields."""
        from textual.widgets import Button, Input

        app = _DescribeTestApp()
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.pause()
            # Key inputs should be hidden initially
            anthropic_input = app.screen.query_one("#input-anthropic-key", Input)
            assert not anthropic_input.display

            # Click Edit API Keys
            app.screen.query_one("#btn-edit-keys", Button).press()
            await pilot.pause()

            # Now key inputs should be visible
            assert anthropic_input.display
