"""Tests for workspace management.

The workspace is the user-facing data layer: markdown profiles with YAML
frontmatter, schema definition, project config. Designed to be an
Obsidian vault or part of one.
"""

from pathlib import Path

import yaml

from recon.workspace import Workspace


class TestWorkspaceInit:
    def test_creates_directory_structure(self, tmp_path: Path) -> None:
        ws = Workspace.init(tmp_path / "myproject")

        assert ws.root.exists()
        assert (ws.root / "competitors").is_dir()
        assert (ws.root / ".recon").is_dir()
        assert (ws.root / ".recon" / "logs").is_dir()

    def test_does_not_overwrite_existing(self, tmp_path: Path) -> None:
        root = tmp_path / "myproject"
        root.mkdir()
        (root / "competitors").mkdir()
        (root / "competitors" / "existing.md").write_text("keep me")

        ws = Workspace.init(root)

        assert (ws.root / "competitors" / "existing.md").read_text() == "keep me"

    def test_creates_recon_yaml_with_schema(self, tmp_path: Path) -> None:
        ws = Workspace.init(
            tmp_path / "myproject",
            domain="Developer Tools",
            company_name="Acme Corp",
            products=["Acme IDE"],
        )

        schema_path = ws.root / "recon.yaml"
        assert schema_path.exists()
        data = yaml.safe_load(schema_path.read_text())
        assert data["domain"] == "Developer Tools"
        assert data["identity"]["company_name"] == "Acme Corp"


class TestWorkspaceOpen:
    def test_opens_existing_workspace(self, tmp_workspace: Path) -> None:
        ws = Workspace.open(tmp_workspace)

        assert ws.root == tmp_workspace
        assert ws.schema is not None
        assert ws.schema.domain == "Developer Tools"

    def test_raises_on_missing_schema(self, tmp_path: Path) -> None:
        import pytest

        with pytest.raises(FileNotFoundError):
            Workspace.open(tmp_path)


class TestProfileManagement:
    def test_creates_competitor_profile(self, tmp_workspace: Path) -> None:
        ws = Workspace.open(tmp_workspace)

        profile_path = ws.create_profile("GitHub Copilot")

        assert profile_path.exists()
        assert profile_path.parent.name == "competitors"

    def test_profile_has_frontmatter(self, tmp_workspace: Path) -> None:
        ws = Workspace.open(tmp_workspace)

        profile_path = ws.create_profile("GitHub Copilot")

        import frontmatter

        post = frontmatter.load(str(profile_path))
        assert post["name"] == "GitHub Copilot"
        assert post["type"] == "competitor"
        assert post["research_status"] == "scaffold"

    def test_profile_uses_slugified_filename(self, tmp_workspace: Path) -> None:
        ws = Workspace.open(tmp_workspace)

        profile_path = ws.create_profile("GitHub Copilot")

        assert profile_path.name == "github-copilot.md"

    def test_creates_own_product_profile(self, tmp_workspace: Path) -> None:
        ws = Workspace.open(tmp_workspace)

        profile_path = ws.create_profile("Acme IDE", own_product=True)

        import frontmatter

        post = frontmatter.load(str(profile_path))
        assert post["type"] == "own_product"

    def test_lists_profiles(self, tmp_workspace: Path) -> None:
        ws = Workspace.open(tmp_workspace)
        ws.create_profile("Alpha")
        ws.create_profile("Beta")

        profiles = ws.list_profiles()

        assert len(profiles) == 2
        names = {p["name"] for p in profiles}
        assert names == {"Alpha", "Beta"}

    def test_rejects_duplicate_profile(self, tmp_workspace: Path) -> None:
        import pytest

        ws = Workspace.open(tmp_workspace)
        ws.create_profile("GitHub Copilot")

        with pytest.raises(FileExistsError):
            ws.create_profile("GitHub Copilot")

    def test_reads_profile(self, tmp_workspace: Path) -> None:
        ws = Workspace.open(tmp_workspace)
        ws.create_profile("GitHub Copilot")

        profile = ws.read_profile("github-copilot")

        assert profile["name"] == "GitHub Copilot"
        assert profile["type"] == "competitor"

    def test_read_missing_profile_returns_none(self, tmp_workspace: Path) -> None:
        ws = Workspace.open(tmp_workspace)

        assert ws.read_profile("nonexistent") is None
