"""Tests for the Research Template screen (Screen 5).

System proposes sections based on the space. User toggles on/off
and can add custom sections via a prompt field.
"""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.widgets import Button, Static


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

    async def test_section_editor_buttons_exist(self) -> None:
        app = _TemplateTestApp()
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.pause()
            assert app.screen.query_one("#btn-add-section", Button) is not None
            assert app.screen.query_one("#btn-edit-section", Button) is not None
            assert app.screen.query_one("#btn-next", Button) is not None

    async def test_add_custom_section_updates_state(self) -> None:
        from recon.tui.screens.template import SectionEditorResult, TemplateScreen
        from recon.tui.widgets import ChecklistItem

        app = _TemplateTestApp()
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, TemplateScreen)
            screen._handle_add_section_result(
                SectionEditorResult(
                    title="Operational Footprint",
                    description="Map manufacturing, fulfillment, service coverage, and the operational constraints that shape competitiveness.",
                )
            )
            await pilot.pause()
            await pilot.pause()
            labels = [item._label for item in screen.query(ChecklistItem)]
            assert "Operational Footprint" in labels

    async def test_edit_selected_section_updates_copy(self) -> None:
        from recon.tui.screens.template import SectionEditorResult, TemplateScreen
        from recon.tui.widgets import ChecklistItem

        app = _TemplateTestApp()
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, TemplateScreen)
            screen._cursor = 0
            screen._handle_edit_section_result(
                SectionEditorResult(
                    title="Market Overview",
                    description="Summarize what the competitor sells, where it plays, how it positions itself, and the strategic facts that matter most before deeper analysis.",
                )
            )
            await pilot.pause()
            await pilot.pause()
            first_item = screen.query(ChecklistItem).first()
            assert first_item._label == "Market Overview"
            detail = screen.query_one("#section-detail-description", Static)
            assert "strategic facts" in str(detail.render())

    async def test_select_all_selects_all_sections(self) -> None:
        from recon.tui.screens.template import TemplateScreen
        from recon.tui.widgets import ChecklistItem

        class _App(App):
            CSS = "Screen { background: #000000; }"

            def compose(self) -> ComposeResult:
                yield Static("")

            def on_mount(self) -> None:
                sections = [
                    {"key": "a", "title": "A", "description": "", "selected": False},
                    {"key": "b", "title": "B", "description": "", "selected": False},
                    {"key": "c", "title": "C", "description": "", "selected": True},
                ]
                self.push_screen(TemplateScreen(sections=sections, domain="test"))

        app = _App()
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, TemplateScreen)
            screen._set_all_selected(True)
            await pilot.pause()
            items = screen.query(ChecklistItem)
            assert all(item._selected for item in items)

    async def test_deselect_all_deselects_all_sections(self) -> None:
        from recon.tui.screens.template import TemplateScreen
        from recon.tui.widgets import ChecklistItem

        class _App(App):
            CSS = "Screen { background: #000000; }"

            def compose(self) -> ComposeResult:
                yield Static("")

            def on_mount(self) -> None:
                sections = [
                    {"key": "a", "title": "A", "description": "", "selected": True},
                    {"key": "b", "title": "B", "description": "", "selected": True},
                ]
                self.push_screen(TemplateScreen(sections=sections, domain="test"))

        app = _App()
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, TemplateScreen)
            screen._set_all_selected(False)
            await pilot.pause()
            items = screen.query(ChecklistItem)
            assert all(not item._selected for item in items)

    async def test_template_has_generic_examples(self) -> None:
        app = _TemplateTestApp()
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.pause()
            statics = app.screen.query(Static)
            all_text = " ".join(str(s.render()) for s in statics)
            assert "filament" not in all_text.lower()
            assert "3D" not in all_text
            assert "firmware" not in all_text.lower()

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

    async def test_enter_toggles_current_section(self) -> None:
        from recon.tui.screens.template import TemplateScreen

        app = _TemplateTestApp()
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, TemplateScreen)
            assert screen._sections[0]["selected"] is True
            await pilot.press("enter")
            await pilot.pause()
            assert screen._sections[0]["selected"] is False

    async def test_space_advances_to_next_tab_when_configured(self) -> None:
        from textual.app import App, ComposeResult

        from recon.tui.screens.template import TemplateScreen

        class _App(App):
            CSS = "Screen { background: #000000; }"

            def __init__(self) -> None:
                super().__init__()
                self.next_tab: str | None = None
                self.saved_sections: list[dict] | None = None

            def compose(self) -> ComposeResult:
                yield Static("")

            def on_mount(self) -> None:
                sections = [
                    {"key": "overview", "title": "Overview", "description": "bg", "selected": True},
                ]
                self.push_screen(TemplateScreen(sections=sections, domain="test", next_tab="comps"))

            def action_goto_tab(self, tab_key: str) -> None:
                self.next_tab = tab_key

            def _update_schema_sections(self, sections: list[dict]) -> None:
                self.saved_sections = sections

        app = _App()
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.pause()
            await pilot.press("space")
            await pilot.pause()
            assert app.next_tab == "comps"
            assert app.saved_sections is not None
