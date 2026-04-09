"""Cost tracker for recon.

Estimates costs from schema complexity, tracks actual API call costs,
provides running totals, and supports verification tier multipliers.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ModelPricing:
    model_id: str
    input_price_per_million: float
    output_price_per_million: float

    def calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost in USD for a given token count."""
        input_cost = (input_tokens / 1_000_000) * self.input_price_per_million
        output_cost = (output_tokens / 1_000_000) * self.output_price_per_million
        return input_cost + output_cost


_TOKEN_ESTIMATES: dict[str, tuple[int, int]] = {
    "prose": (2000, 800),
    "bullet_list": (1500, 500),
    "numbered_list": (1500, 500),
    "table": (2000, 600),
    "rated_table": (2500, 700),
    "status_table": (2000, 500),
    "comparison_table": (2500, 800),
    "key_value": (1500, 400),
}

_VERIFICATION_MULTIPLIERS: dict[str, float] = {
    "standard": 1.0,
    "verified": 2.0,
    "deep": 3.0,
}


@dataclass(frozen=True)
class TokenEstimate:
    input_tokens: int
    output_tokens: int


def estimate_section_tokens(
    format_type: str,
    word_count_range: list[int] | None = None,
) -> TokenEstimate:
    """Estimate token counts for a section based on format type."""
    base_input, base_output = _TOKEN_ESTIMATES.get(format_type, (2000, 600))

    if word_count_range and len(word_count_range) == 2:
        avg_words = (word_count_range[0] + word_count_range[1]) / 2
        output_tokens = max(base_output, int(avg_words * 1.5))
    else:
        output_tokens = base_output

    return TokenEstimate(input_tokens=base_input, output_tokens=output_tokens)


@dataclass
class CostTracker:
    """Tracks API call costs and provides estimates."""

    model_pricing: ModelPricing
    total_input_tokens: int = field(default=0, init=False)
    total_output_tokens: int = field(default=0, init=False)
    total_cost: float = field(default=0.0, init=False)
    call_count: int = field(default=0, init=False)

    def record_call(self, input_tokens: int, output_tokens: int) -> float:
        """Record an API call and return its cost."""
        cost = self.model_pricing.calculate_cost(input_tokens, output_tokens)
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.total_cost += cost
        self.call_count += 1
        return cost

    def estimate_section_cost(
        self,
        format_type: str,
        competitor_count: int,
        verification_tier: str = "standard",
        word_count_range: list[int] | None = None,
    ) -> float:
        """Estimate the cost of researching one section across all competitors."""
        tokens = estimate_section_tokens(format_type, word_count_range)
        per_competitor = self.model_pricing.calculate_cost(tokens.input_tokens, tokens.output_tokens)
        multiplier = _VERIFICATION_MULTIPLIERS.get(verification_tier, 1.0)
        return per_competitor * competitor_count * multiplier
