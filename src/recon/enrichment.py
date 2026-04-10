"""Enrichment pipeline for recon.

Three progressive enrichment passes:
- Cleanup: format alignment, schema compliance, fill gaps
- Sentiment: developer quotes, traction signals, talking points
- Strategic: platform/ecosystem, trust/governance, workflow, time-to-value
"""

from __future__ import annotations

import asyncio  # noqa: TCH003 -- used at runtime for cancel_event type
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

import frontmatter

from recon.llm import LLMClient  # noqa: TCH001
from recon.logging import get_logger
from recon.workers import WorkerPool
from recon.workspace import Workspace  # noqa: TCH001

_log = get_logger(__name__)


class EnrichmentPass(StrEnum):
    CLEANUP = "cleanup"
    SENTIMENT = "sentiment"
    STRATEGIC = "strategic"


_SYSTEM_PROMPTS: dict[EnrichmentPass, str] = {
    EnrichmentPass.CLEANUP: """You are a format cleanup agent for competitive intelligence profiles.

Your job is to:
- Fix formatting inconsistencies (tables, headings, lists)
- Ensure schema compliance (correct sections, proper structure)
- Fill any obvious gaps with "[Needs research]" markers
- Remove any emoji
- Standardize rating formats
- Ensure source citations are properly formatted

Return the cleaned content. Do not add new research -- only fix formatting.""",
    EnrichmentPass.SENTIMENT: """You are a developer sentiment research agent.

Your job is to enrich competitive intelligence profiles with:
- Developer quotes from HN, Reddit, Twitter/X, Discord
- Community sentiment analysis (positive/mixed/negative)
- Traction signals (growth indicators, adoption patterns)
- Migration patterns (where developers are moving from/to)
- Talking points for internal discussion

Search for recent developer discussions and opinions.
Include source URLs for all quotes and claims.""",
    EnrichmentPass.STRATEGIC: """You are a strategic analysis agent for competitive intelligence.

Your job is to enrich profiles with strategic assessment:
- Platform & ecosystem analysis (marketplace, API surface, lock-in)
- Trust & governance (compliance, audit, admin controls)
- Workflow embedding (interaction model, context sources, triggers)
- Time to value (onboarding friction, free tier, self-serve)
- Competitive positioning and strategic threats

Focus on evidence-based analysis with source citations.""",
}


@dataclass
class EnrichmentOrchestrator:
    """Orchestrates enrichment passes across competitor profiles."""

    workspace: Workspace
    llm_client: LLMClient
    enrichment_pass: EnrichmentPass
    max_workers: int = 5

    async def enrich_all(
        self,
        targets: list[str] | None = None,
        *,
        cancel_event: asyncio.Event | None = None,
        pause_event: asyncio.Event | None = None,
    ) -> list[dict[str, Any]]:
        """Run the enrichment pass on eligible profiles.

        If ``targets`` is provided, only those competitors are enriched
        (matched case-insensitively against profile names). Unknown targets
        raise ``ValueError``. Targets that are not eligible (empty profiles)
        are silently skipped after the membership check.
        """
        profiles = self.workspace.list_profiles()

        if targets is not None:
            by_lower = {p["name"].lower(): p["name"] for p in profiles}
            resolved: set[str] = set()
            unknown: list[str] = []
            for requested in targets:
                canonical = by_lower.get(requested.lower())
                if canonical is None:
                    unknown.append(requested)
                else:
                    resolved.add(canonical)
            if unknown:
                msg = f"Unknown target(s): {', '.join(unknown)}"
                raise ValueError(msg)
            profiles = [p for p in profiles if p["name"] in resolved]

        eligible = [p for p in profiles if self._has_content(p)]

        _log.info(
            "enrich pass=%s eligible=%d targets=%s",
            self.enrichment_pass.value,
            len(eligible),
            "all" if targets is None else f"{len(targets)} specified",
        )

        if not eligible:
            _log.info("enrich pass=%s nothing to do", self.enrichment_pass.value)
            return []

        if cancel_event is not None and cancel_event.is_set():
            _log.info("enrich pass=%s cancelled before start", self.enrichment_pass.value)
            return []

        pool = WorkerPool(max_workers=self.max_workers)
        outcomes = await pool.run(
            self._enrich_one,
            eligible,
            cancel_event=cancel_event,
            pause_event=pause_event,
        )

        results = [o.value for o in outcomes if o.success and o.value]
        _log.info(
            "enrich pass=%s complete success=%d failed=%d",
            self.enrichment_pass.value,
            len(results),
            len(outcomes) - len(results),
        )
        return results

    def _has_content(self, profile_meta: dict[str, Any]) -> bool:
        """Check if a profile has research content worth enriching."""
        full = self.workspace.read_profile(profile_meta["_slug"])
        if full is None:
            return False
        content = full.get("_content", "")
        return len(content.strip()) > 0

    async def _enrich_one(self, profile_meta: dict[str, Any]) -> dict[str, Any]:
        """Enrich a single profile."""
        slug = profile_meta["_slug"]
        name = profile_meta["name"]

        full = self.workspace.read_profile(slug)
        if full is None:
            return {}

        content = full["_content"]
        system_prompt = _SYSTEM_PROMPTS[self.enrichment_pass]

        response = await self.llm_client.complete(
            system_prompt=system_prompt,
            user_prompt=(
                f"Enrich the following profile for **{name}**:\n\n"
                f"{content}"
            ),
        )

        self._update_profile(slug, response.text)

        return {
            "competitor": name,
            "pass": self.enrichment_pass.value,
            "tokens": {"input": response.input_tokens, "output": response.output_tokens},
        }

    def _update_profile(self, slug: str, new_content: str) -> None:
        """Update a profile's content with enriched version."""
        path = self.workspace.competitors_dir / f"{slug}.md"
        if not path.exists():
            return

        post = frontmatter.load(str(path))
        post.content = new_content
        path.write_text(frontmatter.dumps(post))
