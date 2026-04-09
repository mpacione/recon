"""Tests for the deliver phase.

Distill: compress deep synthesis into executive 1-pagers.
Meta-synthesis: cross-theme executive summary.
"""

from unittest.mock import AsyncMock

from recon.deliver import Distiller, MetaSynthesizer
from recon.llm import LLMResponse
from recon.synthesis import PassResult, SynthesisMode, SynthesisResult


def _make_response(text: str) -> LLMResponse:
    return LLMResponse(
        text=text, input_tokens=200, output_tokens=100,
        model="claude-sonnet-4-20250514", stop_reason="end_turn",
    )


def _mock_llm(response_text: str) -> AsyncMock:
    client = AsyncMock()
    client.complete = AsyncMock(return_value=_make_response(response_text))
    client.total_input_tokens = 0
    client.total_output_tokens = 0
    client.call_count = 0
    return client


def _sample_synthesis() -> SynthesisResult:
    return SynthesisResult(
        theme="Agentic Shift",
        mode=SynthesisMode.DEEP,
        content="Full executive synthesis with strategic recommendations.",
        passes=[
            PassResult(role="strategist", content="Strategy analysis.", input_tokens=300, output_tokens=200),
            PassResult(role="devils_advocate", content="Counterpoints.", input_tokens=300, output_tokens=200),
            PassResult(role="gap_analyst", content="Gaps found.", input_tokens=300, output_tokens=200),
            PassResult(role="executive_integrator", content="Executive summary.", input_tokens=300, output_tokens=200),
        ],
        total_input_tokens=1200,
        total_output_tokens=800,
    )


class TestDistiller:
    async def test_distills_to_one_pager(self) -> None:
        llm = _mock_llm("# Agentic Shift - Executive Summary\n\nKey findings in one page.")

        distiller = Distiller(llm_client=llm)
        result = await distiller.distill(_sample_synthesis())

        assert result.theme == "Agentic Shift"
        assert "Executive Summary" in result.content or len(result.content) > 0
        assert llm.complete.call_count == 1

    async def test_includes_synthesis_content_in_prompt(self) -> None:
        llm = _mock_llm("Distilled.")

        distiller = Distiller(llm_client=llm)
        await distiller.distill(_sample_synthesis())

        call_kwargs = llm.complete.call_args[1]
        assert "Agentic Shift" in call_kwargs["user_prompt"]
        assert "executive" in call_kwargs["system_prompt"].lower() or "distill" in call_kwargs["system_prompt"].lower()

    async def test_distill_tracks_tokens(self) -> None:
        llm = _mock_llm("Summary.")

        distiller = Distiller(llm_client=llm)
        result = await distiller.distill(_sample_synthesis())

        assert result.input_tokens == 200
        assert result.output_tokens == 100


class TestMetaSynthesizer:
    async def test_creates_cross_theme_summary(self) -> None:
        llm = _mock_llm("# Cross-Theme Executive Summary\n\nThree themes converge.")

        meta = MetaSynthesizer(llm_client=llm)
        distilled_results = [
            {"theme": "Agentic Shift", "content": "Agents are taking over."},
            {"theme": "Platform Wars", "content": "Ecosystem lock-in intensifies."},
            {"theme": "Trust & Governance", "content": "Compliance is table stakes."},
        ]

        result = await meta.synthesize(distilled_results)

        assert "Cross-Theme" in result.content or len(result.content) > 0
        assert llm.complete.call_count == 1

    async def test_includes_all_themes_in_prompt(self) -> None:
        llm = _mock_llm("Summary.")

        meta = MetaSynthesizer(llm_client=llm)
        distilled_results = [
            {"theme": "Theme A", "content": "Content A."},
            {"theme": "Theme B", "content": "Content B."},
        ]

        await meta.synthesize(distilled_results)

        call_kwargs = llm.complete.call_args[1]
        assert "Theme A" in call_kwargs["user_prompt"]
        assert "Theme B" in call_kwargs["user_prompt"]
