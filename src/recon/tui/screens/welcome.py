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
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import Button, Input, Static

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
[bold #DDEDC4]┌─────────────────────────────────────┐[/]
[bold #DDEDC4]│  ▄▄▄▄    ▄▄▄▄  ▄▄▄▄  ▄▄▄▄  ▄▄  ▄▄  │[/]
[bold #DDEDC4]│  ██  ██ ██    ██     ██  ██ ██▄ ██  │[/]
[bold #DDEDC4]│  ██▀▀█▄ ██▀▀  ██     ██  ██ ██ ▀██  │[/]
[bold #DDEDC4]│  ██  ██  ▀▀██  ██▄▄  ██▄▄██ ██  ██  │[/]
[bold #DDEDC4]│         recon  v0.2.0+              │[/]
[bold #DDEDC4]└─────────────────────────────────────┘[/]"""


class WelcomeScreen(ReconScreen):
    """Workspace picker — v4 RECON tab (pre-workspace home).

    Maps to the RECON tab in the numbered nav: ``tab_key='recon'`` so
    the TabStrip highlights ``▌[0] RECON``. Once the user picks a
    workspace, navigation moves to the in-workspace dashboard (which
    also has ``tab_key='recon'`` but shows workspace-scoped stats).
    """

    tab_key = "recon"

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
        /* Top-aligned full-width home view. No fixed narrow container —
         * the v4 Card and intro blurb reach the max 110-col width
         * themselves. */
        height: 1fr;
        overflow-y: auto;
        padding: 1 0 1 0;
    }
    #welcome-intro {
        height: auto;
        padding: 0 1;
        margin: 0 0 1 0;
    }
    #welcome-projects {
        height: auto;
        border: solid #3a3a3a;
        padding: 0 1;
        margin: 0;
    }
    #welcome-projects-head {
        height: auto;
        color: #a59a86;
        padding: 0 0 1 0;
    }
    #welcome-projects-body {
        height: auto;
        padding: 0;
    }
    .proj-row {
        height: 1;
        padding: 0 1;
    }
    .proj-row.is-selected {
        background: #DDEDC4;
        color: #000000;
    }
    #welcome-projects-foot {
        height: auto;
        margin: 1 0 0 0;
        padding: 1 0 0 0;
        border-top: solid #3a3a3a;
    }
    #welcome-foot-copy {
        width: 1fr;
        color: #787266;
    }
    #welcome-input-slot {
        height: auto;
        margin: 1 0 0 0;
    }
    """

    BINDINGS = [
        Binding("n", "new", "new project"),
        Binding("o", "open", "open existing"),
        # v4 row nav — match the web UI's ↑↓ + j/k selection model.
        Binding("j", "cursor_down", "down", show=False),
        Binding("k", "cursor_up", "up", show=False),
        Binding("down", "cursor_down", "down", show=False),
        Binding("up", "cursor_up", "up", show=False),
        Binding("enter", "open_selected", "open", show=False),
        # Numeric fast-jump — same contract as before, still fires
        # `action_open_recent` so the MISSING-workspace guard applies.
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
    # Welcome has no workspace loaded, so the "recon · no workspace"
    # header bar is just noise. TabStrip above carries the screen
    # identity.
    show_header_bar = False

    keybind_hints = (
        "[#DDEDC4]↑↓[/] nav · [#DDEDC4]↲[/] open · [#DDEDC4]n[/] new · "
        "[#DDEDC4]o[/] open path · [#DDEDC4]1-9[/] recent · [#DDEDC4]q[/] quit"
    )

    def __init__(self, recent_projects_path: Path | None = None) -> None:
        super().__init__()
        # Read the module-level default at call time, not definition
        # time. Monkeypatching the module variable (the standard test
        # isolation pattern) would otherwise not affect screens
        # constructed without an explicit path.
        self._recent_path = recent_projects_path or _DEFAULT_RECENT_PATH
        self._manager = RecentProjectsManager(self._recent_path)
        # Index of the currently-highlighted row in the recents list.
        # Zero-based; always points at a valid row when the list is
        # non-empty. Kept as screen state (not reactive) so re-renders
        # are driven explicitly via ``_refresh_selection``.
        self._selected_index: int = 0

    def compose_body(self) -> ComposeResult:
        with Vertical(id="welcome-body"):
            yield Static(
                (
                    "[#DDEDC4]▌[/] [#DDEDC4]Automated grounded competitive intelligence research.[/]  "
                    "[#a59a86]Recon orchestrates LLM agents to discover competitors, research "
                    "them section-by-section against a structured schema, and synthesize the "
                    "results into thematic analyses and executive summaries — all stored "
                    "locally as Obsidian-compatible markdown.[/]"
                ),
                id="welcome-intro",
            )

            projects = self._manager.load()
            meta = (
                f"{len(projects)} project{'s' if len(projects) != 1 else ''}"
                if projects
                else "no projects yet"
            )

            with Vertical(id="welcome-projects"):
                yield Static(
                    f"[#a59a86]PROJECTS[/] [#686359]·[/] [#787266]{meta}[/]",
                    id="welcome-projects-head",
                )
                with Vertical(id="welcome-projects-body"):
                    yield from self._compose_project_rows(projects)
                with Horizontal(id="welcome-projects-foot"):
                    yield Static("[#787266][↑↓][/][#686359] keyboard nav[/]", id="welcome-foot-copy")
                    yield Button("OPEN [↲]", id="welcome-open")
                    yield Button("NEW [N]", id="welcome-new", variant="primary")

            yield Vertical(id="welcome-input-slot")

    def _compose_project_rows(self, projects):
        if not projects:
            yield Static(
                "[#787266]No recent projects. Press [#DDEDC4]n[/] to create one, "
                "or [#DDEDC4]o[/] to open an existing workspace.[/]",
                id="recent-empty",
            )
            return

        # Header row — extra leading space matches the width of the
        # "▌ " selection marker so the columns line up with the row
        # bodies below.
        yield Static(
            "[#787266]       #  NAME                    STATUS     DATE       PATH[/]",
            classes="proj-row",
        )
        for i, project in enumerate(projects[:9]):
            yield Static(
                self._render_project_row(i, project, selected=(i == self._selected_index)),
                id=f"recent-item-{i}",
                # ``recent-item`` kept as a legacy class alongside the
                # new ``proj-row`` style so tests that query the old
                # selector still match.
                classes="proj-row recent-item",
            )

    def _render_project_row(
        self, index: int, project: RecentProject, selected: bool,
    ) -> str:
        """Build a single recent-project row.

        Mirrors the web UI's ``▌`` selection marker: a cream bar on
        the active row, a dim spacer on the rest, so the eye tracks
        the cursor as ↑↓/j/k moves.
        """
        home = str(Path.home())
        display_path = project.path.replace(home, "~")
        status_raw = self._project_status(project.path).strip()
        marker = "[#DDEDC4]▌[/]" if selected else "[#3a3a3a] [/]"
        return (
            f"  {marker} [#DDEDC4]{index + 1:>2}[/]. "
            f"[#DDEDC4]{project.name[:22]:<22}[/]  "
            f"{self._format_status(status_raw):<22}  "
            f"[#787266]{self._format_date(project.last_opened):<9}[/]  "
            f"[#a59a86]{display_path}[/]"
        )

    @staticmethod
    def _format_status(status: str) -> str:
        # ``_project_status`` returns markup-wrapped text; surface the
        # plain label to pad, then re-wrap with the right style.
        if "missing" in status:
            return "[#fb4b4b]MISSING[/]"
        if "done" in status:
            return "[#DDEDC4]DONE   [/]"
        if "ready" in status:
            return "[#DDEDC4]READY  [/]"
        return "[#a59a86]NEW    [/]"

    @staticmethod
    def _format_date(iso: str) -> str:
        if not iso:
            return "—"
        try:
            dt = datetime.datetime.fromisoformat(iso.replace("Z", "+00:00"))
            return dt.strftime("%m/%d/%y")
        except ValueError:
            return iso[:10]

    @staticmethod
    def _project_status(path_str: str) -> str:
        project_path = Path(path_str)
        if not project_path.exists():
            return "[#fb4b4b]missing[/]"
        output_dir = project_path / "output"
        if output_dir.exists() and any(output_dir.iterdir()):
            return "[#DDEDC4]done[/]   "
        if (project_path / "recon.yaml").exists():
            return "[#a59a86]ready[/]  "
        return "[#a59a86]new[/]    "

    def action_new(self) -> None:
        _log.info("WelcomeScreen action_new")
        self._show_new_input()

    def action_open(self) -> None:
        _log.info("WelcomeScreen action_open")
        self._show_open_input()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "welcome-new":
            self.action_new()
        elif event.button.id == "welcome-open":
            self.action_open_selected()

    # -- keyboard row nav -------------------------------------------------

    def action_cursor_down(self) -> None:
        total = len(self._manager.load()[:9])
        if total == 0:
            return
        self._selected_index = (self._selected_index + 1) % total
        self._refresh_selection()

    def action_cursor_up(self) -> None:
        total = len(self._manager.load()[:9])
        if total == 0:
            return
        self._selected_index = (self._selected_index - 1) % total
        self._refresh_selection()

    def action_open_selected(self) -> None:
        # Enter is only meaningful when a recent row is highlighted.
        # If the user has a ``new-path-input`` or ``open-path-input``
        # focused the Input widget's own ``on_input_submitted`` fires
        # instead — Textual routes Enter to the focused widget first.
        self.action_open_recent(self._selected_index)

    def _refresh_selection(self) -> None:
        """Re-render each visible row so the selection marker tracks
        ``self._selected_index``. Single-query walk; cheap enough to
        do on every keystroke.
        """
        projects = self._manager.load()
        for i, project in enumerate(projects[:9]):
            try:
                static = self.query_one(f"#recent-item-{i}", Static)
            except Exception:
                continue
            static.update(
                self._render_project_row(
                    i, project, selected=(i == self._selected_index),
                ),
            )

    def action_open_recent(self, index: int) -> None:
        projects = self._manager.load()
        if not (0 <= index < len(projects)):
            return
        # Track the keystroke-selected row so the ↑↓ cursor and the
        # 1-9 jumps stay in sync. Refresh the visible marker to match.
        self._selected_index = index
        self._refresh_selection()
        path = projects[index].path
        _log.info("WelcomeScreen opening recent index=%d path=%s", index, path)
        if not self._is_valid_workspace_path(path):
            self.app.notify(
                f"{path} is missing. Recent entry kept — delete it from recent.json if stale.",
                title="Workspace unavailable",
                severity="error",
            )
            return
        self.post_message(self.WorkspaceSelected(path))

    @staticmethod
    def _is_valid_workspace_path(path: str) -> bool:
        p = Path(path)
        return p.exists() and p.is_dir()

    def _show_new_input(self) -> None:
        container = self.query_one("#welcome-input-slot", Vertical)
        existing = self.query("#new-path-input")
        if existing:
            return
        default_path = str(Path.home() / "recon-workspaces" / "new-project")
        path_input = Input(
            value=default_path,
            placeholder="Directory for new project",
            id="new-path-input",
        )
        container.mount(path_input)
        path_input.focus()
        self._scroll_input_into_view(path_input)

    def _show_open_input(self) -> None:
        container = self.query_one("#welcome-input-slot", Vertical)
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
            if not self._is_valid_workspace_path(path_str):
                self.app.notify(
                    f"{path_str} does not exist or is not a directory.",
                    title="Workspace unavailable",
                    severity="error",
                )
                return
            self.post_message(self.WorkspaceSelected(path_str))
        elif event.input.id == "new-path-input":
            self.post_message(self.NewProjectRequested(path_str))
