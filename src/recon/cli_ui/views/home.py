"""``recon`` (bare) — the v4 home screen for the CLI.

When the user types ``recon`` from outside a workspace, show the same
list of recent projects the web UI puts on its home screen, plus a
hint to run ``recon init`` for a new one. Mirrors how ``btop`` /
``htop`` behave when run without flags — there's always *something*
useful to show.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from rich.align import Align
from rich.console import Console, Group
from rich.table import Table
from rich.text import Text

from recon.cli_ui.renderables import card, tab_breadcrumb
from recon.cli_ui.renderables.card import CARD_MAX_WIDTH

_STATUS_STYLE = {
    "done":         "accent",
    "complete":     "accent",
    "ready":        "accent",
    "in_progress":  "body",
    "new":          "muted",
    "missing":      "dim",
    "abandoned":    "subdued",
    "unknown":      "dim",
}


def _fmt_date(iso: str) -> str:
    if not iso:
        return "—"
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.strftime("%m/%d/%y")
    except ValueError:
        return iso[:10]


def _humanize(p: str) -> str:
    home = str(Path.home())
    return "~" + p[len(home):] if p.startswith(home) else p


def render_home(console: Console) -> None:
    """Print the no-workspace home screen with a recents table + hints."""
    from recon.tui.screens.welcome import _DEFAULT_RECENT_PATH, RecentProjectsManager
    from recon.web.api import _project_status

    manager = RecentProjectsManager(_DEFAULT_RECENT_PATH)
    projects = manager.load()

    console.print(tab_breadcrumb(active="recon"))
    console.print()

    intro = Text.assemble(
        ("▌ ", "accent"),
        ("Automated grounded competitive intelligence research. ", "accent"),
        (
            "Recon orchestrates LLM agents to discover competitors, research them section-by-section "
            "against a structured schema, and synthesize the results into thematic analyses and "
            "executive summaries — all stored locally as Obsidian-compatible markdown.",
            "body",
        ),
    )
    console.print(Align.left(intro, width=CARD_MAX_WIDTH))
    console.print()

    if not projects:
        body = Group(
            Text(
                "No recent projects. Get started:",
                style="body",
            ),
            Text(""),
            Text.assemble(("  1. ", "dim"), ("recon init ~/recon-workspaces/<name>", "accent")),
            Text.assemble(("  2. ", "dim"), ("cd into that dir", "body")),
            Text.assemble(("  3. ", "dim"), ("recon discover --seed <competitor>", "accent")),
            Text.assemble(("  4. ", "dim"), ("recon run", "accent"), ("     # full pipeline", "subdued")),
        )
        console.print(
            card(
                body,
                title="RECON HOME",
                meta="no projects yet",
                footer="new:  recon init <dir>   ·   help:  recon --help",
            )
        )
        return

    rows = Table.grid(padding=(0, 2), pad_edge=False, expand=True)
    rows.add_column(width=3, no_wrap=True)            # idx
    rows.add_column(min_width=14, no_wrap=True)       # name
    rows.add_column(min_width=8,  no_wrap=True)       # status
    rows.add_column(width=10, no_wrap=True)           # last_opened
    rows.add_column(min_width=18)                      # path
    for i, p in enumerate(projects, start=1):
        status = _project_status(p.path)
        style = _STATUS_STYLE.get(status, "body")
        rows.add_row(
            Text(f"{i:>2}.", style="dim"),
            Text(p.name, style="accent"),
            Text(status.upper(), style=style),
            Text(_fmt_date(getattr(p, "last_opened", "") or ""), style="dim"),
            Text(_humanize(p.path), style="body"),
        )

    console.print(
        card(
            rows,
            title="RECENT PROJECTS",
            meta=f"{len(projects)} project{'s' if len(projects) != 1 else ''}",
            footer=(
                "open:  cd <path> && recon   ·   "
                "new:  recon init <dir>   ·   "
                "docs:  recon --help"
            ),
        )
    )
