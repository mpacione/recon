"""Full pipeline orchestrator for recon.

Manages end-to-end runs through all stages:
research -> verify -> enrich -> index -> themes -> synthesize -> deliver.
Tracks state in SQLite, supports starting from any stage and stopping
after any stage, and exposes hooks for progress updates and theme
curation gates.
"""

from __future__ import annotations

import asyncio  # noqa: TCH003 -- used at runtime for cancel_event type
import contextlib
import datetime as dt
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

import frontmatter

from recon.cost import CostTracker, ModelPricing
from recon.deliver import Distiller, MetaSynthesizer
from recon.enrichment import EnrichmentOrchestrator, EnrichmentPass
from recon.index import IndexManager, chunk_markdown
from recon.llm import LLMClient  # noqa: TCH001
from recon.logging import get_logger
from recon.provenance import ProvenanceRecorder
from recon.research import ResearchOrchestrator
from recon.schema import VerificationTier
from recon.state import RunStatus, StateStore  # noqa: TCH001
from recon.synthesis import SynthesisEngine, SynthesisMode, SynthesisResult
from recon.tag import Tagger
from recon.themes import DiscoveredTheme, ThemeDiscovery, build_workspace_chunks
from recon.verification import (
    SourceStatus,
    VerificationEngine,
    VerificationOutcome,
    VerificationRequest,
)
from recon.workspace import Workspace  # noqa: TCH001

_log = get_logger(__name__)

ProgressCallback = Callable[[str, str], Awaitable[None]]
ThemeCurationCallback = Callable[
    [list[DiscoveredTheme]], Awaitable[list[DiscoveredTheme]]
]


class PipelineStage(StrEnum):
    RESEARCH = "research"
    VERIFY = "verify"
    ENRICH = "enrich"
    INDEX = "index"
    THEMES = "themes"
    SYNTHESIZE = "synthesize"
    DELIVER = "deliver"


_STAGE_ORDER = list(PipelineStage)

_SOURCE_URL_RE = re.compile(r"\((https?://[^)\s]+)\)")
_DEFAULT_MODEL = "claude-sonnet-4-20250514"
_SECTION_HEADING_RE = re.compile(r"^(#{2,4})\s+(.+)$", re.MULTILINE)
_VERIFICATION_RANK = {
    VerificationTier.STANDARD: 0,
    VerificationTier.VERIFIED: 1,
    VerificationTier.DEEP: 2,
}


def _now_iso() -> str:
    return dt.datetime.now(dt.UTC).isoformat()


def _theme_slug(label: str) -> str:
    """File-safe slug for theme label."""
    cleaned = re.sub(r"[^\w\s-]", "", label).strip().lower()
    return re.sub(r"[-\s]+", "_", cleaned) or "unnamed_theme"


def _effective_verification_tier(
    section_tier: VerificationTier,
    config_tier: str,
) -> VerificationTier:
    """Use the plan-level verification mode as a minimum floor."""
    normalized = (config_tier or "standard").strip().lower()
    try:
        requested = VerificationTier(normalized)
    except ValueError:
        requested = VerificationTier.STANDARD
    if _VERIFICATION_RANK[requested] > _VERIFICATION_RANK[section_tier]:
        return requested
    return section_tier


def _split_markdown_sections(content: str) -> list[tuple[str, str]]:
    """Split markdown content into (title, body) pairs by heading.

    Returns an empty list if no headings are found. Drops a leading
    'Sources' section to avoid treating citation URLs as first-class
    section content.
    """
    matches = list(_SECTION_HEADING_RE.finditer(content))
    if not matches:
        return []

    sections: list[tuple[str, str]] = []
    for i, match in enumerate(matches):
        title = match.group(2).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        sections.append((title, content[start:end]))
    return sections


