"""Persistent TUI chrome for recon.

The shell wraps every full-screen view with:

- a top header bar showing workspace context (path, domain, run state,
  cost, API key status)
- a body region where the screen renders its actual content
- a keybind hint line that summarizes the current screen's bindings
- a rolling log tail pane fed by ``recon.logging.MemoryLogHandler``

Modal screens (Discovery, Curation, Selector, Planner, Wizard) opt out
of the chrome -- they pop up over whichever full screen is currently
active and let its chrome show through.

The chrome lives at the screen level via :class:`ReconScreen`, a base
class that overrides ``compose()`` to lay out header / body / footer /
log pane and delegates body content to ``compose_body()``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Static

from recon.logging import get_memory_handler
from recon.tui.widgets import humanize_path

if TYPE_CHECKING:
    from pathlib import Path

    from textual.app import ComposeResult

    from recon.workspace import Workspace


@dataclass
class WorkspaceContext:
    """Snapshot of workspace state shown in the persistent header."""

    workspace_path: Path | None = None
    domain: str = ""
    company_name: str = ""
    total_cost: float = 0.0
    run_count: int = 0
    api_key_present: bool = False
    run_state: str = "idle"  # idle, running, paused, stopping, error, done
    run_phase: str = ""

    @classmethod
    def empty(cls) -> WorkspaceContext:
        return cls()

    @classmethod
    def from_workspace(cls, workspace: Workspace) -> WorkspaceContext:
        from recon.tui.models.dashboard import _read_cost_summary

        schema = workspace.schema
        domain = schema.domain if schema else ""
        company = schema.identity.company_name if schema else ""

        cost_summary = _read_cost_summary(workspace)
        api_key_present = _detect_api_key(workspace.root)

        return cls(
            workspace_path=workspace.root,
            domain=domain,
            company_name=company,
            total_cost=cost_summary.get("total_cost", 0.0),
            run_count=cost_summary.get("run_count", 0),
            api_key_present=api_key_present,
        )


def _detect_api_key(workspace_root: Path) -> bool:
    """Cheap check: env var or .env in workspace root."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        return True
    env_path = workspace_root / ".env"
    if env_path.exists():
        try:
            for line in env_path.read_text().splitlines():
                if line.startswith("ANTHROPIC_API_KEY="):
                    return True
        except OSError:
            pass
    return False


# ----------------------------------------------------------------------
# Widgets
# ----------------------------------------------------------------------


class ReconHeaderBar(Static):
    """Top status strip. Workspace context summary in retro terminal style."""

    DEFAULT_CSS = """
    ReconHeaderBar {
        dock: top;
        height: 1;
        background: #1d1d1d;
        color: #efe5c0;
        padding: 0 1;
    }
    """

    def __init__(self, ctx: WorkspaceContext) -> None:
        super().__init__(self._render_context(ctx), markup=True)
        # NOTE: avoid the attribute name `_context` -- Textual's
        # MessagePump reserves it as an async context manager hook
        # and treats any non-callable assigned there as the context
        # to enter, raising "object is not callable" on mount.
        self._ws_ctx = ctx

    def set_workspace_context(self, ctx: WorkspaceContext) -> None:
        self._ws_ctx = ctx
        self.update(self._render_context(ctx))

    def _render_context(self, ctx: WorkspaceContext) -> str:
        if ctx.workspace_path is None:
            return "[bold #e0a044]recon[/]  [#a89984]no workspace loaded[/]"

        ws_label = humanize_path(ctx.workspace_path, max_width=42)
        company_label = ctx.company_name or "—"
        domain_label = ctx.domain or "—"

        cost_str = f"${ctx.total_cost:.2f}"
        runs_str = f"{ctx.run_count} run{'s' if ctx.run_count != 1 else ''}"

        api_label = "[#98971a]API ✓[/]" if ctx.api_key_present else "[#cc241d]API ✗[/]"

        state_color = {
            "idle": "#a89984",
            "running": "#e0a044",
            "paused": "#d79921",
            "stopping": "#a89984",
            "done": "#98971a",
            "error": "#cc241d",
            "cancelled": "#cc241d",
        }.get(ctx.run_state, "#a89984")
        state_label = f"[{state_color}]{ctx.run_state}[/]"
        if ctx.run_phase and ctx.run_phase != ctx.run_state:
            state_label += f" [{state_color}]·[/] [{state_color}]{ctx.run_phase}[/]"

        return (
            f"[bold #e0a044]recon[/] [#a89984]│[/] "
            f"[#efe5c0]{company_label}[/] · [#efe5c0]{domain_label}[/] "
            f"[#a89984]│[/] [#a89984]{ws_label}[/] "
            f"[#a89984]│[/] {cost_str} · {runs_str} "
            f"[#a89984]│[/] {api_label} "
            f"[#a89984]│[/] {state_label}"
        )


