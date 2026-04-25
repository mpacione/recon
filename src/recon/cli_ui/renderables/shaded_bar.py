"""▓▒░ shaded-block progress bar — the v4 aesthetic in pure text.

Rich's built-in ``ProgressBar`` hardcodes ``━╸╺`` as its fill chars
(see rich/progress_bar.py). We can't swap those, so we implement our
own two ways:

- :func:`shaded_bar`  — a one-shot ``rich.text.Text`` for static
  output (e.g. a card row that prints the bar once and stops).
- :class:`ShadedBarColumn` — a ``rich.progress.ProgressColumn`` for
  the live streaming pattern (``recon research --follow``).

Both share one rendering helper so the output is identical regardless
of path. Shading: full = ``▓``, half = ``▒`` (one cell at the fill
boundary), empty = ``░``.
"""

from __future__ import annotations

from rich.progress import ProgressColumn, Task
from rich.text import Text

_BAR_FILLED = "▓"
_BAR_HALF = "▒"
_BAR_EMPTY = "░"


def _render(pct: float, width: int) -> str:
    """Build the bar string for ``pct`` (0..100) over ``width`` cells."""
    clamped = max(0.0, min(100.0, float(pct)))
    exact = (clamped / 100.0) * width
    filled = int(exact)
    # The single half-cell appears at the fill boundary when the exact
    # fraction lands > 0.5 into the next cell. Keeps the bar feeling
    # smooth without subpixel math.
    half = 1 if (exact - filled) >= 0.5 else 0
    empty = max(0, width - filled - half)
    return _BAR_FILLED * filled + _BAR_HALF * half + _BAR_EMPTY * empty


def shaded_bar(pct: float, width: int = 24, *, style: str = "bar") -> Text:
    """Return a styled :class:`rich.text.Text` shaded bar.

    Use when you have a static known value and want to print once
    (e.g. inside a table row or a card body).
    """
    return Text(_render(pct, width), style=style)


class ShadedBarColumn(ProgressColumn):
    """A ``rich.progress.Progress`` column that renders ``▓▒░``.

    Usage::

        from rich.progress import Progress, TextColumn, TaskProgressColumn

        with Progress(
            TextColumn("[card.title]{task.description:<18}[/]"),
            ShadedBarColumn(width=24),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            ...

    Width is fixed at construction — reflow on terminal resize isn't
    worth the complexity for a one-shot CLI. Callers can pick a width
    that matches the surrounding layout.
    """

    def __init__(self, width: int = 24, *, style: str = "bar") -> None:
        super().__init__()
        self._width = width
        self._style = style

    def render(self, task: Task) -> Text:  # noqa: D401
        pct = task.percentage if task.total is not None and task.total > 0 else 0.0
        return Text(_render(pct, self._width), style=self._style)
