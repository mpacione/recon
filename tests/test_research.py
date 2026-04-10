"""Tests for the research pipeline.

The research pipeline orchestrates section-by-section research across
all competitors. It batches by section (all competitors for section A,
then all competitors for section B) for consistency and verification.
"""

from pathlib import Path
from unittest.mock import AsyncMock

from recon.llm import LLMResponse
from recon.research import ResearchOrchestrator, ResearchPlan
from recon.schema import parse_schema


def _make_schema(sections: list[dict] | None = None) -> dict:
    return {
        "domain": "Developer Tools",
        "identity": {
            "company_name": "Acme Corp",
            "products": ["Acme IDE"],
            "decision_context": ["build-vs-buy"],
        },
        "rating_scales": {},
        "sections": sections or [
            {
                "key": "overview",
                "title": "Overview",
                "description": "High-level summary.",
                "allowed_formats": ["prose"],
                "preferred_format": "prose",
            },
            {
                "key": "pricing",
                "title": "Pricing",
                "description": "Pricing model.",
                "allowed_formats": ["key_value"],
                "preferred_format": "key_value",
            },
        ],
    }


def _mock_llm_client() -> AsyncMock:
    client = AsyncMock()
    client.complete = AsyncMock(
        return_value=LLMResponse(
            text="## Overview\nResearch content here.\n\n## Sources\n- [Docs](https://example.com) -- 2026-01-01",
            input_tokens=500,
            output_tokens=200,
            model="claude-sonnet-4-20250514",
            stop_reason="end_turn",
        ),
    )
    client.total_input_tokens = 0
    client.total_output_tokens = 0
    client.call_count = 0
    return client


class TestResearchPlan:
    def test_creates_plan_from_schema_and_competitors(self) -> None:
        schema = parse_schema(_make_schema())
        competitors = ["Alpha", "Beta", "Gamma"]

        plan = ResearchPlan.from_schema(schema=schema, competitors=competitors)

        assert len(plan.batches) == 2
        assert plan.batches[0].section_key == "overview"
        assert plan.batches[1].section_key == "pricing"

    def test_each_batch_has_all_competitors(self) -> None:
        schema = parse_schema(_make_schema())
        competitors = ["Alpha", "Beta"]

        plan = ResearchPlan.from_schema(schema=schema, competitors=competitors)

        for batch in plan.batches:
            assert set(batch.competitors) == {"Alpha", "Beta"}

    def test_total_tasks(self) -> None:
        schema = parse_schema(_make_schema())
        competitors = ["Alpha", "Beta", "Gamma"]

        plan = ResearchPlan.from_schema(schema=schema, competitors=competitors)

        assert plan.total_tasks == 6

    def test_plan_with_single_section(self) -> None:
        schema = parse_schema(_make_schema(sections=[{
            "key": "overview",
            "title": "Overview",
            "description": "Summary.",
            "allowed_formats": ["prose"],
            "preferred_format": "prose",
        }]))

        plan = ResearchPlan.from_schema(schema=schema, competitors=["Alpha"])

        assert len(plan.batches) == 1
        assert plan.total_tasks == 1

    def test_empty_competitors(self) -> None:
        schema = parse_schema(_make_schema())

        plan = ResearchPlan.from_schema(schema=schema, competitors=[])

        assert plan.total_tasks == 0


