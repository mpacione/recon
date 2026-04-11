"""Tests for ActivityFeed widget.

ActivityFeed lives in the chrome (next to LogPane) and renders typed
engine events from the in-process EventBus with iconography. It is
distinct from LogPane, which renders raw log lines from
``MemoryLogHandler``.
"""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.widgets import Static


class _ActivityFeedTestApp(App):
    CSS = "Screen { background: #000000; }"

    def compose(self) -> ComposeResult:
        from recon.tui.shell import ActivityFeed

        yield ActivityFeed()


class TestActivityFeedRendering:
    async def test_empty_feed_shows_placeholder(self) -> None:
        from recon.tui.shell import ActivityFeed

        app = _ActivityFeedTestApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            feed = app.query_one(ActivityFeed)
            content = str(feed.render())
            assert "waiting" in content.lower() or "no activity" in content.lower()

    async def test_run_started_event_renders_play_icon(self) -> None:
        from recon.events import RunStarted, publish
        from recon.tui.shell import ActivityFeed

        app = _ActivityFeedTestApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            publish(RunStarted(run_id="r1", operation="full_pipeline"))
            await pilot.pause()
            feed = app.query_one(ActivityFeed)
            content = str(feed.render())
            assert "▶" in content
            assert "run started" in content.lower()

    async def test_run_stage_started_event(self) -> None:
        from recon.events import RunStageStarted, publish
        from recon.tui.shell import ActivityFeed

        app = _ActivityFeedTestApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            publish(RunStageStarted(run_id="r1", stage="research"))
            await pilot.pause()
            feed = app.query_one(ActivityFeed)
            content = str(feed.render())
            assert "research" in content
            assert "→" in content

    async def test_run_stage_completed_event(self) -> None:
        from recon.events import RunStageCompleted, publish
        from recon.tui.shell import ActivityFeed

        app = _ActivityFeedTestApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            publish(RunStageCompleted(run_id="r1", stage="enrich"))
            await pilot.pause()
            feed = app.query_one(ActivityFeed)
            content = str(feed.render())
            assert "enrich" in content
            assert "✓" in content

    async def test_run_completed_includes_cost(self) -> None:
        from recon.events import RunCompleted, publish
        from recon.tui.shell import ActivityFeed

        app = _ActivityFeedTestApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            publish(RunCompleted(run_id="r1", total_cost_usd=4.27))
            await pilot.pause()
            feed = app.query_one(ActivityFeed)
            content = str(feed.render())
            assert "$4.27" in content
            assert "run complete" in content.lower()

    async def test_run_failed_renders_x(self) -> None:
        from recon.events import RunFailed, publish
        from recon.tui.shell import ActivityFeed

        app = _ActivityFeedTestApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            publish(RunFailed(run_id="r1", error="api timeout"))
            await pilot.pause()
            feed = app.query_one(ActivityFeed)
            content = str(feed.render())
            assert "✗" in content
            assert "failed" in content.lower()

    async def test_run_cancelled_renders_circle_slash(self) -> None:
        from recon.events import RunCancelled, publish
        from recon.tui.shell import ActivityFeed

        app = _ActivityFeedTestApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            publish(RunCancelled(run_id="r1"))
            await pilot.pause()
            feed = app.query_one(ActivityFeed)
            content = str(feed.render())
            assert "⊘" in content
            assert "cancelled" in content.lower()

    async def test_cost_recorded_renders_dollar(self) -> None:
        from recon.events import CostRecorded, publish
        from recon.tui.shell import ActivityFeed

        app = _ActivityFeedTestApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            publish(
                CostRecorded(
                    run_id="r1",
                    model="claude-sonnet-4-5",
                    input_tokens=1000,
                    output_tokens=500,
                    cost_usd=0.42,
                ),
            )
            await pilot.pause()
            feed = app.query_one(ActivityFeed)
            content = str(feed.render())
            assert "$0.42" in content
            assert "$" in content

    async def test_section_researched_renders_dotted_path(self) -> None:
        from recon.events import SectionResearched, publish
        from recon.tui.shell import ActivityFeed

        app = _ActivityFeedTestApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            publish(SectionResearched(competitor_name="Cursor", section_key="overview"))
            await pilot.pause()
            feed = app.query_one(ActivityFeed)
            content = str(feed.render())
            assert "Cursor" in content
            assert "overview" in content
            assert "✓" in content

    async def test_section_failed_renders_x(self) -> None:
        from recon.events import SectionFailed, publish
        from recon.tui.shell import ActivityFeed

        app = _ActivityFeedTestApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            publish(
                SectionFailed(
                    competitor_name="Linear",
                    section_key="pricing",
                    error="rate limit",
                ),
            )
            await pilot.pause()
            feed = app.query_one(ActivityFeed)
            content = str(feed.render())
            assert "Linear" in content
            assert "pricing" in content
            assert "✗" in content

    async def test_themes_discovered_renders_circle(self) -> None:
        from recon.events import ThemesDiscovered, publish
        from recon.tui.shell import ActivityFeed

        app = _ActivityFeedTestApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            publish(ThemesDiscovered(theme_count=5))
            await pilot.pause()
            feed = app.query_one(ActivityFeed)
            content = str(feed.render())
            assert "5" in content
            assert "themes" in content.lower()
            assert "◎" in content

    async def test_profile_created_renders_plus(self) -> None:
        from recon.events import ProfileCreated, publish
        from recon.tui.shell import ActivityFeed

        app = _ActivityFeedTestApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            publish(ProfileCreated(name="Cursor", slug="cursor"))
            await pilot.pause()
            feed = app.query_one(ActivityFeed)
            content = str(feed.render())
            assert "Cursor" in content
            assert "+" in content


