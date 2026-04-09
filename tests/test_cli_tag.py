"""Tests for the tag CLI command.

Tag discovers themes from the vector index, then writes theme tags
to competitor profile frontmatter.
"""

from __future__ import annotations

from pathlib import Path  # noqa: TCH003 -- used at runtime

import frontmatter
import yaml
from click.testing import CliRunner

from recon.cli import main
from recon.index import IndexManager, chunk_markdown
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


def _setup_workspace_with_index(ws_dir: Path) -> None:
    """Create a workspace with profiles and a populated vector index."""
    ws_dir.mkdir(exist_ok=True)
    (ws_dir / "competitors").mkdir(exist_ok=True)
    (ws_dir / ".recon").mkdir(exist_ok=True)
    (ws_dir / ".recon" / "logs").mkdir(exist_ok=True)
    (ws_dir / "recon.yaml").write_text(yaml.dump(MINIMAL_SCHEMA))

    ws = Workspace.open(ws_dir)

    profiles = [
        ("Alpha", "## Overview\n\nAlpha is an AI code generation platform.\n"),
        ("Beta", "## Overview\n\nBeta is a project management tool.\n"),
        ("Gamma", "## Overview\n\nGamma is an AI code review tool.\n"),
    ]

    for name, content in profiles:
        ws.create_profile(name)
        path = ws.competitors_dir / f"{name.lower()}.md"
        post = frontmatter.load(str(path))
        post.content = content
        post["research_status"] = "researched"
        path.write_text(frontmatter.dumps(post))

    manager = IndexManager(persist_dir=str(ws_dir / ".vectordb"))
    for profile_meta in ws.list_profiles():
        full = ws.read_profile(profile_meta["_slug"])
        if full and full.get("_content", "").strip():
            chunks = chunk_markdown(
                content=full["_content"],
                source_path=str(profile_meta["_path"]),
                frontmatter_meta={k: v for k, v in profile_meta.items() if not k.startswith("_")},
            )
            manager.add_chunks(chunks)


class TestTagCommand:
    def test_dry_run_shows_assignments_without_writing(self, tmp_path: Path) -> None:
        ws_dir = tmp_path / "ws"
        _setup_workspace_with_index(ws_dir)

        runner = CliRunner()
        result = runner.invoke(main, ["tag", "--dry-run", "--n-themes", "2", "--workspace", str(ws_dir)], catch_exceptions=False)

        assert result.exit_code == 0, result.output
        assert "assignment" in result.output.lower() or "theme" in result.output.lower()

        ws = Workspace.open(ws_dir)
        for profile_meta in ws.list_profiles():
            profile = ws.read_profile(profile_meta["_slug"])
            assert "themes" not in profile or profile["themes"] is None or profile["themes"] == []

    def test_tag_writes_themes_to_frontmatter(self, tmp_path: Path) -> None:
        ws_dir = tmp_path / "ws"
        _setup_workspace_with_index(ws_dir)

        runner = CliRunner()
        result = runner.invoke(main, ["tag", "--n-themes", "2", "--workspace", str(ws_dir)], catch_exceptions=False)

        assert result.exit_code == 0, result.output

        ws = Workspace.open(ws_dir)
        any_tagged = False
        for profile_meta in ws.list_profiles():
            profile = ws.read_profile(profile_meta["_slug"])
            if profile.get("themes") and len(profile["themes"]) > 0:
                any_tagged = True
                break

        assert any_tagged, "Expected at least one profile to have theme tags"

    def test_tag_shows_error_without_index(self, tmp_path: Path) -> None:
        ws_dir = tmp_path / "ws"
        ws_dir.mkdir()
        (ws_dir / "competitors").mkdir()
        (ws_dir / ".recon").mkdir()
        (ws_dir / ".recon" / "logs").mkdir()
        (ws_dir / "recon.yaml").write_text(yaml.dump(MINIMAL_SCHEMA))

        runner = CliRunner()
        result = runner.invoke(main, ["tag", "--workspace", str(ws_dir)], catch_exceptions=False)

        assert result.exit_code == 0
        assert "no indexed" in result.output.lower() or "no chunks" in result.output.lower()
