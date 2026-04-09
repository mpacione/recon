"""Tests for the tag system.

Tag: assign theme tags to competitor profile frontmatter based on
retrieval relevance scores from the vector index.
"""

from __future__ import annotations

from pathlib import Path  # noqa: TCH003 -- used at runtime

import chromadb
import frontmatter
import pytest
import yaml

from recon.index import IndexManager, chunk_markdown
from recon.tag import Tagger
from recon.themes import DiscoveredTheme
from recon.workspace import Workspace

MINIMAL_SCHEMA = {
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
        },
    ],
}


def _make_theme(
    label: str,
    queries: list[str] | None = None,
) -> DiscoveredTheme:
    return DiscoveredTheme(
        label=label,
        evidence_chunks=[],
        evidence_strength="strong",
        suggested_queries=queries or [label.lower()],
        cluster_center=[],
    )


@pytest.fixture()
def workspace_with_profiles(tmp_path: Path) -> Workspace:
    """Create a workspace with 3 competitor profiles that have content."""
    ws_dir = tmp_path / "ws"
    ws_dir.mkdir()
    (ws_dir / "competitors").mkdir()
    (ws_dir / ".recon").mkdir()
    (ws_dir / ".recon" / "logs").mkdir()
    (ws_dir / "recon.yaml").write_text(yaml.dump(MINIMAL_SCHEMA))

    ws = Workspace.open(ws_dir)

    for name, content in [
        ("Alpha", "## Overview\n\nAlpha is an AI code generation platform for developers.\n"),
        ("Beta", "## Overview\n\nBeta is a project management tool for enterprise teams.\n"),
        ("Gamma", "## Overview\n\nGamma is an AI-powered code review and generation tool.\n"),
    ]:
        ws.create_profile(name)
        path = ws.competitors_dir / f"{name.lower()}.md"
        post = frontmatter.load(str(path))
        post.content = content
        post["research_status"] = "researched"
        path.write_text(frontmatter.dumps(post))

    return ws


@pytest.fixture()
def populated_index(workspace_with_profiles: Workspace) -> IndexManager:
    """Create an index populated with the workspace profiles."""
    client = chromadb.EphemeralClient()
    manager = IndexManager(client=client)

    for profile_meta in workspace_with_profiles.list_profiles():
        full = workspace_with_profiles.read_profile(profile_meta["_slug"])
        if full and full.get("_content", "").strip():
            chunks = chunk_markdown(
                content=full["_content"],
                source_path=str(profile_meta["_path"]),
                frontmatter_meta={k: v for k, v in profile_meta.items() if not k.startswith("_")},
            )
            manager.add_chunks(chunks)

    return manager


