"""Tests for the full pipeline orchestrator.

The pipeline orchestrator manages end-to-end runs: research -> verify ->
enrich -> index -> discover themes -> retrieve -> synthesize -> distill -> meta-synthesis.
It tracks state via the StateStore and supports incremental/resumable runs.
"""

from pathlib import Path
from unittest.mock import AsyncMock

import yaml

from recon.llm import LLMResponse
from recon.pipeline import Pipeline, PipelineConfig, PipelineStage


def _make_response(text: str = "LLM output.\n\n## Sources\n- [S](https://s.com) -- 2026-01-01") -> LLMResponse:
    return LLMResponse(
        text=text, input_tokens=200, output_tokens=100,
        model="claude-sonnet-4-20250514", stop_reason="end_turn",
    )


def _mock_llm() -> AsyncMock:
    client = AsyncMock()
    client.complete = AsyncMock(return_value=_make_response())
    client.total_input_tokens = 0
    client.total_output_tokens = 0
    client.call_count = 0
    return client


class TestPipelineConfig:
    def test_default_config(self) -> None:
        config = PipelineConfig()

        assert config.max_research_workers == 5
        assert config.max_enrich_workers == 10
        assert config.deep_synthesis is False
        assert config.verification_enabled is True

    def test_custom_config(self) -> None:
        config = PipelineConfig(
            max_research_workers=3,
            deep_synthesis=True,
            start_from=PipelineStage.INDEX,
        )

        assert config.max_research_workers == 3
        assert config.deep_synthesis is True
        assert config.start_from == PipelineStage.INDEX


class TestPipelineStages:
    def test_stage_ordering(self) -> None:
        stages = list(PipelineStage)

        assert stages.index(PipelineStage.RESEARCH) < stages.index(PipelineStage.VERIFY)
        assert stages.index(PipelineStage.VERIFY) < stages.index(PipelineStage.ENRICH)
        assert stages.index(PipelineStage.ENRICH) < stages.index(PipelineStage.INDEX)
        assert stages.index(PipelineStage.INDEX) < stages.index(PipelineStage.THEMES)
        assert stages.index(PipelineStage.THEMES) < stages.index(PipelineStage.SYNTHESIZE)
        assert stages.index(PipelineStage.SYNTHESIZE) < stages.index(PipelineStage.DELIVER)

    def test_all_stages_present(self) -> None:
        expected = {"research", "verify", "enrich", "index", "themes", "synthesize", "deliver"}
        actual = {s.value for s in PipelineStage}
        assert expected == actual


