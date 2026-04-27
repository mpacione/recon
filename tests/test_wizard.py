"""Tests for the schema wizard data model.

The wizard guides workspace creation through 4 phases:
Identity -> Sections -> Sources -> Review. It produces a complete
schema dict suitable for writing to recon.yaml.
"""

from recon.wizard import (
    DecisionContext,
    DefaultSections,
    WizardPhase,
    WizardState,
)


class TestWizardPhaseProgression:
    def test_starts_in_identity_phase(self) -> None:
        state = WizardState()

        assert state.phase == WizardPhase.IDENTITY

    def test_advances_to_sections_after_identity(self) -> None:
        state = WizardState()
        state.set_identity(
            company_name="Acme Corp",
            products=["Acme CI"],
            domain="Developer Tools",
            decision_contexts=[DecisionContext.BUILD_VS_BUY],
        )

        state.advance()

        assert state.phase == WizardPhase.SECTIONS

    def test_advances_to_sources_after_sections(self) -> None:
        state = _state_at_sections_phase()
        state.advance()

        assert state.phase == WizardPhase.SOURCES

    def test_advances_to_review_after_sources(self) -> None:
        state = _state_at_sources_phase()
        state.advance()

        assert state.phase == WizardPhase.REVIEW

    def test_cannot_advance_past_review(self) -> None:
        state = _state_at_review_phase()

        state.advance()

        assert state.phase == WizardPhase.REVIEW

    def test_can_go_back_to_previous_phase(self) -> None:
        state = _state_at_sections_phase()

        state.go_back()

        assert state.phase == WizardPhase.IDENTITY

    def test_cannot_go_back_from_identity(self) -> None:
        state = WizardState()

        state.go_back()

        assert state.phase == WizardPhase.IDENTITY

    def test_identity_must_be_set_before_advancing(self) -> None:
        import pytest

        state = WizardState()

        with pytest.raises(ValueError, match="company_name"):
            state.advance()


class TestIdentityPhase:
    def test_stores_identity_fields(self) -> None:
        state = WizardState()

        state.set_identity(
            company_name="Acme Corp",
            products=["Acme CI", "Acme Deploy"],
            domain="CI/CD Tools",
            decision_contexts=[DecisionContext.BUILD_VS_BUY, DecisionContext.POSITIONING],
            own_product=True,
        )

        assert state.company_name == "Acme Corp"
        assert state.products == ["Acme CI", "Acme Deploy"]
        assert state.domain == "CI/CD Tools"
        assert state.decision_contexts == [DecisionContext.BUILD_VS_BUY, DecisionContext.POSITIONING]
        assert state.own_product is True

    def test_own_product_defaults_to_false(self) -> None:
        state = WizardState()
        state.set_identity(
            company_name="Acme",
            products=["X"],
            domain="Tools",
            decision_contexts=[DecisionContext.GENERAL],
        )

        assert state.own_product is False


class TestSectionRecommendations:
    def test_build_vs_buy_recommends_correct_sections(self) -> None:
        state = WizardState()
        state.set_identity(
            company_name="Acme",
            products=["X"],
            domain="Tools",
            decision_contexts=[DecisionContext.BUILD_VS_BUY],
        )

        recommended = state.recommended_section_keys()

        assert "capabilities" in recommended
        assert "pricing" in recommended
        assert "integration" in recommended
        assert "head_to_head" in recommended

    def test_investment_recommends_correct_sections(self) -> None:
        state = WizardState()
        state.set_identity(
            company_name="Acme",
            products=["X"],
            domain="Tools",
            decision_contexts=[DecisionContext.INVESTMENT],
        )

        recommended = state.recommended_section_keys()

        assert "overview" in recommended
        assert "capabilities" in recommended
        assert "pricing" in recommended
        assert "financial_health" in recommended
        assert "strategic_notes" in recommended

    def test_general_awareness_recommends_all_sections(self) -> None:
        state = WizardState()
        state.set_identity(
            company_name="Acme",
            products=["X"],
            domain="Tools",
            decision_contexts=[DecisionContext.GENERAL],
        )

        recommended = state.recommended_section_keys()

        assert len(recommended) == len(DefaultSections.ALL)

    def test_multiple_contexts_union_recommendations(self) -> None:
        state = WizardState()
        state.set_identity(
            company_name="Acme",
            products=["X"],
            domain="Tools",
            decision_contexts=[DecisionContext.BUILD_VS_BUY, DecisionContext.INVESTMENT],
        )

        recommended = state.recommended_section_keys()

        assert "integration" in recommended
        assert "strategic_notes" in recommended

    def test_section_selection_toggle(self) -> None:
        state = _state_at_sections_phase()

        state.toggle_section("capabilities")

        assert "capabilities" not in state.selected_section_keys

    def test_section_toggle_back_on(self) -> None:
        state = _state_at_sections_phase()
        state.toggle_section("capabilities")

        state.toggle_section("capabilities")

        assert "capabilities" in state.selected_section_keys

    def test_selected_sections_initialize_from_recommendations(self) -> None:
        state = WizardState()
        state.set_identity(
            company_name="Acme",
            products=["X"],
            domain="Tools",
            decision_contexts=[DecisionContext.BUILD_VS_BUY],
        )

        assert state.selected_section_keys == set(state.recommended_section_keys())


