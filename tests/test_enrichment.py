"""Tests for the enrichment pipeline.

Three enrichment passes:
- Cleanup: format alignment, schema compliance
- Sentiment: developer quotes, traction signals, talking points
- Strategic: platform/ecosystem, trust/governance, workflow, time-to-value
"""

from pathlib import Path
from unittest.mock import AsyncMock

from recon.enrichment import EnrichmentOrchestrator, EnrichmentPass
from recon.llm import LLMResponse


def _make_response(text: str) -> LLMResponse:
    return LLMResponse(
        text=text,
        input_tokens=200,
        output_tokens=100,
        model="claude-sonnet-4-20250514",
        stop_reason="end_turn",
    )


def _mock_llm(response_text: str = "Enriched content.") -> AsyncMock:
    client = AsyncMock()
    client.complete = AsyncMock(return_value=_make_response(response_text))
    client.total_input_tokens = 0
    client.total_output_tokens = 0
    client.call_count = 0
    return client


class TestEnrichmentPass:
    def test_cleanup_pass(self) -> None:
        ep = EnrichmentPass.CLEANUP
        assert ep.value == "cleanup"

    def test_sentiment_pass(self) -> None:
        ep = EnrichmentPass.SENTIMENT
        assert ep.value == "sentiment"

    def test_strategic_pass(self) -> None:
        ep = EnrichmentPass.STRATEGIC
        assert ep.value == "strategic"


