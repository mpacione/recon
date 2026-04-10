"""Tests for WelcomeScreen and RecentProjectsManager."""

from __future__ import annotations

from pathlib import Path

import pytest
from textual.widgets import Button, Static

from recon.tui.screens.welcome import (
    RecentProject,
    RecentProjectsManager,
    WelcomeScreen,
)


class TestRecentProject:
    def test_creates_from_path(self) -> None:
        project = RecentProject.from_path(Path("/tmp/acme-ci"), "Acme CI Research")
        assert project.path == "/tmp/acme-ci"
        assert project.name == "Acme CI Research"
        assert project.last_opened != ""

    def test_creates_with_name_from_directory(self) -> None:
        project = RecentProject.from_path(Path("/tmp/acme-ci"))
        assert project.name == "acme-ci"


class TestRecentProjectsManager:
    def test_load_returns_empty_when_no_file(self, tmp_path: Path) -> None:
        manager = RecentProjectsManager(tmp_path / "recent.json")
        assert manager.load() == []

    def test_save_and_load_roundtrip(self, tmp_path: Path) -> None:
        json_path = tmp_path / "recent.json"
        manager = RecentProjectsManager(json_path)

        project = RecentProject.from_path(Path("/tmp/acme"), "Acme")
        manager.save([project])

        loaded = manager.load()
        assert len(loaded) == 1
        assert loaded[0].path == "/tmp/acme"
        assert loaded[0].name == "Acme"

    def test_add_deduplicates_by_path(self, tmp_path: Path) -> None:
        json_path = tmp_path / "recent.json"
        manager = RecentProjectsManager(json_path)

        manager.add(Path("/tmp/acme"), "Acme")
        manager.add(Path("/tmp/acme"), "Acme Updated")

        loaded = manager.load()
        assert len(loaded) == 1
        assert loaded[0].name == "Acme Updated"

    def test_add_caps_at_max_entries(self, tmp_path: Path) -> None:
        json_path = tmp_path / "recent.json"
        manager = RecentProjectsManager(json_path, max_entries=3)

        for i in range(5):
            manager.add(Path(f"/tmp/project-{i}"), f"Project {i}")

        loaded = manager.load()
        assert len(loaded) == 3
        assert loaded[0].path == "/tmp/project-4"
        assert loaded[2].path == "/tmp/project-2"

    def test_add_moves_existing_to_top(self, tmp_path: Path) -> None:
        json_path = tmp_path / "recent.json"
        manager = RecentProjectsManager(json_path)

        manager.add(Path("/tmp/alpha"), "Alpha")
        manager.add(Path("/tmp/beta"), "Beta")
        manager.add(Path("/tmp/alpha"), "Alpha")

        loaded = manager.load()
        assert loaded[0].path == "/tmp/alpha"
        assert loaded[1].path == "/tmp/beta"

    def test_load_handles_corrupt_json(self, tmp_path: Path) -> None:
        json_path = tmp_path / "recent.json"
        json_path.write_text("not valid json{{{")

        manager = RecentProjectsManager(json_path)
        assert manager.load() == []

    def test_creates_parent_directory(self, tmp_path: Path) -> None:
        json_path = tmp_path / "subdir" / "recent.json"
        manager = RecentProjectsManager(json_path)

        manager.add(Path("/tmp/acme"), "Acme")

        assert json_path.exists()
        loaded = manager.load()
        assert len(loaded) == 1


class TestWelcomeScreen:
    @pytest.fixture()
    def welcome_app(self, tmp_path: Path):
        from textual.app import App, ComposeResult

        json_path = tmp_path / "recent.json"

        class WelcomeTestApp(App):
            CSS = """
            Screen { background: #000000; }
            """

            def compose(self) -> ComposeResult:
                yield WelcomeScreen(recent_projects_path=json_path)

        return WelcomeTestApp(), json_path

    async def test_mounts_with_new_and_open_buttons(self, welcome_app) -> None:
        app, _ = welcome_app
        async with app.run_test(size=(120, 40)):
            assert app.query_one("#btn-new", Button)
            assert app.query_one("#btn-open", Button)

    async def test_shows_no_recent_message_when_empty(self, welcome_app) -> None:
        app, _ = welcome_app
        async with app.run_test(size=(120, 40)):
            recent_label = app.query_one("#recent-empty", Static)
            assert "No recent projects" in str(recent_label.content)

    async def test_shows_recent_projects(self, welcome_app) -> None:
        app, json_path = welcome_app
        manager = RecentProjectsManager(json_path)
        manager.add(Path("/tmp/acme"), "Acme CI")
        manager.add(Path("/tmp/fintech"), "Fintech Scan")

        async with app.run_test(size=(120, 40)):
            recent_items = app.query(".recent-item")
            assert len(recent_items) == 2


class TestWelcomeScreenWiring:
    async def test_open_button_shows_path_input(self, tmp_path: Path) -> None:
        from textual.app import App, ComposeResult
        from textual.widgets import Input

        json_path = tmp_path / "recent.json"

        class TestApp(App):
            CSS = "Screen { background: #000000; }"

            def compose(self) -> ComposeResult:
                yield WelcomeScreen(recent_projects_path=json_path)

        app = TestApp()
        async with app.run_test(size=(120, 40)) as pilot:
            app.query_one("#btn-open", Button).press()
            await pilot.pause()
            path_input = app.query_one("#open-path-input", Input)
            assert path_input is not None

    async def test_open_path_submit_posts_message(self, tmp_workspace: Path) -> None:
        from textual.app import App, ComposeResult
        from textual.widgets import Input

        json_path = tmp_workspace.parent / "recent.json"
        workspace_opened: list[str] = []

        class TestApp(App):
            CSS = "Screen { background: #000000; }"

            def compose(self) -> ComposeResult:
                yield WelcomeScreen(recent_projects_path=json_path)

            def on_welcome_screen_workspace_selected(self, event: WelcomeScreen.WorkspaceSelected) -> None:
                workspace_opened.append(event.path)

        app = TestApp()
        async with app.run_test(size=(120, 40)) as pilot:
            app.query_one("#btn-open", Button).press()
            await pilot.pause()
            path_input = app.query_one("#open-path-input", Input)
            path_input.value = str(tmp_workspace)
            path_input.post_message(Input.Submitted(path_input, str(tmp_workspace)))
            await pilot.pause()
            assert len(workspace_opened) == 1
            assert workspace_opened[0] == str(tmp_workspace)
