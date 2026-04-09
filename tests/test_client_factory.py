"""Tests for the LLM client factory.

The factory validates API key presence and creates the async Anthropic
client + LLMClient wrapper used by all pipeline commands.
"""

from __future__ import annotations

import pytest

from recon.client_factory import ClientCreationError, create_llm_client


class TestClientFactory:
    def test_raises_without_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        with pytest.raises(ClientCreationError, match="ANTHROPIC_API_KEY"):
            create_llm_client()

    def test_creates_client_with_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key-12345")

        client = create_llm_client()

        assert client.model == "claude-sonnet-4-20250514"
        assert client.call_count == 0

    def test_accepts_custom_model(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key-12345")

        client = create_llm_client(model="claude-opus-4-20250514")

        assert client.model == "claude-opus-4-20250514"

    def test_error_message_is_actionable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        with pytest.raises(ClientCreationError) as exc_info:
            create_llm_client()

        error_msg = str(exc_info.value)
        assert "ANTHROPIC_API_KEY" in error_msg
        assert "export" in error_msg.lower() or "set" in error_msg.lower()
