"""Tests for WelcomeScreen and RecentProjectsManager."""

from __future__ import annotations

from pathlib import Path

import pytest
from textual.binding import Binding
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

    async def test_renders_primary_action_buttons(self, welcome_app) -> None:
        app, _ = welcome_app
        async with app.run_test(size=(120, 40)):
            assert app.query_one("#welcome-open", Button) is not None
            assert app.query_one("#welcome-new", Button) is not None

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

    async def test_renders_recon_banner_in_intro(self, welcome_app) -> None:
        app, _ = welcome_app
        async with app.run_test(size=(120, 40)):
            intro = app.query_one("#welcome-intro", Static)
            assert "███████" in str(intro.content)


class TestWelcomeScreenKeybindings:
    """Welcome's actions are exposed via keybindings.

    - ``n`` opens the new-project modal
    - ``o`` opens the open-project modal
    - ``1``..``9`` open the corresponding recent project
    """

    async def test_screen_declares_new_open_keybindings(self, tmp_path: Path) -> None:
        from textual.app import App, ComposeResult

        json_path = tmp_path / "recent.json"

        class TestApp(App):
            CSS = "Screen { background: #000000; }"

            def compose(self) -> ComposeResult:
                yield WelcomeScreen(recent_projects_path=json_path)

        app = TestApp()
        async with app.run_test(size=(120, 40)):
            screen = app.query_one(WelcomeScreen)
            keys = {b.key for b in screen.BINDINGS if isinstance(b, Binding)}
            assert "n" in keys
            assert "o" in keys

    async def test_action_new_opens_name_modal(self, tmp_path: Path) -> None:
        from textual.app import App, ComposeResult
        from textual.widgets import Input

        json_path = tmp_path / "recent.json"

        class TestApp(App):
            CSS = "Screen { background: #000000; }"

            def compose(self) -> ComposeResult:
                return ()

            def on_mount(self) -> None:
                self.push_screen(WelcomeScreen(recent_projects_path=json_path))

        app = TestApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, WelcomeScreen)
            screen.action_new()
            await pilot.pause()
            assert app.screen.query_one("#new-project-name-input", Input) is not None

    async def test_action_open_opens_path_modal(self, tmp_path: Path) -> None:
        from textual.app import App, ComposeResult
        from textual.widgets import Input

        json_path = tmp_path / "recent.json"

        class TestApp(App):
            CSS = "Screen { background: #000000; }"

            def compose(self) -> ComposeResult:
                return ()

            def on_mount(self) -> None:
                self.push_screen(WelcomeScreen(recent_projects_path=json_path))

        app = TestApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, WelcomeScreen)
            screen.action_open()
            await pilot.pause()
            assert app.screen.query_one("#open-workspace-path-input", Input) is not None

    async def test_action_open_recent_posts_workspace_selected(
        self, tmp_path: Path
    ) -> None:
        """Pressing a digit key (1..9) opens the matching recent
        project. Implementation detail: each digit binds to
        ``action_open_recent`` with the index as a parameter.
        """
        from textual.app import App, ComposeResult

        json_path = tmp_path / "recent.json"
        manager = RecentProjectsManager(json_path)
        alpha = tmp_path / "alpha"
        beta = tmp_path / "beta"
        alpha.mkdir()
        beta.mkdir()
        manager.add(alpha, "Alpha")
        manager.add(beta, "Beta")

        opened: list[str] = []

        class TestApp(App):
            CSS = "Screen { background: #000000; }"

            def compose(self) -> ComposeResult:
                yield WelcomeScreen(recent_projects_path=json_path)

            def on_welcome_screen_workspace_selected(
                self, event: WelcomeScreen.WorkspaceSelected
            ) -> None:
                opened.append(event.path)

        app = TestApp()
        async with app.run_test(size=(120, 40)) as pilot:
            screen = app.query_one(WelcomeScreen)
            # Open the second recent (index 1) -- which is "Alpha"
            # because beta was added second so it's at index 0
            screen.action_open_recent(1)
            await pilot.pause()
            assert opened == [str(alpha)]

    async def test_keybind_hints_mention_new_open(self, tmp_path: Path) -> None:
        from textual.app import App, ComposeResult

        json_path = tmp_path / "recent.json"

        class TestApp(App):
            CSS = "Screen { background: #000000; }"

            def compose(self) -> ComposeResult:
                yield WelcomeScreen(recent_projects_path=json_path)

        app = TestApp()
        async with app.run_test(size=(120, 40)):
            screen = app.query_one(WelcomeScreen)
            hints = screen.keybind_hints
            assert "n" in hints
            assert "o" in hints
            assert "new" in hints
            assert "open" in hints


class TestWelcomeScreenWiring:
    """Wiring tests that exercise the modal submit flow."""

    async def test_new_name_submit_posts_message(self, tmp_path: Path) -> None:
        from textual.app import App, ComposeResult
        from textual.widgets import Input

        json_path = tmp_path / "recent.json"
        new_requests: list[str] = []

        class TestApp(App):
            CSS = "Screen { background: #000000; }"

            def compose(self) -> ComposeResult:
                return ()

            def on_mount(self) -> None:
                self.push_screen(WelcomeScreen(recent_projects_path=json_path))

            def on_welcome_screen_new_project_requested(
                self, event: WelcomeScreen.NewProjectRequested
            ) -> None:
                new_requests.append(event.path)

        app = TestApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, WelcomeScreen)
            screen.action_new()
            await pilot.pause()
            path_input = app.screen.query_one("#new-project-name-input", Input)
            path_input.value = "My Project"
            path_input.post_message(
                Input.Submitted(path_input, "My Project")
            )
            await pilot.pause()
            assert len(new_requests) == 1
            assert "my-project" in new_requests[0]

    async def test_open_path_submit_posts_message(self, tmp_workspace: Path) -> None:
        from textual.app import App, ComposeResult
        from textual.widgets import Input

        json_path = tmp_workspace.parent / "recent.json"
        workspace_opened: list[str] = []

        class TestApp(App):
            CSS = "Screen { background: #000000; }"

            def compose(self) -> ComposeResult:
                return ()

            def on_mount(self) -> None:
                self.push_screen(WelcomeScreen(recent_projects_path=json_path))

            def on_welcome_screen_workspace_selected(
                self, event: WelcomeScreen.WorkspaceSelected
            ) -> None:
                workspace_opened.append(event.path)

        app = TestApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, WelcomeScreen)
            screen.action_open()
            await pilot.pause()
            path_input = app.screen.query_one("#open-workspace-path-input", Input)
            path_input.value = str(tmp_workspace)
            path_input.post_message(
                Input.Submitted(path_input, str(tmp_workspace))
            )
            await pilot.pause()
            assert len(workspace_opened) == 1
            assert workspace_opened[0] == str(tmp_workspace)