def _summarize_outcome(outcome: VerificationOutcome) -> dict[str, Any]:
    """Build a compact frontmatter-safe summary of a verification outcome."""
    counts: dict[str, int] = {
        SourceStatus.CONFIRMED.value: 0,
        SourceStatus.CORROBORATED.value: 0,
        SourceStatus.DISPUTED.value: 0,
        SourceStatus.UNVERIFIED.value: 0,
    }
    for result in outcome.source_results:
        counts[result.status.value] = counts.get(result.status.value, 0) + 1

    return {
        "tier": outcome.tier,
        "confirmed": counts[SourceStatus.CONFIRMED.value],
        "corroborated": counts[SourceStatus.CORROBORATED.value],
        "disputed": counts[SourceStatus.DISPUTED.value],
        "unverified": counts[SourceStatus.UNVERIFIED.value],
        "sources": [
            {
                "url": r.url,
                "status": r.status.value,
                "notes": r.notes,
            }
            for r in outcome.source_results
        ],
    }


@dataclass
class PipelineConfig:
    max_research_workers: int = 5
    max_enrich_workers: int = 10
    deep_synthesis: bool = False
    verification_enabled: bool = True
    verification_tier: str = "verified"
    start_from: PipelineStage = PipelineStage.RESEARCH
    stop_after: PipelineStage = PipelineStage.DELIVER
    targets: list[str] | None = None
    theme_count: int = 5
    stale_only: bool = False
    max_age_days: int = 30
    failed_only: bool = False


