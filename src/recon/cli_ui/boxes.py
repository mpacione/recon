"""Custom Box() presets to match the v4 web UI corner style.

Rich's built-in boxes (``ROUNDED``, ``SQUARE``, ``HEAVY``) are close
but not exactly what the Figma stickersheet shows. The stickersheet
uses sharp 90° corners with a 1-cell hairline border — so our default
is Rich's ``SQUARE`` mirror, just named ``RECON`` for clarity.

Rich box format is 8 lines × 4 chars:

    ┌─┬┐     top (title rule)
    │ ││     head (between title and body)
    ├─┼┤     row
    │ ││     mid
    ├─┼┤     row
    ├─┼┤     foot
    │ ││     bottom-row
    └─┴┘     bottom
"""

from __future__ import annotations

from rich.box import Box

# Sharp-cornered hairline — the v4 card default.
RECON: Box = Box(
    "┌─┬┐\n"
    "│ ││\n"
    "├─┼┤\n"
    "│ ││\n"
    "├─┼┤\n"
    "├─┼┤\n"
    "│ ││\n"
    "└─┴┘\n",
    ascii=False,
)

# Soft-corner variant for featured panels (home projects card, completion
# modals) — matches btop's signature look and reads as a "standout" card
# against the plainer sharp-cornered rows.
RECON_ROUND: Box = Box(
    "╭─┬╮\n"
    "│ ││\n"
    "├─┼┤\n"
    "│ ││\n"
    "├─┼┤\n"
    "├─┼┤\n"
    "│ ││\n"
    "╰─┴╯\n",
    ascii=False,
)

# Dashed footer divider — swapped into the card between body and footer
# via ``Panel(..., title="foo")`` customization. Usually applied
# manually with a ``Rule`` renderable.
RECON_DASHED: Box = Box(
    "╌─┬╌\n"
    "│ ││\n"
    "├╌┼┤\n"
    "│ ││\n"
    "├╌┼┤\n"
    "├╌┼┤\n"
    "│ ││\n"
    "╌─┴╌\n",
    ascii=False,
)