class TestPipeline:
    async def test_creates_run_in_state_store(self, tmp_workspace: Path) -> None:
        from recon.state import StateStore
        from recon.workspace import Workspace

        ws = Workspace.open(tmp_workspace)
        store = StateStore(tmp_workspace / ".recon" / "state.db")
        await store.initialize()

        pipeline = Pipeline(
            workspace=ws,
            state_store=store,
            llm_client=_mock_llm(),
        )

        run_id = await pipeline.plan()

        assert run_id is not None
        run = await store.get_run(run_id)
        assert run is not None
        assert run["operation"] == "full_pipeline"

    async def test_plan_returns_stage_summary(self, tmp_workspace: Path) -> None:
        from recon.state import StateStore
        from recon.workspace import Workspace

        ws = Workspace.open(tmp_workspace)
        ws.create_profile("Alpha")
        store = StateStore(tmp_workspace / ".recon" / "state.db")
        await store.initialize()

        pipeline = Pipeline(
            workspace=ws,
            state_store=store,
            llm_client=_mock_llm(),
        )

        run_id = await pipeline.plan()
        summary = await pipeline.get_plan_summary(run_id)

        assert "stages" in summary
        assert len(summary["stages"]) > 0

    async def test_plan_writes_run_manifest(self, tmp_workspace: Path) -> None:
        from recon.state import StateStore
        from recon.workspace import Workspace

        ws = Workspace.open(tmp_workspace)
        store = StateStore(tmp_workspace / ".recon" / "state.db")
        await store.initialize()

        pipeline = Pipeline(
            workspace=ws,
            state_store=store,
            llm_client=_mock_llm(),
        )

        run_id = await pipeline.plan()

        manifest_path = tmp_workspace / ".recon" / "runs" / run_id / "run.yaml"
        assert manifest_path.exists()
        manifest = yaml.safe_load(manifest_path.read_text())
        assert manifest["run_id"] == run_id
        assert manifest["status"] == "planning"
        assert manifest["config"]["verification_enabled"] is True

    async def test_execute_runs_research_stage(self, tmp_workspace: Path) -> None:
        from recon.state import StateStore
        from recon.workspace import Workspace

        ws = Workspace.open(tmp_workspace)
        ws.create_profile("Alpha")
        store = StateStore(tmp_workspace / ".recon" / "state.db")
        await store.initialize()

        llm = _mock_llm()

        pipeline = Pipeline(
            workspace=ws,
            state_store=store,
            llm_client=llm,
            config=PipelineConfig(
                verification_enabled=False,
                start_from=PipelineStage.RESEARCH,
                stop_after=PipelineStage.RESEARCH,
            ),
        )

        run_id = await pipeline.plan()
        await pipeline.execute(run_id)

        run = await store.get_run(run_id)
        assert run["status"] == "completed"

    async def test_targets_are_forwarded_to_research_stage(self, tmp_workspace: Path) -> None:
        from recon.state import StateStore
        from recon.workspace import Workspace

        ws = Workspace.open(tmp_workspace)
        ws.create_profile("Alpha")
        ws.create_profile("Beta")
        store = StateStore(tmp_workspace / ".recon" / "state.db")
        await store.initialize()

        llm = _mock_llm()

        pipeline = Pipeline(
            workspace=ws,
            state_store=store,
            llm_client=llm,
            config=PipelineConfig(
                verification_enabled=False,
                start_from=PipelineStage.RESEARCH,
                stop_after=PipelineStage.RESEARCH,
                targets=["Beta"],
            ),
        )

        run_id = await pipeline.plan()
        await pipeline.execute(run_id)

        alpha = ws.read_profile("alpha")
        beta = ws.read_profile("beta")
        assert alpha["research_status"] == "scaffold"
        assert beta["research_status"] == "researched"

    async def test_progress_callback_fires_for_each_stage(self, tmp_workspace: Path) -> None:
        from recon.state import StateStore
        from recon.workspace import Workspace

        ws = Workspace.open(tmp_workspace)
        ws.create_profile("Alpha")
        store = StateStore(tmp_workspace / ".recon" / "state.db")
        await store.initialize()

        events: list[tuple[str, str]] = []

        async def on_progress(stage: str, phase: str) -> None:
            events.append((stage, phase))

        pipeline = Pipeline(
            workspace=ws,
            state_store=store,
            llm_client=_mock_llm(),
            config=PipelineConfig(
                verification_enabled=False,
                start_from=PipelineStage.RESEARCH,
                stop_after=PipelineStage.ENRICH,
            ),
            progress_callback=on_progress,
        )

        run_id = await pipeline.plan()
        await pipeline.execute(run_id)

        stages_started = [stage for stage, phase in events if phase == "start"]
        stages_completed = [stage for stage, phase in events if phase == "complete"]
        assert "research" in stages_started
        assert "enrich" in stages_started
        assert "research" in stages_completed
        assert "enrich" in stages_completed

    async def test_tracks_run_cost(self, tmp_workspace: Path) -> None:
        from recon.state import StateStore
        from recon.workspace import Workspace

        ws = Workspace.open(tmp_workspace)
        ws.create_profile("Alpha")
        store = StateStore(tmp_workspace / ".recon" / "state.db")
        await store.initialize()

        pipeline = Pipeline(
            workspace=ws,
            state_store=store,
            llm_client=_mock_llm(),
            config=PipelineConfig(
                verification_enabled=False,
                start_from=PipelineStage.RESEARCH,
                stop_after=PipelineStage.RESEARCH,
            ),
        )

        run_id = await pipeline.plan()
        await pipeline.execute(run_id)

        total = await store.get_run_total_cost(run_id)
        assert total >= 0


