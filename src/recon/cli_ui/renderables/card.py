"""The canonical recon card — a themed wrapper around ``rich.panel.Panel``.

Mirrors the web UI's card shape:

    ┌── TITLE ─────────────── META ─┐
    │                               │
    │   body goes here              │
    │                               │
    ├── footer ─────────────────────┤
    │ hint1 [K1]   hint2 [K2]       │
    └───────────────────────────────┘

The Rich ``Panel`` natively supports ``title`` (top border) and
``subtitle`` (bottom border). We lean on those rather than drawing a
separate footer row inside the body — it's cheaper and renders better
at narrow widths.
"""

from __future__ import annotations

from rich.align import Align, AlignMethod
from rich.box import Box
from rich.console import Group, RenderableType
from rich.panel import Panel

from recon.cli_ui.boxes import RECON

# Max column width for cards. Matches the web UI's ``max-width: 110ch``
# so the CLI feels like a sibling of the browser view instead of
# sprawling across a 250-column iTerm window.
CARD_MAX_WIDTH: int = 110


def card(
    body: RenderableType,
    *,
    title: str | None = None,
    meta: str | None = None,
    footer: str | None = None,
    box: Box = RECON,
    border_style: str = "border",
    padding: tuple[int, int] = (0, 1),
    title_align: AlignMethod = "left",
    subtitle_align: AlignMethod = "right",
    expand: bool = True,
    max_width: int | None = CARD_MAX_WIDTH,
) -> RenderableType:
    """Build a themed panel.

    - ``title``   → left side of the top border, styled as ``card.title``
    - ``meta``    → right side of the top border, styled as ``card.meta``
    - ``footer``  → bottom border (subtitle), styled as ``card.footer``

    All three are optional. When ``meta`` is supplied alongside
    ``title``, they're joined onto a single top-border line with enough
    padding between them that they read as left/right columns.
    """
    top = None
    if title and meta:
        # Panel renders ``title`` centered or aligned to one side; to
        # show a left-title + right-meta we abuse Rich markup + the
        # ``title_align="left"`` slot for the left half and rely on
        # the user's card width to push the meta apart. Simpler: we
        # build a string with markup styles inline.
        top = f"[card.title]{title}[/]   [card.meta]{meta}[/]"
    elif title:
        top = f"[card.title]{title}[/]"
    elif meta:
        top = f"[card.meta]{meta}[/]"

    subtitle = f"[card.footer]{footer}[/]" if footer else None

    # Cap the panel width so wide terminals don't stretch the card
    # past a readable column. At narrow terminals the card renders at
    # terminal width (Rich clamps `width` to what's available).
    panel = Panel(
        body,
        box=box,
        title=top,
        title_align=title_align,
        subtitle=subtitle,
        subtitle_align=subtitle_align,
        border_style=border_style,
        padding=padding,
        expand=expand,
        width=max_width,
    )
    return panel
