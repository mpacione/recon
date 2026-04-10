"""WelcomeScreen for recon TUI.

Entry point when no workspace is specified. Lets the user create a new
project, open an existing one, or resume from a recent project.
Recent projects stored in ~/.recon/recent.json.
"""

from __future__ import annotations

import datetime
import json
from dataclasses import dataclass
from pathlib import Path

from textual.app import ComposeResult  # noqa: TCH002 -- used at runtime
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.screen import Screen
from textual.widgets import Button, Input, Static

from recon.logging import get_logger

_log = get_logger(__name__)


@dataclass
class RecentProject:
    path: str
    name: str
    last_opened: str

    @classmethod
    def from_path(cls, project_path: Path, name: str | None = None) -> RecentProject:
        return cls(
            path=str(project_path),
            name=name or project_path.name,
            last_opened=datetime.datetime.now(tz=datetime.UTC).isoformat(),
        )


_DEFAULT_MAX_ENTRIES = 10


class RecentProjectsManager:
    """Load/save/add recent projects to a JSON file."""

    def __init__(self, json_path: Path, max_entries: int = _DEFAULT_MAX_ENTRIES) -> None:
        self._json_path = json_path
        self._max_entries = max_entries

    def load(self) -> list[RecentProject]:
        if not self._json_path.exists():
            return []
        try:
            data = json.loads(self._json_path.read_text())
        except (json.JSONDecodeError, OSError) as exc:
            _log.warning("recent projects load failed: %s", exc)
            return []
        if not isinstance(data, list):
            _log.warning(
                "recent projects file is not a JSON list, got %s",
                type(data).__name__,
            )
            return []

        projects: list[RecentProject] = []
        dropped = 0
        for entry in data:
            if not isinstance(entry, dict):
                dropped += 1
                continue
            try:
                projects.append(
                    RecentProject(
                        path=entry["path"],
                        name=entry["name"],
                        last_opened=entry["last_opened"],
                    ),
                )
            except KeyError as missing:
                _log.warning(
                    "recent projects entry missing field %s; got keys %s",
                    missing,
                    sorted(entry.keys()),
                )
                dropped += 1
        if dropped:
            _log.info(
                "recent projects: kept %d, dropped %d malformed entries",
                len(projects),
                dropped,
            )
        return projects

    def save(self, projects: list[RecentProject]) -> None:
        self._json_path.parent.mkdir(parents=True, exist_ok=True)
        data = [{"path": p.path, "name": p.name, "last_opened": p.last_opened} for p in projects]
        self._json_path.write_text(json.dumps(data, indent=2))

    def add(self, project_path: Path, name: str) -> None:
        projects = self.load()
        path_str = str(project_path)
        projects = [p for p in projects if p.path != path_str]
        new_entry = RecentProject.from_path(project_path, name)
        projects.insert(0, new_entry)
        projects = projects[: self._max_entries]
        self.save(projects)


_DEFAULT_RECENT_PATH = Path.home() / ".recon" / "recent.json"


class WelcomeScreen(Screen):
    """Workspace picker: new, open, or recent project."""

    class WorkspaceSelected(Message):
        def __init__(self, path: str) -> None:
            super().__init__()
            self.path = path

    class NewProjectRequested(Message):
        def __init__(self, path: str) -> None:
            super().__init__()
            self.path = path

    DEFAULT_CSS = """
    WelcomeScreen {
        align: center middle;
    }
    #welcome-container {
        width: 60;
        height: auto;
        padding: 2 4;
        border: solid #3a3a3a;
        background: #0d0d0d;
    }
    .action-row {
        height: auto;
        margin: 1 0;
        layout: horizontal;
    }
    .action-row Button {
        margin: 0 1 0 0;
    }
    #recent-section {
        margin: 1 0 0 0;
        height: auto;
    }
    .recent-item {
        width: 100%;
        height: auto;
        margin: 0 0 1 0;
    }
    """

    def __init__(self, recent_projects_path: Path = _DEFAULT_RECENT_PATH) -> None:
        super().__init__()
        self._recent_path = recent_projects_path
        self._manager = RecentProjectsManager(self._recent_path)

    def compose(self) -> ComposeResult:
        with Vertical(id="welcome-container"):
            yield Static("[bold #e0a044]recon[/]", classes="title")
            yield Static("[#a89984]competitive intelligence[/]")
            yield Static("")
            with Horizontal(classes="action-row"):
                yield Button("New Project", id="btn-new", variant="primary")
                yield Button("Open Existing", id="btn-open")
            yield Static("")
            with Vertical(id="recent-section"):
                yield Static("[bold #e0a044]RECENT PROJECTS[/]")
                yield from self._compose_recent_list()

    def _compose_recent_list(self):
        projects = self._manager.load()
        if not projects:
            yield Static("[#a89984]No recent projects[/]", id="recent-empty")
            return
        for i, project in enumerate(projects):
            display_path = project.path.replace(str(Path.home()), "~")
            yield Button(
                f"{project.name}  —  {display_path}",
                id=f"btn-recent-{i}",
                classes="recent-item",
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        _log.info("WelcomeScreen button pressed id=%s", button_id)
        if button_id == "btn-new":
            self._show_new_input()
        elif button_id == "btn-open":
            self._show_open_input()
        elif button_id.startswith("btn-recent-"):
            self._open_recent(button_id)

    def _open_recent(self, button_id: str) -> None:
        try:
            index = int(button_id.removeprefix("btn-recent-"))
        except ValueError:
            return
        projects = self._manager.load()
        if 0 <= index < len(projects):
            path = projects[index].path
            _log.info("WelcomeScreen opening recent path=%s", path)
            self.post_message(self.WorkspaceSelected(path))

    def _show_new_input(self) -> None:
        container = self.query_one("#welcome-container", Vertical)
        existing = self.query("#new-path-input")
        if existing:
            return
        default_path = str(Path.home() / "recon" / "new-project")
        path_input = Input(
            value=default_path,
            placeholder="Directory for new project",
            id="new-path-input",
        )
        container.mount(path_input)
        path_input.focus()

    def _show_open_input(self) -> None:
        container = self.query_one("#welcome-container", Vertical)
        existing = self.query("#open-path-input")
        if existing:
            return
        path_input = Input(
            placeholder="Path to workspace directory",
            id="open-path-input",
        )
        container.mount(path_input)
        path_input.focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        path_str = event.value.strip()
        _log.debug(
            "WelcomeScreen input submitted id=%s value=%s",
            event.input.id,
            path_str,
        )
        if not path_str:
            return
        if event.input.id == "open-path-input":
            self.post_message(self.WorkspaceSelected(path_str))
        elif event.input.id == "new-path-input":
            self.post_message(self.NewProjectRequested(path_str))
