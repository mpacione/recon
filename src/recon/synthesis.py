"""Synthesis pipeline for recon.

Single-pass: one LLM call to generate theme analysis from retrieved chunks.
Deep 4-pass: strategist -> devil's advocate -> gap analyst -> executive integrator.
Each pass builds on the previous, creating a multi-perspective analysis.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from recon.llm import LLMClient  # noqa: TCH001
from recon.logging import get_logger

_log = get_logger(__name__)


class SynthesisMode(StrEnum):
    SINGLE = "single"
    DEEP = "deep"


@dataclass(frozen=True)
class PassResult:
    role: str
    content: str
    input_tokens: int
    output_tokens: int


@dataclass(frozen=True)
class SynthesisResult:
    theme: str
    mode: SynthesisMode
    content: str
    passes: list[PassResult]
    total_input_tokens: int
    total_output_tokens: int


_DEEP_PASS_CONFIGS: list[tuple[str, str]] = [
    (
        "strategist",
        """You are a competitive strategy analyst. Analyze the competitive landscape
for the given theme. Identify patterns, trends, and strategic implications.
Focus on market positioning, competitive dynamics, and strategic opportunities.""",
    ),
    (
        "devils_advocate",
        """You are a devil's advocate analyst. Challenge the strategist's conclusions.
Identify blind spots, alternative interpretations, and risks.
Question assumptions and highlight counterarguments.""",
    ),
    (
        "gap_analyst",
        """You are a gap analysis specialist. Based on the strategist's analysis and
the devil's advocate's challenges, identify specific gaps and opportunities.
Where are the unmet needs? What are competitors missing?""",
    ),
    (
        "executive_integrator",
        """You are an executive integrator. Synthesize all previous analyses into a
clear, actionable executive summary. Balance the strategist's insights with
the devil's advocate's challenges and the gap analyst's findings.
Provide concrete recommendations.""",
    ),
]


def _format_chunks_for_prompt(chunks: list[dict[str, Any]]) -> str:
    """Format retrieved chunks into a context block for the LLM."""
    parts: list[str] = []
    for chunk in chunks:
        meta = chunk.get("metadata", {})
        name = meta.get("name", "Unknown")
        section = meta.get("section", "")
        text = chunk.get("text", "")
        parts.append(f"[{name} - {section}]\n{text}")
    return "\n\n---\n\n".join(parts)


class SynthesisEngine:
    """Generates theme analyses from retrieved chunks."""

    def __init__(self, llm_client: LLMClient) -> None:
        self._llm = llm_client

    async def synthesize(
        self,
        theme: str,
        chunks: list[dict[str, Any]],
        mode: SynthesisMode = SynthesisMode.SINGLE,
    ) -> SynthesisResult:
        """Synthesize theme analysis from retrieved chunks."""
        _log.info(
            "synthesis start theme=%r mode=%s chunks=%d",
            theme,
            mode.value,
            len(chunks),
        )
        if mode == SynthesisMode.SINGLE:
            result = await self._single_pass(theme, chunks)
        else:
            result = await self._deep_pass(theme, chunks)
        _log.info(
            "synthesis complete theme=%r passes=%d in=%d out=%d",
            theme,
            len(result.passes),
            result.total_input_tokens,
            result.total_output_tokens,
        )
        return result

    async def _single_pass(self, theme: str, chunks: list[dict[str, Any]]) -> SynthesisResult:
        """Single-pass synthesis."""
        context = _format_chunks_for_prompt(chunks)
        system_prompt = (
            "You are a competitive intelligence analyst. "
            "Synthesize the provided research into a coherent theme analysis."
        )
        user_prompt = (
            f"Analyze the theme: **{theme}**\n\n"
            f"Research context:\n\n{context}"
        )

        response = await self._llm.complete(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

        pass_result = PassResult(
            role="analyst",
            content=response.text,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
        )

        return SynthesisResult(
            theme=theme,
            mode=SynthesisMode.SINGLE,
            content=response.text,
            passes=[pass_result],
            total_input_tokens=response.input_tokens,
            total_output_tokens=response.output_tokens,
        )

    async def _deep_pass(self, theme: str, chunks: list[dict[str, Any]]) -> SynthesisResult:
        """Deep 4-pass synthesis."""
        context = _format_chunks_for_prompt(chunks)
        passes: list[PassResult] = []
        total_input = 0
        total_output = 0
        previous_outputs: list[str] = []

        for role, system_prompt in _DEEP_PASS_CONFIGS:
            user_prompt_parts = [f"Theme: **{theme}**\n\nResearch context:\n\n{context}"]

            for i, prev in enumerate(previous_outputs):
                prev_role = _DEEP_PASS_CONFIGS[i][0]
                user_prompt_parts.append(f"\n\n--- {prev_role} analysis ---\n{prev}")

            response = await self._llm.complete(
                system_prompt=system_prompt,
                user_prompt="\n".join(user_prompt_parts),
            )

            pass_result = PassResult(
                role=role,
                content=response.text,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
            )
            passes.append(pass_result)
            previous_outputs.append(response.text)
            total_input += response.input_tokens
            total_output += response.output_tokens

        return SynthesisResult(
            theme=theme,
            mode=SynthesisMode.DEEP,
            content=passes[-1].content,
            passes=passes,
            total_input_tokens=total_input,
            total_output_tokens=total_output,
        )
