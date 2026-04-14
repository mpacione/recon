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

import contextlib
import os
import time
from collections import deque
from dataclasses import dataclass
from typing import TYPE_CHECKING

from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Static

from recon.events import (
    CostRecorded,
    Event,
    ProfileCreated,
    RunCancelled,
    RunCompleted,
    RunFailed,
    RunStageCompleted,
    RunStageStarted,
    RunStarted,
    SectionFailed,
    SectionResearched,
    SectionRetrying,
    ThemesDiscovered,
    get_bus,
)
from recon.logging import get_memory_handler
from recon.tui.widgets import format_progress_bar, humanize_path

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
    """Check for an API key and validate it with a lightweight ping."""
    key = _extract_api_key(workspace_root)
    if not key:
        return False
    return _validate_api_key(key)


def _extract_api_key(workspace_root: Path) -> str:
    """Extract the API key from env var or .env file."""
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if key:
        return key
    env_path = workspace_root / ".env"
    if env_path.exists():
        try:
            for line in env_path.read_text().splitlines():
                if line.startswith("ANTHROPIC_API_KEY="):
                    return line.split("=", 1)[1].strip()
        except OSError:
            pass
    return ""


def _validate_api_key(key: str) -> bool:
    """Lightweight ping to verify the API key is valid.

    Uses a minimal count-tokens request to avoid spending credits.
    Falls back to presence-check if the request fails for network reasons.
    """
    if not key or not key.startswith("sk-ant-"):
        return bool(key)
    try:
        import urllib.error
        import urllib.request

        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages/count_tokens",
            data=b'{"model":"claude-sonnet-4-20250514","messages":[{"role":"user","content":"hi"}]}',
            headers={
                "x-api-key": key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except urllib.error.HTTPError as exc:
        return exc.code != 401
    except Exception:
        return True


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
        # Hide "idle" state label — it's the default and adds no info
        if ctx.run_state == "idle":
            state_label = ""
        else:
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
# ActivityFeed -- typed engine events with iconography
# ----------------------------------------------------------------------


class ActivityFeed(Static):
    """Rolling feed of typed engine events from :mod:`recon.events`.

    Distinct from :class:`LogPane`, which renders raw log lines from
    the in-memory log buffer. ActivityFeed subscribes to the
    process-wide event bus and decorates each event with an icon and
    a short human-readable summary so the user can scan pipeline
    progress at a glance.

    Subscription lifecycle: subscribe in :meth:`on_mount`, deregister
    in :meth:`on_unmount`. Events arrive on whichever thread the
    publisher is running on; we route them through ``app.call_from_thread``
    so the deque mutation and re-render happen on the message loop.

    The widget keeps a bounded ``deque`` of the last N entries
    (default 20) and re-renders from the deque on every event. A
    short ``set_interval`` poll catches the case where an event arrives
    while the screen isn't yet mounted (the deque captures it; the
    poll redraws it once the widget is alive).
    """

    DEFAULT_CSS = """
    ActivityFeed {
        height: 8;
        background: #0d0d0d;
        color: #efe5c0;
        padding: 0 1;
        border-top: solid #3a3a3a;
    }
    """

    DEFAULT_CAPACITY = 20
    VISIBLE_LINES = 6

    def __init__(self, capacity: int = DEFAULT_CAPACITY) -> None:
        super().__init__("", markup=True)
        self._entries: deque[str] = deque(maxlen=capacity)
        self._subscriber = self._on_event
        self._dirty = True

    def on_mount(self) -> None:
        get_bus().subscribe(self._subscriber)
        self._render_feed()
        self.set_interval(0.25, self._render_feed_if_dirty, name="activity-feed-tick")

    def on_unmount(self) -> None:
        with contextlib.suppress(Exception):
            get_bus().unsubscribe(self._subscriber)

    # -- subscriber ----------------------------------------------------

    def _on_event(self, event: Event) -> None:
        line = self._format_event(event)
        if line is None:
            return
        # The publisher may be on any thread; route the mutation
        # through the message loop.
        try:
            self.app.call_from_thread(self._append, line)
        except Exception:
            # Test apps without a running message loop can mutate inline
            self._append(line)

    def _append(self, line: str) -> None:
        self._entries.append(line)
        self._dirty = True
        self._render_feed()

    # -- rendering -----------------------------------------------------

    def _render_feed_if_dirty(self) -> None:
        if self._dirty:
            self._render_feed()

    def _render_feed(self) -> None:
        self._dirty = False
        if not self._entries:
            self.update("[#3a3a3a]│ no activity yet[/]")
            return
        visible = list(self._entries)[-self.VISIBLE_LINES :]
        rendered = "\n".join(f"[#3a3a3a]│[/] {line}" for line in visible)
        self.update(rendered)

    # -- formatting ----------------------------------------------------

    def _format_event(self, event: Event) -> str | None:
        if isinstance(event, RunStarted):
            op = event.operation or "run"
            return f"[#e0a044]▶[/] [#efe5c0]run started[/] [#a89984]· {op}[/]"
        if isinstance(event, RunStageStarted):
            return (
                f"[#e0a044]→[/] [#efe5c0]stage[/] [#a89984]:[/] "
                f"[#efe5c0]{event.stage}[/]"
            )
        if isinstance(event, RunStageCompleted):
            return (
                f"[#98971a]✓[/] [#efe5c0]stage[/] [#a89984]:[/] "
                f"[#efe5c0]{event.stage}[/]"
            )
        if isinstance(event, RunCompleted):
            return (
                f"[#98971a]✓[/] [#efe5c0]run complete[/] "
                f"[#a89984]·[/] [#e0a044]${event.total_cost_usd:.2f}[/]"
            )
        if isinstance(event, RunFailed):
            err = (event.error or "")[:60]
            return (
                f"[#cc241d]✗[/] [#efe5c0]run failed[/] "
                f"[#a89984]·[/] [#cc241d]{err}[/]"
            )
        if isinstance(event, RunCancelled):
            return "[#cc241d]⊘[/] [#efe5c0]run cancelled[/]"
        if isinstance(event, CostRecorded):
            return (
                f"[#e0a044]$[/] [#e0a044]${event.cost_usd:.2f}[/] "
                f"[#a89984]({event.model})[/]"
            )
        if isinstance(event, SectionResearched):
            return (
                f"[#98971a]✓[/] [#efe5c0]{event.competitor_name}[/]"
                f"[#3a3a3a].[/][#a89984]{event.section_key}[/]"
            )
        if isinstance(event, SectionRetrying):
            return (
                f"[#d79921]~>[/] [#efe5c0]{event.competitor_name}[/]"
                f"[#3a3a3a].[/][#a89984]{event.section_key}[/]"
                f" [#a89984]retry {event.attempt}[/]"
            )
        if isinstance(event, SectionFailed):
            error_hint = ""
            if event.error:
                short = event.error.strip().split("\n")[0][:30]
                error_hint = f" [#a89984]({short})[/]"
            return (
                f"[#cc241d]✗[/] [#efe5c0]{event.competitor_name}[/]"
                f"[#3a3a3a].[/][#a89984]{event.section_key}[/]"
                f"{error_hint}"
            )
        if isinstance(event, ThemesDiscovered):
            return (
                f"[#e0a044]◎[/] [#e0a044]{event.theme_count}[/] "
                f"[#efe5c0]themes discovered[/]"
            )
        if isinstance(event, ProfileCreated):
            return (
                f"[#98971a]+[/] [#efe5c0]profile[/] [#a89984]:[/] "
                f"[#efe5c0]{event.name}[/]"
            )
        return None


# ----------------------------------------------------------------------
# RunStatusBar -- thin 1-line status bar (hidden when idle)
# ----------------------------------------------------------------------


class RunStatusBar(Static):
    """Single-line status strip surfacing the active run.

    Hidden when ``run_state == idle``; visible the moment a
    ``RunStarted`` event lands; hidden again on ``RunCompleted``,
    ``RunFailed``, or ``RunCancelled``.

    Renders ``stage  [progress bar]  elapsed  $cost`` where the cost
    is cumulative across all ``CostRecorded`` events seen since the
    most recent ``RunStarted``. Subscribes to the EventBus on mount,
    unsubscribes on unmount, ticks once a second so the elapsed time
    counter advances even when no events fire.
    """

    DEFAULT_CSS = """
    RunStatusBar {
        height: 1;
        background: #1d1d1d;
        color: #efe5c0;
        padding: 0 1;
    }
    RunStatusBar.idle {
        display: none;
    }
    """

    def __init__(self) -> None:
        super().__init__("", markup=True)
        self._stage: str = ""
        self._cost: float = 0.0
        self._started_at: float | None = None
        self._active: bool = False
        self._subscriber = self._on_event

    def on_mount(self) -> None:
        self.add_class("idle")
        get_bus().subscribe(self._subscriber)
        self.set_interval(1.0, self._tick, name="run-status-bar-tick")
        self._render_status()

    def on_unmount(self) -> None:
        with contextlib.suppress(Exception):
            get_bus().unsubscribe(self._subscriber)

    # -- subscriber ---------------------------------------------------

    def _on_event(self, event: Event) -> None:
        try:
            self.app.call_from_thread(self._handle, event)
        except Exception:
            self._handle(event)

    def _handle(self, event: Event) -> None:
        if isinstance(event, RunStarted):
            self._stage = ""
            self._cost = 0.0
            self._started_at = time.monotonic()
            self._active = True
            self._show()
        elif isinstance(event, RunStageStarted):
            self._stage = event.stage
            self._render_status()
        elif isinstance(event, RunStageCompleted):
            self._stage = f"{event.stage} ✓"
            self._render_status()
        elif isinstance(event, CostRecorded):
            self._cost += event.cost_usd
            self._render_status()
        elif isinstance(event, (RunCompleted, RunFailed, RunCancelled)):
            self._active = False
            self._hide()

    def _show(self) -> None:
        self.remove_class("idle")
        self._render_status()

    def _hide(self) -> None:
        self.add_class("idle")

    def _tick(self) -> None:
        if self._active:
            self._render_status()

    def _elapsed_str(self) -> str:
        if self._started_at is None:
            return "0:00"
        seconds = int(time.monotonic() - self._started_at)
        minutes, secs = divmod(seconds, 60)
        if minutes >= 60:
            hours, minutes = divmod(minutes, 60)
            return f"{hours}:{minutes:02d}:{secs:02d}"
        return f"{minutes}:{secs:02d}"

    def _render_status(self) -> None:
        stage_label = self._stage or "starting"
        bar = format_progress_bar(0.0, width=20, state="running")
        elapsed = self._elapsed_str()
        cost_str = f"${self._cost:.2f}"
        self.update(
            f"[#e0a044]●[/] [#efe5c0]{stage_label}[/]  "
            f"{bar}  "
            f"[#a89984]{elapsed}[/]  "
            f"[#e0a044]{cost_str}[/]",
        )


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
    show_activity_feed: bool = True
    show_run_status_bar: bool = True
    show_keybind_hint: bool = True

    DEFAULT_CSS = """
    ReconScreen {
        background: #000000;
    }
    #flow-breadcrumb {
        height: 1;
        padding: 0 2;
        background: #0d0d0d;
        color: #a89984;
    }
    #recon-body {
        height: 1fr;
        padding: 1 2;
        overflow-y: auto;
    }
    #recon-footer {
        dock: bottom;
        height: auto;
        layout: vertical;
    }
    """

    keybind_hints: str = "[#a89984]q quit · ? help[/]"

    # Flow step for breadcrumb. None = not part of the v2 flow.
    flow_step: int | None = None

    _FLOW_STEPS = [
        ("describe", "Describe"),
        ("discovery", "Discovery"),
        ("template", "Template"),
        ("confirm", "Confirm"),
        ("run", "Run"),
        ("results", "Results"),
    ]

    def compose(self) -> ComposeResult:
        # Header is reactive: pulls live context from the app on mount
        ctx = self._current_workspace_context()
        yield ReconHeaderBar(ctx)

        # Breadcrumb for v2 flow screens
        if self.flow_step is not None:
            yield Static(self._render_breadcrumb(), id="flow-breadcrumb")

        with Vertical(id="recon-body"):
            yield from self.compose_body()

        # All bottom chrome lives inside a single docked Vertical.
        # Stacking dock:bottom widgets directly under the screen
        # confuses Textual's layout engine -- only one would render
        # in a real terminal.
        with Vertical(id="recon-footer"):
            if getattr(self, "show_run_status_bar", True):
                yield RunStatusBar()
            if getattr(self, "show_activity_feed", True):
                yield ActivityFeed()
            if getattr(self, "show_log_pane", True):
                yield LogPane()
            if getattr(self, "show_keybind_hint", True):
                yield KeybindHint(self.keybind_hints)

    def compose_body(self) -> ComposeResult:
        """Override in subclasses to render the screen's actual content."""
        yield Static("")

    def _render_breadcrumb(self) -> str:
        parts: list[str] = []
        for i, (_key, label) in enumerate(self._FLOW_STEPS):
            if i < self.flow_step:
                parts.append(f"[#98971a]{label}[/]")
            elif i == self.flow_step:
                parts.append(f"[bold #e0a044]{label}[/]")
            else:
                parts.append(f"[#3a3a3a]{label}[/]")
        step_num = (self.flow_step or 0) + 1
        total = len(self._FLOW_STEPS)
        return f"[#a89984]Step {step_num}/{total}[/]  " + " [#3a3a3a]→[/] ".join(parts)

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
