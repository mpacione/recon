"""Live progress monitor for long-running CLI commands.

Bridges the engine's :class:`recon.events.EventBus` to a Rich ``Live``
renderable: subscribes to events, updates a per-competitor state
dict, re-renders a table in place, and prints a final static snapshot
on exit. Mirrors how the web AGENTS tab displays a run.

Usage::

    from recon.cli_ui.live import LiveRunMonitor
    from rich.live import Live

    with LiveRunMonitor(console) as monitor:
        await orchestrator.research_all(...)
        monitor.flush_summary(total_cost=monitor.cost)

``LiveRunMonitor`` installs itself as an :class:`EventBus` subscriber
at enter and detaches at exit. The ``Live`` loop runs inside as well
so callers just ``with`` it and run their engine work inside the
block; events auto-update the view.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from rich.console import Console, Group
from rich.live import Live
from rich.table import Table
from rich.text import Text

from recon.cli_ui.renderables import card, shaded_bar, tab_breadcrumb
from recon.events import (
    CostRecorded,
    Event,
    RunCompleted,
    RunFailed,
    RunStageStarted,
    RunStarted,
    SectionFailed,
    SectionResearched,
    SectionStarted,
    get_bus,
)


@dataclass
class _CompState:
    name: str
    total: int = 0
    done: int = 0
    failed: int = 0
    current: str = ""
    status: str = "pending"  # pending | running | done | failed


@dataclass
class LiveRunMonitor:
    """Subscribes to the EventBus and renders per-competitor rows live."""

    console: Console
    title: str = "RESEARCH"
    active_tab: str | None = "agents"

    # Runtime state — mutated by bus callbacks on the publisher thread.
    cost: float = 0.0
    stage: str = "research"
    run_id: str = ""
    started_at: float = field(default_factory=time.time)
    competitors: dict[str, _CompState] = field(default_factory=dict)
    failed_events: list[tuple[str, str, str]] = field(default_factory=list)
    _live: Live | None = None
    _subscribed: bool = False

    # ------------------------------------------------------------------
    # Bus bridge
    # ------------------------------------------------------------------

    def _on_event(self, event: Event) -> None:
        if isinstance(event, RunStarted):
            self.run_id = event.run_id
            self.stage = event.operation or "research"
        elif isinstance(event, RunStageStarted):
            self.stage = event.stage
        elif isinstance(event, CostRecorded):
            self.cost += event.cost_usd or 0.0
        elif isinstance(event, SectionStarted):
            c = self._ensure(event.competitor_name)
            c.current = event.section_key.upper()
            c.status = "running"
            # Optimistic total bump — we don't know the true total up front.
            if c.done + c.failed + 1 > c.total:
                c.total = c.done + c.failed + 1
        elif isinstance(event, SectionResearched):
            c = self._ensure(event.competitor_name)
            c.done += 1
            c.current = ""
            if c.done + c.failed >= c.total and c.total > 0:
                c.status = "done"
        elif isinstance(event, SectionFailed):
            c = self._ensure(event.competitor_name)
            c.failed += 1
            c.status = "failed"
            self.failed_events.append((event.competitor_name, event.section_key, event.error))
        elif isinstance(event, (RunCompleted, RunFailed)):
            # Final event — Live loop below will read the new state and
            # repaint once more before exit.
            pass

    def _ensure(self, name: str) -> _CompState:
        c = self.competitors.get(name)
        if c is None:
            c = _CompState(name=name)
            self.competitors[name] = c
        return c

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _render(self):
        elapsed = time.time() - self.started_at
        rows = Table.grid(padding=(0, 2), pad_edge=False, expand=True)
        rows.add_column(min_width=18, no_wrap=True)
        rows.add_column(min_width=12, no_wrap=True)
        rows.add_column(width=24, no_wrap=True)
        rows.add_column(width=8, justify="right", no_wrap=True)
        rows.add_column(min_width=10, no_wrap=True)

        if not self.competitors:
            rows.add_row(
                Text("(waiting for first event)", style="subdued"),
                Text("", style="dim"),
                shaded_bar(0, 24),
                Text("0/0", style="dim"),
                Text("IDLE", style="dim"),
            )
        else:
            for c in sorted(self.competitors.values(), key=lambda x: x.name):
                style = {
                    "done":    "accent",
                    "running": "body",
                    "failed":  "error",
                    "pending": "subdued",
                }.get(c.status, "body")
                pct = (c.done / c.total * 100) if c.total else 0.0
                rows.add_row(
                    Text(c.name, style=style),
                    Text(c.current or c.status.upper(), style="dim"),
                    shaded_bar(pct, 24),
                    Text(f"{c.done}/{c.total or '—'}", style="body"),
                    Text(c.status.upper(), style=style),
                )

        done = sum(c.done for c in self.competitors.values())
        total = sum(max(c.total, c.done + c.failed) for c in self.competitors.values())
        fail = sum(c.failed for c in self.competitors.values())
        meta_bits = [
            f"stage {self.stage.upper()}",
            f"cost ${self.cost:.2f}",
            f"{done}/{total or '—'} tasks",
            f"{elapsed:>5.1f}s",
        ]
        if fail:
            meta_bits.append(f"[error]{fail} failed[/]")

        header = tab_breadcrumb(active=self.active_tab)
        body = Group(header, Text(""), rows)
        return card(body, title=self.title, meta="  ·  ".join(meta_bits))

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def __enter__(self) -> LiveRunMonitor:
        bus = get_bus()
        bus.subscribe(self._on_event)
        self._subscribed = True
        self._live = Live(
            self._render(),
            console=self.console,
            refresh_per_second=8,
            transient=False,  # leave the final frame printed
        )
        self._live.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        # Final repaint so the printed frame reflects the terminal state.
        if self._live is not None:
            self._live.update(self._render(), refresh=True)
            self._live.stop()
            self._live = None
        if self._subscribed:
            get_bus().unsubscribe(self._on_event)
            self._subscribed = False

    # ------------------------------------------------------------------
    # Caller helpers
    # ------------------------------------------------------------------

    def flush_summary(self, *, total_cost: float | None = None) -> None:
        """Print a final static summary line under the live card.

        Call this after the ``with`` block if you want a one-line
        wrap-up (total tasks, cost, elapsed). Cheap to call twice.
        """
        elapsed = time.time() - self.started_at
        done = sum(c.done for c in self.competitors.values())
        failed = sum(c.failed for c in self.competitors.values())
        cost = self.cost if total_cost is None else total_cost
        self.console.print(
            Text.assemble(
                ("  ", "body"),
                ("✓ ", "accent"),
                (f"{done} tasks complete", "accent"),
                (f" in {elapsed:.1f}s", "body"),
                (f"  ·  ${cost:.2f}", "body"),
                (f"  ·  {failed} failed" if failed else "", "error"),
            )
        )
