"""Numbered-tab breadcrumb — the ``[0] RECON  ▌[1] PLAN  [2] SCHEMA …`` strip.

Rendered at the top of every per-tab subcommand so users know which
"section" of the flow they're looking at, even though the CLI isn't
interactive. The tabs match the web UI's top nav exactly; the "active"
tab is highlighted with a left-edge marker and the ``active`` style.

Usage::

    console.print(tab_breadcrumb(active="plan"))
"""

from __future__ import annotations

from dataclasses import dataclass

from rich.text import Text


@dataclass(frozen=True)
class _Tab:
    key: str
    label: str
    number: int


# Source of truth for the flow order. Keep in sync with
# ``static/app.js::TABS`` on the web side.
_TABS: tuple[_Tab, ...] = (
    _Tab("recon",  "RECON",  0),   # home
    _Tab("plan",   "PLAN",   1),
    _Tab("schema", "SCHEMA", 2),
    _Tab("comps",  "COMP'S", 3),
    _Tab("agents", "AGENTS", 4),
    _Tab("output", "OUTPUT", 5),
)


def tab_breadcrumb(active: str | None = None, *, sep: str = "  ") -> Text:
    """Return a styled ``Text`` of the tab strip.

    ``active`` is the tab ``key`` to highlight (``"plan"``, ``"schema"``,
    etc.). Pass ``None`` to render all tabs dim — useful for commands
    that don't belong to a single tab (``recon status``).
    """
    out = Text()
    for i, t in enumerate(_TABS):
        if i > 0:
            out.append(sep, style="subdued")
        is_active = t.key == active
        if is_active:
            # Left-edge marker `▌` + cream label on the current tab.
            out.append("▌", style="active")
            out.append(f"[{t.number}] {t.label}", style="active")
        else:
            out.append(f" [{t.number}] {t.label}", style="dim")
    return out