class TestResearchOrchestrator:
    async def test_executes_all_tasks(self, tmp_workspace: Path) -> None:
        from recon.workspace import Workspace

        ws = Workspace.open(tmp_workspace)
        ws.create_profile("Alpha")
        ws.create_profile("Beta")

        llm = _mock_llm_client()
        orchestrator = ResearchOrchestrator(
            workspace=ws,
            llm_client=llm,
            max_workers=2,
        )

        await orchestrator.research_all()

        assert llm.complete.call_count == 2

    async def test_writes_results_to_profiles(self, tmp_workspace: Path) -> None:
        from recon.workspace import Workspace

        ws = Workspace.open(tmp_workspace)
        ws.create_profile("Alpha")

        llm = _mock_llm_client()
        orchestrator = ResearchOrchestrator(
            workspace=ws,
            llm_client=llm,
            max_workers=1,
        )

        await orchestrator.research_all()

        profile = ws.read_profile("alpha")
        assert profile is not None
        assert "Research content here" in profile["_content"]

    async def test_marks_profile_researched(self, tmp_workspace: Path) -> None:
        from recon.workspace import Workspace

        ws = Workspace.open(tmp_workspace)
        ws.create_profile("Alpha")

        before = ws.read_profile("alpha")
        assert before["research_status"] == "scaffold"

        llm = _mock_llm_client()
        orchestrator = ResearchOrchestrator(
            workspace=ws,
            llm_client=llm,
            max_workers=1,
        )
        await orchestrator.research_all()

        after = ws.read_profile("alpha")
        assert after["research_status"] == "researched"

    async def test_passes_web_search_tool_by_default(self, tmp_workspace: Path) -> None:
        from recon.workspace import Workspace

        ws = Workspace.open(tmp_workspace)
        ws.create_profile("Alpha")

        llm = _mock_llm_client()
        orchestrator = ResearchOrchestrator(
            workspace=ws,
            llm_client=llm,
            max_workers=1,
        )
        await orchestrator.research_all()

        call_kwargs = llm.complete.call_args.kwargs
        assert "tools" in call_kwargs
        assert call_kwargs["tools"] is not None
        assert call_kwargs["tools"][0]["name"] == "web_search"

    async def test_web_search_can_be_disabled(self, tmp_workspace: Path) -> None:
        from recon.workspace import Workspace

        ws = Workspace.open(tmp_workspace)
        ws.create_profile("Alpha")

        llm = _mock_llm_client()
        orchestrator = ResearchOrchestrator(
            workspace=ws,
            llm_client=llm,
            max_workers=1,
            use_web_search=False,
        )
        await orchestrator.research_all()

        call_kwargs = llm.complete.call_args.kwargs
        assert call_kwargs.get("tools") is None

    async def test_research_all_filters_to_targets(self, tmp_workspace: Path) -> None:
        from recon.workspace import Workspace

        ws = Workspace.open(tmp_workspace)
        ws.create_profile("Alpha")
        ws.create_profile("Beta")
        ws.create_profile("Gamma")

        llm = _mock_llm_client()
        orchestrator = ResearchOrchestrator(
            workspace=ws,
            llm_client=llm,
            max_workers=1,
        )

        await orchestrator.research_all(targets=["Beta"])

        # Only 1 competitor * 1 section (minimal schema) = 1 call
        assert llm.complete.call_count == 1

        # Beta has research content, Alpha and Gamma do not
        beta = ws.read_profile("beta")
        alpha = ws.read_profile("alpha")
        gamma = ws.read_profile("gamma")
        assert beta["research_status"] == "researched"
        assert alpha["research_status"] == "scaffold"
        assert gamma["research_status"] == "scaffold"

    async def test_research_all_targets_case_insensitive(self, tmp_workspace: Path) -> None:
        from recon.workspace import Workspace

        ws = Workspace.open(tmp_workspace)
        ws.create_profile("Alpha")
        ws.create_profile("Beta")

        llm = _mock_llm_client()
        orchestrator = ResearchOrchestrator(
            workspace=ws,
            llm_client=llm,
            max_workers=1,
        )

        await orchestrator.research_all(targets=["alpha"])

        alpha = ws.read_profile("alpha")
        assert alpha["research_status"] == "researched"

    async def test_research_all_unknown_target_raises(self, tmp_workspace: Path) -> None:
        import pytest

        from recon.workspace import Workspace

        ws = Workspace.open(tmp_workspace)
        ws.create_profile("Alpha")

        llm = _mock_llm_client()
        orchestrator = ResearchOrchestrator(
            workspace=ws,
            llm_client=llm,
            max_workers=1,
        )

        with pytest.raises(ValueError, match="Unknown"):
            await orchestrator.research_all(targets=["Nonexistent"])

    async def test_batches_by_section(self, tmp_workspace: Path) -> None:
        schema_dict = _make_schema()
        schema_dict["sections"].append({
            "key": "capabilities",
            "title": "Capabilities",
            "description": "Product capabilities.",
            "allowed_formats": ["rated_table"],
            "preferred_format": "rated_table",
        })

        from recon.workspace import Workspace

        ws = Workspace.open(tmp_workspace)
        ws.create_profile("Alpha")

        call_order: list[str] = []
        original_complete = AsyncMock(
            return_value=LLMResponse(
                text="Content.\n\n## Sources\n- [S](https://s.com) -- 2026-01-01",
                input_tokens=100,
                output_tokens=50,
                model="claude-sonnet-4-20250514",
                stop_reason="end_turn",
            ),
        )

        async def tracking_complete(**kwargs):
            prompt = kwargs.get("user_prompt", "")
            if "Overview" in prompt:
                call_order.append("overview")
            elif "Pricing" in prompt:
                call_order.append("pricing")
            elif "Capabilities" in prompt:
                call_order.append("capabilities")
            return await original_complete(**kwargs)

        llm = _mock_llm_client()
        llm.complete = AsyncMock(side_effect=tracking_complete)

        orchestrator = ResearchOrchestrator(
            workspace=ws,
            llm_client=llm,
            max_workers=1,
            schema_override=parse_schema(schema_dict),
        )

        await orchestrator.research_all()

        assert call_order == ["overview", "pricing", "capabilities"]
