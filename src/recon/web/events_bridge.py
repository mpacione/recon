"""Bridge between the synchronous engine EventBus and async SSE clients.

The recon engine uses a synchronous in-process EventBus (see
``recon.events``) — every subscriber callback runs inline in the
publisher's stack. The web UI needs to fan those events out to N
concurrently-connected browsers over Server-Sent Events.

This module owns that fan-out. One :class:`EventBridge` instance
subscribes to the bus exactly once and pushes each event onto every
live subscriber's :class:`asyncio.Queue`. SSE handlers consume from
their queue via :meth:`EventBridge.subscribe`, an async generator that
also handles cleanup on disconnect.

Backpressure is best-effort: if a subscriber's queue is full we drop
the event for that subscriber (and bump :attr:`dropped_event_count`)
rather than block the publisher. Browsers can re-fetch missed state
via the REST API; the engine cannot tolerate a slow listener stalling
the pipeline.

Same-loop assumption: ``put_nowait`` is called from the synchronous
publisher's stack. When the publisher runs inside an asyncio coroutine
on the same loop as the SSE handlers — which is the steady state when
``recon serve`` runs the pipeline — this is safe. If a future caller
publishes from a different thread, switch to
``loop.call_soon_threadsafe(queue.put_nowait, event)`` here.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from recon.events import Event, EventBus, event_to_dict, get_bus
from recon.logging import get_logger

_log = get_logger(__name__)

_DEFAULT_QUEUE_MAXSIZE = 1024


class EventBridge:
    """Subscribe-once / fan-many bridge for engine events.

    Args:
        bus: EventBus instance to subscribe to. Defaults to the
            process-wide bus from :func:`recon.events.get_bus`.
        queue_maxsize: Per-subscriber queue capacity. Events are
            dropped (not blocked) when a subscriber's queue is full.
    """

    def __init__(
        self,
        bus: EventBus | None = None,
        *,
        queue_maxsize: int = _DEFAULT_QUEUE_MAXSIZE,
    ) -> None:
        self._bus = bus if bus is not None else get_bus()
        self._queue_maxsize = queue_maxsize
        self._queues: list[asyncio.Queue[Event]] = []
        self._dropped = 0
        self._closed = False
        self._bus.subscribe(self._on_event)

    # ------------------------------------------------------------------
    # Bus side — synchronous, runs in the publisher's stack
    # ------------------------------------------------------------------

    def _on_event(self, event: Event) -> None:
        if self._closed:
            return
        for queue in list(self._queues):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                self._dropped += 1
                _log.warning(
                    "EventBridge dropped %s event for slow subscriber "
                    "(dropped_event_count=%d)",
                    type(event).__name__,
                    self._dropped,
                )

    # ------------------------------------------------------------------
    # Subscriber side — async, awaited by SSE handlers
    # ------------------------------------------------------------------

    def subscribe(self) -> AsyncIterator[dict[str, str]]:
        """Return an async iterator yielding event dicts indefinitely.

        Registration is **eager** — the subscriber's queue is added to
        the fan-out list synchronously, before iteration begins. This
        matters when a publisher fires events in the same tick the
        subscriber is created (and is what enables the ``put_nowait``
        contract in :meth:`_on_event`).

        Yielded shape: ``{"event": <type>, "data": <json>}`` —
        compatible with sse-starlette's ServerSentEvent constructor.

        Cleanup happens in the inner generator's ``finally`` clause on
        close, cancellation, or normal exit.
        """
        queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=self._queue_maxsize)
        self._queues.append(queue)

        async def _stream() -> AsyncIterator[dict[str, str]]:
            try:
                while True:
                    event = await queue.get()
                    yield {
                        "event": type(event).__name__,
                        "data": json.dumps(event_to_dict(event), default=str),
                    }
            finally:
                try:
                    self._queues.remove(queue)
                except ValueError:
                    # Already removed by close() or a race; harmless.
                    pass

        return _stream()

    @property
    def subscriber_count(self) -> int:
        """Number of currently-registered async subscribers."""
        return len(self._queues)

    @property
    def dropped_event_count(self) -> int:
        """Total events dropped due to full subscriber queues, since
        construction."""
        return self._dropped

    def close(self) -> None:
        """Stop receiving events and drop all subscribers.

        Idempotent. Used by the FastAPI shutdown hook so the bridge
        doesn't keep buffering events after uvicorn stops.
        """
        if self._closed:
            return
        self._closed = True
        try:
            self._bus.unsubscribe(self._on_event)
        except Exception:  # noqa: BLE001 - defensive on shutdown
            _log.exception("EventBridge unsubscribe failed")
        self._queues.clear()
