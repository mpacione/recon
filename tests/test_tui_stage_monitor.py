"""Tests for the StageMonitor widget.

Stacked layout: worker cards render above the competitor roster.
Adapts to different pipeline stages (research, enrich, synthesize,
deliver).
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
        verification_mode: str = "standard",
    ) -> None:
        super().__init__()
        self._competitor_names = competitor_names or []
        self._section_keys = section_keys or []
        self._verification_mode = verification_mode

    def compose(self) -> ComposeResult:
        from recon.tui.stage_monitor import StageMonitor

        yield StageMonitor(
            competitor_names=self._competitor_names,
            section_keys=self._section_keys,
            verification_mode=self._verification_mode,
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

    async def test_shows_competitor_names_in_roster(self) -> None:
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

    async def test_shows_agents_and_competitors_sections(self) -> None:
        app = _MonitorTestApp(
            competitor_names=["Alpha", "Beta"],
            section_keys=["overview"],
        )
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            from recon.tui.stage_monitor import StageMonitor

            monitor = app.query_one(StageMonitor)
            content = str(monitor.render())
            assert "AGENTS" in content
            assert "COMPETITORS" in content

    async def test_no_w_numbering_in_worker_cards(self) -> None:
        from recon.events import SectionStarted, publish

        app = _MonitorTestApp(
            competitor_names=["Alpha"],
            section_keys=["overview"],
        )
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            publish(SectionStarted(competitor_name="Alpha", section_key="overview"))
            await pilot.pause()
            from recon.tui.stage_monitor import StageMonitor

            monitor = app.query_one(StageMonitor)
            content = str(monitor.render())
            assert "[W1]" not in content
            assert "Alpha" in content

    async def test_shows_stage_header_and_active_counts(self) -> None:
        app = _MonitorTestApp(
            competitor_names=["Alpha"],
            section_keys=["overview"],
            verification_mode="deep",
        )
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            from recon.tui.stage_monitor import StageMonitor

            monitor = app.query_one(StageMonitor)
            content = str(monitor.render())
            assert "READY" in content
            assert "Active:" in content
