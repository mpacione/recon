"""Gemini-based competitor discovery agent.

Uses Google's Gemini API with grounding (Google Search) as an
alternative to Anthropic's web_search tool. Returns the same
DiscoveryCandidate objects so both agents are interchangeable.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

try:
    from google import genai
    from google.genai import types
except ImportError:  # pragma: no cover -- exercised only when dependency missing
    genai = None
    types = None

from recon.discovery import (
    DiscoveryCandidate,
    DiscoveryState,
    parse_candidates_response,
)
from recon.llm import LLMResponse
from recon.logging import get_logger
from recon.provenance import ProvenanceRecorder

if TYPE_CHECKING:
    pass

_log = get_logger(__name__)

_GEMINI_MODEL = "gemini-2.5-flash"

_SYSTEM_INSTRUCTION = """\
You are a competitive intelligence research agent. Your task is to discover \
competitors in a given market domain by searching the web via Google Search.

Search for real companies in this market. Look at G2, ProductHunt, \
Crunchbase, "alternatives to X" lists, analyst reports, and recent news. \
Err on the side of inclusion -- it's easier for the user to reject than \
to know what's missing.

After searching, return your findings as a JSON object with a "candidates" \
array. Each candidate must have: name, url, blurb (2-line description), \
provenance (where you found it, e.g. "G2 category leader"), and \
suggested_tier (established, emerging, or experimental).

Pre-filter obvious junk: dead companies, unrelated products, duplicates. \
Return 10-15 candidates per batch.

Return ONLY the JSON object, no other text."""


class GeminiDiscoveryAgent:
    """Competitor discovery using Gemini with Google Search grounding."""

    def __init__(
        self,
        api_key: str,
        domain: str,
        seed_competitors: list[str] | None = None,
        provenance: ProvenanceRecorder | None = None,
    ) -> None:
        if genai is None or types is None:
            msg = "google-genai is not installed. Install it to use Gemini discovery."
            raise RuntimeError(msg)
        self._api_key = api_key
        self._domain = domain
        self._seeds = seed_competitors or []
        self._client = genai.Client(api_key=api_key)
        self._provenance = provenance

    async def search(
        self,
        state: DiscoveryState | None = None,
    ) -> list[DiscoveryCandidate]:
        """Search for competitors using Gemini + Google Search grounding."""
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

        grounding_tool = types.Tool(
            google_search=types.GoogleSearch()
        )
        config = types.GenerateContentConfig(
            system_instruction=_SYSTEM_INSTRUCTION,
            tools=[grounding_tool],
            temperature=0.7,
        )

        _log.info(
            "GeminiDiscoveryAgent.search domain=%s model=%s",
            self._domain,
            _GEMINI_MODEL,
        )

        try:
            response = await asyncio.to_thread(
                self._client.models.generate_content,
                model=_GEMINI_MODEL,
                contents=user_prompt,
                config=config,
            )
        except Exception:
            _log.exception("GeminiDiscoveryAgent.search failed")
            raise

        _log.info(
            "GeminiDiscoveryAgent.search got response len=%d",
            len(response.text) if response.text else 0,
        )

        candidates = parse_candidates_response(response.text or "")
        _log.info(
            "GeminiDiscoveryAgent.search parsed %d candidates",
            len(candidates),
        )
        if self._provenance is not None:
            llm_response = LLMResponse(
                text=response.text or "",
                input_tokens=0,
                output_tokens=0,
                model=_GEMINI_MODEL,
                stop_reason="stop",
                metadata={
                    "sdk": "google-genai",
                    "response": {
                        "text": response.text or "",
                    },
                },
            )
            self._provenance.record_discovery_search(
                provider="gemini_google_search",
                domain=self._domain,
                round_count=state.round_count if state else 0,
                system_prompt=_SYSTEM_INSTRUCTION,
                user_prompt=user_prompt,
                tools=[{"type": "google_search"}],
                response=llm_response,
                candidates=[
                    {
                        "name": candidate.name,
                        "url": candidate.url,
                        "blurb": candidate.blurb,
                        "provenance": candidate.provenance,
                        "suggested_tier": candidate.suggested_tier.value,
                    }
                    for candidate in candidates
                ],
            )
        return candidates