class KeybindHint(Static):
    """Bottom hint line showing the current screen's keybinds."""

    DEFAULT_CSS = """
    KeybindHint {
        dock: bottom;
        height: 1;
        background: #1d1d1d;
        color: #a89984;
        padding: 0 1;
    }
    """

    def __init__(self, hints: str = "") -> None:
        super().__init__(hints or "[#a89984]q quit · ? help[/]", markup=True)

    def set_hints(self, hints: str) -> None:
        self.update(hints or "[#a89984]q quit · ? help[/]")


class LogPane(Static):
    """Rolling tail of the in-memory log buffer.

    Shows the last N entries from ``recon.logging.MemoryLogHandler``.
    Polls every 250ms via a Textual interval timer rather than
    subscribing to logging events directly -- subscribing from a
    background thread tends to deadlock the test event loop.
    """

    DEFAULT_CSS = """
    LogPane {
        dock: bottom;
        height: 8;
        background: #0d0d0d;
        color: #a89984;
        padding: 0 1;
        border-top: solid #3a3a3a;
    }
    """

    LEVEL_COLORS = {
        "DEBUG": "#3a3a3a",
        "INFO": "#a89984",
        "WARNING": "#d79921",
        "WARN": "#d79921",
        "ERROR": "#cc241d",
        "CRITICAL": "#cc241d",
    }

    def __init__(self, capacity: int = 6) -> None:
        super().__init__("", markup=True)
        self._capacity = capacity
        self._handler = get_memory_handler()
        self._last_seen_count = -1

    def on_mount(self) -> None:
        self._refresh()
        # Poll the buffer 4x/sec; cheap and avoids cross-thread issues
        self.set_interval(0.25, self._refresh, name="log-pane-tail")

    def _refresh(self) -> None:
        entries = self._handler.tail(self._capacity)
        # Skip the costly markup rebuild if nothing changed
        count_signature = (len(entries), entries[-1].timestamp + entries[-1].message if entries else "")
        if count_signature == self._last_seen_count:
            return
        self._last_seen_count = count_signature

        if not entries:
            self.update("[#3a3a3a]│ waiting for engine activity...[/]")
            return
        lines = []
        for entry in entries:
            color = self.LEVEL_COLORS.get(entry.level, "#a89984")
            level = entry.level[:4].ljust(4)
            # Escape any markup in user-supplied messages
            message = entry.message.replace("[", "\\[")
            line = (
                f"[#3a3a3a]│[/] [#a89984]{entry.timestamp}[/] "
                f"[{color}]{level}[/] "
                f"[#a89984]{entry.name}[/] "
                f"{message}"
            )
            lines.append(line)
        self.update("\n".join(lines))


# ----------------------------------------------------------------------
# Base screen
# ----------------------------------------------------------------------


class ReconScreen(Screen):
    """Full-screen base that adds the persistent recon chrome.

    Subclasses override :meth:`compose_body` instead of ``compose``.
    The base composes::

        ReconHeaderBar
        Vertical#recon-body
            <subclass body>
        LogPane
        KeybindHint

    Modal screens (Discovery, Selector, etc) should NOT inherit from
    this; they remain plain ModalScreen so they pop up over the
    chrome rather than re-rendering it.
    """

    show_log_pane: bool = True
    show_keybind_hint: bool = True

    DEFAULT_CSS = """
    ReconScreen {
        background: #000000;
    }
    #recon-body {
        height: 1fr;
        padding: 1 2;
        overflow-y: auto;
    }
    """

    keybind_hints: str = "[#a89984]q quit · ? help[/]"

    def compose(self) -> ComposeResult:
        # Header is reactive: pulls live context from the app on mount
        ctx = self._current_workspace_context()
        yield ReconHeaderBar(ctx)

        with Vertical(id="recon-body"):
            yield from self.compose_body()

        if getattr(self, "show_log_pane", True):
            yield LogPane()
        if getattr(self, "show_keybind_hint", True):
            yield KeybindHint(self.keybind_hints)

    def compose_body(self) -> ComposeResult:
        """Override in subclasses to render the screen's actual content."""
        yield Static("")

    def _current_workspace_context(self) -> WorkspaceContext:
        ctx = getattr(self.app, "workspace_context", None)
        if isinstance(ctx, WorkspaceContext):
            return ctx
        return WorkspaceContext.empty()

    def refresh_chrome(self) -> None:
        """Re-render the header bar from the current app context."""
        try:
            header = self.query_one(ReconHeaderBar)
        except Exception:
            return
        header.set_workspace_context(self._current_workspace_context())
