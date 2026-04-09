"""Tests for the wizard-powered init command.

The wizard guides workspace creation through Identity -> Sections ->
Sources -> Review, then generates the workspace.
"""

from __future__ import annotations

from pathlib import Path  # noqa: TCH003 -- used at runtime

import yaml
from click.testing import CliRunner

from recon.cli import main


class TestInitWizardFlow:
    def test_wizard_creates_workspace_with_prompted_input(self, tmp_path: Path) -> None:
        ws_dir = tmp_path / "myproject"
        runner = CliRunner()

        result = runner.invoke(
            main,
            ["init", str(ws_dir), "--wizard"],
            input="\n".join([
                "Acme Corp",
                "Acme CI, Acme Deploy",
                "CI/CD Tools",
                "1",
                "n",
                "",
                "",
                "y",
            ]),
            catch_exceptions=False,
        )

        assert result.exit_code == 0
        assert (ws_dir / "recon.yaml").exists()
        schema = yaml.safe_load((ws_dir / "recon.yaml").read_text())
        assert schema["domain"] == "CI/CD Tools"
        assert schema["identity"]["company_name"] == "Acme Corp"

    def test_wizard_includes_selected_sections(self, tmp_path: Path) -> None:
        ws_dir = tmp_path / "myproject"
        runner = CliRunner()

        result = runner.invoke(
            main,
            ["init", str(ws_dir), "--wizard"],
            input="\n".join([
                "Acme Corp",
                "Acme CI",
                "Developer Tools",
                "1",
                "n",
                "",
                "",
                "y",
            ]),
            catch_exceptions=False,
        )

        assert result.exit_code == 0
        schema = yaml.safe_load((ws_dir / "recon.yaml").read_text())
        section_keys = [s["key"] for s in schema["sections"]]
        assert "capabilities" in section_keys
        assert "pricing" in section_keys

    def test_wizard_creates_directory_structure(self, tmp_path: Path) -> None:
        ws_dir = tmp_path / "myproject"
        runner = CliRunner()

        runner.invoke(
            main,
            ["init", str(ws_dir), "--wizard"],
            input="\n".join([
                "Acme Corp",
                "Acme CI",
                "Tools",
                "6",
                "n",
                "",
                "",
                "y",
            ]),
            catch_exceptions=False,
        )

        assert (ws_dir / "competitors").is_dir()
        assert (ws_dir / "themes").is_dir()
        assert (ws_dir / "own-products").is_dir()
        assert (ws_dir / ".recon").is_dir()
        assert (ws_dir / ".recon" / "logs").is_dir()
        assert (ws_dir / ".gitignore").exists()

    def test_wizard_stores_own_product_flag(self, tmp_path: Path) -> None:
        ws_dir = tmp_path / "myproject"
        runner = CliRunner()

        result = runner.invoke(
            main,
            ["init", str(ws_dir), "--wizard"],
            input="\n".join([
                "Acme Corp",
                "Acme CI",
                "Tools",
                "1",
                "y",
                "",
                "",
                "y",
            ]),
            catch_exceptions=False,
        )

        assert result.exit_code == 0
        schema = yaml.safe_load((ws_dir / "recon.yaml").read_text())
        assert schema["identity"]["own_product"] is True

    def test_wizard_abort_on_review_does_not_create(self, tmp_path: Path) -> None:
        ws_dir = tmp_path / "myproject"
        runner = CliRunner()

        result = runner.invoke(
            main,
            ["init", str(ws_dir), "--wizard"],
            input="\n".join([
                "Acme Corp",
                "Acme CI",
                "Tools",
                "1",
                "n",
                "",
                "",
                "n",
            ]),
            catch_exceptions=False,
        )

        assert result.exit_code == 0
        assert not (ws_dir / "recon.yaml").exists()
        assert "cancelled" in result.output.lower() or "abort" in result.output.lower()

    def test_wizard_includes_rating_scales(self, tmp_path: Path) -> None:
        ws_dir = tmp_path / "myproject"
        runner = CliRunner()

        runner.invoke(
            main,
            ["init", str(ws_dir), "--wizard"],
            input="\n".join([
                "Acme Corp",
                "Acme CI",
                "Tools",
                "6",
                "n",
                "",
                "",
                "y",
            ]),
            catch_exceptions=False,
        )

        schema = yaml.safe_load((ws_dir / "recon.yaml").read_text())
        assert "rating_scales" in schema
        assert "capability" in schema["rating_scales"]

    def test_wizard_shows_review_summary(self, tmp_path: Path) -> None:
        ws_dir = tmp_path / "myproject"
        runner = CliRunner()

        result = runner.invoke(
            main,
            ["init", str(ws_dir), "--wizard"],
            input="\n".join([
                "Acme Corp",
                "Acme CI",
                "Developer Tools",
                "1",
                "n",
                "",
                "",
                "y",
            ]),
            catch_exceptions=False,
        )

        assert "Developer Tools" in result.output
        assert "Acme Corp" in result.output


class TestInitHeadlessMode:
    def test_headless_init_with_prompts(self, tmp_path: Path) -> None:
        ws_dir = tmp_path / "myproject"
        runner = CliRunner()

        result = runner.invoke(
            main,
            ["init", str(ws_dir), "--headless"],
            input="\n".join([
                "Developer Tools",
                "Acme Corp",
                "Acme CI",
            ]),
            catch_exceptions=False,
        )

        assert result.exit_code == 0
        assert (ws_dir / "recon.yaml").exists()

    def test_headless_init_with_flags(self, tmp_path: Path) -> None:
        ws_dir = tmp_path / "myproject"
        runner = CliRunner()

        result = runner.invoke(
            main,
            ["init", str(ws_dir), "--domain", "Tools", "--company", "Acme", "--products", "X"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0
        assert (ws_dir / "recon.yaml").exists()
