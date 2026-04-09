"""Discovery module for recon.

Manages iterative competitor finding: candidates are presented in
batches, users toggle accept/reject, and the state tracks everything
across rounds with deduplication by URL domain.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import urlparse

from recon.llm import LLMClient  # noqa: TCH001


class CompetitorTier(StrEnum):
    ESTABLISHED = "established"
    EMERGING = "emerging"
    EXPERIMENTAL = "experimental"
    UNKNOWN = "unknown"


@dataclass
class DiscoveryCandidate:
    name: str
    url: str
    blurb: str
    provenance: str
    suggested_tier: CompetitorTier
    accepted: bool = True


def _extract_domain(url: str) -> str:
    """Extract the registrable domain from a URL for dedup."""
    parsed = urlparse(url)
    hostname = parsed.hostname or ""
    parts = hostname.split(".")
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return hostname


class DiscoveryState:
    """Tracks all candidates across discovery rounds."""

    def __init__(self) -> None:
        self._candidates: list[DiscoveryCandidate] = []
        self._round_count: int = 0
        self._seen_domains: set[str] = set()

    @property
    def all_candidates(self) -> list[DiscoveryCandidate]:
        return list(self._candidates)

    @property
    def round_count(self) -> int:
        return self._round_count

    @property
    def accepted_candidates(self) -> list[DiscoveryCandidate]:
        return [c for c in self._candidates if c.accepted]

    @property
    def rejected_candidates(self) -> list[DiscoveryCandidate]:
        return [c for c in self._candidates if not c.accepted]

    def add_round(self, candidates: list[DiscoveryCandidate]) -> None:
        self._round_count += 1
        for candidate in candidates:
            domain = _extract_domain(candidate.url)
            if domain not in self._seen_domains:
                self._seen_domains.add(domain)
                self._candidates.append(candidate)

    def toggle(self, index: int) -> None:
        if index < 0 or index >= len(self._candidates):
            msg = f"Index {index} out of range (0-{len(self._candidates) - 1})"
            raise IndexError(msg)
        self._candidates[index].accepted = not self._candidates[index].accepted

    def accept_all(self) -> None:
        for c in self._candidates:
            c.accepted = True

    def reject_all(self) -> None:
        for c in self._candidates:
            c.accepted = False

    def add_manual(self, name: str, url: str, blurb: str) -> None:
        candidate = DiscoveryCandidate(
            name=name,
            url=url,
            blurb=blurb,
            provenance="manually added",
            suggested_tier=CompetitorTier.UNKNOWN,
        )
        domain = _extract_domain(url)
        if domain not in self._seen_domains:
            self._seen_domains.add(domain)
            self._candidates.append(candidate)

    def pattern_summary(self) -> str:
        accepted = len(self.accepted_candidates)
        rejected = len(self.rejected_candidates)
        return f"Accepted: {accepted}, Rejected: {rejected}"


def _tier_from_string(value: str) -> CompetitorTier:
    try:
        return CompetitorTier(value.lower())
    except ValueError:
        return CompetitorTier.UNKNOWN


def parse_candidates_response(raw: str) -> list[DiscoveryCandidate]:
    """Parse LLM JSON response into candidate objects."""
    json_str = raw.strip()
    fence_match = re.search(r"```(?:json)?\s*\n(.*?)```", json_str, re.DOTALL)
    if fence_match:
        json_str = fence_match.group(1).strip()

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError:
        return []

    candidates: list[DiscoveryCandidate] = []
    for entry in data.get("candidates", []):
        if not isinstance(entry, dict):
            continue
        name = entry.get("name", "")
        url = entry.get("url", "")
        if not name or not url:
            continue
        candidates.append(DiscoveryCandidate(
            name=name,
            url=url,
            blurb=entry.get("blurb", ""),
            provenance=entry.get("provenance", ""),
            suggested_tier=_tier_from_string(entry.get("suggested_tier", "unknown")),
        ))
    return candidates


_SEARCH_SYSTEM_PROMPT = """\
You are a competitive intelligence research agent. Your task is to discover \
competitors in a given market domain.

Return your findings as a JSON object with a "candidates" array. Each candidate \
must have: name, url, blurb (2-line description), provenance (where you found it), \
and suggested_tier (established, emerging, or experimental).

Err on the side of inclusion. Pre-filter obvious junk: dead companies, unrelated \
products, duplicates. Return 10-15 candidates per batch.

Return ONLY the JSON object, no other text."""


class DiscoveryAgent:
    """LLM-powered competitor discovery agent."""

    def __init__(
        self,
        llm_client: LLMClient,
        domain: str,
        seed_competitors: list[str] | None = None,
    ) -> None:
        self._client = llm_client
        self._domain = domain
        self._seeds = seed_competitors or []

    async def search(
        self,
        state: DiscoveryState | None = None,
    ) -> list[DiscoveryCandidate]:
        prompt_parts = [f"Domain: {self._domain}"]

        if self._seeds:
            prompt_parts.append(f"Known competitors: {', '.join(self._seeds)}")

        if state and state.round_count > 0:
            prompt_parts.append(f"\nPrevious rounds: {state.round_count}")
            if state.accepted_candidates:
                accepted_names = [c.name for c in state.accepted_candidates]
                prompt_parts.append(f"Accepted: {', '.join(accepted_names)}")
            if state.rejected_candidates:
                rejected_names = [c.name for c in state.rejected_candidates]
                prompt_parts.append(f"Rejected: {', '.join(rejected_names)}")
            existing_names = [c.name for c in state.all_candidates]
            prompt_parts.append(f"Already seen: {', '.join(existing_names)}")
            prompt_parts.append("Find NEW candidates not yet seen.")

        user_prompt = "\n".join(prompt_parts)

        response = await self._client.complete(
            system_prompt=_SEARCH_SYSTEM_PROMPT,
            user_prompt=user_prompt,
        )
        return parse_candidates_response(response.text)

    async def analyze_patterns(self, state: DiscoveryState) -> str:
        accepted = [c.name for c in state.accepted_candidates]
        rejected = [c.name for c in state.rejected_candidates]

        prompt = (
            f"Domain: {self._domain}\n"
            f"Accepted competitors: {', '.join(accepted) if accepted else 'none'}\n"
            f"Rejected competitors: {', '.join(rejected) if rejected else 'none'}\n\n"
            "Analyze the accept/reject pattern. What types of competitors does "
            "the user prefer? Suggest a next search direction in 1-2 sentences."
        )

        response = await self._client.complete(
            system_prompt="You are a competitive intelligence analyst.",
            user_prompt=prompt,
        )
        return response.text
