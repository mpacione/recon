"""Tests for the schema system -- the backbone of recon.

The schema drives everything: prompts, validation, format constraints,
cost estimation, verification tiers. All tests verify behavior through
the public API (parse_schema / ReconSchema).
"""

from pathlib import Path

import pytest
from pydantic import ValidationError

from recon.schema import load_schema_file, parse_schema


class TestParseMinimalSchema:
    def test_parses_domain(self, minimal_schema_dict: dict) -> None:
        schema = parse_schema(minimal_schema_dict)

        assert schema.domain == "Developer Tools"

    def test_parses_identity(self, minimal_schema_dict: dict) -> None:
        schema = parse_schema(minimal_schema_dict)

        assert schema.identity.company_name == "Acme Corp"
        assert schema.identity.products == ["Acme IDE"]
        assert schema.identity.decision_context == ["build-vs-buy"]

    def test_parses_single_section(self, minimal_schema_dict: dict) -> None:
        schema = parse_schema(minimal_schema_dict)

        assert len(schema.sections) == 1
        section = schema.sections[0]
        assert section.key == "overview"
        assert section.title == "Overview"
        assert section.description == "High-level company and product summary."

    def test_section_has_allowed_formats(self, minimal_schema_dict: dict) -> None:
        schema = parse_schema(minimal_schema_dict)

        section = schema.sections[0]
        assert section.allowed_formats == ["prose"]
        assert section.preferred_format == "prose"

    def test_parses_rating_scales(self, minimal_schema_dict: dict) -> None:
        schema = parse_schema(minimal_schema_dict)

        assert "capability" in schema.rating_scales
        scale = schema.rating_scales["capability"]
        assert scale.name == "Capability Rating"
        assert scale.values == ["1", "2", "3", "4", "5"]
        assert scale.never_use == ["emoji", "stars"]


class TestSchemaValidation:
    def test_rejects_missing_domain(self, minimal_schema_dict: dict) -> None:
        del minimal_schema_dict["domain"]

        with pytest.raises(ValidationError, match="domain"):
            parse_schema(minimal_schema_dict)

    def test_rejects_missing_identity(self, minimal_schema_dict: dict) -> None:
        del minimal_schema_dict["identity"]

        with pytest.raises(ValidationError, match="identity"):
            parse_schema(minimal_schema_dict)

    def test_rejects_missing_sections(self, minimal_schema_dict: dict) -> None:
        del minimal_schema_dict["sections"]

        with pytest.raises(ValidationError, match="sections"):
            parse_schema(minimal_schema_dict)

    def test_rejects_section_without_key(self, minimal_schema_dict: dict) -> None:
        del minimal_schema_dict["sections"][0]["key"]

        with pytest.raises(ValidationError, match="key"):
            parse_schema(minimal_schema_dict)

    def test_rejects_section_without_title(self, minimal_schema_dict: dict) -> None:
        del minimal_schema_dict["sections"][0]["title"]

        with pytest.raises(ValidationError, match="title"):
            parse_schema(minimal_schema_dict)

    def test_rejects_section_without_allowed_formats(self, minimal_schema_dict: dict) -> None:
        del minimal_schema_dict["sections"][0]["allowed_formats"]

        with pytest.raises(ValidationError, match="allowed_formats"):
            parse_schema(minimal_schema_dict)

    def test_rejects_section_without_preferred_format(self, minimal_schema_dict: dict) -> None:
        del minimal_schema_dict["sections"][0]["preferred_format"]

        with pytest.raises(ValidationError, match="preferred_format"):
            parse_schema(minimal_schema_dict)

    def test_rejects_identity_without_company_name(self, minimal_schema_dict: dict) -> None:
        del minimal_schema_dict["identity"]["company_name"]

        with pytest.raises(ValidationError, match="company_name"):
            parse_schema(minimal_schema_dict)

    def test_rejects_invalid_format_type(self, minimal_schema_dict: dict) -> None:
        minimal_schema_dict["sections"][0]["allowed_formats"] = ["haiku"]

        with pytest.raises(ValidationError, match="haiku"):
            parse_schema(minimal_schema_dict)

    def test_rejects_preferred_format_not_in_allowed(self, minimal_schema_dict: dict) -> None:
        minimal_schema_dict["sections"][0]["allowed_formats"] = ["table", "prose"]
        minimal_schema_dict["sections"][0]["preferred_format"] = "bullet_list"

        with pytest.raises(ValidationError, match="preferred_format"):
            parse_schema(minimal_schema_dict)


