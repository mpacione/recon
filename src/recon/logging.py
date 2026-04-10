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

import logging
from pathlib import Path  # noqa: TCH003 -- used at runtime

_CONFIGURED = False
_LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"


class _FlushingFileHandler(logging.FileHandler):
    """FileHandler that flushes after every emit so tail -f sees writes."""

    def emit(self, record: logging.LogRecord) -> None:
        super().emit(record)
        self.flush()


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

    root.propagate = False
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Get a logger, ensuring it's a child of the recon root logger."""
    if not name.startswith("recon"):
        name = f"recon.{name}"
    return logging.getLogger(name)
