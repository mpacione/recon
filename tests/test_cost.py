"""Tests for the cost tracker.

Estimates costs from schema complexity, tracks actual API call costs,
provides running totals, and supports verification tier multipliers.
"""

import pytest

from recon.cost import (
    CostTracker,
    ModelPricing,
    estimate_full_run,
    estimate_section_tokens,
    get_model_pricing,
    list_available_models,
)


class TestModelPricing:
    def test_calculates_cost_for_tokens(self) -> None:
        pricing = ModelPricing(
            model_id="claude-sonnet-4-20250514",
            input_price_per_million=3.0,
            output_price_per_million=15.0,
        )

        cost = pricing.calculate_cost(input_tokens=1000, output_tokens=500)

        assert cost == pytest.approx(0.0105)

    def test_zero_tokens_zero_cost(self) -> None:
        pricing = ModelPricing(
            model_id="claude-sonnet-4-20250514",
            input_price_per_million=3.0,
            output_price_per_million=15.0,
        )

        assert pricing.calculate_cost(input_tokens=0, output_tokens=0) == 0.0

    def test_get_model_pricing_accepts_short_name(self) -> None:
        pricing = get_model_pricing("sonnet")

        assert pricing.model_id == "claude-sonnet-4-20250514"

    def test_get_model_pricing_accepts_alias(self) -> None:
        pricing = get_model_pricing("claude-haiku-4-5")

        assert pricing.model_id == "claude-haiku-4-20250514"

    def test_list_available_models_includes_three_tiers(self) -> None:
        models = list_available_models()
        names = [str(model["name"]) for model in models]

        assert names == ["sonnet", "opus", "haiku"]

    def test_estimate_full_run_is_positive(self) -> None:
        pricing = get_model_pricing("sonnet")

        estimate = estimate_full_run(
            pricing=pricing,
            section_count=5,
            competitor_count=12,
        )

        assert estimate > 0


class TestSectionTokenEstimation:
    def test_prose_section_estimate(self) -> None:
        estimate = estimate_section_tokens(format_type="prose")

        assert estimate.input_tokens > 0
        assert estimate.output_tokens > 0

    def test_table_section_estimate(self) -> None:
        estimate = estimate_section_tokens(format_type="rated_table")

        assert estimate.input_tokens > 0
        assert estimate.output_tokens > 0

    def test_prose_has_more_output_tokens_than_key_value(self) -> None:
        prose = estimate_section_tokens(format_type="prose")
        kv = estimate_section_tokens(format_type="key_value")

        assert prose.output_tokens > kv.output_tokens

    def test_word_count_range_increases_output_estimate(self) -> None:
        short = estimate_section_tokens(format_type="prose", word_count_range=[50, 100])
        long = estimate_section_tokens(format_type="prose", word_count_range=[800, 1200])

        assert long.output_tokens > short.output_tokens


class TestCostTracker:
    def test_records_api_call(self) -> None:
        tracker = CostTracker(
            model_pricing=ModelPricing(
                model_id="claude-sonnet-4-20250514",
                input_price_per_million=3.0,
                output_price_per_million=15.0,
            ),
        )

        tracker.record_call(input_tokens=1000, output_tokens=500)

        assert tracker.total_cost == pytest.approx(0.0105)
        assert tracker.total_input_tokens == 1000
        assert tracker.total_output_tokens == 500

    def test_accumulates_multiple_calls(self) -> None:
        tracker = CostTracker(
            model_pricing=ModelPricing(
                model_id="claude-sonnet-4-20250514",
                input_price_per_million=3.0,
                output_price_per_million=15.0,
            ),
        )

        tracker.record_call(input_tokens=1000, output_tokens=500)
        tracker.record_call(input_tokens=2000, output_tokens=1000)

        assert tracker.total_input_tokens == 3000
        assert tracker.total_output_tokens == 1500
        assert tracker.call_count == 2

    def test_estimates_cost_for_sections(self) -> None:
        tracker = CostTracker(
            model_pricing=ModelPricing(
                model_id="claude-sonnet-4-20250514",
                input_price_per_million=3.0,
                output_price_per_million=15.0,
            ),
        )

        estimate = tracker.estimate_section_cost(
            format_type="prose",
            competitor_count=10,
        )

        assert estimate > 0

    def test_verification_multiplier_increases_cost(self) -> None:
        tracker = CostTracker(
            model_pricing=ModelPricing(
                model_id="claude-sonnet-4-20250514",
                input_price_per_million=3.0,
                output_price_per_million=15.0,
            ),
        )

        standard = tracker.estimate_section_cost(
            format_type="prose",
            competitor_count=10,
            verification_tier="standard",
        )
        verified = tracker.estimate_section_cost(
            format_type="prose",
            competitor_count=10,
            verification_tier="verified",
        )
        deep = tracker.estimate_section_cost(
            format_type="prose",
            competitor_count=10,
            verification_tier="deep",
        )

        assert verified > standard
        assert deep > verified

    def test_starts_at_zero(self) -> None:
        tracker = CostTracker(
            model_pricing=ModelPricing(
                model_id="claude-sonnet-4-20250514",
                input_price_per_million=3.0,
                output_price_per_million=15.0,
            ),
        )

        assert tracker.total_cost == 0.0
        assert tracker.total_input_tokens == 0
        assert tracker.total_output_tokens == 0
        assert tracker.call_count == 0


class TestModelRegistry:
    def test_get_pricing_sonnet(self) -> None:
        from recon.cost import get_model_pricing

        pricing = get_model_pricing("sonnet")

        assert pricing.input_price_per_million == 3.0
        assert pricing.output_price_per_million == 15.0
        assert "sonnet" in pricing.model_id

    def test_get_pricing_opus(self) -> None:
        from recon.cost import get_model_pricing

        pricing = get_model_pricing("opus")

        assert pricing.input_price_per_million == 15.0
        assert pricing.output_price_per_million == 75.0

    def test_get_pricing_haiku(self) -> None:
        from recon.cost import get_model_pricing

        pricing = get_model_pricing("haiku")

        assert pricing.input_price_per_million == 0.80
        assert pricing.output_price_per_million == 4.0

    def test_list_available_models(self) -> None:
        from recon.cost import list_available_models

        models = list_available_models()

        assert len(models) >= 3
        names = [m["name"] for m in models]
        assert "sonnet" in names
        assert "opus" in names
        assert "haiku" in names

    def test_each_model_has_description(self) -> None:
        from recon.cost import list_available_models

        for model in list_available_models():
            assert "description" in model
            assert len(model["description"]) > 0

    def test_estimate_full_run_cost_varies_by_model(self) -> None:
        from recon.cost import estimate_full_run, get_model_pricing

        sonnet = estimate_full_run(
            pricing=get_model_pricing("sonnet"),
            section_count=5,
            competitor_count=10,
        )
        opus = estimate_full_run(
            pricing=get_model_pricing("opus"),
            section_count=5,
            competitor_count=10,
        )
        haiku = estimate_full_run(
            pricing=get_model_pricing("haiku"),
            section_count=5,
            competitor_count=10,
        )

        assert opus > sonnet > haiku > 0
