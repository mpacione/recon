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


# ---------------------------------------------------------------------------
# Model pricing registry
# ---------------------------------------------------------------------------

_MODEL_REGISTRY: dict[str, dict[str, object]] = {
    "sonnet": {
        "model_id": "claude-sonnet-4-20250514",
        "input_price_per_million": 3.0,
        "output_price_per_million": 15.0,
        "description": "recommended",
    },
    "opus": {
        "model_id": "claude-opus-4-20250514",
        "input_price_per_million": 15.0,
        "output_price_per_million": 75.0,
        "description": "deeper analysis",
    },
    "haiku": {
        "model_id": "claude-haiku-4-5-20251001",
        "input_price_per_million": 0.80,
        "output_price_per_million": 4.0,
        "description": "faster, less depth",
    },
}


def get_model_pricing(name: str) -> ModelPricing:
    """Get pricing for a model by short name (sonnet, opus, haiku)."""
    entry = _MODEL_REGISTRY.get(name)
    if entry is None:
        msg = f"Unknown model: {name}. Available: {list(_MODEL_REGISTRY)}"
        raise ValueError(msg)
    return ModelPricing(
        model_id=str(entry["model_id"]),
        input_price_per_million=float(entry["input_price_per_million"]),
        output_price_per_million=float(entry["output_price_per_million"]),
    )


def list_available_models() -> list[dict[str, object]]:
    """List all available models with pricing and descriptions."""
    return [
        {
            "name": name,
            "model_id": entry["model_id"],
            "input_price_per_million": entry["input_price_per_million"],
            "output_price_per_million": entry["output_price_per_million"],
            "description": entry["description"],
        }
        for name, entry in _MODEL_REGISTRY.items()
    ]


def estimate_full_run(
    pricing: ModelPricing,
    section_count: int,
    competitor_count: int,
    enrichment_passes: int = 3,
    theme_count: int = 5,
) -> float:
    """Estimate total cost for a full pipeline run.

    Breaks down into: research + enrichment + themes + summaries.
    Returns the total estimated cost in USD.
    """
    tracker = CostTracker(model_pricing=pricing)

    research = tracker.estimate_section_cost(
        format_type="prose",
        competitor_count=competitor_count,
    ) * section_count

    enrichment = (
        pricing.calculate_cost(2000, 800) * competitor_count * enrichment_passes
    )

    themes_cost = pricing.calculate_cost(3000, 1500) * theme_count

    summaries = pricing.calculate_cost(3000, 1500) * (theme_count + 1)

    return research + enrichment + themes_cost + summaries


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


@dataclass(frozen=True)
class SectionCostSpec:
    format_type: str = "prose"
    verification_tier: str = "standard"


@dataclass(frozen=True)
class RunCostBreakdown:
    competitor_count: int
    section_count: int
    verification_mode: str
    research_per_company: float
    enrichment_per_company: float
    variable_per_company: float
    research_total: float
    enrichment_total: float
    fixed_themes: float
    fixed_summary: float
    fixed_total: float
    blended_per_company: float
    total_run_cost: float


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


_VERIFICATION_RANK: dict[str, int] = {
    "standard": 0,
    "verified": 1,
    "deep": 2,
}

_VERIFICATION_TIME_MULTIPLIERS: dict[str, float] = {
    "standard": 1.0,
    "verified": 2.0,
    "deep": 3.0,
}


def _effective_verification_tier(section_tier: str, verification_mode: str) -> str:
    normalized_section = (section_tier or "standard").strip().lower()
    normalized_mode = (verification_mode or "standard").strip().lower()
    if normalized_mode == "standard":
        return normalized_section
    section_rank = _VERIFICATION_RANK.get(normalized_section, 0)
    mode_rank = _VERIFICATION_RANK.get(normalized_mode, 0)
    return normalized_mode if mode_rank > section_rank else normalized_section


