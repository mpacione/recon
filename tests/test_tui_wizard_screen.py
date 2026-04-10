"""Tests for WizardScreen -- the wizard as a pushable Screen inside ReconApp."""

from __future__ import annotations

from pathlib import Path  # noqa: TCH003 -- used at runtime

from textual.app import App, ComposeResult
from textual.widgets import Button, Input, Static

from recon.tui.screens.wizard import WizardResult, WizardScreen
from recon.wizard import WizardPhase


class _WizardTestApp(App):
    dismissed: WizardResult | None = None

    def __init__(self, output_dir: Path) -> None:
        super().__init__()
        self._output_dir = output_dir

    def compose(self) -> ComposeResult:
        yield Static("")

    def on_mount(self) -> None:
        def on_dismiss(result: WizardResult | None) -> None:
            self.dismissed = result

        self.push_screen(WizardScreen(output_dir=self._output_dir), on_dismiss)


class TestWizardScreen:
    async def test_mounts_on_identity_phase(self, tmp_path: Path) -> None:
        app = _WizardTestApp(output_dir=tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, WizardScreen)
            assert screen.state.phase == WizardPhase.IDENTITY
            assert app.screen.query_one("#input-company", Input)

    async def test_identity_requires_company_name(self, tmp_path: Path) -> None:
        app = _WizardTestApp(output_dir=tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            app.screen.query_one("#btn-continue", Button).press()
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, WizardScreen)
            assert screen.state.phase == WizardPhase.IDENTITY

    async def test_identity_to_sections_advance(self, tmp_path: Path) -> None:
        app = _WizardTestApp(output_dir=tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            app.screen.query_one("#input-company", Input).value = "Acme Corp"
            app.screen.query_one("#input-products", Input).value = "Acme CI"
            app.screen.query_one("#input-domain", Input).value = "CI/CD Tools"
            app.screen.query_one("#btn-continue", Button).press()
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, WizardScreen)
            assert screen.state.phase == WizardPhase.SECTIONS
            assert screen.state.company_name == "Acme Corp"
            assert screen.state.domain == "CI/CD Tools"

    async def test_back_from_sections_returns_to_identity(self, tmp_path: Path) -> None:
        app = _WizardTestApp(output_dir=tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            app.screen.query_one("#input-company", Input).value = "Acme"
            app.screen.query_one("#input-products", Input).value = "P"
            app.screen.query_one("#input-domain", Input).value = "D"
            app.screen.query_one("#btn-continue", Button).press()
            await pilot.pause()
            app.screen.query_one("#btn-back", Button).press()
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, WizardScreen)
            assert screen.state.phase == WizardPhase.IDENTITY

    async def test_full_flow_dismisses_with_schema(self, tmp_path: Path) -> None:
        app = _WizardTestApp(output_dir=tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            app.screen.query_one("#input-company", Input).value = "Acme Corp"
            app.screen.query_one("#input-products", Input).value = "Acme CI"
            app.screen.query_one("#input-domain", Input).value = "CI/CD Tools"
            app.screen.query_one("#btn-continue", Button).press()
            await pilot.pause()
            app.screen.query_one("#btn-continue", Button).press()
            await pilot.pause()
            app.screen.query_one("#btn-continue", Button).press()
            await pilot.pause()
            app.screen.query_one("#input-api-key", Input).value = "sk-ant-test"
            app.screen.query_one("#btn-confirm", Button).press()
            await pilot.pause()
            await pilot.pause()

            assert app.dismissed is not None
            assert app.dismissed.schema is not None
            assert app.dismissed.api_key == "sk-ant-test"
            assert app.dismissed.schema["identity"]["company_name"] == "Acme Corp"
            assert app.dismissed.output_dir == tmp_path

    async def test_escape_on_identity_cancels(self, tmp_path: Path) -> None:
        app = _WizardTestApp(output_dir=tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, WizardScreen)
            screen.action_go_back()
            await pilot.pause()
            await pilot.pause()
            assert app.dismissed is None or app.dismissed.schema is None
