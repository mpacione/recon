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
    content_blocks: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMClient:
    """Async wrapper around the Anthropic messages API."""

    client: Any
    model: str
    timeout: float = _DEFAULT_TIMEOUT
    total_input_tokens: int = field(default=0, init=False)
    total_output_tokens: int = field(default=0, init=False)
    call_count: int = field(default=0, init=False)

    @staticmethod
    def _serialize_value(value: Any) -> Any:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, dict):
            return {
                str(key): LLMClient._serialize_value(inner)
                for key, inner in value.items()
            }
        if isinstance(value, (list, tuple, set)):
            return [LLMClient._serialize_value(inner) for inner in value]
        if hasattr(value, "model_dump"):
            try:
                return LLMClient._serialize_value(value.model_dump())
            except Exception:
                pass
        if hasattr(value, "to_dict"):
            try:
                return LLMClient._serialize_value(value.to_dict())
            except Exception:
                pass
        if hasattr(value, "__dict__"):
            try:
                return {
                    key: LLMClient._serialize_value(inner)
                    for key, inner in vars(value).items()
                    if not key.startswith("_")
                }
            except Exception:
                pass
        return str(value)

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
        content_blocks: list[dict[str, Any]] = []
        for block in message.content:
            content_blocks.append(self._serialize_value(block))
            if hasattr(block, "text"):
                text += block.text

        response = LLMResponse(
            text=text,
            input_tokens=message.usage.input_tokens,
            output_tokens=message.usage.output_tokens,
            model=message.model,
            stop_reason=message.stop_reason,
            content_blocks=content_blocks,
            metadata={
                "id": getattr(message, "id", ""),
                "role": getattr(message, "role", ""),
                "type": getattr(message, "type", ""),
            },
        )

        self.total_input_tokens += response.input_tokens
        self.total_output_tokens += response.output_tokens
        self.call_count += 1

        return response