class TestEnrichmentOrchestrator:
    async def test_enriches_single_profile(self, tmp_workspace: Path) -> None:
        from recon.workspace import Workspace

        ws = Workspace.open(tmp_workspace)
        profile_path = ws.create_profile("Alpha")
        import frontmatter as fm

        post = fm.load(str(profile_path))
        post.content = "## Overview\nExisting research content.\n"
        profile_path.write_text(fm.dumps(post))

        llm = _mock_llm("Cleaned and formatted content.")

        orchestrator = EnrichmentOrchestrator(
            workspace=ws,
            llm_client=llm,
            enrichment_pass=EnrichmentPass.CLEANUP,
            max_workers=1,
        )

        results = await orchestrator.enrich_all()

        assert len(results) == 1
        assert results[0]["competitor"] == "Alpha"
        assert llm.complete.call_count == 1

    async def test_enriches_multiple_profiles(self, tmp_workspace: Path) -> None:
        from recon.workspace import Workspace

        ws = Workspace.open(tmp_workspace)
        for name in ["Alpha", "Beta", "Gamma"]:
            path = ws.create_profile(name)
            import frontmatter as fm

            post = fm.load(str(path))
            post.content = "## Overview\nContent.\n"
            path.write_text(fm.dumps(post))

        llm = _mock_llm("Enriched.")

        orchestrator = EnrichmentOrchestrator(
            workspace=ws,
            llm_client=llm,
            enrichment_pass=EnrichmentPass.SENTIMENT,
            max_workers=2,
        )

        results = await orchestrator.enrich_all()

        assert len(results) == 3
        assert llm.complete.call_count == 3

    async def test_skips_empty_profiles(self, tmp_workspace: Path) -> None:
        from recon.workspace import Workspace

        ws = Workspace.open(tmp_workspace)
        ws.create_profile("EmptyProfile")

        llm = _mock_llm()

        orchestrator = EnrichmentOrchestrator(
            workspace=ws,
            llm_client=llm,
            enrichment_pass=EnrichmentPass.CLEANUP,
            max_workers=1,
        )

        results = await orchestrator.enrich_all()

        assert len(results) == 0
        assert llm.complete.call_count == 0

    async def test_enrich_all_filters_to_targets(self, tmp_workspace: Path) -> None:
        from recon.workspace import Workspace

        ws = Workspace.open(tmp_workspace)
        for name in ["Alpha", "Beta", "Gamma"]:
            path = ws.create_profile(name)
            import frontmatter as fm

            post = fm.load(str(path))
            post.content = "## Overview\nContent.\n"
            path.write_text(fm.dumps(post))

        llm = _mock_llm("Enriched.")

        orchestrator = EnrichmentOrchestrator(
            workspace=ws,
            llm_client=llm,
            enrichment_pass=EnrichmentPass.SENTIMENT,
            max_workers=1,
        )

        results = await orchestrator.enrich_all(targets=["Beta"])

        assert len(results) == 1
        assert results[0]["competitor"] == "Beta"
        assert llm.complete.call_count == 1

    async def test_enrich_all_unknown_target_raises(self, tmp_workspace: Path) -> None:
        import pytest

        from recon.workspace import Workspace

        ws = Workspace.open(tmp_workspace)
        path = ws.create_profile("Alpha")
        import frontmatter as fm

        post = fm.load(str(path))
        post.content = "## Overview\nContent.\n"
        path.write_text(fm.dumps(post))

        llm = _mock_llm()

        orchestrator = EnrichmentOrchestrator(
            workspace=ws,
            llm_client=llm,
            enrichment_pass=EnrichmentPass.CLEANUP,
            max_workers=1,
        )

        with pytest.raises(ValueError, match="Unknown"):
            await orchestrator.enrich_all(targets=["Nonexistent"])

    async def test_cleanup_prompt_mentions_format(self, tmp_workspace: Path) -> None:
        from recon.workspace import Workspace

        ws = Workspace.open(tmp_workspace)
        path = ws.create_profile("Alpha")
        import frontmatter as fm

        post = fm.load(str(path))
        post.content = "## Overview\nSome content.\n"
        path.write_text(fm.dumps(post))

        llm = _mock_llm("Cleaned.")

        orchestrator = EnrichmentOrchestrator(
            workspace=ws,
            llm_client=llm,
            enrichment_pass=EnrichmentPass.CLEANUP,
            max_workers=1,
        )

        await orchestrator.enrich_all()

        call_kwargs = llm.complete.call_args[1]
        assert "format" in call_kwargs["system_prompt"].lower() or "cleanup" in call_kwargs["system_prompt"].lower()

    async def test_sentiment_prompt_mentions_developer(self, tmp_workspace: Path) -> None:
        from recon.workspace import Workspace

        ws = Workspace.open(tmp_workspace)
        path = ws.create_profile("Alpha")
        import frontmatter as fm

        post = fm.load(str(path))
        post.content = "## Overview\nContent.\n"
        path.write_text(fm.dumps(post))

        llm = _mock_llm("Sentiment findings.")

        orchestrator = EnrichmentOrchestrator(
            workspace=ws,
            llm_client=llm,
            enrichment_pass=EnrichmentPass.SENTIMENT,
            max_workers=1,
        )

        await orchestrator.enrich_all()

        call_kwargs = llm.complete.call_args[1]
        assert "sentiment" in call_kwargs["system_prompt"].lower() or "developer" in call_kwargs["system_prompt"].lower()

    async def test_cost_callback_fires_per_profile(self, tmp_workspace: Path) -> None:
        """Cost callback should fire for each enriched profile."""
        import frontmatter as fm

        from recon.workspace import Workspace

        ws = Workspace.open(tmp_workspace)
        for name in ("Alpha", "Beta"):
            path = ws.create_profile(name)
            post = fm.load(str(path))
            post.content = "## Overview\nResearch content.\n"
            path.write_text(fm.dumps(post))

        llm = _mock_llm("Enriched content.")

        cost_events: list[dict] = []

        async def on_cost(input_tokens: int, output_tokens: int) -> None:
            cost_events.append({"input": input_tokens, "output": output_tokens})

        orchestrator = EnrichmentOrchestrator(
            workspace=ws,
            llm_client=llm,
            enrichment_pass=EnrichmentPass.CLEANUP,
            max_workers=1,
            cost_callback=on_cost,
        )
        await orchestrator.enrich_all()

        assert len(cost_events) == 2
        assert all(e["input"] == 200 for e in cost_events)
        assert all(e["output"] == 100 for e in cost_events)

    async def test_publishes_enrichment_started_and_completed_events(
        self, tmp_workspace: Path
    ) -> None:
        import frontmatter as fm

        from recon.events import EnrichmentCompleted, EnrichmentStarted, get_bus
        from recon.workspace import Workspace

        ws = Workspace.open(tmp_workspace)
        path = ws.create_profile("Alpha")
        post = fm.load(str(path))
        post.content = "## Overview\nContent.\n"
        path.write_text(fm.dumps(post))

        llm = _mock_llm("Enriched.")

        events: list[object] = []

        def capture(event: object) -> None:
            if isinstance(event, (EnrichmentStarted, EnrichmentCompleted)):
                events.append(event)

        bus = get_bus()
        bus.subscribe(capture)

        orchestrator = EnrichmentOrchestrator(
            workspace=ws,
            llm_client=llm,
            enrichment_pass=EnrichmentPass.CLEANUP,
            max_workers=1,
        )
        await orchestrator.enrich_all()

        bus.unsubscribe(capture)

        assert len(events) == 2
        assert isinstance(events[0], EnrichmentStarted)
        assert events[0].pass_name == "cleanup"
        assert isinstance(events[1], EnrichmentCompleted)
        assert events[1].competitor_name == "Alpha"
