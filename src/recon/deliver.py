"""Deliver phase for recon.

Distill: compress deep synthesis into executive 1-pagers.
Meta-synthesis: cross-theme executive summary from all distilled themes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from recon.llm import LLMClient  # noqa: TCH001
from recon.synthesis import SynthesisResult  # noqa: TCH001


@dataclass(frozen=True)
class DistilledResult:
    theme: str
    content: str
    input_tokens: int
    output_tokens: int


@dataclass(frozen=True)
class MetaSynthesisResult:
    content: str
    input_tokens: int
    output_tokens: int
    theme_count: int


class Distiller:
    """Compresses deep synthesis into executive 1-pagers."""

    def __init__(self, llm_client: LLMClient) -> None:
        self._llm = llm_client

    async def distill(self, synthesis: SynthesisResult) -> DistilledResult:
        """Distill a deep synthesis into a concise executive summary."""
        system_prompt = (
            "You are an executive communications specialist. Distill the following "
            "multi-perspective competitive analysis into a concise 1-page executive "
            "summary. Include: key findings, strategic implications, recommended actions. "
            "Be direct and actionable. No filler."
        )

        pass_content = "\n\n".join(
            f"### {p.role}\n{p.content}" for p in synthesis.passes
        )

        user_prompt = (
            f"Theme: **{synthesis.theme}**\n\n"
            f"Full analysis:\n\n{pass_content}"
        )

        response = await self._llm.complete(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

        return DistilledResult(
            theme=synthesis.theme,
            content=response.text,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
        )


class MetaSynthesizer:
    """Generates cross-theme executive summary from all distilled themes."""

    def __init__(self, llm_client: LLMClient) -> None:
        self._llm = llm_client

    async def synthesize(self, distilled_results: list[dict[str, Any]]) -> MetaSynthesisResult:
        """Create a cross-theme executive summary."""
        system_prompt = (
            "You are a senior strategy advisor. Synthesize the following theme-level "
            "executive summaries into a single cross-cutting analysis. Identify: "
            "convergent trends, strategic tensions, priority actions, and open questions. "
            "Write for a leadership audience making investment decisions."
        )

        theme_blocks = "\n\n".join(
            f"## {r['theme']}\n{r['content']}" for r in distilled_results
        )

        user_prompt = (
            f"Cross-theme synthesis across {len(distilled_results)} themes:\n\n"
            f"{theme_blocks}"
        )

        response = await self._llm.complete(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

        return MetaSynthesisResult(
            content=response.text,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            theme_count=len(distilled_results),
        )
