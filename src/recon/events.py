"""In-process event bus for recon.

A small publish/subscribe primitive the engine modules use to
broadcast meaningful state transitions (run started, stage
complete, profile created, cost recorded). The TUI's persistent
chrome subscribes so the header bar's run state, cost, and
activity counters update reactively without polling disk state.

Design constraints:
- Synchronous: publish() does not await. Subscribers run inline.
- Best-effort: a misbehaving subscriber must not break the engine.
- Process-wide singleton via :func:`get_bus`. The CLI and TUI
  share one bus instance for the lifetime of the process.
- Strongly typed events: each event subclass declares its fields
  so subscribers can pattern-match on type instead of guessing
  string keys.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from recon.logging import get_logger

_log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Event types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Event:
    """Base class for every recon engine event."""

    timestamp: dt.datetime = field(default_factory=lambda: dt.datetime.now(dt.UTC))


@dataclass(frozen=True)
class WorkspaceOpened(Event):
    workspace_path: str = ""
    domain: str = ""
    company_name: str = ""


@dataclass(frozen=True)
class ProfileCreated(Event):
    name: str = ""
    slug: str = ""
    profile_type: str = "competitor"


@dataclass(frozen=True)
class DiscoveryStarted(Event):
    domain: str = ""
    round_num: int = 1


@dataclass(frozen=True)
class DiscoveryComplete(Event):
    domain: str = ""
    candidates: int = 0
    round_num: int = 1


@dataclass(frozen=True)
class RunStarted(Event):
    run_id: str = ""
    operation: str = ""


@dataclass(frozen=True)
class RunStageStarted(Event):
    run_id: str = ""
    stage: str = ""


@dataclass(frozen=True)
class RunStageCompleted(Event):
    run_id: str = ""
    stage: str = ""


@dataclass(frozen=True)
class RunCompleted(Event):
    run_id: str = ""
    total_cost_usd: float = 0.0


@dataclass(frozen=True)
class RunFailed(Event):
    run_id: str = ""
    error: str = ""


@dataclass(frozen=True)
class RunCancelled(Event):
    run_id: str = ""


@dataclass(frozen=True)
class RunPaused(Event):
    run_id: str = ""


@dataclass(frozen=True)
class RunResumed(Event):
    run_id: str = ""


@dataclass(frozen=True)
class CostRecorded(Event):
    run_id: str = ""
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0


@dataclass(frozen=True)
class SectionStarted(Event):
    competitor_name: str = ""
    section_key: str = ""


@dataclass(frozen=True)
class SectionResearched(Event):
    competitor_name: str = ""
    section_key: str = ""


@dataclass(frozen=True)
class SectionRetrying(Event):
    competitor_name: str = ""
    section_key: str = ""
    attempt: int = 1
    error: str = ""


@dataclass(frozen=True)
class SectionFailed(Event):
    competitor_name: str = ""
    section_key: str = ""
    error: str = ""


@dataclass(frozen=True)
class ThemesDiscovered(Event):
    theme_count: int = 0


# ---------------------------------------------------------------------------
# Bus
# ---------------------------------------------------------------------------


Subscriber = Callable[[Event], None]


class EventBus:
    """Synchronous in-process publish/subscribe bus."""

    def __init__(self) -> None:
        self._subscribers: list[Subscriber] = []

    def publish(self, event: Event) -> None:
        """Broadcast an event to every subscriber.

        Each subscriber runs inline. Exceptions are caught and
        logged so a single broken listener can't poison the engine.
        """
        for subscriber in list(self._subscribers):
            try:
                subscriber(event)
            except Exception:
                _log.exception("event subscriber raised on %s", type(event).__name__)

    def subscribe(self, subscriber: Subscriber) -> None:
        if subscriber not in self._subscribers:
            self._subscribers.append(subscriber)

    def unsubscribe(self, subscriber: Subscriber) -> None:
        if subscriber in self._subscribers:
            self._subscribers.remove(subscriber)

    def clear(self) -> None:
        """Drop every subscriber. Used by tests for isolation."""
        self._subscribers.clear()


_BUS: EventBus | None = None


def get_bus() -> EventBus:
    """Return the process-wide event bus, creating it on first call."""
    global _BUS
    if _BUS is None:
        _BUS = EventBus()
    return _BUS


def reset_bus() -> None:
    """Replace the process-wide bus with a fresh instance.

    Tests use this to make sure subscribers from earlier tests
    don't bleed in.
    """
    global _BUS
    _BUS = EventBus()


def publish(event: Event) -> None:
    """Convenience: ``publish(event)`` instead of ``get_bus().publish(event)``."""
    get_bus().publish(event)


# ---------------------------------------------------------------------------
# Helpers for assembling event payloads from structured data
# ---------------------------------------------------------------------------


def event_to_dict(event: Event) -> dict[str, Any]:
    """Render an event as a flat dict (for logging or serialization)."""
    payload: dict[str, Any] = {"type": type(event).__name__, "ts": event.timestamp.isoformat()}
    for k, v in event.__dict__.items():
        if k == "timestamp":
            continue
        payload[k] = v
    return payload
