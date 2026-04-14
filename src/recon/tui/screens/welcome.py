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
from textual.binding import Binding
from textual.containers import Vertical
from textual.message import Message
from textual.widgets import Input, Static

from recon.logging import get_logger
from recon.tui.shell import ReconScreen

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


_RECON_BANNER = """\
[bold #e0a044]┌─────────────────────────────────────┐[/]
[bold #e0a044]│  ▄▄▄▄    ▄▄▄▄  ▄▄▄▄  ▄▄▄▄  ▄▄  ▄▄  │[/]
[bold #e0a044]│  ██  ██ ██    ██     ██  ██ ██▄ ██  │[/]
[bold #e0a044]│  ██▀▀█▄ ██▀▀  ██     ██  ██ ██ ▀██  │[/]
[bold #e0a044]│  ██  ██  ▀▀██  ██▄▄  ██▄▄██ ██  ██  │[/]
[bold #e0a044]│         recon  v0.2.0+              │[/]
[bold #e0a044]└─────────────────────────────────────┘[/]"""


class WelcomeScreen(ReconScreen):
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
        background: #000000;
    }
    #welcome-body {
        /* top-align so the banner stays visible and any newly-
           mounted Input below the recents list doesn't get clipped
           off the bottom when content grows past the viewport. */
        align: center top;
        height: 1fr;
        overflow-y: auto;
    }
    #welcome-container {
        width: 70;
        height: auto;
        padding: 1 3;
        border: solid #3a3a3a;
        background: #0d0d0d;
    }
    #recent-section {
        margin: 1 0 0 0;
        height: auto;
    }
    .recent-item {
        width: 100%;
        height: auto;
    }
    """

    BINDINGS = [
        Binding("n", "new", "new project"),
        Binding("o", "open", "open existing"),
        Binding("1", "open_recent(0)", "recent 1", show=False),
        Binding("2", "open_recent(1)", "recent 2", show=False),
        Binding("3", "open_recent(2)", "recent 3", show=False),
        Binding("4", "open_recent(3)", "recent 4", show=False),
        Binding("5", "open_recent(4)", "recent 5", show=False),
        Binding("6", "open_recent(5)", "recent 6", show=False),
        Binding("7", "open_recent(6)", "recent 7", show=False),
        Binding("8", "open_recent(7)", "recent 8", show=False),
        Binding("9", "open_recent(8)", "recent 9", show=False),
    ]

    show_log_pane = False
    show_activity_feed = False
    show_run_status_bar = False

    keybind_hints = (
        "[#e0a044]n[/] new · [#e0a044]o[/] open · [#e0a044]1-9[/] recent · "
        "[#e0a044]q[/] quit · [#e0a044]?[/] help"
    )

    def __init__(self, recent_projects_path: Path | None = None) -> None:
        super().__init__()
        # Read the module-level default at call time, not definition
        # time. Monkeypatching the module variable (the standard test
        # isolation pattern) would otherwise not affect screens
        # constructed without an explicit path.
        self._recent_path = recent_projects_path or _DEFAULT_RECENT_PATH
        self._manager = RecentProjectsManager(self._recent_path)

    def compose_body(self) -> ComposeResult:
        with Vertical(id="welcome-body"), Vertical(id="welcome-container"):
            yield Static(_RECON_BANNER, id="welcome-banner")
            yield Static("[#a89984]competitive intelligence research[/]")
            yield Static("")
            yield Static(
                "Press [#e0a044]n[/] to create a new project,\n"
                "or press [#e0a044]o[/] to open an existing workspace.",
                id="welcome-actions-hint",
            )
            yield Static("")
            with Vertical(id="recent-section"):
                yield Static("[bold #e0a044]── RECENT PROJECTS ──[/]")
                yield from self._compose_recent_list()

    def _compose_recent_list(self):
        projects = self._manager.load()
        if not projects:
            yield Static("[#a89984]No recent projects[/]", id="recent-empty")
            return
        for i, project in enumerate(projects[:9]):
            display_path = project.path.replace(str(Path.home()), "~")
            status = self._project_status(project.path)
            yield Static(
                f"  [#e0a044]{i + 1}[/]  {status} [#efe5c0]{project.name}[/]"
                f"  [#3a3a3a]·[/]  [#a89984]{display_path}[/]",
                id=f"recent-item-{i}",
                classes="recent-item",
            )

    @staticmethod
    def _project_status(path_str: str) -> str:
        project_path = Path(path_str)
        if not project_path.exists():
            return "[#cc241d]missing[/]"
        output_dir = project_path / "output"
        if output_dir.exists() and any(output_dir.iterdir()):
            return "[#98971a]done[/]   "
        if (project_path / "recon.yaml").exists():
            return "[#d79921]ready[/]  "
        return "[#a89984]new[/]    "

    def action_new(self) -> None:
        _log.info("WelcomeScreen action_new")
        self._show_new_input()

    def action_open(self) -> None:
        _log.info("WelcomeScreen action_open")
        self._show_open_input()

    def action_open_recent(self, index: int) -> None:
        projects = self._manager.load()
        if 0 <= index < len(projects):
            path = projects[index].path
            _log.info("WelcomeScreen opening recent index=%d path=%s", index, path)
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
        self._scroll_input_into_view(path_input)

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
        self._scroll_input_into_view(path_input)

    def _scroll_input_into_view(self, widget: Input) -> None:
        """Scroll the welcome body so a freshly mounted Input is visible.

        Without this, screens with a full recents list push the Input
        below the viewport fold and the user sees no visible change
        when they press ``n`` / ``o``. ``scroll_visible`` walks
        ancestor scrollables until the widget is in frame.
        """
        # Defer a tick so the mount completes before we scroll.
        self.call_after_refresh(widget.scroll_visible, animate=False)

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
