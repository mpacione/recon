"""Schema wizard data model for recon.

Guides workspace creation through 4 phases: Identity -> Sections ->
Sources -> Review. Produces a complete schema dict for recon.yaml.

This is a pure data model -- no TUI rendering. The TUI layer renders
the wizard state, and the CLI collects input to feed into it.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from recon.section_library import all_sections


class WizardPhase(StrEnum):
    IDENTITY = "identity"
    SECTIONS = "sections"
    SOURCES = "sources"
    REVIEW = "review"


_PHASE_ORDER = [
    WizardPhase.IDENTITY,
    WizardPhase.SECTIONS,
    WizardPhase.SOURCES,
    WizardPhase.REVIEW,
]


class DecisionContext(StrEnum):
    BUILD_VS_BUY = "build-vs-buy"
    INVESTMENT = "investment"
    POSITIONING = "positioning"
    MARKET_ENTRY = "market-entry"
    EXECUTIVE_BRIEFING = "executive-briefing"
    GENERAL = "general"


_SECTION_RECOMMENDATIONS: dict[DecisionContext, list[str]] = {
    DecisionContext.BUILD_VS_BUY: [
        "capabilities",
        "pricing",
        "integration",
        "head_to_head",
    ],
    DecisionContext.INVESTMENT: [
        "overview",
        "capabilities",
        "pricing",
        "financial_health",
        "strategic_notes",
    ],
    DecisionContext.POSITIONING: [
        "capabilities",
        "brand_market",
        "head_to_head",
        "pricing",
    ],
    DecisionContext.MARKET_ENTRY: [
        "overview",
        "capabilities",
        "pricing",
        "distribution_gtm",
        "customer_segments",
    ],
    DecisionContext.EXECUTIVE_BRIEFING: [
        "overview",
        "capabilities",
        "enterprise",
        "head_to_head",
        "leadership_strategy",
        "strategic_notes",
    ],
}


_DEFAULT_SOURCE_PREFERENCES: dict[str, dict[str, list[str]]] = {
    "overview": {
        "primary": ["official website", "About page", "Wikipedia"],
        "secondary": ["Crunchbase", "LinkedIn", "press releases"],
        "avoid": ["user-generated wikis"],
    },
    "capabilities": {
        "primary": ["official docs", "feature pages", "API docs"],
        "secondary": ["G2 feature comparisons", "technical reviews"],
        "avoid": ["marketing landing pages without specifics"],
    },
    "pricing": {
        "primary": ["official pricing pages", "documentation"],
        "secondary": ["G2 reviews", "TrustRadius", "analyst reports"],
        "avoid": ["reddit speculation", "outdated blog posts"],
    },
    "integration": {
        "primary": ["official integration directory", "API docs"],
        "secondary": ["partner announcements", "technical blogs"],
        "avoid": ["marketing claims without API evidence"],
    },
    "enterprise": {
        "primary": ["trust/security pages", "compliance documentation"],
        "secondary": ["analyst reports", "enterprise review sites"],
        "avoid": ["vendor press releases without verification"],
    },
    "brand_market": {
        "primary": ["Hacker News", "Reddit", "dev.to", "Stack Overflow"],
        "secondary": ["Twitter/X", "Discord communities"],
        "avoid": ["sponsored content", "vendor press releases"],
    },
    "customer_segments": {
        "primary": ["official website", "case studies", "customer stories"],
        "secondary": ["review sites", "analyst reports", "job postings"],
        "avoid": ["vague positioning copy without customer evidence"],
    },
    "distribution_gtm": {
        "primary": ["official website", "store locators", "partner directories"],
        "secondary": ["industry news", "marketplace listings", "channel partner pages"],
        "avoid": ["generic launch copy without distribution evidence"],
    },
    "financial_health": {
        "primary": ["earnings", "investor relations", "funding databases"],
        "secondary": ["industry reporting", "hiring signals", "executive interviews"],
        "avoid": ["rumors", "unsourced speculation"],
    },
    "leadership_strategy": {
        "primary": ["leadership pages", "interviews", "shareholder letters"],
        "secondary": ["conference talks", "press releases", "earnings calls"],
        "avoid": ["generic bios without strategic substance"],
    },
    "head_to_head": {
        "primary": ["official comparison pages", "feature matrices"],
        "secondary": ["G2 comparisons", "analyst reports"],
        "avoid": ["biased vendor comparisons"],
    },
    "strategic_notes": {
        "primary": ["analyst reports", "funding announcements", "earnings"],
        "secondary": ["industry news", "executive interviews"],
        "avoid": ["social media speculation"],
    },
}


class DefaultSections:
    ALL: list[dict[str, Any]] = all_sections()


_DEFAULT_RATING_SCALES: dict[str, dict[str, Any]] = {
    "capability": {
        "name": "Capability Rating",
        "values": ["1", "2", "3", "4", "5"],
        "never_use": ["emoji", "letter grades"],
    },
    "status": {
        "name": "Feature Status",
        "values": ["Y", "~", "N", "?"],
        "never_use": ["emoji checkmarks", "colored circles"],
    },
    "threat": {
        "name": "Threat Level",
        "values": ["Critical", "High", "Medium", "Low", "Watch"],
        "never_use": ["emoji indicators", "color names"],
    },
}


class WizardState:
    """Tracks wizard state through all phases."""

    def __init__(self) -> None:
        self.phase = WizardPhase.IDENTITY
        self.company_name = ""
        self.products: list[str] = []
        self.domain = ""
        self.decision_contexts: list[DecisionContext] = []
        self.own_product = False
        self.selected_section_keys: set[str] = set()
        self._source_overrides: dict[str, dict[str, list[str]]] = {}

    def set_identity(
        self,
        company_name: str,
        products: list[str],
        domain: str,
        decision_contexts: list[DecisionContext],
        own_product: bool = False,
    ) -> None:
        self.company_name = company_name
        self.products = products
        self.domain = domain
        self.decision_contexts = decision_contexts
        self.own_product = own_product
        self.selected_section_keys = set(self.recommended_section_keys())

    def recommended_section_keys(self) -> list[str]:
        if DecisionContext.GENERAL in self.decision_contexts:
            return [s["key"] for s in DefaultSections.ALL]

        keys: list[str] = []
        for ctx in self.decision_contexts:
            for key in _SECTION_RECOMMENDATIONS.get(ctx, []):
                if key not in keys:
                    keys.append(key)
        return keys

    def toggle_section(self, key: str) -> None:
        if key in self.selected_section_keys:
            self.selected_section_keys.discard(key)
        else:
            self.selected_section_keys.add(key)

    def get_source_preferences(self, section_key: str) -> dict[str, list[str]]:
        if section_key in self._source_overrides:
            return self._source_overrides[section_key]
        return dict(_DEFAULT_SOURCE_PREFERENCES.get(section_key, {
            "primary": [],
            "secondary": [],
            "avoid": [],
        }))

    def set_source_preferences(
        self,
        section_key: str,
        primary: list[str] | None = None,
        secondary: list[str] | None = None,
        avoid: list[str] | None = None,
    ) -> None:
        current = self.get_source_preferences(section_key)
        if primary is not None:
            current["primary"] = primary
        if secondary is not None:
            current["secondary"] = secondary
        if avoid is not None:
            current["avoid"] = avoid
        self._source_overrides[section_key] = current

    def advance(self) -> None:
        if self.phase == WizardPhase.IDENTITY and not self.company_name:
            msg = "company_name must be set before advancing"
            raise ValueError(msg)
        idx = _PHASE_ORDER.index(self.phase)
        if idx < len(_PHASE_ORDER) - 1:
            self.phase = _PHASE_ORDER[idx + 1]

    def go_back(self) -> None:
        idx = _PHASE_ORDER.index(self.phase)
        if idx > 0:
            self.phase = _PHASE_ORDER[idx - 1]

    def to_schema_dict(self) -> dict[str, Any]:
        sections: list[dict[str, Any]] = []
        for section_def in DefaultSections.ALL:
            key = section_def["key"]
            if key not in self.selected_section_keys:
                continue
            section = dict(section_def)
            sources = self.get_source_preferences(key)
            if sources.get("primary") or sources.get("secondary") or sources.get("avoid"):
                section["source_preferences"] = {
                    "primary": sources.get("primary", []),
                    "secondary": sources.get("secondary", []),
                    "avoid": sources.get("avoid", []),
                }
            sections.append(section)

        return {
            "domain": self.domain,
            "identity": {
                "company_name": self.company_name,
                "products": self.products,
                "decision_context": [ctx.value for ctx in self.decision_contexts],
                "own_product": self.own_product,
            },
            "rating_scales": _DEFAULT_RATING_SCALES,
            "sections": sections,
        }
