"""Tests for the run monitor display formatting."""

from __future__ import annotations

from recon.tui.monitor import RunMonitorModel, WorkerStatus
from recon.tui.widgets import format_progress_bar, format_worker_list


class TestFormatWorkerList:
    def test_renders_active_workers(self) -> None:
        model = RunMonitorModel(run_id="abc", total_competitors=10, total_sections=3)
        model.update_worker("W01", "Cursor", WorkerStatus.SEARCHING)
        model.update_worker("W02", "Linear", WorkerStatus.WRITING)

        lines = format_worker_list(model)

        assert len(lines) == 2
        assert "W01" in lines[0]
        assert "Cursor" in lines[0]
        assert "searching" in lines[0]

    def test_renders_complete_workers(self) -> None:
        model = RunMonitorModel(run_id="abc", total_competitors=10, total_sections=3)
        model.update_worker("W01", "Cursor", WorkerStatus.COMPLETE)

        lines = format_worker_list(model)

        assert "Y" in lines[0] or "complete" in lines[0]

    def test_empty_workers_returns_empty(self) -> None:
        model = RunMonitorModel(run_id="abc", total_competitors=10, total_sections=3)

        lines = format_worker_list(model)

        assert lines == []


class TestFormatProgressBar:
    def test_renders_progress(self) -> None:
        bar = format_progress_bar(0.5, width=20)

        assert "50%" in bar
        assert "=" in bar

    def test_zero_progress(self) -> None:
        bar = format_progress_bar(0.0, width=20)

        assert "0%" in bar

    def test_full_progress(self) -> None:
        bar = format_progress_bar(1.0, width=20)

        assert "100%" in bar

    def test_error_state_uses_red_and_x_marks(self) -> None:
        bar = format_progress_bar(0.5, width=10, state="error")

        assert "#cc241d" in bar
        assert "X" in bar  # X-marks for unfilled portion

    def test_done_state_uses_green(self) -> None:
        bar = format_progress_bar(1.0, width=10, state="done")

        assert "#98971a" in bar

    def test_paused_state_uses_yellow(self) -> None:
        bar = format_progress_bar(0.5, width=10, state="paused")

        assert "#d79921" in bar

    def test_idle_state_renders_empty_bar(self) -> None:
        bar = format_progress_bar(0.0, width=10, state="idle")

        assert "0%" in bar
        # Idle bar uses dashes only -- no equals signs
        assert "=" not in bar


class TestHumanizePath:
    def test_replaces_home_with_tilde(self) -> None:
        from pathlib import Path

        from recon.tui.widgets import humanize_path

        home = Path.home()
        result = humanize_path(home / "projects" / "recon-test")
        assert result == "~/projects/recon-test"

    def test_collapses_macos_temp_dir(self) -> None:
        from recon.tui.widgets import humanize_path

        result = humanize_path("/var/folders/zd/abc123/T/recon-audit-xyz/ws")
        assert "var/folders" not in result
        assert "$TMP" in result
        assert "ws" in result

    def test_collapses_long_path_with_ellipsis(self) -> None:
        from recon.tui.widgets import humanize_path

        result = humanize_path(
            "/a/very/long/path/with/many/segments/and/even/more/levels/leaf",
            max_width=30,
        )
        assert len(result) <= 30
        assert "leaf" in result
        assert "…" in result

    def test_short_path_unchanged(self) -> None:
        from recon.tui.widgets import humanize_path

        result = humanize_path("/usr/local/bin")
        assert result == "/usr/local/bin"
