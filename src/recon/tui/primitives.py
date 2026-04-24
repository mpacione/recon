"""Reusable container primitives for the recon TUI.

These are the body-content building blocks that screens compose into
card-stack layouts. They own the visual language the user sees inside
each screen body -- borders, padding, titles, vertical rhythm --
without each screen having to re-declare the CSS.

``TerminalBox``
    A bordered card container. 1px solid ``#3a3a3a`` border, 5px
    radius, 12px/16px padding, black background. Optional
    ``title=`` renders a ``── HEADING ──`` divider at the top of
    the box (Phase D visual language). Optional ``meta=`` renders a
    dim subtitle line under the title.

``CardStack``
    A thin ``Vertical`` wrapper that gives a stack of TerminalBox
    children consistent vertical rhythm. Use when a screen renders a
    list of cards (dashboard sections, browser detail panes, run
    monitor blocks) and wants consistent spacing between them.

The primitives mirror the ``.terminal-box`` class pattern from
cyberspace.online, which recon's palette already matches byte-for-
byte (both use Gruvbox ``#DDEDC4`` / ``#000`` / ``#DDEDC4`` /
``#a59a86`` / ``#3a3a3a``). Phase J closes the remaining layout gap
by letting screens reach for these primitives instead of hand-rolling
borders.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.containers import Vertical
from textual.widgets import Static

if TYPE_CHECKING:
    from textual.app import ComposeResult


class TerminalBox(Vertical):
    """Bordered card container.

    The primitive ships with recon's border styling baked in; screens
    don't have to repeat the CSS. Pass ``title=`` to render a
    ``── HEADING ──`` divider and ``meta=`` for a dim subtitle.
    """

    DEFAULT_CSS = """
    TerminalBox {
        height: auto;
        width: 100%;
        margin: 0;
        padding: 0 1;
        border: solid #3a3a3a;
        background: #000000;
    }
    TerminalBox > .terminal-box-title {
        height: 1;
        color: #DDEDC4;
    }
    TerminalBox > .terminal-box-meta {
        height: 1;
        color: #a59a86;
    }
    """

    def __init__(
        self,
        *children,
        title: str | None = None,
        meta: str | None = None,
        id: str | None = None,  # noqa: A002 -- matches Textual's Vertical signature
        classes: str | None = None,
    ) -> None:
        # Prepend the title/meta widget to the positional children so
        # it renders FIRST in the vertical stack. Yielding from
        # compose() lands the title after the user's body widgets
        # because Textual processes positional children before
        # compose-yielded children.
        header = self._build_header(title, meta)
        if header is not None:
            children = (header, *children)
        super().__init__(*children, id=id, classes=classes)
        self._title = title
        self._meta = meta

    @staticmethod
    def _build_header(title: str | None, meta: str | None) -> Static | None:
        # Title and meta share a single row so the box stays compact.
        # v4 palette: cream title, tan meta.
        if title and meta:
            return Static(
                f"[bold #DDEDC4]── {title} ──[/]  [#a59a86]{meta}[/]",
                classes="terminal-box-title terminal-box-meta",
                markup=True,
            )
        if title:
            return Static(
                f"[bold #DDEDC4]── {title} ──[/]",
                classes="terminal-box-title",
                markup=True,
            )
        if meta:
            return Static(
                f"[#a59a86]{meta}[/]",
                classes="terminal-box-meta",
                markup=True,
            )
        return None

    def compose(self) -> ComposeResult:
        return ()


class CardStack(Vertical):
    """Vertical stack of ``TerminalBox`` cards with consistent rhythm.

    Thin wrapper around ``Vertical``. Sets ``height: auto`` so the
    stack grows with its children and gives the stack a margin-top
    so the first card isn't flush against the screen body padding.
    """

    DEFAULT_CSS = """
    CardStack {
        height: auto;
        width: 100%;
        margin: 0 0 0 0;
    }
    """


# ---------------------------------------------------------------------
# v4 chrome — TabStrip, KeyBar
# ---------------------------------------------------------------------


from dataclasses import dataclass as _dataclass

from textual.reactive import reactive as _reactive


@_dataclass(frozen=True)
class _Tab:
    key: str
    label: str
    number: int


# Source of truth for the v4 flow order. Mirror of:
#   - web/static/app.js::TABS
#   - cli_ui/renderables/tab_breadcrumb.py::_TABS
TABS: tuple[_Tab, ...] = (
    _Tab("recon",  "RECON",  0),
    _Tab("plan",   "PLAN",   1),
    _Tab("schema", "SCHEMA", 2),
    _Tab("comps",  "COMP'S", 3),
    _Tab("agents", "AGENTS", 4),
    _Tab("output", "OUTPUT", 5),
)


class TabStrip(Static):
    """Top-dock numbered tab nav. Reactive on ``active`` (tab key).

    The active tab highlights with a ``▌`` marker + pure-white bold;
    others render dim tan. Click routing happens in the owning screen.
    """

    DEFAULT_CSS = ""  # owned by theme.py::RECON_CSS

    active: _reactive[str | None] = _reactive(None)

    def __init__(self, active: str | None = None, *, id: str | None = None) -> None:
        super().__init__(id=id, markup=True)
        self.active = active

    def render(self) -> str:
        parts = []
        for i, t in enumerate(TABS):
            if i > 0:
                parts.append("[#686359]  [/]")
            if t.key == self.active:
                parts.append(f"[#ffffff bold]▌[{t.number}] {t.label}[/]")
            else:
                parts.append(f"[#a59a86] [{t.number}] {t.label}[/]")
        return "".join(parts)


class KeyBar(Static):
    """Bottom-dock keybar of ``[KEY] LABEL`` hints, v4 styled.

    Supplied hints override Textual's default ``Footer`` rendering.
    Screens set ``hints=[("q", "QUIT"), ("s", "SAVE"), ...]`` at
    compose time; reactive so live updates re-render in place.
    """

    DEFAULT_CSS = ""

    hints: _reactive[tuple[tuple[str, str], ...]] = _reactive(())

    def __init__(
        self,
        hints: tuple[tuple[str, str], ...] = (),
        *,
        id: str | None = None,
    ) -> None:
        super().__init__(id=id, markup=True)
        self.hints = hints

    def render(self) -> str:
        if not self.hints:
            return ""
        parts = []
        for i, (key, label) in enumerate(self.hints):
            if i > 0:
                parts.append("[#686359]  ·  [/]")
            parts.append(f"[#DDEDC4 bold][{key}][/] [#787266]{label}[/]")
        return "".join(parts)


# ---------------------------------------------------------------------
# ShadedBar — ▓▒░ static progress, reactive pct
# ---------------------------------------------------------------------


class ShadedBar(Static):
    """Static shaded-block progress bar.

    ``pct`` is a reactive ``float`` 0..100; bar redraws on each
    mutation. ``width`` is fixed at construction — Textual auto-reflow
    on resize isn't worth the complexity for a progress primitive
    this thin.
    """

    DEFAULT_CSS = ""

    pct: _reactive[float] = _reactive(0.0)

    def __init__(self, pct: float = 0.0, *, width: int = 24, id: str | None = None) -> None:
        super().__init__(id=id, markup=True)
        self.pct = pct
        self._width = width

    def render(self) -> str:
        clamped = max(0.0, min(100.0, float(self.pct)))
        exact = (clamped / 100.0) * self._width
        filled = int(exact)
        half = 1 if (exact - filled) >= 0.5 else 0
        empty = max(0, self._width - filled - half)
        bar = "▓" * filled + "▒" * half + "░" * empty
        return f"[#DDEDC4]{bar}[/]"


# ---------------------------------------------------------------------
# Card — v4 bordered container with title/meta/footer labels
# ---------------------------------------------------------------------


class Card(Vertical):
    """Bordered container mirroring the web UI's card rhythm.

    ``title`` and ``meta`` render as a header row inside the card
    rather than as border labels. ``footer`` renders as a dim footer
    strip with a top rule. This reads much closer to the web UI's
    card-head / card-body / card-foot structure than Textual's native
    border-title treatment.
    """

    DEFAULT_CSS = """
    Card {
        border: solid #3a3a3a;
        padding: 0 1;
        height: auto;
        width: 100%;
        margin: 0 0 1 0;
        background: #000000;
    }
    Card > .card-head {
        height: auto;
        color: #a59a86;
        padding: 0 0 1 0;
    }
    Card > .card-body-copy {
        color: #a59a86;
    }
    Card > .card-foot {
        height: auto;
        color: #787266;
        border-top: solid #3a3a3a;
        padding: 1 0 0 0;
        margin: 1 0 0 0;
    }
    Card.card-filled {
        background: #DDEDC4;
        color: #000000;
        border: solid #DDEDC4;
    }
    Card.card-filled > * {
        color: #000000;
    }
    Card.card-highlight {
        border: thick #DDEDC4;
    }
    """

    def __init__(
        self,
        *children,
        title: str | None = None,
        meta: str | None = None,
        footer: str | None = None,
        variant: str = "default",
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        css = ["card"]
        if variant == "filled":
            css.append("card-filled")
        elif variant == "highlight":
            css.append("card-highlight")
        if classes:
            css.append(classes)

        built_children = []
        header = self._build_header(title, meta)
        if header is not None:
            built_children.append(header)
        built_children.extend(children)
        footer_widget = self._build_footer(footer)
        if footer_widget is not None:
            built_children.append(footer_widget)

        super().__init__(*built_children, id=id, classes=" ".join(css))

    @staticmethod
    def _build_header(title: str | None, meta: str | None) -> Static | None:
        if title and meta:
            return Static(
                f"[#a59a86]{title}[/] [#686359]·[/] [#787266]{meta}[/]",
                classes="card-head",
                markup=True,
            )
        if title:
            return Static(f"[#a59a86]{title}[/]", classes="card-head", markup=True)
        if meta:
            return Static(f"[#787266]{meta}[/]", classes="card-head", markup=True)
        return None

    @staticmethod
    def _build_footer(footer: str | None) -> Static | None:
        if not footer:
            return None
        return Static(f"[#787266]{footer}[/]", classes="card-foot", markup=True)