def estimate_run_breakdown(
    pricing: ModelPricing,
    *,
    competitor_count: int,
    sections: list[SectionCostSpec] | None = None,
    section_count: int | None = None,
    verification_mode: str = "standard",
    enrichment_passes: int = 3,
    theme_count: int = 5,
) -> RunCostBreakdown:
    """Estimate a run with variable per-company cost plus fixed overhead."""
    normalized_mode = (verification_mode or "standard").strip().lower()
    specs = list(sections or [])
    if not specs and section_count:
        specs = [SectionCostSpec()] * max(0, int(section_count))

    effective_section_count = len(specs)
    if competitor_count <= 0 or effective_section_count <= 0:
        return RunCostBreakdown(
            competitor_count=max(0, competitor_count),
            section_count=effective_section_count,
            verification_mode=normalized_mode,
            research_per_company=0.0,
            enrichment_per_company=0.0,
            variable_per_company=0.0,
            research_total=0.0,
            enrichment_total=0.0,
            fixed_themes=0.0,
            fixed_summary=0.0,
            fixed_total=0.0,
            blended_per_company=0.0,
            total_run_cost=0.0,
        )

    tracker = CostTracker(model_pricing=pricing)
    research_per_company = 0.0
    for spec in specs:
        effective_tier = _effective_verification_tier(
            spec.verification_tier,
            normalized_mode,
        )
        research_per_company += tracker.estimate_section_cost(
            format_type=spec.format_type,
            competitor_count=1,
            verification_tier=effective_tier,
        )

    enrichment_per_company = pricing.calculate_cost(2000, 800) * enrichment_passes
    variable_per_company = research_per_company + enrichment_per_company
    research_total = research_per_company * competitor_count
    enrichment_total = enrichment_per_company * competitor_count
    fixed_themes = pricing.calculate_cost(3000, 1500) * theme_count
    fixed_summary = pricing.calculate_cost(3000, 1500) * (theme_count + 1)
    fixed_total = fixed_themes + fixed_summary
    total_run_cost = research_total + enrichment_total + fixed_total
    blended_per_company = total_run_cost / competitor_count if competitor_count > 0 else 0.0

    return RunCostBreakdown(
        competitor_count=competitor_count,
        section_count=effective_section_count,
        verification_mode=normalized_mode,
        research_per_company=research_per_company,
        enrichment_per_company=enrichment_per_company,
        variable_per_company=variable_per_company,
        research_total=research_total,
        enrichment_total=enrichment_total,
        fixed_themes=fixed_themes,
        fixed_summary=fixed_summary,
        fixed_total=fixed_total,
        blended_per_company=blended_per_company,
        total_run_cost=total_run_cost,
    )


def estimate_run_duration_minutes(
    *,
    section_count: int,
    competitor_count: int,
    worker_count: int,
    verification_mode: str = "standard",
    enrichment_passes: int = 3,
) -> float:
    """Estimate wall-clock minutes for a full run.

    The TUI needs a simple user-facing planning number, not a precise
    scheduler simulation. This estimate assumes:
    - research is parallelized across the configured worker count
    - stricter verification tiers increase research time
    - enrichment also benefits from parallelism, though with smaller
      gains than research
    - synthesis / delivery add a small fixed tail
    """
    if section_count <= 0 or competitor_count <= 0:
        return 0.0

    workers = max(1, worker_count)
    verification = (verification_mode or "standard").strip().lower()
    verification_multiplier = _VERIFICATION_TIME_MULTIPLIERS.get(verification, 1.0)

    research_secs = (section_count * competitor_count * 60.0 * verification_multiplier) / workers
    enrich_secs = (competitor_count * enrichment_passes * 25.0) / max(1, min(workers, 10))
    fixed_secs = 240.0
    total_secs = research_secs + enrich_secs + fixed_secs
    return total_secs / 60.0


def estimate_full_run(
    pricing: ModelPricing,
    section_count: int,
    competitor_count: int,
    verification_mode: str = "standard",
) -> float:
    """Estimate the total LLM cost for the default full pipeline."""
    breakdown = estimate_run_breakdown(
        pricing,
        competitor_count=competitor_count,
        section_count=section_count,
        verification_mode=verification_mode,
    )
    return breakdown.total_run_cost


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
