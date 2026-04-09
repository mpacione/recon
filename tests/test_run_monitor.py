"""Tests for the run monitor data model.

The run monitor tracks live pipeline execution state: phase, section,
worker status, progress, costs, and activity feed.
"""

from __future__ import annotations

import pytest

from recon.tui.monitor import RunMonitorModel, WorkerStatus


class TestRunMonitorModel:
    def test_initial_state(self) -> None:
        model = RunMonitorModel(
            run_id="abc123",
            total_competitors=50,
            total_sections=8,
        )

        assert model.run_id == "abc123"
        assert model.current_phase == "idle"
        assert model.progress == 0.0
        assert model.cost_usd == 0.0
        assert model.workers == []
        assert model.activity == []
        assert model.errors == []

    def test_set_phase(self) -> None:
        model = RunMonitorModel(run_id="abc", total_competitors=10, total_sections=3)

        model.set_phase("research", section="overview", section_index=1, total_sections=3)

        assert model.current_phase == "research"
        assert model.current_section == "overview"
        assert model.section_index == 1

    def test_update_progress(self) -> None:
        model = RunMonitorModel(run_id="abc", total_competitors=10, total_sections=3)
        model.set_phase("research", section="overview", section_index=1, total_sections=3)

        model.update_progress(completed=5, total=10)

        assert model.progress == 0.5

    def test_update_worker(self) -> None:
        model = RunMonitorModel(run_id="abc", total_competitors=10, total_sections=3)

        model.update_worker(worker_id="W01", competitor="Cursor", status=WorkerStatus.SEARCHING)

        assert len(model.workers) == 1
        assert model.workers[0].worker_id == "W01"
        assert model.workers[0].competitor == "Cursor"
        assert model.workers[0].status == WorkerStatus.SEARCHING

    def test_update_worker_replaces_existing(self) -> None:
        model = RunMonitorModel(run_id="abc", total_competitors=10, total_sections=3)

        model.update_worker(worker_id="W01", competitor="Cursor", status=WorkerStatus.SEARCHING)
        model.update_worker(worker_id="W01", competitor="Cursor", status=WorkerStatus.COMPLETE)

        assert len(model.workers) == 1
        assert model.workers[0].status == WorkerStatus.COMPLETE

    def test_add_activity(self) -> None:
        model = RunMonitorModel(run_id="abc", total_competitors=10, total_sections=3)

        model.add_activity("Cursor -- Overview -- Y verified")

        assert len(model.activity) == 1
        assert "Cursor" in model.activity[0]

    def test_activity_capped_at_max(self) -> None:
        model = RunMonitorModel(run_id="abc", total_competitors=10, total_sections=3)

        for i in range(60):
            model.add_activity(f"Activity {i}")

        assert len(model.activity) <= 50

    def test_add_error(self) -> None:
        model = RunMonitorModel(run_id="abc", total_competitors=10, total_sections=3)

        model.add_error("Buildkite: table missing Evidence column, retry 1/3")

        assert len(model.errors) == 1
        assert "Buildkite" in model.errors[0]

    def test_record_cost(self) -> None:
        model = RunMonitorModel(run_id="abc", total_competitors=10, total_sections=3)

        model.record_cost(0.12)
        model.record_cost(0.08)

        assert model.cost_usd == pytest.approx(0.20)

    def test_active_worker_count(self) -> None:
        model = RunMonitorModel(run_id="abc", total_competitors=10, total_sections=3)
        model.update_worker("W01", "A", WorkerStatus.SEARCHING)
        model.update_worker("W02", "B", WorkerStatus.WRITING)
        model.update_worker("W03", "C", WorkerStatus.COMPLETE)

        assert model.active_worker_count == 2

    def test_summary_line(self) -> None:
        model = RunMonitorModel(run_id="abc", total_competitors=10, total_sections=3)
        model.set_phase("research", section="capabilities", section_index=2, total_sections=3)
        model.update_progress(completed=7, total=10)

        summary = model.summary_line()

        assert "research" in summary.lower()
        assert "capabilities" in summary.lower()
        assert "70%" in summary
