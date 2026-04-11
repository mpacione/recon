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
byte (both use Gruvbox ``#efe5c0`` / ``#000`` / ``#e0a044`` /
``#a89984`` / ``#3a3a3a``). Phase J closes the remaining layout gap
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
        border: round #3a3a3a;
        background: #000000;
    }
    TerminalBox > .terminal-box-title {
        height: 1;
        color: #e0a044;
    }
    TerminalBox > .terminal-box-meta {
        height: 1;
        color: #a89984;
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
        # Phase-D divider on the left, dim stat line on the right.
        if title and meta:
            return Static(
                f"[bold #e0a044]── {title} ──[/]  [#a89984]{meta}[/]",
                classes="terminal-box-title terminal-box-meta",
                markup=True,
            )
        if title:
            return Static(
                f"[bold #e0a044]── {title} ──[/]",
                classes="terminal-box-title",
                markup=True,
            )
        if meta:
            return Static(
                f"[#a89984]{meta}[/]",
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
