"""Tag system for recon.

Assigns theme tags to competitor profile frontmatter based on retrieval
relevance scores from the vector index. Each theme's suggested queries
are run against the index, results aggregated by competitor, filtered
by threshold and top-N, then written to profile frontmatter.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

import frontmatter

from recon.index import IndexManager  # noqa: TCH001 -- used at runtime
from recon.logging import get_logger
from recon.themes import DiscoveredTheme  # noqa: TCH001 -- used at runtime
from recon.workspace import Workspace  # noqa: TCH001 -- used at runtime

_log = get_logger(__name__)


@dataclass(frozen=True)
class TagAssignment:
    theme_label: str
    competitor_slug: str
    relevance_score: float


class Tagger:
    """Assigns theme tags to competitor profiles via retrieval relevance."""

    def __init__(self, index: IndexManager, workspace: Workspace) -> None:
        self._index = index
        self._workspace = workspace

    def tag(
        self,
        themes: list[DiscoveredTheme],
        threshold: float = 0.3,
        top_n: int = 30,
    ) -> list[TagAssignment]:
        """Compute theme assignments for all competitors.

        For each theme, queries the index with the theme's suggested queries,
        aggregates relevance scores by competitor, and returns assignments
        above the threshold, limited to top_n per theme.
        """
        _log.info(
            "tag computing assignments themes=%d threshold=%.2f top_n=%d",
            len(themes),
            threshold,
            top_n,
        )
        all_assignments: list[TagAssignment] = []

        profiles = self._workspace.list_profiles()
        name_to_slug = {p.get("name", ""): p["_slug"] for p in profiles}

        for theme in themes:
            competitor_scores: dict[str, float] = defaultdict(float)

            for query in theme.suggested_queries:
                results = self._index.retrieve(query, n_results=50)
                for result in results:
                    distance = result.get("distance", 1.0)
                    relevance = 1.0 / (1.0 + distance)

                    meta = result.get("metadata", {})
                    competitor_name = meta.get("name", "")
                    slug = name_to_slug.get(competitor_name, "")
                    if not slug:
                        continue

                    competitor_scores[slug] = max(competitor_scores[slug], relevance)

            ranked = sorted(competitor_scores.items(), key=lambda x: x[1], reverse=True)
            for slug, score in ranked[:top_n]:
                if score >= threshold:
                    all_assignments.append(
                        TagAssignment(
                            theme_label=theme.label,
                            competitor_slug=slug,
                            relevance_score=score,
                        )
                    )

        _log.info(
            "tag produced %d assignments across %d themes",
            len(all_assignments),
            len(themes),
        )
        return all_assignments

    def apply(self, assignments: list[TagAssignment]) -> None:
        """Write theme tags to competitor profile frontmatter.

        Accumulates themes without duplicating existing entries.
        """
        themes_by_slug: dict[str, list[str]] = defaultdict(list)
        for assignment in assignments:
            themes_by_slug[assignment.competitor_slug].append(assignment.theme_label)

        for slug, new_themes in themes_by_slug.items():
            path = self._workspace.competitors_dir / f"{slug}.md"
            if not path.exists():
                continue

            post = frontmatter.load(str(path))
            existing_themes: list[str] = post.metadata.get("themes", [])
            if not isinstance(existing_themes, list):
                existing_themes = []

            merged = list(existing_themes)
            for theme in new_themes:
                if theme not in merged:
                    merged.append(theme)

            post.metadata["themes"] = merged
            path.write_text(frontmatter.dumps(post))
