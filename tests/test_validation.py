"""Tests for the format validator.

The format validator performs deterministic (non-LLM) checks on agent output:
format type, table structure, rating scales, word counts, emoji detection,
required fields, source list.
"""

from recon.validation import (
    ValidationResult,
    validate_emoji_free,
    validate_has_sources,
    validate_table_columns,
    validate_word_count,
)


class TestEmojiDetection:
    def test_clean_text_passes(self) -> None:
        result = validate_emoji_free("This is clean text with no emoji.")

        assert result.passed is True

    def test_detects_common_emoji(self) -> None:
        result = validate_emoji_free("Great product! 🚀 Very fast.")

        assert result.passed is False
        assert "emoji" in result.message.lower()

    def test_detects_star_emoji(self) -> None:
        result = validate_emoji_free("Rating: ⭐⭐⭐")

        assert result.passed is False

    def test_allows_standard_symbols(self) -> None:
        result = validate_emoji_free("Price: $100. Status: OK. Rating: 4/5.")

        assert result.passed is True

    def test_detects_emoji_in_tables(self) -> None:
        table = "| Feature | Status |\n| Auth | ✅ |\n| SSO | ❌ |"

        result = validate_emoji_free(table)

        assert result.passed is False


class TestSourceValidation:
    def test_passes_with_sources_section(self) -> None:
        content = """## Overview
Some content here.

## Sources
- [Official Docs](https://example.com) -- accessed 2026-01-15
"""
        result = validate_has_sources(content)

        assert result.passed is True

    def test_fails_without_sources(self) -> None:
        content = """## Overview
Some content here without any sources.
"""
        result = validate_has_sources(content)

        assert result.passed is False

    def test_passes_with_sources_heading_variations(self) -> None:
        content = "## Overview\nContent.\n\n### Sources\n- [Link](url)"

        result = validate_has_sources(content)

        assert result.passed is True


class TestWordCount:
    def test_within_range(self) -> None:
        text = " ".join(["word"] * 150)

        result = validate_word_count(text, min_words=100, max_words=200)

        assert result.passed is True

    def test_below_minimum(self) -> None:
        text = "Too short."

        result = validate_word_count(text, min_words=100, max_words=200)

        assert result.passed is False
        assert "below" in result.message.lower() or "few" in result.message.lower() or "minimum" in result.message.lower()

    def test_above_maximum(self) -> None:
        text = " ".join(["word"] * 300)

        result = validate_word_count(text, min_words=100, max_words=200)

        assert result.passed is False

    def test_exact_boundary_values(self) -> None:
        text_min = " ".join(["word"] * 100)
        text_max = " ".join(["word"] * 200)

        assert validate_word_count(text_min, min_words=100, max_words=200).passed is True
        assert validate_word_count(text_max, min_words=100, max_words=200).passed is True


class TestTableColumns:
    def test_correct_columns_pass(self) -> None:
        table = "| Name | Rating | Notes |\n|---|---|---|\n| Auth | 4 | Good |"

        result = validate_table_columns(table, expected_columns=["Name", "Rating", "Notes"])

        assert result.passed is True

    def test_missing_column_fails(self) -> None:
        table = "| Name | Rating |\n|---|---|\n| Auth | 4 |"

        result = validate_table_columns(table, expected_columns=["Name", "Rating", "Notes"])

        assert result.passed is False
        assert "Notes" in result.message

    def test_extra_columns_still_pass(self) -> None:
        table = "| Name | Rating | Notes | Extra |\n|---|---|---|---|\n| Auth | 4 | Good | Yes |"

        result = validate_table_columns(table, expected_columns=["Name", "Rating", "Notes"])

        assert result.passed is True

    def test_no_table_fails(self) -> None:
        text = "This is just prose, no table here."

        result = validate_table_columns(text, expected_columns=["Name", "Rating"])

        assert result.passed is False

    def test_case_insensitive_matching(self) -> None:
        table = "| name | rating | notes |\n|---|---|---|\n| Auth | 4 | Good |"

        result = validate_table_columns(table, expected_columns=["Name", "Rating", "Notes"])

        assert result.passed is True


class TestValidationResult:
    def test_passed_result(self) -> None:
        result = ValidationResult(passed=True, message="OK")

        assert result.passed is True
        assert result.message == "OK"

    def test_failed_result(self) -> None:
        result = ValidationResult(passed=False, message="Missing sources")

        assert result.passed is False
