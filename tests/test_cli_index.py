"""Tests for the index CLI command with incremental indexing."""

from __future__ import annotations

from pathlib import Path  # noqa: TCH003 -- used at runtime

import frontmatter
import yaml
from click.testing import CliRunner

from recon.cli import main
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


def _setup_workspace(ws_dir: Path) -> None:
    ws_dir.mkdir(exist_ok=True)
    (ws_dir / "competitors").mkdir(exist_ok=True)
    (ws_dir / ".recon").mkdir(exist_ok=True)
    (ws_dir / ".recon" / "logs").mkdir(exist_ok=True)
    (ws_dir / "recon.yaml").write_text(yaml.dump(MINIMAL_SCHEMA))

    ws = Workspace.open(ws_dir)
    ws.create_profile("Alpha")
    path = ws.competitors_dir / "alpha.md"
    post = frontmatter.load(str(path))
    post.content = "## Overview\n\nAlpha is an AI code tool.\n"
    post["research_status"] = "researched"
    path.write_text(frontmatter.dumps(post))


class TestIndexCommand:
    def test_incremental_index_reports_counts(self, tmp_path: Path) -> None:
        ws_dir = tmp_path / "ws"
        _setup_workspace(ws_dir)

        runner = CliRunner()
        result = runner.invoke(
            main, ["index", "--workspace", str(ws_dir)],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.output
        assert "indexed" in result.output.lower()
        assert "1" in result.output

    def test_incremental_skips_unchanged(self, tmp_path: Path) -> None:
        ws_dir = tmp_path / "ws"
        _setup_workspace(ws_dir)

        runner = CliRunner()
        runner.invoke(
            main, ["index", "--workspace", str(ws_dir)],
            catch_exceptions=False,
        )
        result = runner.invoke(
            main, ["index", "--workspace", str(ws_dir)],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.output
        assert "skipped" in result.output.lower()

    def test_full_reindex_with_force(self, tmp_path: Path) -> None:
        ws_dir = tmp_path / "ws"
        _setup_workspace(ws_dir)

        runner = CliRunner()
        runner.invoke(
            main, ["index", "--workspace", str(ws_dir)],
            catch_exceptions=False,
        )
        result = runner.invoke(
            main, ["index", "--full", "--workspace", str(ws_dir)],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.output
        assert "indexed" in result.output.lower()
