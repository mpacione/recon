"""Tests for the EventBridge that fans EventBus events to SSE clients.

The bridge sits between the synchronous engine EventBus and the async
SSE endpoints. We prove:

- It subscribes to the bus on construction and forwards events.
- Multiple async subscribers each get every event independently.
- A subscriber that disconnects cleans itself out of the fan-out list.
- Slow subscribers don't block the publisher (best-effort drop on full).
- Events are serialized as ``{"event": "<TypeName>", "data": "<json>"}``
  ready for sse-starlette's ServerSentEvent format.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from recon.events import (
    CostRecorded,
    EventBus,
    RunStarted,
    SectionStarted,
    get_bus,
    publish,
)
from recon.web.events_bridge import EventBridge


@pytest.fixture()
def bridge() -> EventBridge:
    """Fresh bridge bound to the (per-test) reset event bus."""
    return EventBridge(bus=get_bus())


@pytest.mark.asyncio()
async def test_subscriber_receives_published_event(bridge: EventBridge) -> None:
    """A single subscriber sees an event published after subscribe()."""
    received: list[dict] = []
    iterator = bridge.subscribe()

    async def consume() -> None:
        # Pull a single message then release.
        msg = await asyncio.wait_for(anext(iterator), timeout=1.0)
        received.append(msg)

    consumer_task = asyncio.create_task(consume())
    # Yield once so the consumer registers its queue.
    await asyncio.sleep(0)

    publish(RunStarted(run_id="run-abc", operation="pipeline"))
    await consumer_task

    assert len(received) == 1
    assert received[0]["event"] == "RunStarted"
    payload = json.loads(received[0]["data"])
    assert payload["type"] == "RunStarted"
    assert payload["run_id"] == "run-abc"
    assert payload["operation"] == "pipeline"


@pytest.mark.asyncio()
async def test_two_subscribers_each_receive_event(bridge: EventBridge) -> None:
    """Two simultaneous subscribers both see the same event."""
    iter_a = bridge.subscribe()
    iter_b = bridge.subscribe()

    async def grab(it):
        return await asyncio.wait_for(anext(it), timeout=1.0)

    task_a = asyncio.create_task(grab(iter_a))
    task_b = asyncio.create_task(grab(iter_b))
    await asyncio.sleep(0)

    publish(SectionStarted(competitor_name="Acme", section_key="overview"))
    msg_a = await task_a
    msg_b = await task_b

    assert msg_a["event"] == msg_b["event"] == "SectionStarted"
    assert json.loads(msg_a["data"])["competitor_name"] == "Acme"
    assert json.loads(msg_b["data"])["competitor_name"] == "Acme"


@pytest.mark.asyncio()
async def test_subscriber_count_reflects_active_iterators(
    bridge: EventBridge,
) -> None:
    """subscriber_count tracks live consumers and decrements on close."""
    assert bridge.subscriber_count == 0

    iter_a = bridge.subscribe()
    iter_b = bridge.subscribe()

    # Iterators register lazily on first await; force registration.
    task_a = asyncio.create_task(anext(iter_a))
    task_b = asyncio.create_task(anext(iter_b))
    await asyncio.sleep(0)
    assert bridge.subscriber_count == 2

    publish(RunStarted(run_id="x", operation="pipeline"))
    await task_a
    await task_b

    # Closing one iterator deregisters its queue.
    await iter_a.aclose()
    # Give the finally clause a chance to run.
    await asyncio.sleep(0)
    assert bridge.subscriber_count == 1

    await iter_b.aclose()
    await asyncio.sleep(0)
    assert bridge.subscriber_count == 0


@pytest.mark.asyncio()
async def test_full_queue_drops_event_for_that_subscriber(
    bridge: EventBridge,
) -> None:
    """A wedged subscriber must not block the publisher.

    Construct a bridge with a tiny per-subscriber queue, register a
    subscriber but never consume from it, publish more events than
    the queue can hold, then assert the publisher returned cleanly and
    the drop counter incremented.

    Eager registration in :meth:`EventBridge.subscribe` means we don't
    need to start a consumer task at all — the queue is already in the
    fan-out list once ``subscribe()`` returns.
    """
    small_bridge = EventBridge(bus=get_bus(), queue_maxsize=2)
    iterator = small_bridge.subscribe()
    assert small_bridge.subscriber_count == 1
    # iterator is intentionally never consumed; we hold a ref so the
    # generator (and thus the queue registration) stays alive.

    for i in range(5):
        publish(RunStarted(run_id=f"run-{i}", operation="pipeline"))

    # Publisher returned (we got here). Two events fit in the queue,
    # the remaining three should have been dropped for our wedged
    # subscriber.
    assert small_bridge.dropped_event_count == 3

    # Tidy up so the generator's finally runs deterministically.
    await iterator.aclose()


@pytest.mark.asyncio()
async def test_events_published_before_subscribe_are_not_delivered(
    bridge: EventBridge,
) -> None:
    """The bridge fans live events; it doesn't replay history."""
    publish(RunStarted(run_id="historical", operation="pipeline"))

    iterator = bridge.subscribe()
    consume_task = asyncio.create_task(
        asyncio.wait_for(anext(iterator), timeout=0.2),
    )
    await asyncio.sleep(0)

    publish(CostRecorded(
        run_id="live", model="claude-sonnet-4-20250514",
        input_tokens=10, output_tokens=20, cost_usd=0.001,
    ))

    msg = await consume_task
    assert msg["event"] == "CostRecorded"
    assert json.loads(msg["data"])["run_id"] == "live"


@pytest.mark.asyncio()
async def test_bridge_with_explicit_bus_does_not_touch_global() -> None:
    """Constructing with a private bus keeps the global bus untouched.

    Useful for unit tests and for any future per-run bridges.
    """
    private_bus = EventBus()
    bridge = EventBridge(bus=private_bus)

    iterator = bridge.subscribe()
    consume_task = asyncio.create_task(
        asyncio.wait_for(anext(iterator), timeout=0.5),
    )
    await asyncio.sleep(0)

    # Publishing on the private bus reaches the bridge.
    private_bus.publish(RunStarted(run_id="private", operation="pipeline"))
    msg = await consume_task
    assert json.loads(msg["data"])["run_id"] == "private"

    # Publishing on the global bus does NOT reach this bridge.
    iterator2 = bridge.subscribe()
    consume_task2 = asyncio.create_task(anext(iterator2))
    await asyncio.sleep(0)

    publish(RunStarted(run_id="global", operation="pipeline"))
    # Wait briefly — the message must NOT arrive.
    await asyncio.sleep(0.05)
    assert not consume_task2.done()
    consume_task2.cancel()
    with pytest.raises(asyncio.CancelledError):
        await consume_task2


@pytest.mark.asyncio()
async def test_close_drops_all_subscribers(bridge: EventBridge) -> None:
    """close() empties the subscriber list and unsubscribes from the bus."""
    iterator = bridge.subscribe()
    consume_task = asyncio.create_task(anext(iterator))
    await asyncio.sleep(0)
    assert bridge.subscriber_count == 1

    bridge.close()
    # Subscribers go to zero and the bus subscriber is removed.
    assert bridge.subscriber_count == 0

    # Future publishes should not reach a closed bridge.
    publish(RunStarted(run_id="post-close", operation="pipeline"))
    await asyncio.sleep(0.05)
    assert not consume_task.done()
    consume_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await consume_task
