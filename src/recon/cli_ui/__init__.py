"""Terminal-CLI rendering layer for recon.

Third tier alongside the Textual TUI (``recon.tui``) and the FastAPI
web UI (``recon.web``). This layer handles **one-shot styled stdout**
for click subcommands — no event loop, no screen ownership, just
``rich.console.Console.print()`` with our theme applied.

Entry points:

- :func:`build_console` — factory returning a themed Console. Screens
  get this via ``ctx.obj["console"]`` off the click group.
- :mod:`cli_ui.renderables` — custom Rich renderables (shaded block
  progress bar, card wrapper, numbered tab breadcrumb) that match the
  v4 web UI aesthetic.
- :mod:`cli_ui.views` — one ``render_*`` function per subcommand,
  taking a Pydantic DTO (shared with ``recon.web.schemas``) and a
  Console.
"""

from __future__ import annotations

from recon.cli_ui.console import build_console
from recon.cli_ui.theme import RECON_THEME

__all__ = ["build_console", "RECON_THEME"]
