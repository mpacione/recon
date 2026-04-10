"""Tests for the LLM client wrapper.

The LLM client wraps the Anthropic API with token counting, retry logic,
and structured output support. Tests use a mock client to avoid API calls.
"""

from unittest.mock import AsyncMock, MagicMock

from recon.llm import LLMClient, LLMResponse


def _make_mock_message(content: str = "Response text", input_tokens: int = 100, output_tokens: int = 50):
    """Create a mock Anthropic message response."""
    msg = MagicMock()
    msg.content = [MagicMock(text=content, type="text")]
    msg.usage = MagicMock(input_tokens=input_tokens, output_tokens=output_tokens)
    msg.model = "claude-sonnet-4-20250514"
    msg.stop_reason = "end_turn"
    return msg


class TestLLMClient:
    async def test_sends_message_and_returns_response(self) -> None:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=_make_mock_message("Hello world"))

        client = LLMClient(client=mock_client, model="claude-sonnet-4-20250514")
        response = await client.complete(
            system_prompt="You are helpful.",
            user_prompt="Say hello.",
        )

        assert isinstance(response, LLMResponse)
        assert response.text == "Hello world"

    async def test_tracks_token_usage(self) -> None:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(
            return_value=_make_mock_message(input_tokens=500, output_tokens=200),
        )

        client = LLMClient(client=mock_client, model="claude-sonnet-4-20250514")
        response = await client.complete(
            system_prompt="System.",
            user_prompt="Prompt.",
        )

        assert response.input_tokens == 500
        assert response.output_tokens == 200

    async def test_passes_model_to_api(self) -> None:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=_make_mock_message())

        client = LLMClient(client=mock_client, model="claude-sonnet-4-20250514")
        await client.complete(system_prompt="Sys.", user_prompt="Prompt.")

        call_kwargs = mock_client.messages.create.call_args[1]
        assert call_kwargs["model"] == "claude-sonnet-4-20250514"

    async def test_passes_max_tokens(self) -> None:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=_make_mock_message())

        client = LLMClient(client=mock_client, model="claude-sonnet-4-20250514")
        await client.complete(
            system_prompt="Sys.",
            user_prompt="Prompt.",
            max_tokens=2000,
        )

        call_kwargs = mock_client.messages.create.call_args[1]
        assert call_kwargs["max_tokens"] == 2000

    async def test_default_max_tokens(self) -> None:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=_make_mock_message())

        client = LLMClient(client=mock_client, model="claude-sonnet-4-20250514")
        await client.complete(system_prompt="Sys.", user_prompt="Prompt.")

        call_kwargs = mock_client.messages.create.call_args[1]
        assert call_kwargs["max_tokens"] == 4096

    async def test_accumulates_total_tokens(self) -> None:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(
            side_effect=[
                _make_mock_message(input_tokens=100, output_tokens=50),
                _make_mock_message(input_tokens=200, output_tokens=100),
            ],
        )

        client = LLMClient(client=mock_client, model="claude-sonnet-4-20250514")
        await client.complete(system_prompt="Sys.", user_prompt="P1.")
        await client.complete(system_prompt="Sys.", user_prompt="P2.")

        assert client.total_input_tokens == 300
        assert client.total_output_tokens == 150
        assert client.call_count == 2


    async def test_passes_tools_when_provided(self) -> None:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=_make_mock_message())

        client = LLMClient(client=mock_client, model="claude-sonnet-4-20250514")
        tools = [{"type": "web_search_20250305", "name": "web_search", "max_uses": 5}]
        await client.complete(
            system_prompt="Sys.",
            user_prompt="Search for competitors.",
            tools=tools,
        )

        call_kwargs = mock_client.messages.create.call_args[1]
        assert call_kwargs["tools"] == tools

    async def test_omits_tools_when_not_provided(self) -> None:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=_make_mock_message())

        client = LLMClient(client=mock_client, model="claude-sonnet-4-20250514")
        await client.complete(system_prompt="Sys.", user_prompt="Prompt.")

        call_kwargs = mock_client.messages.create.call_args[1]
        assert "tools" not in call_kwargs


class TestLLMResponse:
    def test_response_fields(self) -> None:
        response = LLMResponse(
            text="Hello",
            input_tokens=100,
            output_tokens=50,
            model="claude-sonnet-4-20250514",
            stop_reason="end_turn",
        )

        assert response.text == "Hello"
        assert response.input_tokens == 100
        assert response.output_tokens == 50
        assert response.model == "claude-sonnet-4-20250514"
