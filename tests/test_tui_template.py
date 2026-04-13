"""Tests for the Research Template screen (Screen 5).

System proposes sections based on the space. User toggles on/off
and can add custom sections via a prompt field.
"""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.widgets import Static


class _TemplateTestApp(App):
    CSS = "Screen { background: #000000; }"

    def compose(self) -> ComposeResult:
        yield Static("")

    def on_mount(self) -> None:
        from recon.tui.screens.template import TemplateScreen

        sections = [
            {"key": "overview", "title": "Overview", "description": "Company background", "selected": True},
            {"key": "pricing", "title": "Pricing", "description": "Pricing model", "selected": True},
            {"key": "community", "title": "Community", "description": "User community", "selected": False},
        ]
        self.push_screen(TemplateScreen(sections=sections, domain="additive manufacturing"))


class TestTemplateScreen:
    async def test_mounts_without_error(self) -> None:
        app = _TemplateTestApp()
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.pause()
            from recon.tui.screens.template import TemplateScreen

            assert isinstance(app.screen, TemplateScreen)

    async def test_shows_section_list(self) -> None:
        from recon.tui.widgets import ChecklistItem

        app = _TemplateTestApp()
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.pause()
            items = app.screen.query(ChecklistItem)
            assert len(items) >= 2
            labels = [item._label for item in items]
            assert "Overview" in labels
            assert "Pricing" in labels

    async def test_result_contains_selected_sections(self) -> None:
        from recon.tui.screens.template import TemplateResult, TemplateScreen

        results: list[TemplateResult] = []

        class _App(App):
            CSS = "Screen { background: #000000; }"

            def compose(self) -> ComposeResult:
                yield Static("")

            def on_mount(self) -> None:
                sections = [
                    {"key": "overview", "title": "Overview", "description": "bg", "selected": True},
                    {"key": "pricing", "title": "Pricing", "description": "model", "selected": True},
                    {"key": "community", "title": "Community", "description": "users", "selected": False},
                ]

                def capture(result: object) -> None:
                    if isinstance(result, TemplateResult):
                        results.append(result)

                self.push_screen(
                    TemplateScreen(sections=sections, domain="CI/CD"),
                    capture,
                )

        app = _App()
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.pause()
            app.screen.action_submit()
            await pilot.pause()

        assert len(results) == 1
        selected_keys = [s["key"] for s in results[0].sections if s["selected"]]
        assert "overview" in selected_keys
        assert "pricing" in selected_keys
        assert "community" not in selected_keys
