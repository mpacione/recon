"""Verification engine for recon.

Multi-agent consensus verification with three tiers:
- Standard: Agent A only (1x cost) -- sources marked unverified
- Verified: Agent A + B consensus (~2x) -- B checks and corroborates
- Deep Verified: A + B + C tie-breaking (~3x) -- C resolves disputes

Per-source status tracking: Confirmed, Corroborated, Unverified, Disputed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum

from recon.llm import LLMClient  # noqa: TCH001
from recon.logging import get_logger
from recon.provenance import ProvenanceRecorder

_log = get_logger(__name__)


class SourceStatus(StrEnum):
    CONFIRMED = "confirmed"
    CORROBORATED = "corroborated"
    UNVERIFIED = "unverified"
    DISPUTED = "disputed"


@dataclass(frozen=True)
class SourceResult:
    url: str
    status: SourceStatus
    notes: str = ""


@dataclass(frozen=True)
class VerificationRequest:
    content: str
    sources: list[str]
    section_key: str
    competitor_name: str
    tier: str


@dataclass(frozen=True)
class VerificationOutcome:
    tier: str
    content: str
    source_results: list[SourceResult]
    corroboration_notes: str = ""
    competitor_name: str = ""
    section_key: str = ""
    input_tokens: int = 0
    output_tokens: int = 0


_AGENT_B_SYSTEM = """You are a verification agent. Your job is to check the accuracy
of research produced by another agent.

For each source URL provided:
1. Assess whether the source supports the claims made
2. Independently search for corroboration

Respond with JSON in this exact format:
{
  "sources": [
    {"url": "...", "status": "confirmed|disputed|unverified", "notes": "..."}
  ],
  "corroboration": "Your independent corroboration findings."
}"""

_AGENT_C_SYSTEM = """You are a tie-breaking verification agent. Two agents have
reviewed research and you need to resolve any disagreements.

For each source, provide your independent assessment.

Respond with JSON in this exact format:
{
  "sources": [
    {"url": "...", "status": "confirmed|disputed|unverified", "notes": "..."}
  ],
  "additional_corroboration": "Any additional evidence found."
}"""


class VerificationEngine:
    """Multi-agent consensus verification engine."""

    def __init__(
        self,
        llm_client: LLMClient,
        provenance: ProvenanceRecorder | None = None,
    ) -> None:
        self._llm = llm_client
        self._provenance = provenance

    async def verify(self, request: VerificationRequest) -> VerificationOutcome:
        """Verify research content based on the requested tier."""
        _log.info(
            "verify tier=%s competitor=%s section=%s sources=%d",
            request.tier,
            request.competitor_name,
            request.section_key,
            len(request.sources),
        )
        if request.tier == "standard":
            return self._standard_verification(request)
        if request.tier == "verified":
            return await self._verified_verification(request)
        if request.tier == "deep":
            return await self._deep_verification(request)

        return self._standard_verification(request)

    def _standard_verification(self, request: VerificationRequest) -> VerificationOutcome:
        """Standard tier: no verification, mark all sources as unverified."""
        return VerificationOutcome(
            tier="standard",
            content=request.content,
            source_results=[
                SourceResult(url=url, status=SourceStatus.UNVERIFIED)
                for url in request.sources
            ],
            competitor_name=request.competitor_name,
            section_key=request.section_key,
        )

    async def _verified_verification(self, request: VerificationRequest) -> VerificationOutcome:
        """Verified tier: Agent B checks and corroborates Agent A's work."""
        user_prompt = (
            f"Verify the following research about {request.competitor_name} "
            f"(section: {request.section_key}):\n\n"
            f"Content:\n{request.content}\n\n"
            f"Sources to check:\n" + "\n".join(f"- {url}" for url in request.sources)
        )

        response = await self._llm.complete(
            system_prompt=_AGENT_B_SYSTEM,
            user_prompt=user_prompt,
        )

        source_results = self._parse_source_results(response.text, request.sources)
        corroboration = self._extract_field(response.text, "corroboration")
        if self._provenance is not None:
            self._provenance.record_llm_call(
                actor="verification_agent_b",
                system_prompt=_AGENT_B_SYSTEM,
                user_prompt=user_prompt,
                tools=None,
                response=response,
                context={
                    "competitor": request.competitor_name,
                    "section": request.section_key,
                    "tier": request.tier,
                },
            )

        return VerificationOutcome(
            tier="verified",
            content=request.content,
            source_results=source_results,
            corroboration_notes=corroboration,
            competitor_name=request.competitor_name,
            section_key=request.section_key,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
        )

    async def _deep_verification(self, request: VerificationRequest) -> VerificationOutcome:
        """Deep verified tier: Agent B + Agent C for tie-breaking."""
        verified = await self._verified_verification(request)

        user_prompt = (
            f"Review the verification results for {request.competitor_name} "
            f"(section: {request.section_key}):\n\n"
            f"Original content:\n{request.content}\n\n"
            f"Agent B findings:\n{verified.corroboration_notes}\n\n"
            f"Sources:\n" + "\n".join(
                f"- {r.url}: {r.status.value} ({r.notes})" for r in verified.source_results
            )
        )

        response = await self._llm.complete(
            system_prompt=_AGENT_C_SYSTEM,
            user_prompt=user_prompt,
        )

        source_results = self._parse_source_results(response.text, request.sources)
        if self._provenance is not None:
            self._provenance.record_llm_call(
                actor="verification_agent_c",
                system_prompt=_AGENT_C_SYSTEM,
                user_prompt=user_prompt,
                tools=None,
                response=response,
                context={
                    "competitor": request.competitor_name,
                    "section": request.section_key,
                    "tier": request.tier,
                },
            )

        return VerificationOutcome(
            tier="deep",
            content=request.content,
            source_results=source_results if source_results else verified.source_results,
            corroboration_notes=self._extract_field(response.text, "additional_corroboration"),
            competitor_name=request.competitor_name,
            section_key=request.section_key,
            input_tokens=verified.input_tokens + response.input_tokens,
            output_tokens=verified.output_tokens + response.output_tokens,
        )

    def _parse_source_results(self, text: str, fallback_urls: list[str]) -> list[SourceResult]:
        """Parse source results from agent JSON response."""
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return [SourceResult(url=url, status=SourceStatus.UNVERIFIED) for url in fallback_urls]

        results: list[SourceResult] = []
        for source in data.get("sources", []):
            url = source.get("url", "")
            raw_status = source.get("status", "unverified").lower()
            status = SourceStatus(raw_status) if raw_status in SourceStatus.__members__.values() else SourceStatus.UNVERIFIED
            notes = source.get("notes", "")
            results.append(SourceResult(url=url, status=status, notes=notes))

        return results

    def _extract_field(self, text: str, field_name: str) -> str:
        """Extract a field from JSON response text."""
        try:
            data = json.loads(text)
            return str(data.get(field_name, ""))
        except json.JSONDecodeError:
            return ""