def _fill_profile(ws: object, slug: str, content: str) -> None:
    """Write `content` into an existing profile and mark it researched."""
    import frontmatter as fm

    path = ws.competitors_dir / f"{slug}.md"
    post = fm.load(str(path))
    post.content = content
    post["research_status"] = "researched"
    path.write_text(fm.dumps(post))


class TestPipelineCancellation:
    async def test_cancelled_before_start_marks_run_cancelled(
        self, tmp_workspace: Path
    ) -> None:
        import asyncio

        from recon.state import RunStatus, StateStore
        from recon.workspace import Workspace

        ws = Workspace.open(tmp_workspace)
        ws.create_profile("Alpha")
        store = StateStore(tmp_workspace / ".recon" / "state.db")
        await store.initialize()

        cancel_event = asyncio.Event()
        cancel_event.set()

        llm = _mock_llm()
        pipeline = Pipeline(
            workspace=ws,
            state_store=store,
            llm_client=llm,
            config=PipelineConfig(
                verification_enabled=False,
                start_from=PipelineStage.RESEARCH,
                stop_after=PipelineStage.RESEARCH,
            ),
            cancel_event=cancel_event,
        )

        run_id = await pipeline.plan()
        await pipeline.execute(run_id)

        run = await store.get_run(run_id)
        assert run["status"] == RunStatus.CANCELLED.value
        # No LLM call should have happened
        assert llm.complete.call_count == 0

    async def test_cancel_mid_pipeline_stops_at_next_stage(
        self, tmp_workspace: Path
    ) -> None:
        import asyncio

        from recon.state import RunStatus, StateStore
        from recon.workspace import Workspace

        ws = Workspace.open(tmp_workspace)
        ws.create_profile("Alpha")
        store = StateStore(tmp_workspace / ".recon" / "state.db")
        await store.initialize()

        cancel_event = asyncio.Event()

        async def on_progress(stage: str, phase: str) -> None:
            if stage == "research" and phase == "complete":
                cancel_event.set()

        pipeline = Pipeline(
            workspace=ws,
            state_store=store,
            llm_client=_mock_llm(),
            config=PipelineConfig(
                verification_enabled=False,
                start_from=PipelineStage.RESEARCH,
                stop_after=PipelineStage.ENRICH,
            ),
            progress_callback=on_progress,
            cancel_event=cancel_event,
        )

        run_id = await pipeline.plan()
        await pipeline.execute(run_id)

        run = await store.get_run(run_id)
        assert run["status"] == RunStatus.CANCELLED.value


class TestPipelinePause:
    async def test_pipeline_blocks_at_stage_boundary_until_resumed(
        self, tmp_workspace: Path
    ) -> None:
        import asyncio

        from recon.state import StateStore
        from recon.workspace import Workspace

        ws = Workspace.open(tmp_workspace)
        ws.create_profile("Alpha")
        store = StateStore(tmp_workspace / ".recon" / "state.db")
        await store.initialize()

        pause_event = asyncio.Event()
        pause_event.set()

        stages_seen: list[tuple[str, str]] = []

        async def on_progress(stage: str, phase: str) -> None:
            stages_seen.append((stage, phase))
            # After research starts, pause -- the next stage should not begin
            if (stage, phase) == ("research", "complete"):
                pause_event.clear()

        async def resume_after_delay() -> None:
            await asyncio.sleep(0.1)
            pause_event.set()

        pipeline = Pipeline(
            workspace=ws,
            state_store=store,
            llm_client=_mock_llm(),
            config=PipelineConfig(
                verification_enabled=False,
                start_from=PipelineStage.RESEARCH,
                stop_after=PipelineStage.ENRICH,
            ),
            progress_callback=on_progress,
            pause_event=pause_event,
        )

        run_id = await pipeline.plan()

        resume_task = asyncio.create_task(resume_after_delay())
        await pipeline.execute(run_id)
        await resume_task

        # Both research and enrich should have completed in order, even
        # though pause was set after research and only released asynchronously
        # by resume_after_delay. Verify is in the loop range (research..enrich)
        # but is a no-op because verification_enabled=False; it still emits
        # start/complete events.
        starts = [s for s, p in stages_seen if p == "start"]
        completes = [s for s, p in stages_seen if p == "complete"]
        assert "research" in starts
        assert "enrich" in starts
        assert "research" in completes
        assert "enrich" in completes
        assert starts.index("research") < starts.index("enrich")