class TestActivityFeedBoundedDeque:
    async def test_feed_holds_at_most_20_entries(self) -> None:
        from recon.events import RunStageStarted, publish
        from recon.tui.shell import ActivityFeed

        app = _ActivityFeedTestApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            for i in range(25):
                publish(RunStageStarted(run_id="r1", stage=f"stage_{i}"))
            await pilot.pause()
            feed = app.query_one(ActivityFeed)
            # The first 5 entries should have been dropped
            content = str(feed.render())
            assert "stage_0" not in content
            assert "stage_4" not in content
            assert "stage_24" in content

    async def test_feed_ordering_newest_at_bottom(self) -> None:
        from recon.events import RunStageStarted, publish
        from recon.tui.shell import ActivityFeed

        app = _ActivityFeedTestApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            publish(RunStageStarted(run_id="r1", stage="alpha"))
            publish(RunStageStarted(run_id="r1", stage="beta"))
            publish(RunStageStarted(run_id="r1", stage="gamma"))
            await pilot.pause()
            feed = app.query_one(ActivityFeed)
            content = str(feed.render())
            alpha_pos = content.find("alpha")
            beta_pos = content.find("beta")
            gamma_pos = content.find("gamma")
            assert alpha_pos != -1
            assert beta_pos != -1
            assert gamma_pos != -1
            assert alpha_pos < beta_pos < gamma_pos


class TestActivityFeedSubscriptionLifecycle:
    async def test_unmount_unsubscribes_from_bus(self) -> None:
        """When the widget is unmounted its subscriber must come off
        the bus so leftover refs don't fire on later events / leak
        across screen swaps.
        """
        from recon.events import RunStarted, get_bus, publish
        from recon.tui.shell import ActivityFeed

        app = _ActivityFeedTestApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            bus = get_bus()
            initial_count = len(bus._subscribers)
            assert initial_count >= 1, "feed should subscribe on mount"
            feed = app.query_one(ActivityFeed)
            await feed.remove()
            await pilot.pause()
            assert len(bus._subscribers) < initial_count, (
                "feed should unsubscribe on unmount"
            )
            # Publishing now must not raise
            publish(RunStarted(run_id="r1", operation="x"))


class TestReconScreenChromeComposesActivityFeed:
    """ActivityFeed should appear in the persistent chrome alongside
    the LogPane on every full screen.
    """

    async def test_recon_screen_includes_activity_feed_widget(self) -> None:
        from recon.tui.shell import ActivityFeed, LogPane, ReconScreen

        class _DummyScreen(ReconScreen):
            def compose_body(self):
                yield Static("dummy body")

        class _DummyApp(App):
            CSS = "Screen { background: #000000; }"

            def compose(self) -> ComposeResult:
                yield Static("")

            def on_mount(self) -> None:
                self.push_screen(_DummyScreen())

        app = _DummyApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.pause()
            # Both panes coexist in the chrome of the active screen
            screen = app.screen
            assert screen.query_one(LogPane) is not None
            assert screen.query_one(ActivityFeed) is not None
