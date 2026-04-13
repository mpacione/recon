"""Tests for API key management.

Keys are loaded from workspace .env and global ~/.recon/.env.
Saved keys persist across sessions. Validation checks key format.
"""

from pathlib import Path


class TestLoadApiKeys:
    def test_loads_from_workspace_env(self, tmp_path: Path) -> None:
        from recon.api_keys import load_api_keys

        env_path = tmp_path / ".env"
        env_path.write_text("ANTHROPIC_API_KEY=sk-ant-test123\n")

        keys = load_api_keys(workspace_root=tmp_path)

        assert keys["anthropic"] == "sk-ant-test123"

    def test_loads_multiple_keys(self, tmp_path: Path) -> None:
        from recon.api_keys import load_api_keys

        env_path = tmp_path / ".env"
        env_path.write_text(
            "ANTHROPIC_API_KEY=sk-ant-test123\n"
            "GOOGLE_AI_API_KEY=AIza-test456\n"
        )

        keys = load_api_keys(workspace_root=tmp_path)

        assert keys["anthropic"] == "sk-ant-test123"
        assert keys["google_ai"] == "AIza-test456"

    def test_falls_back_to_global_env(self, tmp_path: Path) -> None:
        from recon.api_keys import load_api_keys

        global_dir = tmp_path / "global"
        global_dir.mkdir()
        (global_dir / ".env").write_text("ANTHROPIC_API_KEY=sk-ant-global\n")

        workspace = tmp_path / "workspace"
        workspace.mkdir()

        keys = load_api_keys(workspace_root=workspace, global_env_dir=global_dir)

        assert keys["anthropic"] == "sk-ant-global"

    def test_workspace_env_takes_precedence_over_global(self, tmp_path: Path) -> None:
        from recon.api_keys import load_api_keys

        global_dir = tmp_path / "global"
        global_dir.mkdir()
        (global_dir / ".env").write_text("ANTHROPIC_API_KEY=sk-ant-global\n")

        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / ".env").write_text("ANTHROPIC_API_KEY=sk-ant-local\n")

        keys = load_api_keys(workspace_root=workspace, global_env_dir=global_dir)

        assert keys["anthropic"] == "sk-ant-local"

    def test_returns_empty_when_no_env_files(self, tmp_path: Path) -> None:
        from recon.api_keys import load_api_keys

        # Use a fake global dir so real ~/.recon/.env doesn't interfere
        fake_global = tmp_path / "no-global"
        keys = load_api_keys(workspace_root=tmp_path, global_env_dir=fake_global)

        assert keys == {}

    def test_ignores_comments_and_blank_lines(self, tmp_path: Path) -> None:
        from recon.api_keys import load_api_keys

        (tmp_path / ".env").write_text(
            "# This is a comment\n"
            "\n"
            "ANTHROPIC_API_KEY=sk-ant-test\n"
            "# Another comment\n"
        )

        keys = load_api_keys(workspace_root=tmp_path)

        assert keys["anthropic"] == "sk-ant-test"

    def test_also_reads_env_vars(self, tmp_path: Path, monkeypatch) -> None:
        from recon.api_keys import load_api_keys

        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-fromenv")

        keys = load_api_keys(workspace_root=tmp_path)

        assert keys["anthropic"] == "sk-ant-fromenv"


class TestSaveApiKey:
    def test_saves_to_workspace_env(self, tmp_path: Path) -> None:
        from recon.api_keys import load_api_keys, save_api_key

        save_api_key("anthropic", "sk-ant-new123", workspace_root=tmp_path)

        keys = load_api_keys(workspace_root=tmp_path)
        assert keys["anthropic"] == "sk-ant-new123"

    def test_preserves_existing_keys(self, tmp_path: Path) -> None:
        from recon.api_keys import load_api_keys, save_api_key

        (tmp_path / ".env").write_text("GOOGLE_AI_API_KEY=AIza-existing\n")

        save_api_key("anthropic", "sk-ant-new123", workspace_root=tmp_path)

        keys = load_api_keys(workspace_root=tmp_path)
        assert keys["anthropic"] == "sk-ant-new123"
        assert keys["google_ai"] == "AIza-existing"

    def test_overwrites_existing_key(self, tmp_path: Path) -> None:
        from recon.api_keys import load_api_keys, save_api_key

        (tmp_path / ".env").write_text("ANTHROPIC_API_KEY=sk-ant-old\n")

        save_api_key("anthropic", "sk-ant-new", workspace_root=tmp_path)

        keys = load_api_keys(workspace_root=tmp_path)
        assert keys["anthropic"] == "sk-ant-new"

    def test_saves_to_global_env_for_future_projects(self, tmp_path: Path) -> None:
        from recon.api_keys import load_api_keys, save_api_key

        workspace = tmp_path / "project1"
        workspace.mkdir()
        global_dir = tmp_path / "global"

        save_api_key(
            "anthropic", "sk-ant-global123",
            workspace_root=workspace,
            global_env_dir=global_dir,
        )

        # Key should be in workspace .env
        keys_ws = load_api_keys(workspace_root=workspace)
        assert keys_ws["anthropic"] == "sk-ant-global123"

        # Key should ALSO be in global .env
        assert (global_dir / ".env").exists()
        new_project = tmp_path / "project2"
        new_project.mkdir()
        keys_new = load_api_keys(workspace_root=new_project, global_env_dir=global_dir)
        assert keys_new["anthropic"] == "sk-ant-global123"


class TestMaskApiKey:
    def test_masks_middle_of_key(self) -> None:
        from recon.api_keys import mask_api_key

        masked = mask_api_key("sk-ant-api03-abcdefghijklmnop")

        assert masked.startswith("sk-ant")
        assert masked.endswith("mnop")
        assert "···" in masked

    def test_returns_empty_for_empty(self) -> None:
        from recon.api_keys import mask_api_key

        assert mask_api_key("") == ""

    def test_short_key_still_masked(self) -> None:
        from recon.api_keys import mask_api_key

        masked = mask_api_key("short")
        assert "···" in masked