class TestPipelineThemesStage:
    async def test_themes_stage_discovers_and_tags(self, tmp_workspace: Path) -> None:
        from recon.state import StateStore
        from recon.workspace import Workspace

        ws = Workspace.open(tmp_workspace)
        ws.create_profile("Alpha")
        ws.create_profile("Beta")
        ws.create_profile("Gamma")
        _fill_profile(ws, "alpha", "## Overview\n\nAlpha has AI code generation features.\n")
        _fill_profile(ws, "beta", "## Overview\n\nBeta focuses on enterprise compliance.\n")
        _fill_profile(ws, "gamma", "## Overview\n\nGamma offers developer onboarding tools.\n")

        store = StateStore(tmp_workspace / ".recon" / "state.db")
        await store.initialize()

        llm = _mock_llm()
        pipeline = Pipeline(
            workspace=ws,
            state_store=store,
            llm_client=llm,
            config=PipelineConfig(
                verification_enabled=False,
                start_from=PipelineStage.INDEX,
                stop_after=PipelineStage.THEMES,
                theme_count=2,
            ),
        )

        run_id = await pipeline.plan()
        await pipeline.execute(run_id)

        themes = pipeline.discovered_themes
        assert len(themes) >= 1
        # At least one profile should have gotten a theme tag in frontmatter
        any_tagged = any(
            ws.read_profile(slug).get("themes")
            for slug in ["alpha", "beta", "gamma"]
        )
        assert any_tagged

    async def test_theme_curation_callback_can_filter(self, tmp_workspace: Path) -> None:
        from recon.state import StateStore
        from recon.themes import DiscoveredTheme
        from recon.workspace import Workspace

        ws = Workspace.open(tmp_workspace)
        ws.create_profile("Alpha")
        ws.create_profile("Beta")
        _fill_profile(ws, "alpha", "## Overview\n\nAlpha content.\n")
        _fill_profile(ws, "beta", "## Overview\n\nBeta content.\n")

        store = StateStore(tmp_workspace / ".recon" / "state.db")
        await store.initialize()

        seen_themes: list[list[DiscoveredTheme]] = []

        async def curate(themes: list[DiscoveredTheme]) -> list[DiscoveredTheme]:
            seen_themes.append(list(themes))
            return themes[:1]  # keep only the first theme

        pipeline = Pipeline(
            workspace=ws,
            state_store=store,
            llm_client=_mock_llm(),
            config=PipelineConfig(
                verification_enabled=False,
                start_from=PipelineStage.INDEX,
                stop_after=PipelineStage.THEMES,
                theme_count=2,
            ),
            theme_curation_callback=curate,
        )

        run_id = await pipeline.plan()
        await pipeline.execute(run_id)

        assert len(seen_themes) == 1, "curation callback should fire exactly once"
        assert len(pipeline.discovered_themes) <= 1


