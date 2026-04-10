"""Tests for recon.logging module."""

from __future__ import annotations

import logging
from pathlib import Path  # noqa: TCH003 -- used at runtime

from recon.logging import configure_logging, get_logger


class TestConfigureLogging:
    def test_configures_file_handler(self, tmp_path: Path) -> None:
        log_file = tmp_path / "recon.log"
        configure_logging(level="DEBUG", log_file=log_file)

        logger = get_logger("test")
        logger.info("hello world")

        assert log_file.exists()
        content = log_file.read_text()
        assert "hello world" in content

    def test_respects_level(self, tmp_path: Path) -> None:
        log_file = tmp_path / "recon.log"
        configure_logging(level="WARNING", log_file=log_file)

        logger = get_logger("test2")
        logger.debug("debug message")
        logger.warning("warning message")

        content = log_file.read_text()
        assert "debug message" not in content
        assert "warning message" in content

    def test_includes_timestamps(self, tmp_path: Path) -> None:
        log_file = tmp_path / "recon.log"
        configure_logging(level="INFO", log_file=log_file)

        logger = get_logger("test3")
        logger.info("timestamped entry")

        content = log_file.read_text()
        import re

        assert re.search(r"\d{4}-\d{2}-\d{2}", content)

    def test_includes_logger_name(self, tmp_path: Path) -> None:
        log_file = tmp_path / "recon.log"
        configure_logging(level="INFO", log_file=log_file)

        logger = get_logger("recon.tui.app")
        logger.info("app started")

        content = log_file.read_text()
        assert "recon.tui.app" in content

    def test_creates_parent_directory(self, tmp_path: Path) -> None:
        log_file = tmp_path / "nested" / "dir" / "recon.log"
        configure_logging(level="INFO", log_file=log_file)

        logger = get_logger("test5")
        logger.info("nested log")

        assert log_file.exists()


class TestGetLogger:
    def test_returns_logger_instance(self) -> None:
        logger = get_logger("some.module")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "recon.some.module"

    def test_prefixed_name_not_double_prefixed(self) -> None:
        logger = get_logger("recon.already.prefixed")
        assert logger.name == "recon.already.prefixed"

    def test_same_name_returns_same_logger(self) -> None:
        logger1 = get_logger("same.name")
        logger2 = get_logger("same.name")
        assert logger1 is logger2
