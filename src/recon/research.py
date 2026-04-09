"""Research pipeline for recon.

Orchestrates section-by-section research across all competitors.
Batches by section (all competitors for overview, then all for pricing, etc.)
for consistency, format enforcement, and clean resume points.
"""

from __future__ import annotations

from dataclasses import dataclass

import frontmatter

from recon.llm import LLMClient  # noqa: TCH001
from recon.prompts import compose_research_prompt, compose_system_prompt
from recon.schema import ReconSchema  # noqa: TCH001
from recon.workers import WorkerPool
from recon.workspace import Workspace  # noqa: TCH001


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

    @property
    def _schema(self) -> ReconSchema:
        if self.schema_override:
            return self.schema_override
        if self.workspace.schema is None:
            msg = "Workspace has no schema loaded"
            raise ValueError(msg)
        return self.workspace.schema

    async def research_all(self) -> list[dict]:
        """Research all sections for all competitors in the workspace."""
        profiles = self.workspace.list_profiles()
        competitors = [p["name"] for p in profiles]

        plan = ResearchPlan.from_schema(schema=self._schema, competitors=competitors)
        system_prompt = compose_system_prompt(self._schema)

        all_results: list[dict] = []

        for batch in plan.batches:
            tasks = [
                ResearchTask(
                    section_key=batch.section_key,
                    competitor_name=name,
                    competitor_slug=self.workspace._slug_for_name(name, profiles),
                )
                for name in batch.competitors
            ]

            pool = WorkerPool(max_workers=self.max_workers)
            outcomes = await pool.run(
                lambda task: self._research_one(system_prompt, task),
                tasks,
            )

            for outcome in outcomes:
                if outcome.success and outcome.value:
                    all_results.append(outcome.value)

        return all_results

    async def _research_one(self, system_prompt: str, task: ResearchTask) -> dict:
        """Research a single section for a single competitor."""
        user_prompt = compose_research_prompt(
            schema=self._schema,
            section_key=task.section_key,
            competitor_name=task.competitor_name,
        )

        response = await self.llm_client.complete(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

        self._append_to_profile(task.competitor_slug, task.section_key, response.text)

        return {
            "competitor": task.competitor_name,
            "section": task.section_key,
            "tokens": {"input": response.input_tokens, "output": response.output_tokens},
        }

    def _append_to_profile(self, slug: str, section_key: str, content: str) -> None:
        """Append research content to a competitor's profile."""
        path = self.workspace.competitors_dir / f"{slug}.md"
        if not path.exists():
            return

        post = frontmatter.load(str(path))
        existing = post.content or ""
        post.content = f"{existing}\n{content}\n" if existing.strip() else f"{content}\n"
        path.write_text(frontmatter.dumps(post))
