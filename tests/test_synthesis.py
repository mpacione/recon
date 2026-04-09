"""Tests for the synthesis pipeline.

Single-pass synthesis: one LLM call to generate theme analysis.
Deep 4-pass synthesis: strategist, devil's advocate, gap analyst,
executive integrator -- each builds on the previous pass.
"""

from unittest.mock import AsyncMock

from recon.llm import LLMResponse
from recon.synthesis import SynthesisEngine, SynthesisMode


def _make_response(text: str) -> LLMResponse:
    return LLMResponse(
        text=text,
        input_tokens=300,
        output_tokens=200,
        model="claude-sonnet-4-20250514",
        stop_reason="end_turn",
    )


def _mock_llm(responses: list[str]) -> AsyncMock:
    client = AsyncMock()
    client.complete = AsyncMock(
        side_effect=[_make_response(t) for t in responses],
    )
    client.total_input_tokens = 0
    client.total_output_tokens = 0
    client.call_count = 0
    return client


SAMPLE_CHUNKS = [
    {"text": "Alpha has strong AI code generation capabilities.", "metadata": {"name": "Alpha", "section": "Overview"}},
    {"text": "Beta focuses on enterprise code review.", "metadata": {"name": "Beta", "section": "Overview"}},
    {"text": "Gamma offers real-time collaboration features.", "metadata": {"name": "Gamma", "section": "Capabilities"}},
]


class TestSinglePassSynthesis:
    async def test_generates_analysis(self) -> None:
        llm = _mock_llm(["## Theme Analysis\n\nAI tools are converging on code generation."])

        engine = SynthesisEngine(llm_client=llm)
        result = await engine.synthesize(
            theme="AI Code Generation",
            chunks=SAMPLE_CHUNKS,
            mode=SynthesisMode.SINGLE,
        )

        assert "AI" in result.content or "code generation" in result.content.lower()
        assert llm.complete.call_count == 1

    async def test_includes_theme_in_prompt(self) -> None:
        llm = _mock_llm(["Analysis."])

        engine = SynthesisEngine(llm_client=llm)
        await engine.synthesize(
            theme="Platform Wars",
            chunks=SAMPLE_CHUNKS,
            mode=SynthesisMode.SINGLE,
        )

        call_kwargs = llm.complete.call_args[1]
        assert "Platform Wars" in call_kwargs["user_prompt"]

    async def test_includes_chunk_content_in_prompt(self) -> None:
        llm = _mock_llm(["Analysis."])

        engine = SynthesisEngine(llm_client=llm)
        await engine.synthesize(
            theme="Test",
            chunks=SAMPLE_CHUNKS,
            mode=SynthesisMode.SINGLE,
        )

        call_kwargs = llm.complete.call_args[1]
        assert "Alpha" in call_kwargs["user_prompt"]
        assert "code generation" in call_kwargs["user_prompt"].lower()


class TestDeepSynthesis:
    async def test_calls_four_passes(self) -> None:
        llm = _mock_llm([
            "Strategist analysis.",
            "Devil's advocate counterpoints.",
            "Gap analysis findings.",
            "Executive summary integrating all perspectives.",
        ])

        engine = SynthesisEngine(llm_client=llm)
        result = await engine.synthesize(
            theme="Agentic Shift",
            chunks=SAMPLE_CHUNKS,
            mode=SynthesisMode.DEEP,
        )

        assert llm.complete.call_count == 4
        assert "Executive summary" in result.content or len(result.content) > 0

    async def test_each_pass_builds_on_previous(self) -> None:
        call_prompts: list[str] = []

        async def track_complete(**kwargs):
            call_prompts.append(kwargs.get("user_prompt", ""))
            return _make_response(f"Pass {len(call_prompts)} output.")

        llm = _mock_llm([])
        llm.complete = AsyncMock(side_effect=track_complete)

        engine = SynthesisEngine(llm_client=llm)
        await engine.synthesize(
            theme="Test",
            chunks=SAMPLE_CHUNKS,
            mode=SynthesisMode.DEEP,
        )

        assert len(call_prompts) == 4
        assert "Pass 1 output" in call_prompts[1]
        assert "Pass 2 output" in call_prompts[2]
        assert "Pass 3 output" in call_prompts[3]

    async def test_result_includes_all_passes(self) -> None:
        llm = _mock_llm([
            "Strategist findings.",
            "Counterpoints raised.",
            "Gaps identified.",
            "Final executive synthesis.",
        ])

        engine = SynthesisEngine(llm_client=llm)
        result = await engine.synthesize(
            theme="Test",
            chunks=SAMPLE_CHUNKS,
            mode=SynthesisMode.DEEP,
        )

        assert len(result.passes) == 4
        assert result.passes[0].role == "strategist"
        assert result.passes[1].role == "devils_advocate"
        assert result.passes[2].role == "gap_analyst"
        assert result.passes[3].role == "executive_integrator"


class TestSynthesisResult:
    async def test_single_pass_has_no_sub_passes(self) -> None:
        llm = _mock_llm(["Result."])

        engine = SynthesisEngine(llm_client=llm)
        result = await engine.synthesize(
            theme="Test",
            chunks=SAMPLE_CHUNKS,
            mode=SynthesisMode.SINGLE,
        )

        assert len(result.passes) == 1
        assert result.passes[0].role == "analyst"

    async def test_tracks_total_tokens(self) -> None:
        llm = _mock_llm(["Result."])

        engine = SynthesisEngine(llm_client=llm)
        result = await engine.synthesize(
            theme="Test",
            chunks=SAMPLE_CHUNKS,
            mode=SynthesisMode.SINGLE,
        )

        assert result.total_input_tokens == 300
        assert result.total_output_tokens == 200
