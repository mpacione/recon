"""WelcomeScreen for recon TUI.

Entry point when no workspace is specified. Lets the user create a new
project, open an existing one, or resume from a recent project.
Recent projects stored in ~/.recon/recent.json.
"""

from __future__ import annotations

import datetime
import json
import re
from dataclasses import dataclass
from pathlib import Path

from textual.app import ComposeResult  # noqa: TCH002 -- used at runtime
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Static

from recon.logging import get_logger
from recon.tui.shell import ReconScreen
from recon.tui.widgets import button_label

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
_DEFAULT_WORKSPACES_PARENT = Path.home() / "recon-workspaces"


_RECON_BANNER = """\
[bold #DDEDC4]░▒▓██████▓▒░   ░▒▓███████▓▒░ ░▒▓██████▓▒░ ░▒▓██████▓▒░   ░▒▓██████▓▒░[/]
[bold #DDEDC4]░▒▓█▓▒░▒▓█▓▒░  ░▒▓█▓▒░       ░▒▓█▓▒░░▒▓█▒ ░▒▓█▓▒░░▒▓█▓▒░ ░▒▓█▓▒░▒▓█▓▒░[/]
[bold #DDEDC4]░▒▓█▓▒ ░▒▓█▓▒░ ░▒▓█▓▒░       ░▒▓█▓▒░      ░▒▓█▓▒ ░▒▓█▓▒░ ░▒▓█▓▒░░▒▓█▓▒░[/]
[bold #DDEDC4]░▒▓██████▓▒░   ░▒▓██████▓▒░  ░▒▓█▓▒░      ░▒▓█▓▒ ░▒▓█▓▒░ ░▒▓█▓▒░ ░▒▓█▓▒░[/]
[bold #DDEDC4]░▒▓█▓▒░▒▓█▓▒░  ░▒▓█▓▒░       ░▒▓█▓▒░      ░▒▓█▓▒ ░▒▓█▓▒░ ░▒▓█▓▒░ ░▒▓█▓▒░[/]
[bold #DDEDC4]░▒▓█▓▒ ░▒▓█▓▒░ ░▒▓█▓▒░       ░▒▓█▓▒░░▒▓█▒ ░▒▓█▓▒ ░▒▓█▓▒░ ░▒▓█▓▒░ ░▒▓█▓▒░[/]
[bold #DDEDC4]░▒▓█▓▒ ░▒▓█▓▒░ ░▒▓███████▓▒░ ░▒▓██████▓▒░ ░▒▓██████▓▒░   ░▒▓█▓▒░ ░▒▓█▓▒░[/]"""


def _slugify_workspace_name(name: str) -> str:
    slug = name.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    return re.sub(r"-+", "-", slug).strip("-") or "project"


def _next_workspace_path(name: str, parent: Path = _DEFAULT_WORKSPACES_PARENT) -> Path:
    slug = _slugify_workspace_name(name)
    target = parent / slug
    suffix = 2
    while target.exists():
        target = parent / f"{slug}-{suffix}"
        suffix += 1
    return target


