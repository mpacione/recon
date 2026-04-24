"""A deterministic fake LLM client for the web prototype.

The web UI's "Start research" button drives a real pipeline so users
can see the run screen actually stream events. We do NOT want that
click to cost real money while the UX is still settling — so the web
endpoint currently always injects this fake client.

The fake mirrors :class:`recon.llm.LLMClient` closely enough that
every call site in :mod:`recon.pipeline` is satisfied:

- ``complete(system_prompt, user_prompt, ...)`` → :class:`LLMResponse`
- ``total_input_tokens`` / ``total_output_tokens`` counters
- tiny artificial latency so SSE subscribers see events trickle in

When the web endpoint grows a "real run" toggle, we'll gate this
behind a flag and fall back to :func:`recon.client_factory.create_llm_client`.
Until then, a dedicated module keeps the mock out of production code
paths (no AsyncMock from unittest.mock leaking into runtime).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from recon.llm import LLMResponse

_DEFAULT_LATENCY_SECONDS = 0.05


@dataclass
class FakeLLMClient:
    """LLMClient-shaped stand-in that returns deterministic output.

    The shape of the generated text is chosen so downstream parsers
    (research → synthesis → deliver) all accept it: a top-level H2,
    a short paragraph, and a bulleted list of fake "claims" so the
    enrichment stage has something to index.
    """

    model: str = "fake-claude-sonnet"
    latency_seconds: float = _DEFAULT_LATENCY_SECONDS
    total_input_tokens: int = field(default=0, init=False)
    total_output_tokens: int = field(default=0, init=False)
    call_count: int = field(default=0, init=False)

    async def complete(
        self,
        system_prompt: str,  # noqa: ARG002 -- matches real LLMClient signature
        user_prompt: str,
        max_tokens: int = 4096,  # noqa: ARG002 -- ignored by fake
        tools: list[dict[str, Any]] | None = None,  # noqa: ARG002 -- ignored by fake
        timeout: float | None = None,  # noqa: ARG002 -- ignored by fake
    ) -> LLMResponse:
        """Return a deterministic :class:`LLMResponse`.

        We sleep briefly so the run screen's SSE subscription gets a
        chance to render each ``SectionStarted`` / ``SectionResearched``
        pair in sequence rather than in a single flush.
        """
        if self.latency_seconds > 0:
            await asyncio.sleep(self.latency_seconds)

        # Echo the first ~40 chars of the user prompt into the body so
        # different sections produce visibly different output, even in
        # fake mode. Helps debug streaming rendering.
        hint = (user_prompt or "").strip().splitlines()[0:1]
        hint_text = hint[0][:80] if hint else "section"

        text = (
            "## Overview\n\n"
            f"Placeholder research output for: {hint_text}\n\n"
            "### Key points\n\n"
            "- Fact one about this section.\n"
            "- Fact two, with a source at https://example.com/one.\n"
            "- Fact three tying back to the competitor's positioning.\n"
        )

        input_tokens = max(1, len(user_prompt) // 4)
        output_tokens = max(1, len(text) // 4)
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.call_count += 1

        return LLMResponse(
            text=text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model=self.model,
            stop_reason="end_turn",
        )
