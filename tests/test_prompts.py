"""Tests for the prompt composer.

The prompt composer assembles prompts from composable fragments:
base system prompt + per-section fragment + example output.
Prompts are generated from schema metadata at composition time.
"""

from recon.prompts import compose_research_prompt, compose_system_prompt
from recon.schema import parse_schema


def _make_schema(sections: list[dict] | None = None, rating_scales: dict | None = None) -> dict:
    """Build a schema dict with optional overrides."""
    return {
        "domain": "Developer Tools",
        "identity": {
            "company_name": "Acme Corp",
            "products": ["Acme IDE"],
            "decision_context": ["build-vs-buy"],
        },
        "rating_scales": rating_scales or {
            "capability": {
                "name": "Capability Rating",
                "values": ["1", "2", "3", "4", "5"],
                "never_use": ["emoji"],
            },
        },
        "sections": sections or [
            {
                "key": "overview",
                "title": "Overview",
                "description": "High-level company and product summary.",
                "evidence_types": ["factual", "analytical"],
                "allowed_formats": ["prose"],
                "preferred_format": "prose",
            },
        ],
    }


class TestSystemPrompt:
    def test_includes_domain(self) -> None:
        schema = parse_schema(_make_schema())

        prompt = compose_system_prompt(schema)

        assert "Developer Tools" in prompt

    def test_includes_no_emoji_rule(self) -> None:
        schema = parse_schema(_make_schema())

        prompt = compose_system_prompt(schema)

        assert "emoji" in prompt.lower()

    def test_includes_source_attribution_rule(self) -> None:
        schema = parse_schema(_make_schema())

        prompt = compose_system_prompt(schema)

        assert "source" in prompt.lower()


class TestResearchPrompt:
    def test_includes_section_title(self) -> None:
        schema = parse_schema(_make_schema())

        prompt = compose_research_prompt(
            schema=schema,
            section_key="overview",
            competitor_name="GitHub Copilot",
        )

        assert "Overview" in prompt

    def test_includes_section_description(self) -> None:
        schema = parse_schema(_make_schema())

        prompt = compose_research_prompt(
            schema=schema,
            section_key="overview",
            competitor_name="GitHub Copilot",
        )

        assert "High-level company and product summary" in prompt

    def test_includes_competitor_name(self) -> None:
        schema = parse_schema(_make_schema())

        prompt = compose_research_prompt(
            schema=schema,
            section_key="overview",
            competitor_name="GitHub Copilot",
        )

        assert "GitHub Copilot" in prompt

    def test_includes_format_instructions(self) -> None:
        schema = parse_schema(_make_schema())

        prompt = compose_research_prompt(
            schema=schema,
            section_key="overview",
            competitor_name="Cursor",
        )

        assert "prose" in prompt.lower()

    def test_includes_evidence_types(self) -> None:
        schema = parse_schema(_make_schema())

        prompt = compose_research_prompt(
            schema=schema,
            section_key="overview",
            competitor_name="Cursor",
        )

        assert "factual" in prompt
        assert "analytical" in prompt

    def test_includes_rating_scale_when_referenced(self) -> None:
        sections = [
            {
                "key": "capabilities",
                "title": "Capabilities",
                "description": "Product capability ratings.",
                "allowed_formats": ["rated_table"],
                "preferred_format": "rated_table",
                "format_spec": {
                    "columns": ["Capability", "Rating", "Notes"],
                    "rating_scale_ref": "capability",
                },
            },
        ]
        schema = parse_schema(_make_schema(sections=sections))

        prompt = compose_research_prompt(
            schema=schema,
            section_key="capabilities",
            competitor_name="Cursor",
        )

        assert "Capability Rating" in prompt
        assert "1" in prompt and "5" in prompt

    def test_includes_source_preferences(self) -> None:
        sections = [
            {
                "key": "pricing",
                "title": "Pricing",
                "description": "Pricing model.",
                "allowed_formats": ["key_value"],
                "preferred_format": "key_value",
                "source_preferences": {
                    "primary": ["official pricing page"],
                    "secondary": ["G2"],
                    "avoid": ["Wikipedia"],
                },
            },
        ]
        schema = parse_schema(_make_schema(sections=sections))

        prompt = compose_research_prompt(
            schema=schema,
            section_key="pricing",
            competitor_name="Cursor",
        )

        assert "official pricing page" in prompt
        assert "Wikipedia" in prompt

    def test_includes_search_guidance(self) -> None:
        sections = [
            {
                "key": "overview",
                "title": "Overview",
                "description": "Summary.",
                "allowed_formats": ["prose"],
                "preferred_format": "prose",
                "search_guidance": "Focus on recent announcements and funding rounds.",
            },
        ]
        schema = parse_schema(_make_schema(sections=sections))

        prompt = compose_research_prompt(
            schema=schema,
            section_key="overview",
            competitor_name="Cursor",
        )

        assert "recent announcements" in prompt

    def test_raises_for_unknown_section(self) -> None:
        import pytest

        schema = parse_schema(_make_schema())

        with pytest.raises(KeyError, match="nonexistent"):
            compose_research_prompt(
                schema=schema,
                section_key="nonexistent",
                competitor_name="Cursor",
            )

    def test_includes_format_spec_columns(self) -> None:
        sections = [
            {
                "key": "capabilities",
                "title": "Capabilities",
                "description": "Ratings.",
                "allowed_formats": ["rated_table"],
                "preferred_format": "rated_table",
                "format_spec": {
                    "columns": ["Capability", "Rating", "Notes"],
                },
            },
        ]
        schema = parse_schema(_make_schema(sections=sections))

        prompt = compose_research_prompt(
            schema=schema,
            section_key="capabilities",
            competitor_name="Cursor",
        )

        assert "Capability" in prompt
        assert "Rating" in prompt
        assert "Notes" in prompt

    def test_includes_word_count_range(self) -> None:
        sections = [
            {
                "key": "overview",
                "title": "Overview",
                "description": "Summary.",
                "allowed_formats": ["prose"],
                "preferred_format": "prose",
                "format_spec": {
                    "word_count_range": [100, 200],
                },
            },
        ]
        schema = parse_schema(_make_schema(sections=sections))

        prompt = compose_research_prompt(
            schema=schema,
            section_key="overview",
            competitor_name="Cursor",
        )

        assert "100" in prompt
        assert "200" in prompt