class _PromptModal(ModalScreen[str | None]):
    BINDINGS = [
        Binding("escape", "cancel", "cancel", show=False),
    ]

    DEFAULT_CSS = """
    _PromptModal {
        align: center middle;
    }
    #prompt-modal {
        width: 76;
        height: auto;
        padding: 1 2;
        border: solid #3a3a3a;
        background: #000000;
    }
    #prompt-copy {
        height: auto;
        margin: 0 0 1 0;
        color: #a59a86;
    }
    #prompt-actions {
        height: auto;
        margin: 1 0 0 0;
    }
    #prompt-actions Button {
        margin: 0 1 0 0;
        width: 18;
    }
    """

    def __init__(
        self,
        *,
        title: str,
        copy: str,
        placeholder: str,
        submit_label: tuple[str, str] | tuple[str, None],
        input_id: str,
    ) -> None:
        super().__init__()
        self._title = title
        self._copy = copy
        self._placeholder = placeholder
        self._submit_label = submit_label
        self._input_id = input_id

    def compose(self) -> ComposeResult:
        with Vertical(id="prompt-modal"):
            yield Static(f"[bold #DDEDC4]── {self._title} ──[/]")
            yield Static(self._copy, id="prompt-copy")
            yield Input(placeholder=self._placeholder, id=self._input_id)
            with Horizontal(id="prompt-actions"):
                yield Button(button_label(*self._submit_label), id="prompt-submit", variant="primary")
                yield Button(button_label("CANCEL", "Esc"), id="prompt-cancel")

    def on_mount(self) -> None:
        self.query_one(Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "prompt-submit":
            self.action_submit()
        elif event.button.id == "prompt-cancel":
            self.action_cancel()

    def on_input_submitted(self, _event: Input.Submitted) -> None:
        self.action_submit()

    def action_submit(self) -> None:
        value = self.query_one(Input).value.strip()
        if not value:
            self.app.notify("Enter a value to continue.", severity="warning")
            return
        self.dismiss(value)

    def action_cancel(self) -> None:
        self.dismiss(None)


class _NewProjectModal(_PromptModal):
    def __init__(self) -> None:
        parent = str(_DEFAULT_WORKSPACES_PARENT).replace(str(Path.home()), "~")
        super().__init__(
            title="NEW PROJECT",
            copy=(
                "[#a59a86]Name the workspace.[/] "
                f"[#787266]Recon will create it in {parent}.[/]"
            ),
            placeholder="e.g. Acme competitive intelligence",
            submit_label=("CREATE", "↲"),
            input_id="new-project-name-input",
        )


class _OpenWorkspaceModal(_PromptModal):
    def __init__(self) -> None:
        super().__init__(
            title="OPEN WORKSPACE",
            copy="[#a59a86]Enter a workspace path to open directly.[/]",
            placeholder="~/recon-workspaces/acme",
            submit_label=("OPEN", "↲"),
            input_id="open-workspace-path-input",
        )


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
    #welcome-projects-foot Button {
        margin: 0 0 0 1;
    }
    #welcome-foot-copy {
        width: 1fr;
        color: #787266;
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
    show_tab_strip = False
    # Welcome has no workspace loaded, so the "recon · no workspace"
    # header bar is just noise. TabStrip above carries the screen
    # identity.
    show_header_bar = False
    keybar_items = (
        ("↑↓", "NAV"),
        ("↲", "OPEN"),
        ("N", "NEW"),
        ("O", "OPEN PATH"),
        ("1-9", "RECENT"),
        ("Q", "QUIT"),
    )

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
                    f"{_RECON_BANNER}\n\n"
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
                    yield Button(
                        button_label("OPEN", "↲"),
                        id="welcome-open",
                        classes="welcome-action",
                    )
                    yield Button(
                        button_label("NEW", "N"),
                        id="welcome-new",
                        variant="primary",
                        classes="welcome-action",
                    )

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
        self.app.push_screen(_NewProjectModal(), self._handle_new_project_name)

    def action_open(self) -> None:
        _log.info("WelcomeScreen action_open")
        self.app.push_screen(_OpenWorkspaceModal(), self._handle_open_workspace_path)

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
        # If the user has a modal prompt focused, that Input widget's
        # own ``on_input_submitted`` fires instead — Textual routes
        # Enter to the focused widget first.
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
        p = Path(path).expanduser()
        return p.exists() and p.is_dir()

    def _handle_new_project_name(self, name: str | None) -> None:
        if not name:
            return
        target = _next_workspace_path(name)
        _log.info("WelcomeScreen new project name=%s target=%s", name, target)
        self.post_message(self.NewProjectRequested(str(target)))

    def _handle_open_workspace_path(self, path_str: str | None) -> None:
        if not path_str:
            return
        normalized = str(Path(path_str).expanduser())
        if not self._is_valid_workspace_path(normalized):
            self.app.notify(
                f"{normalized} does not exist or is not a directory.",
                title="Workspace unavailable",
                severity="error",
            )
            return
        self.post_message(self.WorkspaceSelected(normalized))
