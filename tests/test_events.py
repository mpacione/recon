"""Tests for the in-process engine event bus."""

from __future__ import annotations

from recon.events import (
    CostRecorded,
    EventBus,
    ProfileCreated,
    RunCancelled,
    RunCompleted,
    RunFailed,
    RunStageCompleted,
    RunStageStarted,
    RunStarted,
    SectionFailed,
    SectionResearched,
    ThemesDiscovered,
    WorkspaceOpened,
    event_to_dict,
    get_bus,
    publish,
    reset_bus,
)


class TestEventBus:
    def test_publish_calls_subscribers(self) -> None:
        bus = EventBus()
        seen: list = []
        bus.subscribe(seen.append)

        bus.publish(RunStarted(run_id="abc", operation="pipeline"))

        assert len(seen) == 1
        assert isinstance(seen[0], RunStarted)
        assert seen[0].run_id == "abc"

    def test_subscribe_idempotent(self) -> None:
        bus = EventBus()
        seen: list = []
        bus.subscribe(seen.append)
        bus.subscribe(seen.append)

        bus.publish(RunStarted(run_id="x"))

        assert len(seen) == 1

    def test_unsubscribe_removes_listener(self) -> None:
        bus = EventBus()
        seen: list = []
        bus.subscribe(seen.append)
        bus.unsubscribe(seen.append)

        bus.publish(RunStarted(run_id="x"))

        assert seen == []

    def test_subscriber_exception_does_not_break_others(self) -> None:
        bus = EventBus()
        good: list = []

        def boom(_event):
            raise RuntimeError("subscriber blew up")

        bus.subscribe(boom)
        bus.subscribe(good.append)

        bus.publish(RunStarted(run_id="x"))

        assert len(good) == 1

    def test_clear_drops_all_subscribers(self) -> None:
        bus = EventBus()
        seen: list = []
        bus.subscribe(seen.append)
        bus.clear()

        bus.publish(RunStarted(run_id="x"))

        assert seen == []


class TestProcessBusSingleton:
    def test_get_bus_returns_same_instance(self) -> None:
        a = get_bus()
        b = get_bus()
        assert a is b

    def test_publish_helper_uses_singleton(self) -> None:
        seen: list = []
        get_bus().subscribe(seen.append)
        publish(RunStarted(run_id="abc"))

        assert len(seen) == 1
        assert seen[0].run_id == "abc"

    def test_reset_bus_replaces_singleton(self) -> None:
        old = get_bus()
        seen: list = []
        old.subscribe(seen.append)

        reset_bus()
        publish(RunStarted(run_id="x"))

        # The old subscriber doesn't see anything because it's bound
        # to the old bus instance
        assert seen == []
        assert get_bus() is not old


class TestEventTypes:
    def test_workspace_opened(self) -> None:
        e = WorkspaceOpened(
            workspace_path="/tmp/ws",
            domain="AI tools",
            company_name="Acme",
        )
        assert e.workspace_path == "/tmp/ws"
        assert e.domain == "AI tools"

    def test_profile_created(self) -> None:
        e = ProfileCreated(name="Cursor", slug="cursor", profile_type="competitor")
        assert e.slug == "cursor"

    def test_run_lifecycle_events(self) -> None:
        started = RunStarted(run_id="abc", operation="pipeline")
        stage = RunStageStarted(run_id="abc", stage="research")
        stage_done = RunStageCompleted(run_id="abc", stage="research")
        completed = RunCompleted(run_id="abc", total_cost_usd=1.42)
        failed = RunFailed(run_id="abc", error="boom")
        cancelled = RunCancelled(run_id="abc")

        for e in [started, stage, stage_done, completed, failed, cancelled]:
            assert e.run_id == "abc"

        assert completed.total_cost_usd == 1.42
        assert failed.error == "boom"

    def test_cost_recorded(self) -> None:
        e = CostRecorded(
            run_id="abc",
            model="claude-sonnet-4-5",
            input_tokens=1000,
            output_tokens=500,
            cost_usd=0.42,
        )
        assert e.cost_usd == 0.42
        assert e.input_tokens == 1000

    def test_section_events(self) -> None:
        ok = SectionResearched(competitor_name="Cursor", section_key="overview")
        fail = SectionFailed(
            competitor_name="Cursor",
            section_key="pricing",
            error="LLM timed out",
        )
        assert ok.section_key == "overview"
        assert fail.error == "LLM timed out"

    def test_themes_discovered(self) -> None:
        e = ThemesDiscovered(theme_count=5)
        assert e.theme_count == 5


class TestEventToDict:
    def test_renders_all_payload_fields(self) -> None:
        e = RunStarted(run_id="abc", operation="pipeline")
        d = event_to_dict(e)
        assert d["type"] == "RunStarted"
        assert d["run_id"] == "abc"
        assert d["operation"] == "pipeline"
        assert "ts" in d

    def test_does_not_include_timestamp_field(self) -> None:
        e = RunStarted(run_id="abc")
        d = event_to_dict(e)
        # ts is the rendered ISO string, not the dataclass field name
        assert "timestamp" not in d
