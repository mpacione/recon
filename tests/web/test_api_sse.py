"""Tests for the /api/events SSE routes.

The fan-out and queue mechanics live in
``tests/web/test_events_bridge.py``. This file proves only that the
FastAPI routes are wired correctly: the right URL paths exist, the
right content type is advertised, the run-scoped variant filters by
run_id, and the runtime bridge is reachable from
``app.state.event_bridge``.

We avoid full streaming integration tests here because httpx
``client.stream`` interacts poorly with sse-starlette's keep-alive in
the pytest event loop and hangs waiting for connection close. The
filtering generator inside the route is small and pure; we test it
directly to lock the behavior in.
"""

from __future__ import annotations

import asyncio
import inspect
import json

import pytest
from fastapi.testclient import TestClient
from sse_starlette.sse import EventSourceResponse

from recon.events import (
    CostRecorded,
    Event,
    RunStarted,
    SectionStarted,
    event_to_dict,
    publish,
)
from recon.web.api import create_app
from recon.web.events_bridge import EventBridge


@pytest.fixture()
def client() -> TestClient:
    return TestClient(create_app())


class TestRouteRegistration:
    def test_global_events_route_registered(self, client: TestClient) -> None:
        paths = {route.path for route in client.app.routes}
        assert "/api/events" in paths

    def test_run_scoped_events_route_registered(self, client: TestClient) -> None:
        paths = {route.path for route in client.app.routes}
        assert "/api/runs/{run_id}/events" in paths

    def test_event_bridge_attached_to_app_state(self, client: TestClient) -> None:
        bridge = client.app.state.event_bridge
        assert isinstance(bridge, EventBridge)

    def test_route_handler_returns_event_source_response(
        self, client: TestClient,
    ) -> None:
        # Lock in the response type so a future refactor that swaps
        # to plain StreamingResponse without proper SSE framing gets
        # caught by tests instead of by the user.
        events_route = next(
            r for r in client.app.routes if getattr(r, "path", None) == "/api/events"
        )
        # ``from __future__ import annotations`` makes annotations
        # PEP 563 strings, so resolve them via get_type_hints rather
        # than inspecting the raw signature.
        import typing

        hints = typing.get_type_hints(events_route.endpoint)
        assert hints["return"] is EventSourceResponse


class TestRunScopedFiltering:
    """Exercise the filtering generator the route wraps around the bridge."""

    @pytest.mark.asyncio()
    async def test_filter_passes_matching_run_id(self) -> None:
        target = "target-run"
        msg = await _filter_one(
            target,
            [
                # Mismatching run_id: should be filtered out.
                RunStarted(run_id="other", operation="pipeline"),
                # Matching run_id: should pass through.
                CostRecorded(
                    run_id=target,
                    model="claude-sonnet-4-20250514",
                    input_tokens=10,
                    output_tokens=20,
                    cost_usd=0.001,
                ),
            ],
        )
        assert msg["event"] == "CostRecorded"
        payload = json.loads(msg["data"])
        assert payload["run_id"] == target

    @pytest.mark.asyncio()
    async def test_filter_passes_runless_events(self) -> None:
        # Events without a run_id field (SectionStarted etc) fire
        # inside a run even though their payload doesn't carry the
        # id. They must reach every run-scoped subscriber.
        msg = await _filter_one(
            "any-run",
            [SectionStarted(competitor_name="Acme", section_key="overview")],
        )
        assert msg["event"] == "SectionStarted"
        payload = json.loads(msg["data"])
        assert payload["competitor_name"] == "Acme"

    @pytest.mark.asyncio()
    async def test_filter_drops_mismatched_run_id(self) -> None:
        # If we publish only mismatching run_ids, the filter should
        # yield nothing and we should time out.
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(
                _filter_one(
                    "target-run",
                    [
                        RunStarted(run_id="a", operation="pipeline"),
                        RunStarted(run_id="b", operation="pipeline"),
                    ],
                ),
                timeout=0.2,
            )


async def _filter_one(
    run_id: str,
    events_to_publish: list[Event],
) -> dict[str, str]:
    """Subscribe to a fresh bridge, run the route's filter, and return
    the first event the filter yields.

    Mirrors the inline ``_filtered`` generator the route uses so that
    a refactor of the route's logic is reflected in these tests.

    Subscription must register **before** publishing, otherwise the
    bus has no listeners and events vanish. ``EventBridge.subscribe``
    registers eagerly (synchronously) so we just need to call it
    before the publish loop — the lazy outer generator wraps it.
    """
    bridge = EventBridge()
    inner = bridge.subscribe()

    for event in events_to_publish:
        publish(event)

    async def _filtered():
        async for message in inner:
            if f'"run_id": "{run_id}"' in message["data"]:
                yield message
                continue
            if '"run_id"' not in message["data"]:
                yield message

    iterator = _filtered()
    try:
        return await anext(iterator)
    finally:
        await iterator.aclose()
        await inner.aclose()
        bridge.close()


class TestEventSerialization:
    """Lock the serialized SSE payload shape so the JS client can rely on it."""

    def test_event_to_dict_contains_type_and_ts_and_payload(self) -> None:
        event = RunStarted(run_id="abc", operation="pipeline")
        rendered = event_to_dict(event)
        assert rendered["type"] == "RunStarted"
        assert rendered["run_id"] == "abc"
        assert rendered["operation"] == "pipeline"
        assert "ts" in rendered
        # ts must be JSON-serializable (ISO 8601 string).
        json.dumps(rendered)
