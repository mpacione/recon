"""Tests for the CompetitorGrid and WorkerPanel run monitor widgets."""

from __future__ import annotations

from textual.app import App, ComposeResult


class _GridTestApp(App):
    CSS = "Screen { background: #000000; }"

    def __init__(
        self,
        competitor_names: list[str] | None = None,
        section_keys: list[str] | None = None,
    ) -> None:
        super().__init__()
        self._competitor_names = competitor_names or []
        self._section_keys = section_keys or []

    def compose(self) -> ComposeResult:
        from recon.tui.run_monitor import CompetitorGrid, WorkerPanel

        grid = CompetitorGrid(
            competitor_names=self._competitor_names,
            section_keys=self._section_keys,
        )
        yield grid
        yield WorkerPanel(grid=grid)


class TestCompetitorGridRendering:
    async def test_empty_grid_shows_waiting(self) -> None:
        from recon.tui.run_monitor import CompetitorGrid

        app = _GridTestApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            grid = app.query_one(CompetitorGrid)
            content = str(grid.render())
            assert "waiting" in content.lower()

    async def test_grid_shows_competitor_names(self) -> None:
        from recon.tui.run_monitor import CompetitorGrid

        app = _GridTestApp(
            competitor_names=["Cursor", "Copilot", "Codeium"],
            section_keys=["overview", "pricing"],
        )
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            grid = app.query_one(CompetitorGrid)
            content = str(grid.render())
            assert "Cursor" in content
            assert "Copilot" in content
            assert "Codeium" in content

    async def test_grid_shows_progress_bar_per_competitor(self) -> None:
        from recon.tui.run_monitor import CompetitorGrid

        app = _GridTestApp(
            competitor_names=["Alpha"],
            section_keys=["overview", "pricing", "capabilities"],
        )
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            grid = app.query_one(CompetitorGrid)
            content = str(grid.render())
            assert "0/3" in content
            assert "0%" in content


class TestCompetitorGridEventHandling:
    async def test_section_started_shows_active_indicator(self) -> None:
        from recon.events import SectionStarted, publish
        from recon.tui.run_monitor import CompetitorGrid

        app = _GridTestApp(
            competitor_names=["Cursor"],
            section_keys=["overview", "pricing"],
        )
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            publish(SectionStarted(competitor_name="Cursor", section_key="overview"))
            await pilot.pause()
            grid = app.query_one(CompetitorGrid)
            content = str(grid.render())
            assert ">>" in content
            assert "overview" in content

    async def test_section_researched_increments_progress(self) -> None:
        from recon.events import SectionResearched, publish
        from recon.tui.run_monitor import CompetitorGrid

        app = _GridTestApp(
            competitor_names=["Cursor"],
            section_keys=["overview", "pricing", "capabilities"],
        )
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            publish(SectionResearched(competitor_name="Cursor", section_key="overview"))
            await pilot.pause()
            grid = app.query_one(CompetitorGrid)
            content = str(grid.render())
            assert "1/3" in content
            assert "33%" in content

    async def test_all_sections_done_shows_ok(self) -> None:
        from recon.events import SectionResearched, publish
        from recon.tui.run_monitor import CompetitorGrid

        app = _GridTestApp(
            competitor_names=["Cursor"],
            section_keys=["overview", "pricing"],
        )
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            publish(SectionResearched(competitor_name="Cursor", section_key="overview"))
            publish(SectionResearched(competitor_name="Cursor", section_key="pricing"))
            await pilot.pause()
            grid = app.query_one(CompetitorGrid)
            content = str(grid.render())
            assert "2/2" in content
            assert "ok" in content.lower()

    async def test_section_failed_shows_failed_count(self) -> None:
        from recon.events import SectionFailed, publish
        from recon.tui.run_monitor import CompetitorGrid

        app = _GridTestApp(
            competitor_names=["Cursor"],
            section_keys=["overview", "pricing"],
        )
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            publish(SectionFailed(competitor_name="Cursor", section_key="pricing", error="timeout"))
            await pilot.pause()
            grid = app.query_one(CompetitorGrid)
            content = str(grid.render())
            assert "failed" in content.lower()

    async def test_section_failed_shows_error_detail_inline(self) -> None:
        from recon.events import SectionFailed, publish
        from recon.tui.run_monitor import CompetitorGrid

        app = _GridTestApp(
            competitor_names=["Cursor"],
            section_keys=["overview", "pricing"],
        )
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            publish(SectionFailed(
                competitor_name="Cursor",
                section_key="pricing",
                error="rate limit exceeded",
            ))
            await pilot.pause()
            grid = app.query_one(CompetitorGrid)
            content = str(grid.render())
            assert "rate limit" in content.lower()

    async def test_section_retrying_shows_retrying_state(self) -> None:
        from recon.events import SectionRetrying, publish
        from recon.tui.run_monitor import CompetitorGrid

        app = _GridTestApp(
            competitor_names=["Cursor"],
            section_keys=["overview", "pricing"],
        )
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            publish(SectionRetrying(
                competitor_name="Cursor",
                section_key="pricing",
                attempt=1,
                error="timeout",
            ))
            await pilot.pause()
            grid = app.query_one(CompetitorGrid)
            content = str(grid.render())
            assert "retrying" in content.lower()

    async def test_cost_recorded_updates_total(self) -> None:
        from recon.events import CostRecorded, RunStarted, publish
        from recon.tui.run_monitor import CompetitorGrid

        app = _GridTestApp(
            competitor_names=["Cursor"],
            section_keys=["overview"],
        )
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            publish(RunStarted(run_id="r1", operation="full_pipeline"))
            publish(CostRecorded(run_id="r1", model="m", input_tokens=100, output_tokens=50, cost_usd=0.42))
            publish(CostRecorded(run_id="r1", model="m", input_tokens=80, output_tokens=40, cost_usd=0.31))
            await pilot.pause()
            grid = app.query_one(CompetitorGrid)
            content = str(grid.render())
            assert "$0.73" in content

    async def test_global_progress_bar_shows_total(self) -> None:
        from recon.events import SectionResearched, publish
        from recon.tui.run_monitor import CompetitorGrid

        app = _GridTestApp(
            competitor_names=["A", "B"],
            section_keys=["overview", "pricing"],
        )
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            publish(SectionResearched(competitor_name="A", section_key="overview"))
            publish(SectionResearched(competitor_name="A", section_key="pricing"))
            publish(SectionResearched(competitor_name="B", section_key="overview"))
            await pilot.pause()
            grid = app.query_one(CompetitorGrid)
            content = str(grid.render())
            assert "3/4" in content or "3" in content
            assert "75%" in content


