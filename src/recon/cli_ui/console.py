"""Factory for the themed Rich Console used across every subcommand."""

from __future__ import annotations

import sys

from rich.console import Console
from rich.traceback import install as install_pretty_tracebacks

from recon.cli_ui.theme import RECON_THEME


class _ReconConsole(Console):
    """Themed console that emits a trailing blank line on exit.

    The CLI-tier output runs right up against the shell prompt without
    visual breathing room by default. We register an ``atexit`` hook
    that prints an empty line after the last render, so commands end
    with one spacer before the shell reclaims the screen.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        import atexit

        atexit.register(self._farewell)

    def _farewell(self) -> None:
        # Only print if we actually rendered something — otherwise
        # we'd stamp a blank line after `recon --help`'s plain click
        # output and mess with the pure-stdout contract for pipes.
        if self.is_terminal:
            try:
                print()
            except Exception:  # noqa: BLE001
                pass


def build_console(*, force_color: bool | None = None, record: bool = False, width: int | None = None) -> Console:
    """Return a themed Rich Console.

    Defaults:
    - Auto-detects TTY (so ``recon plan | less`` strips ANSI).
    - Honors ``NO_COLOR`` and ``FORCE_COLOR`` env vars natively.
    - ``highlight=False`` — no auto-highlighting of numbers/repr; views
      style explicitly via markup so tests stay stable.
    - Width auto-detects on TTY, falls back to 120 on pipe.

    Call ``install_tracebacks(console)`` once at CLI entry if you want
    uncaught exceptions to render pretty.
    """
    target_width = width
    if target_width is None and not sys.stdout.isatty():
        target_width = 120
    return _ReconConsole(
        theme=RECON_THEME,
        force_terminal=force_color,
        highlight=False,
        width=target_width,
        record=record,
    )


def install_tracebacks(console: Console) -> None:
    """Pretty-print uncaught exceptions via Rich.

    Called once from the CLI entry. Suppresses ``click`` internals from
    the traceback so the user sees their own call site, not our routing.
    """
    try:
        import click
        suppressed = [click]
    except ImportError:
        suppressed = []
    install_pretty_tracebacks(console=console, show_locals=False, suppress=suppressed)
