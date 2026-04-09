"""Tests for the CLI add command with --from-list support."""

from __future__ import annotations

from pathlib import Path  # noqa: TCH003 -- used at runtime

import yaml
from click.testing import CliRunner

from recon.cli import main

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
            "description": "Summary.",
            "allowed_formats": ["prose"],
            "preferred_format": "prose",
        },
    ],
}


def _setup_workspace(ws_dir: Path) -> None:
    ws_dir.mkdir(exist_ok=True)
    (ws_dir / "competitors").mkdir(exist_ok=True)
    (ws_dir / "themes").mkdir(exist_ok=True)
    (ws_dir / "own-products").mkdir(exist_ok=True)
    (ws_dir / ".recon").mkdir(exist_ok=True)
    (ws_dir / ".recon" / "logs").mkdir(exist_ok=True)
    (ws_dir / "recon.yaml").write_text(yaml.dump(MINIMAL_SCHEMA))


class TestAddFromList:
    def test_adds_competitors_from_file(self, tmp_path: Path) -> None:
        ws_dir = tmp_path / "ws"
        _setup_workspace(ws_dir)
        list_file = tmp_path / "competitors.txt"
        list_file.write_text("Alpha\nBeta\nGamma\n")

        import os
        old_cwd = os.getcwd()
        os.chdir(ws_dir)
        try:
            runner = CliRunner()
            result = runner.invoke(
                main,
                ["add", "--from-list", str(list_file)],
                catch_exceptions=False,
            )
        finally:
            os.chdir(old_cwd)

        assert result.exit_code == 0
        assert (ws_dir / "competitors" / "alpha.md").exists()
        assert (ws_dir / "competitors" / "beta.md").exists()
        assert (ws_dir / "competitors" / "gamma.md").exists()

    def test_skips_blank_lines_in_list(self, tmp_path: Path) -> None:
        ws_dir = tmp_path / "ws"
        _setup_workspace(ws_dir)
        list_file = tmp_path / "competitors.txt"
        list_file.write_text("Alpha\n\n  \nBeta\n")

        import os
        old_cwd = os.getcwd()
        os.chdir(ws_dir)
        try:
            runner = CliRunner()
            result = runner.invoke(
                main,
                ["add", "--from-list", str(list_file)],
                catch_exceptions=False,
            )
        finally:
            os.chdir(old_cwd)

        assert result.exit_code == 0
        assert "2" in result.output or "Alpha" in result.output

    def test_skips_duplicates_in_list(self, tmp_path: Path) -> None:
        ws_dir = tmp_path / "ws"
        _setup_workspace(ws_dir)
        list_file = tmp_path / "competitors.txt"
        list_file.write_text("Alpha\nBeta\n")

        import os
        old_cwd = os.getcwd()
        os.chdir(ws_dir)
        try:
            runner = CliRunner()
            runner.invoke(main, ["add", "Alpha"], catch_exceptions=False)

            result = runner.invoke(
                main,
                ["add", "--from-list", str(list_file)],
                catch_exceptions=False,
            )
        finally:
            os.chdir(old_cwd)

        assert result.exit_code == 0
        assert "exists" in result.output.lower() or "skip" in result.output.lower()

    def test_single_add_still_works(self, tmp_path: Path) -> None:
        ws_dir = tmp_path / "ws"
        _setup_workspace(ws_dir)

        import os
        old_cwd = os.getcwd()
        os.chdir(ws_dir)
        try:
            runner = CliRunner()
            result = runner.invoke(
                main,
                ["add", "Alpha"],
                catch_exceptions=False,
            )
        finally:
            os.chdir(old_cwd)

        assert result.exit_code == 0
        assert (ws_dir / "competitors" / "alpha.md").exists()
