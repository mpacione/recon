"""Canonical section library for recon schemas.

One source of truth for:
- default workspace sections
- SCHEMA tab section pool
- web template API pool
- schema designer defaults
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


SECTION_LIBRARY: list[dict[str, Any]] = [
    {
        "key": "overview",
        "title": "Overview",
        "description": (
            "Summarize the company at a high level: what it sells, who it serves, how it "
            "positions itself, how it describes its value, and the key facts an executive "
            "should know before reading the rest of the dossier."
        ),
        "when_relevant": "always",
        "allowed_formats": ["prose", "bullet_list"],
        "preferred_format": "prose",
    },
    {
        "key": "capabilities",
        "title": "Offerings & Capabilities",
        "description": (
            "Map the company’s core offerings, flagship products or services, important feature "
            "areas, technical strengths, differentiators, and where the portfolio appears shallow, "
            "commoditized, or especially strong."
        ),
        "when_relevant": "always",
        "allowed_formats": ["rated_table", "prose"],
        "preferred_format": "rated_table",
    },
    {
        "key": "pricing",
        "title": "Business Model & Pricing",
        "description": (
            "Document how the business makes money: pricing structure, packaging, entry points, "
            "upsell paths, service layers, monetization logic, and the signals that show whether "
            "it is competing on margin, volume, premium positioning, or lock-in."
        ),
        "when_relevant": "always",
        "allowed_formats": ["table", "key_value", "prose"],
        "preferred_format": "table",
    },
    {
        "key": "customer_segments",
        "title": "Customer Segments & Use Cases",
        "description": (
            "Identify the customer groups this company appears to prioritize, the use cases it "
            "optimizes for, the needs it serves well, and any gaps between its messaging, product "
            "depth, and the segments it is trying to win."
        ),
        "when_relevant": "always",
        "allowed_formats": ["bullet_list", "prose", "table"],
        "preferred_format": "bullet_list",
    },
    {
        "key": "distribution_gtm",
        "title": "Distribution & Go-to-Market",
        "description": (
            "Explain how the company gets to market: sales motion, channels, retail or field "
            "presence, partnerships, online conversion paths, geographic reach, and the commercial "
            "mechanics that appear to drive adoption and revenue."
        ),
        "when_relevant": "always",
        "allowed_formats": ["prose", "bullet_list", "table"],
        "preferred_format": "prose",
    },
    {
        "key": "integration",
        "title": "Ecosystem & Partnerships",
        "description": (
            "Assess how connected the business is to surrounding platforms, suppliers, partners, "
            "resellers, integrators, marketplaces, and adjacent tools. Look for evidence of network "
            "effects, dependency risk, or weak ecosystem support."
        ),
        "when_relevant": "often relevant",
        "allowed_formats": ["status_table", "prose", "bullet_list"],
        "preferred_format": "status_table",
    },
    {
        "key": "enterprise",
        "title": "Operations, Enterprise & Compliance",
        "description": (
            "Review operational maturity and trust signals: service reliability, support model, "
            "governance, compliance posture, procurement readiness, internationalization, and the "
            "practical evidence that larger customers or regulated buyers could depend on it."
        ),
        "when_relevant": "important for scaled, enterprise, or regulated businesses",
        "allowed_formats": ["status_table", "key_value", "prose"],
        "preferred_format": "status_table",
    },
    {
        "key": "brand_market",
        "title": "Brand, Experience & Market Sentiment",
        "description": (
            "Capture how the company is perceived in the market: brand strength, customer love or "
            "friction, reputation, reviews, community sentiment, and the emotional or experiential "
            "qualities that shape preference beyond raw features."
        ),
        "when_relevant": "always",
        "allowed_formats": ["key_value", "bullet_list", "prose"],
        "preferred_format": "key_value",
    },
    {
        "key": "financial_health",
        "title": "Financial Health & Momentum",
        "description": (
            "Look for signals of economic strength or weakness: funding, profitability, growth, "
            "revenue quality, manufacturing scale, hiring patterns, investor support, or other "
            "evidence that indicates momentum, instability, or capital constraints."
        ),
        "when_relevant": "when public, funded, or strategically important",
        "allowed_formats": ["key_value", "bullet_list", "prose"],
        "preferred_format": "key_value",
    },
    {
        "key": "leadership_strategy",
        "title": "Leadership & Strategic Direction",
        "description": (
            "Summarize the leadership team, strategic priorities, notable hires, public statements, "
            "product roadmap signals, and the broader direction the company seems to be pursuing "
            "based on decisions, investments, and messaging."
        ),
        "when_relevant": "often relevant",
        "allowed_formats": ["prose", "bullet_list"],
        "preferred_format": "prose",
    },
    {
        "key": "head_to_head",
        "title": "Head-to-Head Comparison",
        "description": (
            "Compare this competitor directly against your company or offering across the dimensions "
            "that matter most: strengths, weaknesses, strategic tradeoffs, likely buying reasons, "
            "and where they are structurally advantaged or exposed."
        ),
        "when_relevant": "always",
        "allowed_formats": ["comparison_table", "prose"],
        "preferred_format": "comparison_table",
    },
    {
        "key": "strategic_notes",
        "title": "Risks, Signals & Strategic Notes",
        "description": (
            "Capture the watchpoints that matter for decision-making: emerging threats, likely moves, "
            "organizational signals, partnership risk, market shifts, consolidation potential, and "
            "the strategic implications of everything above."
        ),
        "when_relevant": "always",
        "allowed_formats": ["prose", "bullet_list"],
        "preferred_format": "prose",
    },
]


SECTION_LIBRARY_BY_KEY: dict[str, dict[str, Any]] = {
    section["key"]: section for section in SECTION_LIBRARY
}


def all_sections() -> list[dict[str, Any]]:
    """Return deep-copied canonical section definitions."""
    return [deepcopy(section) for section in SECTION_LIBRARY]


def default_sections() -> list[dict[str, Any]]:
    """Return the default selected section set for new workspaces."""
    return all_sections()


def merge_with_selected(selected_sections: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Overlay selected workspace sections onto the full library.

    Returned sections always include a ``selected`` flag.
    Unknown custom sections are appended to the end.
    """
    selected_sections = selected_sections or []
    selected_by_key = {str(section.get("key", "")): dict(section) for section in selected_sections}
    merged: list[dict[str, Any]] = []
    for base in all_sections():
        selected = selected_by_key.pop(base["key"], None)
        if selected:
            section = {**base, **selected}
            section["selected"] = True
        else:
            section = {**base, "selected": False}
        merged.append(section)

    for custom in selected_by_key.values():
        merged.append({**custom, "selected": bool(custom.get("selected", True))})

    return merged
