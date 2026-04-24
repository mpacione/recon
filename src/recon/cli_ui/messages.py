"""One-liner styled message helpers for CLI subcommands.

Short status lines that don't warrant a full card — success
confirmations, warnings, quiet notes. They print in a consistent v4
aesthetic (glyph prefix + color) so every command feels like part of
the same CLI.

All helpers accept a ``Console`` first so they compose with the
themed console that lives on ``ctx.obj["console"]``.
"""

from __future__ import annotations

from rich.console import Console
from rich.text import Text


def success(console: Console, message: str, *, detail: str | None = None) -> None:
    """Green-check confirmation. Use for "workspace created", "saved", etc."""
    out = Text.assemble(("✓ ", "accent"), (message, "accent"))
    if detail:
        out.append(f"  {detail}", style="body")
    console.print(out)


def info(console: Console, message: str, *, detail: str | None = None) -> None:
    """Neutral info line. Dim glyph + body text."""
    out = Text.assemble(("· ", "dim"), (message, "body"))
    if detail:
        out.append(f"  {detail}", style="dim")
    console.print(out)


def warn(console: Console, message: str) -> None:
    """Non-fatal warning. Amber-equivalent via the muted style."""
    console.print(Text.assemble(("▲ ", "muted"), (message, "muted")))


def error(console: Console, message: str) -> None:
    """Error line. Red glyph + red text. Caller decides whether to ``sys.exit``."""
    console.print(Text.assemble(("✕ ", "error"), (message, "error")))