class TestTaggerAggregation:
    def test_assigns_themes_to_relevant_competitors(
        self,
        workspace_with_profiles: Workspace,
        populated_index: IndexManager,
    ) -> None:
        themes = [_make_theme("AI Code Generation", queries=["AI code generation"])]

        tagger = Tagger(index=populated_index, workspace=workspace_with_profiles)
        assignments = tagger.tag(themes=themes, threshold=0.0, top_n=10)

        assert len(assignments) > 0
        competitor_slugs = [a.competitor_slug for a in assignments]
        assert any(s in competitor_slugs for s in ["alpha", "gamma"])

    def test_each_assignment_has_theme_and_score(
        self,
        workspace_with_profiles: Workspace,
        populated_index: IndexManager,
    ) -> None:
        themes = [_make_theme("AI Code Generation", queries=["AI code generation"])]

        tagger = Tagger(index=populated_index, workspace=workspace_with_profiles)
        assignments = tagger.tag(themes=themes, threshold=0.0, top_n=10)

        for assignment in assignments:
            assert assignment.theme_label == "AI Code Generation"
            assert assignment.competitor_slug != ""
            assert assignment.relevance_score > 0.0

    def test_filters_below_threshold(
        self,
        workspace_with_profiles: Workspace,
        populated_index: IndexManager,
    ) -> None:
        themes = [_make_theme("AI Code Generation", queries=["AI code generation"])]

        tagger = Tagger(index=populated_index, workspace=workspace_with_profiles)
        assignments = tagger.tag(themes=themes, threshold=0.99, top_n=10)

        assert len(assignments) == 0

    def test_limits_to_top_n(
        self,
        workspace_with_profiles: Workspace,
        populated_index: IndexManager,
    ) -> None:
        themes = [_make_theme("AI Code Generation", queries=["AI code generation tools"])]

        tagger = Tagger(index=populated_index, workspace=workspace_with_profiles)
        assignments = tagger.tag(themes=themes, threshold=0.0, top_n=1)

        assert len(assignments) <= 1

    def test_returns_empty_for_empty_index(
        self,
        workspace_with_profiles: Workspace,
    ) -> None:
        client = chromadb.EphemeralClient()
        empty_index = IndexManager(client=client)
        empty_index.clear()
        themes = [_make_theme("Anything", queries=["anything"])]

        tagger = Tagger(index=empty_index, workspace=workspace_with_profiles)
        assignments = tagger.tag(themes=themes, threshold=0.0, top_n=10)

        assert assignments == []

    def test_multiple_themes_produce_separate_assignments(
        self,
        workspace_with_profiles: Workspace,
        populated_index: IndexManager,
    ) -> None:
        themes = [
            _make_theme("AI Code Generation", queries=["AI code generation"]),
            _make_theme("Project Management", queries=["project management enterprise"]),
        ]

        tagger = Tagger(index=populated_index, workspace=workspace_with_profiles)
        assignments = tagger.tag(themes=themes, threshold=0.0, top_n=10)

        theme_labels = {a.theme_label for a in assignments}
        assert len(theme_labels) == 2


class TestTaggerWritesFrontmatter:
    def test_apply_writes_themes_to_profiles(
        self,
        workspace_with_profiles: Workspace,
        populated_index: IndexManager,
    ) -> None:
        themes = [_make_theme("AI Code Generation", queries=["AI code generation"])]

        tagger = Tagger(index=populated_index, workspace=workspace_with_profiles)
        assignments = tagger.tag(themes=themes, threshold=0.0, top_n=10)
        tagger.apply(assignments)

        tagged_slugs = {a.competitor_slug for a in assignments}
        for slug in tagged_slugs:
            profile = workspace_with_profiles.read_profile(slug)
            assert "themes" in profile
            assert "AI Code Generation" in profile["themes"]

    def test_apply_accumulates_multiple_themes(
        self,
        workspace_with_profiles: Workspace,
        populated_index: IndexManager,
    ) -> None:
        themes = [
            _make_theme("AI Code Generation", queries=["AI code generation"]),
            _make_theme("Project Management", queries=["project management enterprise"]),
        ]

        tagger = Tagger(index=populated_index, workspace=workspace_with_profiles)
        assignments = tagger.tag(themes=themes, threshold=0.0, top_n=10)
        tagger.apply(assignments)

        for profile_meta in workspace_with_profiles.list_profiles():
            profile = workspace_with_profiles.read_profile(profile_meta["_slug"])
            if profile.get("themes"):
                assert isinstance(profile["themes"], list)

    def test_apply_does_not_duplicate_existing_themes(
        self,
        workspace_with_profiles: Workspace,
        populated_index: IndexManager,
    ) -> None:
        themes = [_make_theme("AI Code Generation", queries=["AI code generation"])]

        tagger = Tagger(index=populated_index, workspace=workspace_with_profiles)
        assignments = tagger.tag(themes=themes, threshold=0.0, top_n=10)
        tagger.apply(assignments)
        tagger.apply(assignments)

        for slug in {a.competitor_slug for a in assignments}:
            profile = workspace_with_profiles.read_profile(slug)
            theme_list = profile.get("themes", [])
            assert theme_list.count("AI Code Generation") == 1
