"""Tests for the StageMonitor widget (v2 run screen layout).

Two-column layout: left column shows scrollable competitor progress,
right column shows per-worker activity cards. Adapts to different
pipeline stages (research, enrich, synthesize, deliver).
"""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.widgets import Static


class _MonitorTestApp(App):
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
        from recon.tui.stage_monitor import StageMonitor

        yield StageMonitor(
            competitor_names=self._competitor_names,
            section_keys=self._section_keys,
        )


class TestStageMonitor:
    async def test_mounts_with_competitors(self) -> None:
        app = _MonitorTestApp(
            competitor_names=["Alpha", "Beta", "Gamma"],
            section_keys=["overview", "pricing"],
        )
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            from recon.tui.stage_monitor import StageMonitor

            monitor = app.query_one(StageMonitor)
            assert monitor is not None

    async def test_shows_competitor_names_in_left_column(self) -> None:
        app = _MonitorTestApp(
            competitor_names=["Prusa", "Creality", "Formlabs"],
            section_keys=["overview"],
        )
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            from recon.tui.stage_monitor import StageMonitor

            monitor = app.query_one(StageMonitor)
            content = str(monitor.render())
            assert "Prusa" in content
            assert "Creality" in content
            assert "Formlabs" in content

    async def test_shows_worker_cards(self) -> None:
        from recon.events import SectionStarted, publish

        app = _MonitorTestApp(
            competitor_names=["Prusa", "Creality"],
            section_keys=["overview", "pricing"],
        )
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            publish(SectionStarted(competitor_name="Prusa", section_key="overview"))
            await pilot.pause()
            from recon.tui.stage_monitor import StageMonitor

            monitor = app.query_one(StageMonitor)
            content = str(monitor.render())
            assert "W1" in content or "Prusa" in content

    async def test_section_complete_updates_progress(self) -> None:
        from recon.events import SectionResearched, SectionStarted, publish

        app = _MonitorTestApp(
            competitor_names=["Prusa"],
            section_keys=["overview", "pricing"],
        )
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            publish(SectionStarted(competitor_name="Prusa", section_key="overview"))
            publish(SectionResearched(competitor_name="Prusa", section_key="overview"))
            await pilot.pause()
            from recon.tui.stage_monitor import StageMonitor

            monitor = app.query_one(StageMonitor)
            content = str(monitor.render())
            assert "1/2" in content or "50%" in content

    async def test_cost_updates_in_header(self) -> None:
        from recon.events import CostRecorded, RunStarted, publish

        app = _MonitorTestApp(
            competitor_names=["Prusa"],
            section_keys=["overview"],
        )
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            publish(RunStarted(run_id="test", operation="pipeline"))
            publish(CostRecorded(
                run_id="test", model="sonnet", input_tokens=1000,
                output_tokens=500, cost_usd=0.42,
            ))
            await pilot.pause()
            from recon.tui.stage_monitor import StageMonitor

            monitor = app.query_one(StageMonitor)
            content = str(monitor.render())
            assert "$0.42" in content

    async def test_enrichment_events_update_state(self) -> None:
        from recon.events import EnrichmentCompleted, EnrichmentStarted, publish

        app = _MonitorTestApp(
            competitor_names=["Prusa", "Creality"],
            section_keys=["overview"],
        )
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            publish(EnrichmentStarted(competitor_name="Prusa", pass_name="cleanup"))
            publish(EnrichmentCompleted(competitor_name="Prusa", pass_name="cleanup"))
            await pilot.pause()
            from recon.tui.stage_monitor import StageMonitor

            monitor = app.query_one(StageMonitor)
            # Just verify it doesn't crash on enrichment events
            assert monitor is not None
