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

_MODEL_CATALOG: tuple[dict[str, object], ...] = (
    {
        "name": "sonnet",
        "label": "Sonnet 4",
        "model_id": "claude-sonnet-4-20250514",
        "aliases": ("claude-sonnet-4-5",),
        "description": "recommended",
        "input_price_per_million": 3.0,
        "output_price_per_million": 15.0,
        "recommended": True,
    },
    {
        "name": "opus",
        "label": "Opus 4",
        "model_id": "claude-opus-4-20250805",
        "aliases": ("claude-opus-4-5", "claude-opus-4-20250514"),
        "description": "deeper analysis",
        "input_price_per_million": 15.0,
        "output_price_per_million": 75.0,
        "recommended": False,
    },
    {
        "name": "haiku",
        "label": "Haiku 4",
        "model_id": "claude-haiku-4-20250514",
        "aliases": ("claude-haiku-4-5",),
        "description": "faster, less depth",
        "input_price_per_million": 0.8,
        "output_price_per_million": 4.0,
        "recommended": False,
    },
)


@dataclass(frozen=True)
class TokenEstimate:
    input_tokens: int
    output_tokens: int


def list_available_models() -> list[dict[str, object]]:
    """Return the canonical model options for confirm/run flows."""
    return [
        {
            "name": entry["name"],
            "label": entry["label"],
            "id": entry["model_id"],
            "description": entry["description"],
            "input_price_per_million": entry["input_price_per_million"],
            "output_price_per_million": entry["output_price_per_million"],
            "recommended": entry["recommended"],
        }
        for entry in _MODEL_CATALOG
    ]


def get_model_pricing(model_name: str) -> ModelPricing:
    """Resolve a short model name or model id to pricing metadata."""
    requested = (model_name or "").strip().lower()
    for entry in _MODEL_CATALOG:
        aliases = {str(alias).lower() for alias in entry.get("aliases", ())}
        aliases.add(str(entry["name"]).lower())
        aliases.add(str(entry["model_id"]).lower())
        if requested in aliases:
            return ModelPricing(
                model_id=str(entry["model_id"]),
                input_price_per_million=float(entry["input_price_per_million"]),
                output_price_per_million=float(entry["output_price_per_million"]),
            )
    raise ValueError(f"Unknown model: {model_name}")


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


def estimate_full_run(
    pricing: ModelPricing,
    section_count: int,
    competitor_count: int,
) -> float:
    """Estimate the total LLM cost for the default full pipeline."""
    if section_count <= 0 or competitor_count <= 0:
        return 0.0

    section_calls = section_count * competitor_count
    research_cost = pricing.calculate_cost(2000, 800) * section_calls
    enrich_cost = pricing.calculate_cost(2000, 800) * competitor_count * 3
    themes_cost = pricing.calculate_cost(3000, 1500) * 5
    summary_cost = pricing.calculate_cost(3000, 1500) * 6
    return research_cost + enrich_cost + themes_cost + summary_cost


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
