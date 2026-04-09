"""Tests for the verification engine.

Multi-agent consensus verification with three tiers:
- Standard: Agent A only (1x cost)
- Verified: Agent A + B consensus (~2x cost)
- Deep Verified: A + B + C tie-breaking (~3x cost)

Agent B checks Agent A's sources then independently corroborates.
Agent C breaks ties where A and B disagree.
"""

from unittest.mock import AsyncMock

from recon.llm import LLMResponse
from recon.verification import (
    SourceStatus,
    VerificationEngine,
    VerificationOutcome,
    VerificationRequest,
)


def _make_response(text: str) -> LLMResponse:
    return LLMResponse(
        text=text,
        input_tokens=200,
        output_tokens=100,
        model="claude-sonnet-4-20250514",
        stop_reason="end_turn",
    )


def _mock_llm(responses: list[str]) -> AsyncMock:
    client = AsyncMock()
    client.complete = AsyncMock(
        side_effect=[_make_response(text) for text in responses],
    )
    client.total_input_tokens = 0
    client.total_output_tokens = 0
    client.call_count = 0
    return client


class TestStandardVerification:
    async def test_returns_original_content_unchanged(self) -> None:
        llm = _mock_llm([])
        engine = VerificationEngine(llm_client=llm)

        request = VerificationRequest(
            content="Agent A's research output.",
            sources=["https://example.com"],
            section_key="overview",
            competitor_name="Alpha",
            tier="standard",
        )

        outcome = await engine.verify(request)

        assert isinstance(outcome, VerificationOutcome)
        assert outcome.tier == "standard"
        assert outcome.content == "Agent A's research output."
        assert llm.complete.call_count == 0

    async def test_standard_marks_sources_unverified(self) -> None:
        llm = _mock_llm([])
        engine = VerificationEngine(llm_client=llm)

        request = VerificationRequest(
            content="Content.",
            sources=["https://a.com", "https://b.com"],
            section_key="overview",
            competitor_name="Alpha",
            tier="standard",
        )

        outcome = await engine.verify(request)

        assert all(s.status == SourceStatus.UNVERIFIED for s in outcome.source_results)


class TestVerifiedTier:
    async def test_calls_agent_b_for_verification(self) -> None:
        llm = _mock_llm([
            '{"sources": [{"url": "https://a.com", "status": "confirmed", "notes": "Matches official docs"}],'
            '"corroboration": "Independently confirmed via product page."}',
        ])
        engine = VerificationEngine(llm_client=llm)

        request = VerificationRequest(
            content="Content from Agent A.",
            sources=["https://a.com"],
            section_key="overview",
            competitor_name="Alpha",
            tier="verified",
        )

        outcome = await engine.verify(request)

        assert outcome.tier == "verified"
        assert llm.complete.call_count == 1

    async def test_parses_source_statuses_from_agent_b(self) -> None:
        llm = _mock_llm([
            '{"sources": ['
            '{"url": "https://a.com", "status": "confirmed", "notes": "Correct"},'
            '{"url": "https://b.com", "status": "disputed", "notes": "Outdated"}'
            '],'
            '"corroboration": "Partially confirmed."}',
        ])
        engine = VerificationEngine(llm_client=llm)

        request = VerificationRequest(
            content="Content.",
            sources=["https://a.com", "https://b.com"],
            section_key="overview",
            competitor_name="Alpha",
            tier="verified",
        )

        outcome = await engine.verify(request)

        statuses = {r.url: r.status for r in outcome.source_results}
        assert statuses["https://a.com"] == SourceStatus.CONFIRMED
        assert statuses["https://b.com"] == SourceStatus.DISPUTED


class TestDeepVerifiedTier:
    async def test_calls_agents_b_and_c(self) -> None:
        llm = _mock_llm([
            '{"sources": [{"url": "https://a.com", "status": "confirmed", "notes": "OK"}],'
            '"corroboration": "Confirmed."}',
            '{"sources": [{"url": "https://a.com", "status": "confirmed", "notes": "Also confirmed"}],'
            '"additional_corroboration": "Found third source."}',
        ])
        engine = VerificationEngine(llm_client=llm)

        request = VerificationRequest(
            content="Content.",
            sources=["https://a.com"],
            section_key="overview",
            competitor_name="Alpha",
            tier="deep",
        )

        outcome = await engine.verify(request)

        assert outcome.tier == "deep"
        assert llm.complete.call_count == 2

    async def test_handles_agent_b_json_parse_error_gracefully(self) -> None:
        llm = _mock_llm(["not valid json at all"])
        engine = VerificationEngine(llm_client=llm)

        request = VerificationRequest(
            content="Content.",
            sources=["https://a.com"],
            section_key="overview",
            competitor_name="Alpha",
            tier="verified",
        )

        outcome = await engine.verify(request)

        assert all(s.status == SourceStatus.UNVERIFIED for s in outcome.source_results)


class TestVerificationRequest:
    def test_request_fields(self) -> None:
        request = VerificationRequest(
            content="Content.",
            sources=["https://a.com"],
            section_key="overview",
            competitor_name="Alpha",
            tier="verified",
        )

        assert request.content == "Content."
        assert request.sources == ["https://a.com"]
        assert request.tier == "verified"
