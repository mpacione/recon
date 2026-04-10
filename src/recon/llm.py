"""LLM client wrapper for recon.

Wraps the Anthropic async API with token counting and usage tracking.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

_DEFAULT_TIMEOUT = 120.0


@dataclass(frozen=True)
class LLMResponse:
    text: str
    input_tokens: int
    output_tokens: int
    model: str
    stop_reason: str


@dataclass
class LLMClient:
    """Async wrapper around the Anthropic messages API."""

    client: Any
    model: str
    timeout: float = _DEFAULT_TIMEOUT
    total_input_tokens: int = field(default=0, init=False)
    total_output_tokens: int = field(default=0, init=False)
    call_count: int = field(default=0, init=False)

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 4096,
        tools: list[dict[str, Any]] | None = None,
        timeout: float | None = None,
    ) -> LLMResponse:
        """Send a message and return a structured response."""
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        }
        if tools is not None:
            kwargs["tools"] = tools

        effective_timeout = timeout if timeout is not None else self.timeout
        message = await asyncio.wait_for(
            self.client.messages.create(**kwargs),
            timeout=effective_timeout,
        )

        text = ""
        for block in message.content:
            if hasattr(block, "text"):
                text += block.text

        response = LLMResponse(
            text=text,
            input_tokens=message.usage.input_tokens,
            output_tokens=message.usage.output_tokens,
            model=message.model,
            stop_reason=message.stop_reason,
        )

        self.total_input_tokens += response.input_tokens
        self.total_output_tokens += response.output_tokens
        self.call_count += 1

        return response