class TestDefaultSections:
    def test_all_default_sections_have_required_fields(self) -> None:
        for section in DefaultSections.ALL:
            assert "key" in section
            assert "title" in section
            assert "description" in section
            assert "allowed_formats" in section
            assert "preferred_format" in section

    def test_default_sections_cover_expected_keys(self) -> None:
        keys = {s["key"] for s in DefaultSections.ALL}

        assert keys == {
            "overview",
            "capabilities",
            "pricing",
            "customer_segments",
            "distribution_gtm",
            "integration",
            "enterprise",
            "brand_market",
            "financial_health",
            "leadership_strategy",
            "head_to_head",
            "strategic_notes",
        }


class TestSourcePreferences:
    def test_default_sources_for_pricing(self) -> None:
        state = _state_at_sources_phase()

        sources = state.get_source_preferences("pricing")

        assert len(sources["primary"]) > 0
        assert "official pricing pages" in sources["primary"]

    def test_default_sources_for_brand_market(self) -> None:
        state = _state_at_sources_phase()

        sources = state.get_source_preferences("brand_market")

        assert "Hacker News" in sources["primary"]
        assert "Reddit" in sources["primary"]

    def test_set_custom_source_preferences(self) -> None:
        state = _state_at_sources_phase()

        state.set_source_preferences("pricing", primary=["custom source"])

        sources = state.get_source_preferences("pricing")
        assert sources["primary"] == ["custom source"]


class TestSchemaGeneration:
    def test_generates_valid_schema_dict(self) -> None:
        state = _state_at_review_phase()

        schema = state.to_schema_dict()

        assert schema["domain"] == "CI/CD Tools"
        assert schema["identity"]["company_name"] == "Acme Corp"
        assert schema["identity"]["products"] == ["Acme CI"]
        assert len(schema["sections"]) > 0

    def test_generated_schema_parses_with_pydantic(self) -> None:
        from recon.schema import parse_schema

        state = _state_at_review_phase()

        schema = state.to_schema_dict()
        parsed = parse_schema(schema)

        assert parsed.domain == "CI/CD Tools"
        assert parsed.identity.company_name == "Acme Corp"

    def test_only_selected_sections_in_schema(self) -> None:
        state = _state_at_review_phase()
        state.toggle_section("capabilities")

        schema = state.to_schema_dict()

        section_keys = [s["key"] for s in schema["sections"]]
        assert "capabilities" not in section_keys

    def test_source_preferences_included_in_sections(self) -> None:
        state = _state_at_review_phase()

        schema = state.to_schema_dict()

        pricing = next((s for s in schema["sections"] if s["key"] == "pricing"), None)
        assert pricing is not None
        assert "source_preferences" in pricing

    def test_own_product_flag_in_identity(self) -> None:
        state = WizardState()
        state.set_identity(
            company_name="Acme Corp",
            products=["Acme CI"],
            domain="CI/CD Tools",
            decision_contexts=[DecisionContext.BUILD_VS_BUY],
            own_product=True,
        )

        schema = state.to_schema_dict()

        assert schema["identity"]["own_product"] is True

    def test_decision_context_stored_in_identity(self) -> None:
        state = _state_at_review_phase()

        schema = state.to_schema_dict()

        assert "build-vs-buy" in schema["identity"]["decision_context"]

    def test_includes_rating_scales(self) -> None:
        state = _state_at_review_phase()

        schema = state.to_schema_dict()

        assert "rating_scales" in schema
        assert "capability" in schema["rating_scales"]
        assert "status" in schema["rating_scales"]


def _state_at_sections_phase() -> WizardState:
    state = WizardState()
    state.set_identity(
        company_name="Acme Corp",
        products=["Acme CI"],
        domain="CI/CD Tools",
        decision_contexts=[DecisionContext.BUILD_VS_BUY],
    )
    state.advance()
    return state


def _state_at_sources_phase() -> WizardState:
    state = _state_at_sections_phase()
    state.advance()
    return state


def _state_at_review_phase() -> WizardState:
    state = _state_at_sources_phase()
    state.advance()
    return state
