"""Tests for the discovery agent.

The discovery agent uses LLM to find competitor candidates in batches,
analyze accept/reject patterns, and suggest next search directions.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

from recon.discovery import (
    CompetitorTier,
    DiscoveryAgent,
    DiscoveryCandidate,
    DiscoveryState,
    parse_candidates_response,
)
from recon.llm import LLMClient, LLMResponse


def _make_mock_client(response_text: str) -> LLMClient:
    """Create a mock LLM client that returns the given text."""
    mock_client = AsyncMock()
    mock_client.complete = AsyncMock(return_value=LLMResponse(
        text=response_text,
        input_tokens=100,
        output_tokens=200,
        model="claude-sonnet-4-20250514",
        stop_reason="end_turn",
    ))
    return mock_client


def _candidates_json(candidates: list[dict]) -> str:
    return json.dumps({"candidates": candidates})


class TestParseCandidatesResponse:
    def test_parses_valid_json(self) -> None:
        raw = _candidates_json([
            {
                "name": "Cursor",
                "url": "https://cursor.com",
                "blurb": "AI-first code editor",
                "provenance": "G2 category leader",
                "suggested_tier": "established",
            },
        ])

        candidates = parse_candidates_response(raw)

        assert len(candidates) == 1
        assert candidates[0].name == "Cursor"
        assert candidates[0].suggested_tier == CompetitorTier.ESTABLISHED

    def test_parses_multiple_candidates(self) -> None:
        raw = _candidates_json([
            {
                "name": "A",
                "url": "https://a.com",
                "blurb": "Tool A",
                "provenance": "G2",
                "suggested_tier": "established",
            },
            {
                "name": "B",
                "url": "https://b.com",
                "blurb": "Tool B",
                "provenance": "HN",
                "suggested_tier": "emerging",
            },
        ])

        candidates = parse_candidates_response(raw)

        assert len(candidates) == 2

    def test_handles_unknown_tier(self) -> None:
        raw = _candidates_json([
            {
                "name": "X",
                "url": "https://x.com",
                "blurb": "Unknown",
                "provenance": "search",
                "suggested_tier": "not_a_tier",
            },
        ])

        candidates = parse_candidates_response(raw)

        assert candidates[0].suggested_tier == CompetitorTier.UNKNOWN

    def test_handles_json_in_markdown_fence(self) -> None:
        raw = "Here are the candidates:\n```json\n" + _candidates_json([
            {
                "name": "A",
                "url": "https://a.com",
                "blurb": "Tool",
                "provenance": "G2",
                "suggested_tier": "established",
            },
        ]) + "\n```"

        candidates = parse_candidates_response(raw)

        assert len(candidates) == 1

    def test_returns_empty_on_invalid_json(self) -> None:
        candidates = parse_candidates_response("not json at all")

        assert candidates == []

    def test_skips_candidates_missing_required_fields(self) -> None:
        raw = _candidates_json([
            {
                "name": "Valid",
                "url": "https://valid.com",
                "blurb": "Good",
                "provenance": "G2",
                "suggested_tier": "established",
            },
            {
                "name": "Missing URL",
                "blurb": "Bad",
            },
        ])

        candidates = parse_candidates_response(raw)

        assert len(candidates) == 1
        assert candidates[0].name == "Valid"


class TestDiscoveryAgent:
    def test_search_returns_candidates(self) -> None:
        response = _candidates_json([
            {
                "name": "Cursor",
                "url": "https://cursor.com",
                "blurb": "AI editor",
                "provenance": "G2",
                "suggested_tier": "established",
            },
        ])
        mock_client = _make_mock_client(response)
        agent = DiscoveryAgent(
            llm_client=mock_client,
            domain="Developer Tools",
            seed_competitors=["VS Code"],
        )

        candidates = _run(agent.search())

        assert len(candidates) == 1
        assert candidates[0].name == "Cursor"

    def test_search_uses_domain_in_prompt(self) -> None:
        response = _candidates_json([])
        mock_client = _make_mock_client(response)
        agent = DiscoveryAgent(
            llm_client=mock_client,
            domain="CI/CD Platforms",
            seed_competitors=[],
        )

        _run(agent.search())

        call_args = mock_client.complete.call_args
        assert "CI/CD Platforms" in call_args.kwargs.get("user_prompt", call_args[1] if len(call_args) > 1 else "")

    def test_search_includes_seed_competitors(self) -> None:
        response = _candidates_json([])
        mock_client = _make_mock_client(response)
        agent = DiscoveryAgent(
            llm_client=mock_client,
            domain="Developer Tools",
            seed_competitors=["VS Code", "Sublime Text"],
        )

        _run(agent.search())

        call_args = mock_client.complete.call_args
        prompt = call_args.kwargs.get("user_prompt", "")
        assert "VS Code" in prompt
        assert "Sublime Text" in prompt

    def test_search_with_context_includes_patterns(self) -> None:
        response = _candidates_json([])
        mock_client = _make_mock_client(response)
        state = DiscoveryState()
        state.add_round([
            DiscoveryCandidate(
                name="Enterprise Tool", url="https://enterprise.com",
                blurb="Enterprise", provenance="Gartner",
                suggested_tier=CompetitorTier.ESTABLISHED,
            ),
        ])
        state.toggle(0)

        agent = DiscoveryAgent(
            llm_client=mock_client,
            domain="Developer Tools",
            seed_competitors=[],
        )

        _run(agent.search(state=state))

        call_args = mock_client.complete.call_args
        prompt = call_args.kwargs.get("user_prompt", "")
        assert "Enterprise Tool" in prompt or "rejected" in prompt.lower()

    def test_analyze_patterns_returns_suggestion(self) -> None:
        response = "Focus on open-source alternatives -- user rejected all proprietary tools."
        mock_client = _make_mock_client(response)
        state = DiscoveryState()
        state.add_round([
            DiscoveryCandidate(
                name="A", url="https://a.com", blurb="Proprietary",
                provenance="G2", suggested_tier=CompetitorTier.ESTABLISHED,
            ),
            DiscoveryCandidate(
                name="B", url="https://b.com", blurb="Open source",
                provenance="HN", suggested_tier=CompetitorTier.EMERGING,
            ),
        ])
        state.toggle(0)

        agent = DiscoveryAgent(
            llm_client=mock_client,
            domain="Developer Tools",
            seed_competitors=[],
        )

        suggestion = _run(agent.analyze_patterns(state))

        assert len(suggestion) > 0


def _run(coro):
    """Run async coroutine in tests."""
    import asyncio
    return asyncio.run(coro)