class TestFormatSpec:
    def test_parses_format_spec_with_columns(self, minimal_schema_dict: dict) -> None:
        minimal_schema_dict["sections"][0]["allowed_formats"] = ["table"]
        minimal_schema_dict["sections"][0]["preferred_format"] = "table"
        minimal_schema_dict["sections"][0]["format_spec"] = {
            "columns": ["Name", "Rating", "Notes"],
            "rating_scale_ref": "capability",
        }

        schema = parse_schema(minimal_schema_dict)

        spec = schema.sections[0].format_spec
        assert spec is not None
        assert spec.columns == ["Name", "Rating", "Notes"]
        assert spec.rating_scale_ref == "capability"

    def test_parses_format_spec_with_word_count(self, minimal_schema_dict: dict) -> None:
        minimal_schema_dict["sections"][0]["format_spec"] = {
            "word_count_range": [100, 200],
        }

        schema = parse_schema(minimal_schema_dict)

        spec = schema.sections[0].format_spec
        assert spec is not None
        assert spec.word_count_range == [100, 200]

    def test_format_spec_defaults_to_none(self, minimal_schema_dict: dict) -> None:
        schema = parse_schema(minimal_schema_dict)

        assert schema.sections[0].format_spec is None


class TestSourcePreferences:
    def test_parses_source_preferences(self, minimal_schema_dict: dict) -> None:
        minimal_schema_dict["sections"][0]["source_preferences"] = {
            "primary": ["official docs", "pricing pages"],
            "secondary": ["G2", "Capterra"],
            "avoid": ["Wikipedia"],
            "source_recency_days": 180,
        }

        schema = parse_schema(minimal_schema_dict)

        prefs = schema.sections[0].source_preferences
        assert prefs is not None
        assert prefs.primary == ["official docs", "pricing pages"]
        assert prefs.secondary == ["G2", "Capterra"]
        assert prefs.avoid == ["Wikipedia"]
        assert prefs.source_recency_days == 180

    def test_source_preferences_defaults_to_none(self, minimal_schema_dict: dict) -> None:
        schema = parse_schema(minimal_schema_dict)

        assert schema.sections[0].source_preferences is None

    def test_source_preferences_with_only_primary(self, minimal_schema_dict: dict) -> None:
        minimal_schema_dict["sections"][0]["source_preferences"] = {
            "primary": ["official docs"],
        }

        schema = parse_schema(minimal_schema_dict)

        prefs = schema.sections[0].source_preferences
        assert prefs is not None
        assert prefs.primary == ["official docs"]
        assert prefs.secondary == []
        assert prefs.avoid == []
        assert prefs.source_recency_days is None


class TestVerificationTier:
    def test_defaults_to_standard(self, minimal_schema_dict: dict) -> None:
        schema = parse_schema(minimal_schema_dict)

        assert schema.sections[0].verification_tier.value == "standard"

    def test_parses_verified_tier(self, minimal_schema_dict: dict) -> None:
        minimal_schema_dict["sections"][0]["verification_tier"] = "verified"

        schema = parse_schema(minimal_schema_dict)

        assert schema.sections[0].verification_tier.value == "verified"

    def test_parses_deep_tier(self, minimal_schema_dict: dict) -> None:
        minimal_schema_dict["sections"][0]["verification_tier"] = "deep"

        schema = parse_schema(minimal_schema_dict)

        assert schema.sections[0].verification_tier.value == "deep"

    def test_rejects_invalid_tier(self, minimal_schema_dict: dict) -> None:
        minimal_schema_dict["sections"][0]["verification_tier"] = "ultra"

        with pytest.raises(ValidationError, match="verification_tier"):
            parse_schema(minimal_schema_dict)


