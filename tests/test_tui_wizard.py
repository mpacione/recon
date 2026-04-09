"""Tests for the TUI wizard screen.

The wizard is a standalone Textual App that guides workspace creation
through 4 phases: Identity -> Sections -> Sources -> Review.
It produces a schema dict that the CLI writes to recon.yaml.
"""

from __future__ import annotations

from pathlib import Path  # noqa: TCH003 -- used at runtime

from textual.widgets import Button, Input, SelectionList, Static

from recon.tui.wizard import WizardApp
from recon.wizard import WizardPhase


class TestWizardAppLifecycle:
    async def test_wizard_app_mounts(self, tmp_path: Path) -> None:
        app = WizardApp(output_dir=tmp_path)
        async with app.run_test(size=(120, 40)):
            assert app.state is not None

    async def test_wizard_starts_in_identity_phase(self, tmp_path: Path) -> None:
        app = WizardApp(output_dir=tmp_path)
        async with app.run_test(size=(120, 40)):
            assert app.state.phase == WizardPhase.IDENTITY

    async def test_wizard_shows_phase_indicator(self, tmp_path: Path) -> None:
        app = WizardApp(output_dir=tmp_path)
        async with app.run_test(size=(120, 40)):
            indicator = app.query_one("#phase-indicator", Static)
            text = str(indicator.render())
            assert "1" in text
            assert "Identity" in text

    async def test_cancel_produces_no_schema(self, tmp_path: Path) -> None:
        app = WizardApp(output_dir=tmp_path)
        async with app.run_test(size=(120, 40)):
            assert app.result_schema is None


class TestIdentityPhaseInput:
    async def test_identity_shows_input_fields(self, tmp_path: Path) -> None:
        app = WizardApp(output_dir=tmp_path)
        async with app.run_test(size=(120, 40)):
            assert app.query_one("#input-company", Input) is not None
            assert app.query_one("#input-products", Input) is not None
            assert app.query_one("#input-domain", Input) is not None

    async def test_advance_without_company_stays_on_identity(self, tmp_path: Path) -> None:
        app = WizardApp(output_dir=tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            app.query_one("#btn-continue", Button).press()
            await pilot.pause()
            assert app.state.phase == WizardPhase.IDENTITY

    async def test_can_fill_and_advance(self, tmp_path: Path) -> None:
        app = WizardApp(output_dir=tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            await _fill_identity_and_advance(app, pilot)
            assert app.state.phase == WizardPhase.SECTIONS


class TestPhaseNavigation:
    async def test_advance_from_identity_to_sections(self, tmp_path: Path) -> None:
        app = WizardApp(output_dir=tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            await _fill_identity_and_advance(app, pilot)
            assert app.state.phase == WizardPhase.SECTIONS

    async def test_advance_to_sources(self, tmp_path: Path) -> None:
        app = WizardApp(output_dir=tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            await _fill_identity_and_advance(app, pilot)
            app.query_one("#btn-continue", Button).press()
            await pilot.pause()
            assert app.state.phase == WizardPhase.SOURCES

    async def test_advance_to_review(self, tmp_path: Path) -> None:
        app = WizardApp(output_dir=tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            await _advance_to_review(app, pilot)
            assert app.state.phase == WizardPhase.REVIEW

    async def test_go_back_from_sections(self, tmp_path: Path) -> None:
        app = WizardApp(output_dir=tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            await _fill_identity_and_advance(app, pilot)
            app.query_one("#btn-back", Button).press()
            await pilot.pause()
            assert app.state.phase == WizardPhase.IDENTITY

    async def test_phase_indicator_updates(self, tmp_path: Path) -> None:
        app = WizardApp(output_dir=tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            await _fill_identity_and_advance(app, pilot)
            indicator = app.query_one("#phase-indicator", Static)
            text = str(indicator.render())
            assert "2" in text


class TestSectionsPhase:
    async def test_sections_shows_selection_list(self, tmp_path: Path) -> None:
        app = WizardApp(output_dir=tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            await _fill_identity_and_advance(app, pilot)
            section_list = app.query_one("#section-selection", SelectionList)
            assert section_list is not None

    async def test_sections_pre_selected_from_recommendations(self, tmp_path: Path) -> None:
        app = WizardApp(output_dir=tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            await _fill_identity_and_advance(app, pilot)
            section_list = app.query_one("#section-selection", SelectionList)
            selected = section_list.selected
            assert len(selected) > 0


class TestFullWizardFlow:
    async def test_complete_flow_produces_valid_schema(self, tmp_path: Path) -> None:
        app = WizardApp(output_dir=tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            await _advance_to_review(app, pilot)
            app.query_one("#input-api-key", Input).value = "sk-ant-test-key"
            app.query_one("#btn-confirm", Button).press()
            await pilot.pause()

        assert app.result_schema is not None
        assert app.result_schema["domain"] == "CI/CD Tools"
        assert app.result_schema["identity"]["company_name"] == "Acme Corp"
        assert len(app.result_schema["sections"]) > 0

    async def test_schema_parses_with_pydantic(self, tmp_path: Path) -> None:
        from recon.schema import parse_schema

        app = WizardApp(output_dir=tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            await _advance_to_review(app, pilot)
            app.query_one("#input-api-key", Input).value = "sk-ant-test-key"
            app.query_one("#btn-confirm", Button).press()
            await pilot.pause()

        parsed = parse_schema(app.result_schema)
        assert parsed.domain == "CI/CD Tools"
        assert parsed.identity.company_name == "Acme Corp"

    async def test_api_key_stored_in_result(self, tmp_path: Path) -> None:
        app = WizardApp(output_dir=tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            await _advance_to_review(app, pilot)
            app.query_one("#input-api-key", Input).value = "sk-ant-my-secret"
            app.query_one("#btn-confirm", Button).press()
            await pilot.pause()

        assert app.api_key == "sk-ant-my-secret"

    async def test_review_shows_api_key_input(self, tmp_path: Path) -> None:
        app = WizardApp(output_dir=tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            await _advance_to_review(app, pilot)
            api_input = app.query_one("#input-api-key", Input)
            assert api_input is not None
            assert api_input.password is True


async def _fill_identity_and_advance(app: WizardApp, pilot) -> None:
    """Fill identity fields and advance to sections phase."""
    app.query_one("#input-company", Input).value = "Acme Corp"
    app.query_one("#input-products", Input).value = "Acme CI"
    app.query_one("#input-domain", Input).value = "CI/CD Tools"

    ctx_list = app.query_one("#ctx-selection", SelectionList)
    ctx_list.select(5)

    app.query_one("#btn-continue", Button).press()
    await pilot.pause()


async def _advance_to_review(app: WizardApp, pilot) -> None:
    """Fill identity and advance through all phases to review."""
    await _fill_identity_and_advance(app, pilot)
    app.query_one("#btn-continue", Button).press()
    await pilot.pause()
    app.query_one("#btn-continue", Button).press()
    await pilot.pause()