@dataclass
class Pipeline:
    """Full pipeline orchestrator."""

    workspace: Workspace
    state_store: StateStore
    llm_client: LLMClient
    config: PipelineConfig = field(default_factory=PipelineConfig)
    progress_callback: ProgressCallback | None = None
    theme_curation_callback: ThemeCurationCallback | None = None
    cancel_event: asyncio.Event | None = None
    pause_event: asyncio.Event | None = None

    # Populated during execute()
    discovered_themes: list[DiscoveredTheme] = field(default_factory=list)
    syntheses: list[SynthesisResult] = field(default_factory=list)
    verification_results: list[VerificationOutcome] = field(default_factory=list)
    _provenance: ProvenanceRecorder | None = field(default=None, init=False, repr=False)

    @property
    def _cancelled(self) -> bool:
        return self.cancel_event is not None and self.cancel_event.is_set()

    async def _await_resume(self) -> None:
        """Block at the stage boundary while the pause_event is cleared.

        Returns immediately if no pause_event was provided or if the
        event is set (running). Polls so it can also notice a
        cancel_event mid-pause.
        """
        if self.pause_event is None:
            return
        while not self.pause_event.is_set():
            if self._cancelled:
                return
            try:
                await asyncio.wait_for(self.pause_event.wait(), timeout=0.05)
            except TimeoutError:
                continue

    async def _emit(self, stage: str, phase: str) -> None:
        if self.progress_callback is None:
            return
        with contextlib.suppress(Exception):
            await self.progress_callback(stage, phase)

    async def plan(self) -> str:
        """Create a run plan and return the run_id."""
        run_id = await self.state_store.create_run(
            operation="full_pipeline",
            parameters={
                "start_from": self.config.start_from.value,
                "stop_after": self.config.stop_after.value,
                "deep_synthesis": self.config.deep_synthesis,
                "verification_enabled": self.config.verification_enabled,
            },
        )
        self._provenance = ProvenanceRecorder.for_run(self.workspace.root, run_id)
        self._provenance.write_yaml(
            "run.yaml",
            {
                "run_id": run_id,
                "workspace_root": str(self.workspace.root),
                "status": "planning",
                "created_at": _now_iso(),
                "config": {
                    "start_from": self.config.start_from.value,
                    "stop_after": self.config.stop_after.value,
                    "deep_synthesis": self.config.deep_synthesis,
                    "verification_enabled": self.config.verification_enabled,
                    "verification_tier": self.config.verification_tier,
                    "max_research_workers": self.config.max_research_workers,
                    "max_enrich_workers": self.config.max_enrich_workers,
                    "targets": self.config.targets or [],
                    "theme_count": self.config.theme_count,
                    "stale_only": self.config.stale_only,
                    "max_age_days": self.config.max_age_days,
                    "failed_only": self.config.failed_only,
                },
            },
        )
        return run_id

    async def get_plan_summary(self, run_id: str) -> dict[str, Any]:
        """Get a summary of what the pipeline will do."""
        profiles = self.workspace.list_profiles()
        schema = self.workspace.schema
        section_count = len(schema.sections) if schema else 0

        start_idx = _STAGE_ORDER.index(self.config.start_from)
        stop_idx = _STAGE_ORDER.index(self.config.stop_after)
        active_stages = _STAGE_ORDER[start_idx : stop_idx + 1]

        return {
            "run_id": run_id,
            "competitors": len(profiles),
            "sections": section_count,
            "stages": [s.value for s in active_stages],
            "deep_synthesis": self.config.deep_synthesis,
            "verification_enabled": self.config.verification_enabled,
        }

    async def execute(self, run_id: str) -> None:
        """Execute the pipeline."""
        from recon.events import RunStarted, publish

        _log.info(
            "pipeline execute run_id=%s start=%s stop=%s deep=%s verify=%s targets=%s",
            run_id,
            self.config.start_from.value,
            self.config.stop_after.value,
            self.config.deep_synthesis,
            self.config.verification_enabled,
            self.config.targets if self.config.targets else "all",
        )
        if self._provenance is None:
            self._provenance = ProvenanceRecorder.for_run(self.workspace.root, run_id)
        self._provenance.write_yaml(
            "run.yaml",
            {
                "run_id": run_id,
                "workspace_root": str(self.workspace.root),
                "status": "running",
                "started_at": _now_iso(),
                "config": {
                    "start_from": self.config.start_from.value,
                    "stop_after": self.config.stop_after.value,
                    "deep_synthesis": self.config.deep_synthesis,
                    "verification_enabled": self.config.verification_enabled,
                    "verification_tier": self.config.verification_tier,
                    "max_research_workers": self.config.max_research_workers,
                    "max_enrich_workers": self.config.max_enrich_workers,
                    "targets": self.config.targets or [],
                    "theme_count": self.config.theme_count,
                    "stale_only": self.config.stale_only,
                    "max_age_days": self.config.max_age_days,
                    "failed_only": self.config.failed_only,
                },
            },
        )
        publish(RunStarted(run_id=run_id, operation="pipeline"))
        await self.state_store.update_run_status(run_id, RunStatus.RUNNING)

        cost_tracker = CostTracker(
            model_pricing=ModelPricing(
                model_id=_DEFAULT_MODEL,
                input_price_per_million=3.0,
                output_price_per_million=15.0,
            ),
        )

        start_idx = _STAGE_ORDER.index(self.config.start_from)
        stop_idx = _STAGE_ORDER.index(self.config.stop_after)

        from recon.events import (
            RunCancelled,
            RunCompleted,
            RunFailed,
            RunStageCompleted,
            RunStageStarted,
        )
        from recon.events import publish as _publish

        try:
            for stage in _STAGE_ORDER[start_idx : stop_idx + 1]:
                await self._await_resume()
                if self._cancelled:
                    await self._emit(stage.value, "cancelled")
                    if self._provenance is not None:
                        self._provenance.write_yaml(
                            "run.yaml",
                            {
                                "run_id": run_id,
                                "workspace_root": str(self.workspace.root),
                                "status": "cancelled",
                                "cancelled_at": _now_iso(),
                            },
                        )
                    _publish(RunCancelled(run_id=run_id))
                    await self.state_store.update_run_status(
                        run_id, RunStatus.CANCELLED,
                    )
                    return
                await self._emit(stage.value, "start")
                _publish(RunStageStarted(run_id=run_id, stage=stage.value))
                await self._execute_stage(run_id, stage, cost_tracker)
                await self._emit(stage.value, "complete")
                _publish(RunStageCompleted(run_id=run_id, stage=stage.value))

            if self._cancelled:
                _log.info("pipeline execute run_id=%s -> CANCELLED", run_id)
                _publish(RunCancelled(run_id=run_id))
                if self._provenance is not None:
                    self._provenance.write_yaml(
                        "run.yaml",
                        {
                            "run_id": run_id,
                            "workspace_root": str(self.workspace.root),
                            "status": "cancelled",
                            "cancelled_at": _now_iso(),
                        },
                    )
                await self.state_store.update_run_status(
                    run_id, RunStatus.CANCELLED,
                )
                return

            _log.info("pipeline execute run_id=%s -> COMPLETED", run_id)
            total = await self.state_store.get_run_total_cost(run_id)
            if self._provenance is not None:
                self._provenance.write_yaml(
                    "run.yaml",
                    {
                        "run_id": run_id,
                        "workspace_root": str(self.workspace.root),
                        "status": "completed",
                        "completed_at": _now_iso(),
                        "total_cost_usd": total,
                        "theme_count": len(self.discovered_themes),
                        "synthesis_count": len(self.syntheses),
                        "verification_count": len(self.verification_results),
                    },
                )
            _publish(RunCompleted(run_id=run_id, total_cost_usd=total))
            await self.state_store.update_run_status(run_id, RunStatus.COMPLETED)
        except Exception as exc:
            _log.exception("pipeline execute run_id=%s -> FAILED", run_id)
            if self._provenance is not None:
                self._provenance.write_yaml(
                    "run.yaml",
                    {
                        "run_id": run_id,
                        "workspace_root": str(self.workspace.root),
                        "status": "failed",
                        "failed_at": _now_iso(),
                        "error": str(exc),
                    },
                )
            _publish(RunFailed(run_id=run_id, error=str(exc)))
            await self.state_store.update_run_status(run_id, RunStatus.FAILED)
            raise

    async def _execute_stage(
        self,
        run_id: str,
        stage: PipelineStage,
        cost_tracker: CostTracker,
    ) -> None:
        """Execute a single pipeline stage."""
        if stage == PipelineStage.RESEARCH:
            await self._stage_research(run_id, cost_tracker)
        elif stage == PipelineStage.VERIFY:
            if self.config.verification_enabled:
                await self._stage_verify(run_id, cost_tracker)
        elif stage == PipelineStage.ENRICH:
            await self._stage_enrich(run_id, cost_tracker)
        elif stage == PipelineStage.INDEX:
            await self._stage_index(run_id)
        elif stage == PipelineStage.THEMES:
            await self._stage_themes(run_id, cost_tracker)
        elif stage == PipelineStage.SYNTHESIZE:
            await self._stage_synthesize(run_id, cost_tracker)
        elif stage == PipelineStage.DELIVER:
            await self._stage_deliver(run_id, cost_tracker)

    # ------------------------------------------------------------------
    # Cost helpers
    # ------------------------------------------------------------------

    async def _record_tokens(
        self,
        run_id: str,
        cost_tracker: CostTracker,
        input_tokens: int,
        output_tokens: int,
    ) -> None:
        if input_tokens <= 0 and output_tokens <= 0:
            return
        cost = cost_tracker.record_call(input_tokens, output_tokens)
        await self.state_store.record_cost(
            run_id=run_id,
            model=_DEFAULT_MODEL,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
        )

        from recon.events import CostRecorded
        from recon.events import publish as _publish

        _publish(
            CostRecorded(
                run_id=run_id,
                model=_DEFAULT_MODEL,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost,
            ),
        )

    # ------------------------------------------------------------------
    # Stage implementations
    # ------------------------------------------------------------------

    async def _stage_research(self, run_id: str, cost_tracker: CostTracker) -> None:
        """Execute the research stage.

        Cost is recorded per-section via a callback, not aggregated
        after the batch. This enables streaming cost in the TUI/web UI.
        """

        async def _on_cost(input_tokens: int, output_tokens: int) -> None:
            await self._record_tokens(run_id, cost_tracker, input_tokens, output_tokens)

        orchestrator = ResearchOrchestrator(
            workspace=self.workspace,
            llm_client=self.llm_client,
            max_workers=self.config.max_research_workers,
            cost_callback=_on_cost,
            provenance=self._provenance,
        )

        await orchestrator.research_all(
            targets=self.config.targets,
            stale_only=self.config.stale_only,
            max_age_days=self.config.max_age_days,
            failed_only=self.config.failed_only,
            cancel_event=self.cancel_event,
            pause_event=self.pause_event,
        )

    async def _stage_verify(self, run_id: str, cost_tracker: CostTracker) -> None:
        """Execute the verification stage.

        Iterates profiles that have been researched, splits each one by
        section header, and runs the verification engine at the tier
        declared for that section in the schema. Skips sections whose
        declared tier is ``standard`` (no LLM call needed). Outcomes are
        stored on ``self.verification_results`` and attached to each
        profile's frontmatter as a structured ``verification`` dict so
        users can see per-section status without re-running the pipeline.
        """
        profiles = self.workspace.list_profiles()
        if self.config.targets is not None:
            lowered = {t.lower() for t in self.config.targets}
            profiles = [p for p in profiles if p["name"].lower() in lowered]

        schema = self.workspace.schema
        if schema is None or not schema.sections:
            self.verification_results = []
            return

        engine = VerificationEngine(
            llm_client=self.llm_client,
            provenance=self._provenance,
        )
        section_tiers = {s.key: s.verification_tier for s in schema.sections}
        title_to_key = {s.title: s.key for s in schema.sections}

        outcomes: list[VerificationOutcome] = []
        for profile_meta in profiles:
            full = self.workspace.read_profile(profile_meta["_slug"])
            if not full or not full.get("_content", "").strip():
                continue
            if profile_meta.get("research_status") == "scaffold":
                continue

            content = full["_content"]
            sections = _split_markdown_sections(content)

            profile_summary: dict[str, dict[str, Any]] = {}

            for section_title, section_text in sections:
                key = title_to_key.get(section_title)
                if key is None:
                    # Try case-insensitive title match as a fallback
                    matches = [k for t, k in title_to_key.items() if t.lower() == section_title.lower()]
                    if not matches:
                        continue
                    key = matches[0]

                tier = section_tiers.get(key, VerificationTier.STANDARD)
                tier = _effective_verification_tier(
                    tier,
                    self.config.verification_tier,
                )
                if tier == VerificationTier.STANDARD:
                    continue

                sources = _SOURCE_URL_RE.findall(section_text)
                if not sources:
                    continue

                request = VerificationRequest(
                    content=section_text,
                    sources=sources,
                    section_key=key,
                    competitor_name=profile_meta.get("name", profile_meta["_slug"]),
                    tier=tier.value,
                )
                try:
                    outcome = await engine.verify(request)
                except Exception:
                    _log.exception(
                        "verification failed for %s/%s",
                        profile_meta.get("name"),
                        key,
                    )
                    continue

                outcomes.append(outcome)
                profile_summary[key] = _summarize_outcome(outcome)
                if self._provenance is not None:
                    self._provenance.record_sources(
                        actor="verification",
                        context={
                            "competitor": profile_meta.get("name", profile_meta["_slug"]),
                            "competitor_slug": profile_meta["_slug"],
                            "section": key,
                            "tier": tier.value,
                        },
                        cited_urls=request.sources,
                        selected_urls=[
                            result.url
                            for result in outcome.source_results
                            if result.status != SourceStatus.DISPUTED
                        ],
                        source_results=[
                            {
                                "url": result.url,
                                "status": result.status.value,
                                "notes": result.notes,
                            }
                            for result in outcome.source_results
                        ],
                        notes=outcome.corroboration_notes,
                    )
                await self._record_tokens(
                    run_id,
                    cost_tracker,
                    outcome.input_tokens,
                    outcome.output_tokens,
                )

            if profile_summary:
                self._write_verification_frontmatter(
                    profile_meta["_slug"], profile_summary,
                )

        self.verification_results = outcomes

    def _write_verification_frontmatter(
        self,
        slug: str,
        summary: dict[str, dict[str, Any]],
    ) -> None:
        path = self.workspace.competitors_dir / f"{slug}.md"
        if not path.exists():
            return
        post = frontmatter.load(str(path))
        existing = post.metadata.get("verification")
        if isinstance(existing, dict):
            existing.update(summary)
            post["verification"] = existing
        else:
            post["verification"] = summary
        path.write_text(frontmatter.dumps(post))

    async def _stage_enrich(self, run_id: str, cost_tracker: CostTracker) -> None:
        """Execute all enrichment passes.

        Cost is recorded per-profile via a callback, not aggregated
        after each pass. This enables streaming cost in the TUI/web UI.
        """

        async def _on_cost(input_tokens: int, output_tokens: int) -> None:
            await self._record_tokens(run_id, cost_tracker, input_tokens, output_tokens)

        for enrichment_pass in EnrichmentPass:
            orchestrator = EnrichmentOrchestrator(
                workspace=self.workspace,
                llm_client=self.llm_client,
                enrichment_pass=enrichment_pass,
                max_workers=self.config.max_enrich_workers,
                cost_callback=_on_cost,
            )
            await orchestrator.enrich_all(
                targets=self.config.targets,
                cancel_event=self.cancel_event,
                pause_event=self.pause_event,
            )

    async def _stage_index(self, run_id: str) -> None:
        """Execute the indexing stage.

        Use the incremental indexer so repeated pipeline runs do not
        append duplicate chunks for unchanged files.
        """
        from recon.incremental import IncrementalIndexer

        manager = self._open_index_manager()
        try:
            indexer = IncrementalIndexer(
                workspace=self.workspace,
                index_manager=manager,
                state_store=self.state_store,
            )
            await indexer.index(force=False)
        finally:
            manager.close()

    async def _stage_themes(self, run_id: str, cost_tracker: CostTracker) -> None:
        """Discover themes, optionally curate them, and tag profiles."""
        chunks = build_workspace_chunks(self.workspace)
        if not chunks:
            _log.info("themes stage: no content chunks; skipping")
            self.discovered_themes = []
            return

        # Thread the LLM client so ThemeDiscovery can generate real
        # strategic labels instead of falling back to the mechanical
        # term-frequency labeler. The previous code constructed
        # ThemeDiscovery() with no llm_client to "avoid nested event
        # loop" — but that just meant _llm_label always returned the
        # fallback. Now that discover() and _llm_label() are async,
        # they run naturally inside the pipeline's event loop.
        discovery = ThemeDiscovery(llm_client=self.llm_client)
        themes = await discovery.discover(chunks, n_themes=self.config.theme_count)

        if self.theme_curation_callback is not None:
            try:
                curated = await self.theme_curation_callback(list(themes))
                if isinstance(curated, list):
                    themes = curated
            except Exception:
                _log.exception("theme_curation_callback failed; keeping discovered themes")

        self.discovered_themes = list(themes)

        from recon.events import ThemesDiscovered
        from recon.events import publish as _publish

        _publish(ThemesDiscovered(theme_count=len(self.discovered_themes)))

        if not self.discovered_themes:
            return

        manager = self._open_index_manager()
        if manager.collection_count() == 0:
            _log.info("themes stage: index is empty; skipping tag application")
            return

        tagger = Tagger(index=manager, workspace=self.workspace)
        assignments = tagger.tag(themes=self.discovered_themes)
        if assignments:
            tagger.apply(assignments)

    async def _stage_synthesize(
        self, run_id: str, cost_tracker: CostTracker
    ) -> None:
        """Run synthesis for each discovered theme and write theme files."""
        if not self.discovered_themes:
            _log.info("synthesize stage: no themes discovered; skipping")
            self.syntheses = []
            return

        themes_dir = self.workspace.root / "themes"
        themes_dir.mkdir(parents=True, exist_ok=True)

        engine = SynthesisEngine(llm_client=self.llm_client)
        mode = (
            SynthesisMode.DEEP if self.config.deep_synthesis else SynthesisMode.SINGLE
        )

        manager = self._open_index_manager()
        syntheses: list[SynthesisResult] = []

        from recon.events import SynthesisCompleted, SynthesisStarted
        from recon.events import publish as _publish

        for theme in self.discovered_themes:
            _publish(SynthesisStarted(theme_label=theme.label))
            chunks = self._retrieve_for_theme(manager, theme)
            try:
                result = await engine.synthesize(
                    theme=theme.label, chunks=chunks, mode=mode,
                )
            except Exception:
                _log.exception("synthesis failed for theme %s", theme.label)
                continue

            syntheses.append(result)

            output_path = themes_dir / f"{_theme_slug(theme.label)}.md"
            output_path.write_text(result.content)

            await self._record_tokens(
                run_id,
                cost_tracker,
                result.total_input_tokens,
                result.total_output_tokens,
            )
            _publish(SynthesisCompleted(theme_label=theme.label))

        self.syntheses = syntheses

    async def _stage_deliver(self, run_id: str, cost_tracker: CostTracker) -> None:
        """Distill each synthesis and run a cross-theme meta-synthesis."""
        if not self.syntheses:
            _log.info("deliver stage: no syntheses to distill; skipping")
            return

        distilled_dir = self.workspace.root / "themes" / "distilled"
        distilled_dir.mkdir(parents=True, exist_ok=True)

        from recon.events import DeliveryCompleted, DeliveryStarted
        from recon.events import publish as _publish

        distiller = Distiller(llm_client=self.llm_client)
        distilled_payloads: list[dict[str, Any]] = []

        for synthesis in self.syntheses:
            _publish(DeliveryStarted(theme_label=synthesis.theme))
            try:
                distilled = await distiller.distill(synthesis)
            except Exception:
                _log.exception("distill failed for theme %s", synthesis.theme)
                continue

            path = distilled_dir / f"{_theme_slug(synthesis.theme)}.md"
            path.write_text(distilled.content)
            distilled_payloads.append(
                {"theme": distilled.theme, "content": distilled.content}
            )
            await self._record_tokens(
                run_id, cost_tracker, distilled.input_tokens, distilled.output_tokens,
            )
            _publish(DeliveryCompleted(theme_label=synthesis.theme))

        if not distilled_payloads:
            return

        meta = MetaSynthesizer(llm_client=self.llm_client)
        try:
            summary = await meta.synthesize(distilled_payloads)
        except Exception:
            _log.exception("meta-synthesis failed")
            return

        summary_path = self.workspace.root / "executive_summary.md"
        summary_path.write_text(summary.content)
        await self._record_tokens(
            run_id, cost_tracker, summary.input_tokens, summary.output_tokens,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _open_index_manager(self) -> IndexManager:
        return IndexManager(persist_dir=str(self.workspace.root / ".vectordb"))

    def _retrieve_for_theme(
        self,
        manager: IndexManager,
        theme: DiscoveredTheme,
    ) -> list[dict[str, Any]]:
        """Retrieve chunks for a theme's synthesis prompt."""
        if manager.collection_count() == 0:
            return [
                {"text": c.get("text", ""), "metadata": c.get("metadata", {})}
                for c in theme.evidence_chunks
            ]
        query = theme.label
        if theme.suggested_queries:
            query = theme.suggested_queries[0]
        return manager.retrieve(query, n_results=10)