class TestMultipleSections:
    def test_preserves_section_order(self, minimal_schema_dict: dict) -> None:
        minimal_schema_dict["sections"].append({
            "key": "capabilities",
            "title": "Capabilities",
            "description": "Product capability assessment.",
            "allowed_formats": ["rated_table", "table"],
            "preferred_format": "rated_table",
            "verification_tier": "verified",
        })

        schema = parse_schema(minimal_schema_dict)

        assert len(schema.sections) == 2
        assert schema.sections[0].key == "overview"
        assert schema.sections[1].key == "capabilities"

    def test_each_section_independent(self, minimal_schema_dict: dict) -> None:
        minimal_schema_dict["sections"].append({
            "key": "pricing",
            "title": "Pricing",
            "description": "Pricing model and tiers.",
            "allowed_formats": ["key_value", "table"],
            "preferred_format": "key_value",
            "source_preferences": {
                "primary": ["official pricing page"],
            },
        })

        schema = parse_schema(minimal_schema_dict)

        assert schema.sections[0].source_preferences is None
        assert schema.sections[1].source_preferences is not None
        assert schema.sections[1].source_preferences.primary == ["official pricing page"]


class TestOwnProduct:
    def test_own_product_defaults_to_false(self, minimal_schema_dict: dict) -> None:
        schema = parse_schema(minimal_schema_dict)

        assert schema.identity.own_product is False

    def test_own_product_can_be_set_true(self, minimal_schema_dict: dict) -> None:
        minimal_schema_dict["identity"]["own_product"] = True

        schema = parse_schema(minimal_schema_dict)

        assert schema.identity.own_product is True


class TestSchemaFileLoading:
    def test_loads_schema_from_yaml_file(self, tmp_workspace: Path) -> None:
        schema = load_schema_file(tmp_workspace / "recon.yaml")

        assert schema.domain == "Developer Tools"
        assert len(schema.sections) == 1

    def test_raises_on_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_schema_file(tmp_path / "nonexistent.yaml")


class TestCrossReferenceValidation:
    def test_rejects_unknown_rating_scale_ref(self, minimal_schema_dict: dict) -> None:
        minimal_schema_dict["sections"][0]["format_spec"] = {
            "rating_scale_ref": "nonexistent_scale",
        }

        with pytest.raises(ValidationError, match="nonexistent_scale"):
            parse_schema(minimal_schema_dict)

    def test_accepts_valid_rating_scale_ref(self, minimal_schema_dict: dict) -> None:
        minimal_schema_dict["sections"][0]["allowed_formats"] = ["rated_table"]
        minimal_schema_dict["sections"][0]["preferred_format"] = "rated_table"
        minimal_schema_dict["sections"][0]["format_spec"] = {
            "columns": ["Capability", "Rating"],
            "rating_scale_ref": "capability",
        }

        schema = parse_schema(minimal_schema_dict)

        assert schema.sections[0].format_spec.rating_scale_ref == "capability"

    def test_rejects_duplicate_section_keys(self, minimal_schema_dict: dict) -> None:
        minimal_schema_dict["sections"].append({
            "key": "overview",
            "title": "Overview Again",
            "description": "Duplicate key.",
            "allowed_formats": ["prose"],
            "preferred_format": "prose",
        })

        with pytest.raises(ValidationError, match="Duplicate section key"):
            parse_schema(minimal_schema_dict)

    def test_section_lookup_by_key(self, minimal_schema_dict: dict) -> None:
        schema = parse_schema(minimal_schema_dict)

        section = schema.get_section("overview")
        assert section is not None
        assert section.title == "Overview"

    def test_section_lookup_returns_none_for_unknown(self, minimal_schema_dict: dict) -> None:
        schema = parse_schema(minimal_schema_dict)

        assert schema.get_section("nonexistent") is None
