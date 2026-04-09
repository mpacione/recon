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
