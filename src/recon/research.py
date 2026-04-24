"""Research pipeline for recon.

Orchestrates section-by-section research across all competitors.
Batches by section (all competitors for overview, then all for pricing, etc.)
for consistency, format enforcement, and clean resume points.

Supports three scoping modes via ``research_all``:
- default: research every (profile, section) pair
- ``stale_only``: skip sections whose ``researched_at`` timestamp is
  within ``max_age_days``
- ``failed_only``: only research sections whose ``section_status`` is
  ``failed`` or missing (never successfully researched)

A ``cancel_event`` (asyncio.Event) can be passed to short-circuit a
running batch -- the worker pool checks it before starting each task.
"""

from __future__ import annotations

import asyncio  # noqa: TCH003 -- used at runtime in type hints
import datetime as dt
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import frontmatter

from recon.llm import LLMClient  # noqa: TCH001
from recon.logging import get_logger
from recon.prompts import compose_research_prompt, compose_system_prompt
from recon.schema import ReconSchema  # noqa: TCH001
from recon.workers import WorkerPool
from recon.workspace import Workspace  # noqa: TCH001

CostCallback = Callable[[int, int], Awaitable[None]]

_log = get_logger(__name__)

_WEB_SEARCH_TOOL = {
    "type": "web_search_20250305",
    "name": "web_search",
    "max_uses": 5,
}


@dataclass(frozen=True)
class SectionBatch:
    section_key: str
    competitors: list[str]


@dataclass(frozen=True)
class ResearchPlan:
    batches: list[SectionBatch]

    @property
    def total_tasks(self) -> int:
        return sum(len(b.competitors) for b in self.batches)

    @classmethod
    def from_schema(cls, schema: ReconSchema, competitors: list[str]) -> ResearchPlan:
        """Create a research plan: one batch per section, each batch has all competitors."""
        batches = [
            SectionBatch(section_key=section.key, competitors=list(competitors))
            for section in schema.sections
        ]
        return cls(batches=batches)


@dataclass(frozen=True)
class ResearchTask:
    section_key: str
    competitor_name: str
    competitor_slug: str


