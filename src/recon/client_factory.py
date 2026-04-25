"""LLM client factory for recon.

Creates the async Anthropic client and LLMClient wrapper from environment
configuration. Used by all CLI commands that need API access.
"""

from __future__ import annotations

import os

from recon.api_keys import normalize_api_key
from recon.llm import LLMClient

DEFAULT_MODEL = "claude-sonnet-4-20250514"


class ClientCreationError(Exception):
    """Raised when the LLM client cannot be created."""


def create_llm_client(model: str = DEFAULT_MODEL, api_key: str | None = None) -> LLMClient:
    """Create an LLMClient from environment configuration.

    Requires ANTHROPIC_API_KEY to be set. Raises ClientCreationError
    with actionable guidance if missing.
    """
    resolved_api_key = normalize_api_key(api_key or os.environ.get("ANTHROPIC_API_KEY", ""))
    if not resolved_api_key:
        msg = (
            "ANTHROPIC_API_KEY not set. "
            "Set it with: export ANTHROPIC_API_KEY=sk-your-key"
        )
        raise ClientCreationError(msg)

    import anthropic

    async_client = anthropic.AsyncAnthropic(api_key=resolved_api_key)
    return LLMClient(client=async_client, model=model)