class TestPipelineSynthesizeStage:
    async def test_synthesize_stage_writes_theme_files(self, tmp_workspace: Path) -> None:
        from recon.state import StateStore
        from recon.themes import DiscoveredTheme
        from recon.workspace import Workspace

        ws = Workspace.open(tmp_workspace)
        ws.create_profile("Alpha")
        _fill_profile(ws, "alpha", "## Overview\n\nAlpha content.\n")

        store = StateStore(tmp_workspace / ".recon" / "state.db")
        await store.initialize()

        llm = _mock_llm()

        # Seed discovered themes by keeping the curation callback stable
        injected = [
            DiscoveredTheme(
                label="Test Theme",
                evidence_chunks=[{"text": "Alpha content.", "metadata": {"name": "Alpha"}}],
                evidence_strength="strong",
                suggested_queries=["alpha content"],
                cluster_center=[0.1],
            ),
        ]

        async def curate(_):
            return injected

        pipeline = Pipeline(
            workspace=ws,
            state_store=store,
            llm_client=llm,
            config=PipelineConfig(
                verification_enabled=False,
                start_from=PipelineStage.INDEX,
                stop_after=PipelineStage.SYNTHESIZE,
                theme_count=1,
            ),
            theme_curation_callback=curate,
        )

        run_id = await pipeline.plan()
        await pipeline.execute(run_id)

        themes_dir = ws.root / "themes"
        assert themes_dir.exists()
        theme_files = list(themes_dir.glob("*.md"))
        assert len(theme_files) >= 1, "synthesize should write at least one theme file"
        assert len(pipeline.syntheses) >= 1


class TestPipelineDeliverStage:
    async def test_deliver_stage_writes_executive_summary(self, tmp_workspace: Path) -> None:
        from recon.state import StateStore
        from recon.themes import DiscoveredTheme
        from recon.workspace import Workspace

        ws = Workspace.open(tmp_workspace)
        ws.create_profile("Alpha")
        _fill_profile(ws, "alpha", "## Overview\n\nAlpha content.\n")

        store = StateStore(tmp_workspace / ".recon" / "state.db")
        await store.initialize()

        llm = _mock_llm()

        injected = [
            DiscoveredTheme(
                label="Test Theme",
                evidence_chunks=[{"text": "Alpha content.", "metadata": {"name": "Alpha"}}],
                evidence_strength="strong",
                suggested_queries=["alpha content"],
                cluster_center=[0.1],
            ),
        ]

        async def curate(_):
            return injected

        pipeline = Pipeline(
            workspace=ws,
            state_store=store,
            llm_client=llm,
            config=PipelineConfig(
                verification_enabled=False,
                start_from=PipelineStage.INDEX,
                stop_after=PipelineStage.DELIVER,
                theme_count=1,
            ),
            theme_curation_callback=curate,
        )

        run_id = await pipeline.plan()
        await pipeline.execute(run_id)

        executive_summary = ws.root / "executive_summary.md"
        assert executive_summary.exists(), "deliver stage should write executive_summary.md"
        distilled_dir = ws.root / "themes" / "distilled"
        assert distilled_dir.exists()
        assert list(distilled_dir.glob("*.md")), "deliver stage should write distilled theme files"