class TestWorkerPanel:
    async def test_no_active_workers_shows_none(self) -> None:
        from recon.tui.run_monitor import WorkerPanel

        app = _GridTestApp(
            competitor_names=["Cursor"],
            section_keys=["overview"],
        )
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            panel = app.query_one(WorkerPanel)
            # Force an immediate refresh instead of waiting for the
            # 0.5s poll interval to fire.
            panel._refresh()
            content = str(panel.render())
            assert "none" in content.lower() or "WORKERS" in content

    async def test_active_workers_show_competitor_and_section(self) -> None:
        from recon.events import SectionStarted, publish
        from recon.tui.run_monitor import WorkerPanel

        app = _GridTestApp(
            competitor_names=["Cursor", "Copilot"],
            section_keys=["overview", "pricing"],
        )
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            publish(SectionStarted(competitor_name="Cursor", section_key="pricing"))
            publish(SectionStarted(competitor_name="Copilot", section_key="overview"))
            await pilot.pause()
            panel = app.query_one(WorkerPanel)
            panel._refresh()
            content = str(panel.render())
            assert "Cursor" in content
            assert "pricing" in content
            assert "Copilot" in content

    async def test_worker_count_updates_on_completion(self) -> None:
        from recon.events import SectionResearched, SectionStarted, publish
        from recon.tui.run_monitor import CompetitorGrid

        app = _GridTestApp(
            competitor_names=["A", "B"],
            section_keys=["overview"],
        )
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            publish(SectionStarted(competitor_name="A", section_key="overview"))
            publish(SectionStarted(competitor_name="B", section_key="overview"))
            await pilot.pause()
            grid = app.query_one(CompetitorGrid)
            assert len(grid.state.active_section_names) == 2

            publish(SectionResearched(competitor_name="A", section_key="overview"))
            await pilot.pause()
            assert len(grid.state.active_section_names) == 1


class TestRunMonitorState:
    def test_progress_fraction_with_no_sections(self) -> None:
        from recon.tui.run_monitor import RunMonitorState

        state = RunMonitorState()
        assert state.progress_fraction == 0.0

    def test_progress_fraction_partial(self) -> None:
        from collections import OrderedDict

        from recon.tui.run_monitor import DONE, WAITING, CompetitorStatus, RunMonitorState

        state = RunMonitorState()
        cs = CompetitorStatus(
            name="Test",
            sections=OrderedDict([("a", DONE), ("b", WAITING), ("c", DONE), ("d", WAITING)]),
        )
        state.competitors["Test"] = cs
        assert state.progress_fraction == 0.5

    def test_elapsed_str_format(self) -> None:
        import time

        from recon.tui.run_monitor import RunMonitorState

        state = RunMonitorState(started_at=time.monotonic() - 125)
        elapsed = state.elapsed_str
        assert ":" in elapsed
        assert "2:0" in elapsed  # ~2 minutes 5 seconds
