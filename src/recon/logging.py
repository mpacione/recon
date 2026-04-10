"""Logging infrastructure for recon.

Centralized logging setup that writes to a file and optionally
to the console. Used by both the CLI and the TUI to diagnose
hangs, async deadlocks, and engine errors.

Usage:
    from recon.logging import configure_logging, get_logger

    configure_logging(level="DEBUG", log_file=Path("~/.recon/tui.log"))
    logger = get_logger(__name__)
    logger.info("something happened")
"""

from __future__ import annotations

import contextlib
import logging
from collections import deque
from dataclasses import dataclass
from pathlib import Path  # noqa: TCH003 -- used at runtime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

_CONFIGURED = False
_LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"


class _FlushingFileHandler(logging.FileHandler):
    """FileHandler that flushes after every emit so tail -f sees writes."""

    def emit(self, record: logging.LogRecord) -> None:
        super().emit(record)
        self.flush()


@dataclass(frozen=True)
class LogEntry:
    """A single log line, ready to render in the TUI log pane."""

    timestamp: str  # HH:MM:SS
    level: str  # INFO/WARN/ERROR/etc
    name: str  # short logger name (last component)
    message: str


class MemoryLogHandler(logging.Handler):
    """Logging handler that keeps the last N records in a deque.

    The TUI's log pane reads from one of these so it can show a live
    tail of engine activity without needing to poll the file. Listener
    callbacks fire on each emit so the pane can refresh reactively.
    """

    def __init__(self, capacity: int = 200) -> None:
        super().__init__()
        self._buffer: deque[LogEntry] = deque(maxlen=capacity)
        self._listeners: list[Callable[[LogEntry], None]] = []

    def emit(self, record: logging.LogRecord) -> None:
        try:
            short_name = record.name.split(".")[-1]
            entry = LogEntry(
                timestamp=self.formatter.formatTime(record, "%H:%M:%S")
                if self.formatter
                else "",
                level=record.levelname,
                name=short_name,
                message=record.getMessage(),
            )
        except Exception:
            return
        self._buffer.append(entry)
        for listener in list(self._listeners):
            with contextlib.suppress(Exception):
                listener(entry)

    def tail(self, n: int) -> list[LogEntry]:
        """Return the most recent ``n`` entries (oldest first)."""
        if n <= 0 or not self._buffer:
            return []
        return list(self._buffer)[-n:]

    def subscribe(self, listener: Callable[[LogEntry], None]) -> None:
        """Register a callback fired on each new log entry."""
        self._listeners.append(listener)

    def unsubscribe(self, listener: Callable[[LogEntry], None]) -> None:
        if listener in self._listeners:
            self._listeners.remove(listener)


_MEMORY_HANDLER: MemoryLogHandler | None = None


def get_memory_handler() -> MemoryLogHandler:
    """Return the process-wide MemoryLogHandler attached to recon's logger.

    The handler is created lazily on first call. After
    ``configure_logging`` runs, the handler is also attached to the
    ``recon`` root logger so every engine module's log calls flow
    through it.
    """
    global _MEMORY_HANDLER
    if _MEMORY_HANDLER is None:
        _MEMORY_HANDLER = MemoryLogHandler()
        _MEMORY_HANDLER.setFormatter(logging.Formatter(_LOG_FORMAT))
    return _MEMORY_HANDLER


def configure_logging(
    level: str = "INFO",
    log_file: Path | None = None,
    console: bool = False,
) -> None:
    """Configure the root recon logger with a file handler.

    Args:
        level: Log level name (DEBUG, INFO, WARNING, ERROR).
        log_file: Path to write logs. Parent dir is created if needed.
        console: If True, also log to stderr. Avoid in TUI mode --
            stderr output corrupts the Textual terminal buffer.
    """
    global _CONFIGURED

    root = logging.getLogger("recon")
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    for handler in list(root.handlers):
        root.removeHandler(handler)

    formatter = logging.Formatter(_LOG_FORMAT)

    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = _FlushingFileHandler(log_file, mode="a", encoding="utf-8")
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

    if console:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        root.addHandler(console_handler)

    # Always attach the in-memory tail handler so the TUI's log pane
    # has something to read.
    memory_handler = get_memory_handler()
    memory_handler.setFormatter(formatter)
    if memory_handler not in root.handlers:
        root.addHandler(memory_handler)

    root.propagate = False
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Get a logger, ensuring it's a child of the recon root logger."""
    if not name.startswith("recon"):
        name = f"recon.{name}"
    return logging.getLogger(name)