@dataclass
class ResearchOrchestrator:
    """Orchestrates section-by-section research across all competitors."""

    workspace: Workspace
    llm_client: LLMClient
    max_workers: int = 5
    schema_override: ReconSchema | None = None
    use_web_search: bool = True
    max_retries: int = 1
    cost_callback: CostCallback | None = None

    @property
    def _schema(self) -> ReconSchema:
        if self.schema_override:
            return self.schema_override
        if self.workspace.schema is None:
            msg = "Workspace has no schema loaded"
            raise ValueError(msg)
        return self.workspace.schema

    async def research_all(
        self,
        targets: list[str] | None = None,
        *,
        stale_only: bool = False,
        max_age_days: int = 30,
        failed_only: bool = False,
        cancel_event: asyncio.Event | None = None,
        pause_event: asyncio.Event | None = None,
    ) -> list[dict]:
        """Research sections for competitors in the workspace.

        ``targets`` filters to specific competitors (case-insensitive;
        unknown names raise ``ValueError``).

        ``stale_only=True`` skips any section whose ``section_status``
        ``researched_at`` is newer than ``max_age_days`` days ago.

        ``failed_only=True`` restricts work to sections whose
        ``section_status`` is ``failed``, or sections with no recorded
        status (never successfully researched).
        """
        profiles = self.workspace.list_profiles()
        all_names = [p["name"] for p in profiles]

        if targets is None:
            competitors = all_names
        else:
            by_lower = {name.lower(): name for name in all_names}
            resolved: list[str] = []
            unknown: list[str] = []
            for requested in targets:
                canonical = by_lower.get(requested.lower())
                if canonical is None:
                    unknown.append(requested)
                elif canonical not in resolved:
                    resolved.append(canonical)
            if unknown:
                msg = f"Unknown target(s): {', '.join(unknown)}"
                raise ValueError(msg)
            competitors = resolved

        plan = ResearchPlan.from_schema(schema=self._schema, competitors=competitors)
        system_prompt = compose_system_prompt(self._schema)

        all_results: list[dict] = []

        for batch in plan.batches:
            tasks: list[ResearchTask] = []
            for name in batch.competitors:
                slug = self.workspace._slug_for_name(name, profiles)
                if not self._should_research_section(
                    slug=slug,
                    section_key=batch.section_key,
                    stale_only=stale_only,
                    max_age_days=max_age_days,
                    failed_only=failed_only,
                ):
                    continue
                tasks.append(
                    ResearchTask(
                        section_key=batch.section_key,
                        competitor_name=name,
                        competitor_slug=slug,
                    ),
                )

            if not tasks:
                continue

            if cancel_event is not None and cancel_event.is_set():
                break

            pool = WorkerPool(max_workers=self.max_workers)
            outcomes = await pool.run(
                lambda task: self._research_one(system_prompt, task),
                tasks,
                cancel_event=cancel_event,
                pause_event=pause_event,
            )

            for outcome in outcomes:
                if outcome.success and outcome.value:
                    all_results.append(outcome.value)

        return all_results

    def _should_research_section(
        self,
        *,
        slug: str,
        section_key: str,
        stale_only: bool,
        max_age_days: int,
        failed_only: bool,
    ) -> bool:
        """Decide whether this (profile, section) pair should be researched."""
        if not stale_only and not failed_only:
            return True

        full = self.workspace.read_profile(slug)
        if full is None:
            return True

        section_status = full.get("section_status") or {}
        if not isinstance(section_status, dict):
            section_status = {}
        entry = section_status.get(section_key) or {}
        if not isinstance(entry, dict):
            entry = {}

        status = entry.get("status", "")

        if failed_only:
            # Rerun only if never successfully researched
            return status != "researched"

        # stale_only: include if there is no timestamp, or it is older
        # than max_age_days
        researched_at = entry.get("researched_at")
        if not researched_at:
            return True
        try:
            timestamp = dt.datetime.fromisoformat(researched_at)
        except ValueError:
            return True
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=dt.UTC)
        age = dt.datetime.now(dt.UTC) - timestamp
        return age > dt.timedelta(days=max_age_days)

    async def _research_one(self, system_prompt: str, task: ResearchTask) -> dict:
        """Research a single section for a single competitor.

        Retries up to ``max_retries`` times on failure before marking the
        section as failed. Each retry emits a ``SectionRetrying`` event so
        the TUI can show retry state.
        """
        from recon.events import SectionRetrying, SectionStarted, publish

        publish(
            SectionStarted(
                competitor_name=task.competitor_name,
                section_key=task.section_key,
            ),
        )

        last_error: Exception | None = None

        for attempt in range(1 + self.max_retries):
            if attempt > 0:
                _log.info(
                    "research retry attempt=%d section=%s competitor=%s error=%s",
                    attempt,
                    task.section_key,
                    task.competitor_name,
                    last_error,
                )
                publish(
                    SectionRetrying(
                        competitor_name=task.competitor_name,
                        section_key=task.section_key,
                        attempt=attempt,
                        error=str(last_error),
                    ),
                )

            try:
                response = await self._call_llm(system_prompt, task)
            except Exception as exc:
                last_error = exc
                continue

            _log.info(
                "research got response section=%s competitor=%s in=%d out=%d len=%d",
                task.section_key,
                task.competitor_name,
                response.input_tokens,
                response.output_tokens,
                len(response.text),
            )

            self._append_to_profile(task.competitor_slug, task.section_key, response.text)

            if self.cost_callback is not None:
                try:
                    await self.cost_callback(response.input_tokens, response.output_tokens)
                except Exception:
                    _log.exception("cost_callback raised")

            return {
                "competitor": task.competitor_name,
                "section": task.section_key,
                "tokens": {"input": response.input_tokens, "output": response.output_tokens},
            }

        _log.exception(
            "research failed after %d attempts section=%s competitor=%s",
            1 + self.max_retries,
            task.section_key,
            task.competitor_name,
        )
        error_detail = str(last_error) if last_error else "unknown"
        self._mark_section_failed(task.competitor_slug, task.section_key, error_detail)
        raise last_error  # type: ignore[misc]

    async def _call_llm(self, system_prompt: str, task: ResearchTask) -> "LLMResponse":
        """Make the LLM call, falling back to no-tools if web_search is unavailable."""
        from recon.llm import LLMResponse  # noqa: F811

        user_prompt = compose_research_prompt(
            schema=self._schema,
            section_key=task.section_key,
            competitor_name=task.competitor_name,
        )

        tools = [_WEB_SEARCH_TOOL] if self.use_web_search else None

        _log.info(
            "research section=%s competitor=%s tools=%s",
            task.section_key,
            task.competitor_name,
            "web_search" if tools else "none",
        )

        try:
            return await self.llm_client.complete(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                tools=tools,
                max_tokens=8192,
            )
        except Exception as exc:
            msg = str(exc).lower()
            if tools and ("web_search" in msg or "tool" in msg or "not enabled" in msg):
                _log.warning(
                    "research web_search tool unavailable, retrying without: %s",
                    exc,
                )
                return await self.llm_client.complete(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    max_tokens=4096,
                )
            raise

    def _append_to_profile(self, slug: str, section_key: str, content: str) -> None:
        """Append research content to a profile and update section_status."""
        path = self.workspace.competitors_dir / f"{slug}.md"
        if not path.exists():
            return

        post = frontmatter.load(str(path))
        existing = post.content or ""
        post.content = f"{existing}\n{content}\n" if existing.strip() else f"{content}\n"
        post["research_status"] = "researched"

        section_status = self._coerce_section_status(post.metadata.get("section_status"))
        section_status[section_key] = {
            "status": "researched",
            "researched_at": dt.datetime.now(dt.UTC).isoformat(),
        }
        post["section_status"] = section_status

        path.write_text(frontmatter.dumps(post))

        # Publish event so the TUI chrome can react in real time
        from recon.events import SectionResearched, publish

        publish(
            SectionResearched(
                competitor_name=post.metadata.get("name", slug),
                section_key=section_key,
            ),
        )

    def _mark_section_failed(self, slug: str, section_key: str, error: str = "") -> None:
        """Flag ``section_key`` as failed in the profile's section_status map."""
        path = self.workspace.competitors_dir / f"{slug}.md"
        if not path.exists():
            return

        post = frontmatter.load(str(path))
        section_status = self._coerce_section_status(post.metadata.get("section_status"))
        existing = section_status.get(section_key) or {}
        if not isinstance(existing, dict):
            existing = {}
        existing = {**existing, "status": "failed", "error": error}
        section_status[section_key] = existing
        post["section_status"] = section_status
        path.write_text(frontmatter.dumps(post))

        from recon.events import SectionFailed, publish

        publish(
            SectionFailed(
                competitor_name=post.metadata.get("name", slug),
                section_key=section_key,
                error=error,
            ),
        )

    def _coerce_section_status(self, value: Any) -> dict[str, dict[str, Any]]:
        """Normalize a frontmatter section_status value into a dict."""
        if isinstance(value, dict):
            return {k: v for k, v in value.items()}
        return {}