class TestPipelineVerifyStagePerSection:
    async def test_verify_honors_per_section_schema_tier(
        self, tmp_workspace: Path
    ) -> None:
        """Sections with tier=standard should not cost LLM calls; only
        sections with tier=verified or deep trigger the engine.
        """
        import yaml as y

        from recon.state import StateStore
        from recon.workspace import Workspace

        schema = {
            "domain": "Developer Tools",
            "identity": {
                "company_name": "Acme Corp",
                "products": ["Acme IDE"],
                "decision_context": [],
            },
            "rating_scales": {},
            "sections": [
                {
                    "key": "overview",
                    "title": "Overview",
                    "description": "High-level summary.",
                    "allowed_formats": ["prose"],
                    "preferred_format": "prose",
                    "verification_tier": "standard",
                },
                {
                    "key": "pricing",
                    "title": "Pricing",
                    "description": "Pricing model.",
                    "allowed_formats": ["prose"],
                    "preferred_format": "prose",
                    "verification_tier": "verified",
                },
            ],
        }
        (tmp_workspace / "recon.yaml").write_text(y.dump(schema))

        ws = Workspace.open(tmp_workspace)
        ws.create_profile("Alpha")
        _fill_profile(
            ws,
            "alpha",
            (
                "## Overview\n\nAlpha overview content.\n\n"
                "Source: [Docs](https://overview.example.com)\n\n"
                "## Pricing\n\nAlpha pricing details.\n\n"
                "Source: [Pricing](https://pricing.example.com)\n"
            ),
        )

        store = StateStore(tmp_workspace / ".recon" / "state.db")
        await store.initialize()

        verify_llm = AsyncMock()
        verify_llm.complete = AsyncMock(
            return_value=LLMResponse(
                text='{"sources": [{"url": "https://pricing.example.com", "status": "confirmed", "notes": "ok"}], "corroboration": "verified"}',
                input_tokens=100,
                output_tokens=50,
                model="claude-sonnet-4-5",
                stop_reason="end_turn",
            ),
        )

        pipeline = Pipeline(
            workspace=ws,
            state_store=store,
            llm_client=verify_llm,
            config=PipelineConfig(
                verification_enabled=True,
                start_from=PipelineStage.VERIFY,
                stop_after=PipelineStage.VERIFY,
            ),
        )

        run_id = await pipeline.plan()
        await pipeline.execute(run_id)

        # Only the pricing section should trigger an LLM call
        assert verify_llm.complete.call_count == 1
        # And only the pricing section should appear in results
        section_keys = {o.section_key for o in pipeline.verification_results}
        assert section_keys == {"pricing"}

    async def test_verify_writes_summary_to_profile_frontmatter(
        self, tmp_workspace: Path
    ) -> None:
        import yaml as y

        from recon.state import StateStore
        from recon.workspace import Workspace

        schema = {
            "domain": "Developer Tools",
            "identity": {
                "company_name": "Acme Corp",
                "products": ["Acme IDE"],
                "decision_context": [],
            },
            "rating_scales": {},
            "sections": [
                {
                    "key": "overview",
                    "title": "Overview",
                    "description": "High-level summary.",
                    "allowed_formats": ["prose"],
                    "preferred_format": "prose",
                    "verification_tier": "verified",
                },
            ],
        }
        (tmp_workspace / "recon.yaml").write_text(y.dump(schema))

        ws = Workspace.open(tmp_workspace)
        ws.create_profile("Alpha")
        _fill_profile(
            ws,
            "alpha",
            (
                "## Overview\n\nAlpha overview content.\n\n"
                "Source: [Docs](https://example.com)\n"
            ),
        )

        store = StateStore(tmp_workspace / ".recon" / "state.db")
        await store.initialize()

        verify_llm = AsyncMock()
        verify_llm.complete = AsyncMock(
            return_value=LLMResponse(
                text='{"sources": [{"url": "https://example.com", "status": "confirmed", "notes": "match"}], "corroboration": "ok"}',
                input_tokens=100,
                output_tokens=50,
                model="claude-sonnet-4-5",
                stop_reason="end_turn",
            ),
        )

        pipeline = Pipeline(
            workspace=ws,
            state_store=store,
            llm_client=verify_llm,
            config=PipelineConfig(
                verification_enabled=True,
                start_from=PipelineStage.VERIFY,
                stop_after=PipelineStage.VERIFY,
            ),
        )

        run_id = await pipeline.plan()
        await pipeline.execute(run_id)

        alpha = ws.read_profile("alpha")
        verification = alpha.get("verification")
        assert verification is not None, "verify stage should attach frontmatter"
        assert "overview" in verification
        overview_entry = verification["overview"]
        assert overview_entry["tier"] == "verified"
        assert overview_entry["confirmed"] == 1
        assert any(
            s["url"] == "https://example.com" and s["status"] == "confirmed"
            for s in overview_entry["sources"]
        )

    async def test_verify_records_cost_through_state_store(
        self, tmp_workspace: Path
    ) -> None:
        import yaml as y

        from recon.state import StateStore
        from recon.workspace import Workspace

        schema = {
            "domain": "Developer Tools",
            "identity": {
                "company_name": "Acme Corp",
                "products": ["Acme IDE"],
                "decision_context": [],
            },
            "rating_scales": {},
            "sections": [
                {
                    "key": "overview",
                    "title": "Overview",
                    "description": "High-level summary.",
                    "allowed_formats": ["prose"],
                    "preferred_format": "prose",
                    "verification_tier": "verified",
                },
            ],
        }
        (tmp_workspace / "recon.yaml").write_text(y.dump(schema))

        ws = Workspace.open(tmp_workspace)
        ws.create_profile("Alpha")
        _fill_profile(
            ws,
            "alpha",
            "## Overview\n\nContent.\n\nSource: [Docs](https://example.com)\n",
        )

        store = StateStore(tmp_workspace / ".recon" / "state.db")
        await store.initialize()

        verify_llm = AsyncMock()
        verify_llm.complete = AsyncMock(
            return_value=LLMResponse(
                text='{"sources": [{"url": "https://example.com", "status": "confirmed", "notes": "ok"}], "corroboration": "verified"}',
                input_tokens=500,
                output_tokens=200,
                model="claude-sonnet-4-5",
                stop_reason="end_turn",
            ),
        )

        pipeline = Pipeline(
            workspace=ws,
            state_store=store,
            llm_client=verify_llm,
            config=PipelineConfig(
                verification_enabled=True,
                start_from=PipelineStage.VERIFY,
                stop_after=PipelineStage.VERIFY,
            ),
        )

        run_id = await pipeline.plan()
        await pipeline.execute(run_id)

        total = await store.get_run_total_cost(run_id)
        assert total > 0.0, "verify stage should record cost"


