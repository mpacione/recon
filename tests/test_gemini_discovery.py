"""Tests for the Gemini-based discovery agent.

Uses Google's Gemini API with grounding (Google Search) as an
alternative to Anthropic's web_search tool for competitor discovery.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from recon.discovery import CompetitorTier, DiscoveryCandidate, DiscoveryState


class TestGeminiDiscoveryAgent:
    async def test_returns_discovery_candidates(self) -> None:
        from recon.gemini_discovery import GeminiDiscoveryAgent

        mock_response = MagicMock()
        mock_response.text = '''{
            "candidates": [
                {
                    "name": "Cursor",
                    "url": "https://cursor.sh/",
                    "blurb": "AI-first code editor",
                    "provenance": "Google Search",
                    "suggested_tier": "established"
                },
                {
                    "name": "Windsurf",
                    "url": "https://windsurf.com/",
                    "blurb": "AI coding IDE",
                    "provenance": "Google Search",
                    "suggested_tier": "emerging"
                }
            ]
        }'''

        with patch("recon.gemini_discovery.genai") as mock_genai:
            mock_client = MagicMock()
            mock_genai.Client.return_value = mock_client
            mock_client.models.generate_content.return_value = mock_response

            agent = GeminiDiscoveryAgent(
                api_key="AIza-test",
                domain="AI coding tools",
            )
            candidates = await agent.search()

        assert len(candidates) == 2
        assert candidates[0].name == "Cursor"
        assert isinstance(candidates[0], DiscoveryCandidate)

    async def test_handles_empty_response(self) -> None:
        from recon.gemini_discovery import GeminiDiscoveryAgent

        mock_response = MagicMock()
        mock_response.text = "I couldn't find any competitors."

        with patch("recon.gemini_discovery.genai") as mock_genai:
            mock_client = MagicMock()
            mock_genai.Client.return_value = mock_client
            mock_client.models.generate_content.return_value = mock_response

            agent = GeminiDiscoveryAgent(
                api_key="AIza-test",
                domain="obscure niche",
            )
            candidates = await agent.search()

        assert candidates == []

    async def test_passes_existing_state_to_prompt(self) -> None:
        from recon.gemini_discovery import GeminiDiscoveryAgent

        mock_response = MagicMock()
        mock_response.text = '{"candidates": []}'

        state = DiscoveryState()
        state.add_round([
            DiscoveryCandidate(
                name="Cursor", url="https://cursor.sh/", blurb="",
                provenance="", suggested_tier=CompetitorTier.ESTABLISHED,
            ),
        ])

        with patch("recon.gemini_discovery.genai") as mock_genai:
            mock_client = MagicMock()
            mock_genai.Client.return_value = mock_client
            mock_client.models.generate_content.return_value = mock_response

            agent = GeminiDiscoveryAgent(
                api_key="AIza-test",
                domain="AI coding tools",
            )
            await agent.search(state=state)

        call_args = mock_client.models.generate_content.call_args
        prompt = call_args.kwargs.get("contents", "")
        assert "Cursor" in prompt
        assert "Already seen" in prompt

    async def test_uses_google_search_grounding(self) -> None:
        from recon.gemini_discovery import GeminiDiscoveryAgent

        mock_response = MagicMock()
        mock_response.text = '{"candidates": []}'

        with patch("recon.gemini_discovery.genai") as mock_genai:
            mock_client = MagicMock()
            mock_genai.Client.return_value = mock_client
            mock_client.models.generate_content.return_value = mock_response

            agent = GeminiDiscoveryAgent(
                api_key="AIza-test",
                domain="AI coding tools",
            )
            await agent.search()

        call_args = mock_client.models.generate_content.call_args
        config = call_args.kwargs.get("config")
        assert config is not None
        assert config.tools is not None
