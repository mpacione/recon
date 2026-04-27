"""Tests for dynamic schema design.

Phase (a): LLM selects from a predefined pool of ~15 sections.
Phase (c): Custom section generation from user prompt.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

from recon.llm import LLMResponse


def _mock_llm(response_text: str) -> AsyncMock:
    client = AsyncMock()
    client.complete = AsyncMock(
        return_value=LLMResponse(
            text=response_text,
            input_tokens=100,
            output_tokens=50,
            model="claude-sonnet-4-20250514",
            stop_reason="end_turn",
        ),
    )
    return client


class TestSectionPool:
    def test_pool_has_at_least_10_sections(self) -> None:
        from recon.schema_designer import SECTION_POOL

        assert len(SECTION_POOL) >= 10

    def test_each_section_has_required_fields(self) -> None:
        from recon.schema_designer import SECTION_POOL

        for section in SECTION_POOL:
            assert "key" in section
            assert "title" in section
            assert "description" in section
            assert "when_relevant" in section


class TestDesignSections:
    async def test_returns_selected_sections(self) -> None:
        from recon.schema_designer import design_sections

        llm = _mock_llm("overview, pricing, customer_segments, strategic_notes")

        sections = await design_sections(
            description="Bambu Lab makes 3D printers",
            competitors=["Prusa", "Creality"],
            llm_client=llm,
        )

        assert len(sections) >= 1
        keys = [s["key"] for s in sections]
        assert "overview" in keys

    async def test_always_includes_overview(self) -> None:
        from recon.schema_designer import design_sections

        llm = _mock_llm("pricing")

        sections = await design_sections(
            description="SaaS company",
            competitors=["Competitor A"],
            llm_client=llm,
        )

        keys = [s["key"] for s in sections]
        assert "overview" in keys

    async def test_fallback_on_llm_error(self) -> None:
        from recon.schema_designer import design_sections

        llm = AsyncMock()
        llm.complete = AsyncMock(side_effect=RuntimeError("API down"))

        sections = await design_sections(
            description="Some company",
            competitors=["A"],
            llm_client=llm,
        )

        assert len(sections) >= 3
        keys = [s["key"] for s in sections]
        assert "overview" in keys


class TestCreateCustomSection:
    async def test_creates_section_from_description(self) -> None:
        from recon.schema_designer import create_custom_section

        llm = _mock_llm(
            "key: firmware_strategy\n"
            "title: Open Source vs Proprietary Firmware\n"
            "description: Analysis of firmware openness strategy"
        )

        section = await create_custom_section(
            description="Compare open-source vs proprietary firmware approaches",
            llm_client=llm,
        )

        assert section["key"]
        assert section["title"]
        assert section["description"]
        assert section["selected"] is True

    async def test_fallback_on_llm_error(self) -> None:
        from recon.schema_designer import create_custom_section

        llm = AsyncMock()
        llm.complete = AsyncMock(side_effect=RuntimeError("API down"))

        section = await create_custom_section(
            description="Compare firmware approaches",
            llm_client=llm,
        )

        assert section["key"]
        assert section["title"]
        assert section["selected"] is True
