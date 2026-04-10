"""Async worker pool for recon.

Semaphore-controlled concurrency for dispatching work to LLM agents.
Preserves input order in results, captures errors per-task, and honors
an optional :class:`asyncio.Event` cancellation token so long-running
pipelines can be stopped from the outside (e.g. the TUI Stop button).
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable  # noqa: TCH003 -- used at runtime
from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")
R = TypeVar("R")


class PipelineCancelledError(Exception):
    """Raised when a task is skipped because the cancel_event fired."""


@dataclass
class WorkResult(Generic[T, R]):
    item: T
    index: int
    success: bool
    value: R | None = None
    error: Exception | None = None


class WorkerPool:
    """Async semaphore-controlled worker pool."""

    def __init__(self, max_workers: int = 5) -> None:
        self.max_workers = max_workers

    async def run(
        self,
        task_fn: Callable[[T], Awaitable[R]],
        items: list[T],
        cancel_event: asyncio.Event | None = None,
        pause_event: asyncio.Event | None = None,
    ) -> list[WorkResult[T, R]]:
        """Execute ``task_fn`` on all items with bounded concurrency.

        Results preserve input order. Exceptions in ``task_fn`` become
        ``WorkResult(success=False, error=...)``.

        If ``cancel_event`` is provided and becomes set before a task
        starts, that task is marked cancelled (``success=False`` with a
        :class:`PipelineCancelledError`) instead of running.

        If ``pause_event`` is provided, each worker waits for the event
        to be set before dispatching its task. The semantics are
        ``set = running`` and ``cleared = paused``. Cancellation
        always wins over pause -- a paused worker that observes a
        cancel_event becoming set returns immediately.
        """
        if not items:
            return []

        semaphore = asyncio.Semaphore(self.max_workers)
        results: list[WorkResult[T, R]] = [None] * len(items)  # type: ignore[list-item]

        async def _wait_for_resume() -> bool:
            """Block until pause_event is set or cancel_event fires.

            Returns True if cancelled while waiting, False otherwise.
            """
            if pause_event is None:
                return False
            while not pause_event.is_set():
                if cancel_event is not None and cancel_event.is_set():
                    return True
                try:
                    await asyncio.wait_for(pause_event.wait(), timeout=0.05)
                except TimeoutError:
                    continue
            return False

        async def _wrapped(index: int, item: T) -> None:
            async with semaphore:
                cancelled_during_pause = await _wait_for_resume()
                if cancelled_during_pause or (
                    cancel_event is not None and cancel_event.is_set()
                ):
                    results[index] = WorkResult(
                        item=item,
                        index=index,
                        success=False,
                        error=PipelineCancelledError("cancelled before start"),
                    )
                    return
                try:
                    value = await task_fn(item)
                    results[index] = WorkResult(
                        item=item, index=index, success=True, value=value,
                    )
                except Exception as exc:
                    results[index] = WorkResult(
                        item=item, index=index, success=False, error=exc,
                    )

        await asyncio.gather(*[_wrapped(i, item) for i, item in enumerate(items)])

        return results