class TestPipelineVerifyStage:
    async def test_verify_stage_runs_when_enabled_and_section_tier_requires_it(
        self, tmp_workspace: Path
    ) -> None:
        import yaml as y

        from recon.state import StateStore
        from recon.workspace import Workspace

        schema = {
            "domain": "Developer Tools",
            "identity": {
                "company_name": "Acme Corp",
                "products": ["Acme IDE"],
                "decision_context": [],
            },
            "rating_scales": {},
            "sections": [
                {
                    "key": "overview",
                    "title": "Overview",
                    "description": "High-level summary.",
                    "allowed_formats": ["prose"],
                    "preferred_format": "prose",
                    "verification_tier": "verified",
                },
            ],
        }
        (tmp_workspace / "recon.yaml").write_text(y.dump(schema))

        ws = Workspace.open(tmp_workspace)
        ws.create_profile("Alpha")
        _fill_profile(
            ws,
            "alpha",
            "## Overview\n\nAlpha content. Source: [Docs](https://example.com)\n",
        )

        store = StateStore(tmp_workspace / ".recon" / "state.db")
        await store.initialize()

        verify_llm = AsyncMock()
        verify_llm.complete = AsyncMock(
            return_value=LLMResponse(
                text='{"sources": [{"url": "https://example.com", "status": "confirmed", "notes": "ok"}], "corroboration": "verified"}',
                input_tokens=100,
                output_tokens=50,
                model="claude-sonnet-4-5",
                stop_reason="end_turn",
            ),
        )

        pipeline = Pipeline(
            workspace=ws,
            state_store=store,
            llm_client=verify_llm,
            config=PipelineConfig(
                verification_enabled=True,
                start_from=PipelineStage.VERIFY,
                stop_after=PipelineStage.VERIFY,
            ),
        )

        run_id = await pipeline.plan()
        await pipeline.execute(run_id)

        assert verify_llm.complete.called, "verification engine should be called"
        assert len(pipeline.verification_results) >= 1

    async def test_verify_stage_noop_when_disabled(self, tmp_workspace: Path) -> None:
        from recon.state import StateStore
        from recon.workspace import Workspace

        ws = Workspace.open(tmp_workspace)
        ws.create_profile("Alpha")
        _fill_profile(ws, "alpha", "## Overview\n\nAlpha content.\n")

        store = StateStore(tmp_workspace / ".recon" / "state.db")
        await store.initialize()

        llm = _mock_llm()

        pipeline = Pipeline(
            workspace=ws,
            state_store=store,
            llm_client=llm,
            config=PipelineConfig(
                verification_enabled=False,
                start_from=PipelineStage.VERIFY,
                stop_after=PipelineStage.VERIFY,
            ),
        )

        run_id = await pipeline.plan()
        await pipeline.execute(run_id)

        assert not llm.complete.called
        assert pipeline.verification_results == []
