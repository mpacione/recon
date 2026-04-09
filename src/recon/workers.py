"""Async worker pool for recon.

Semaphore-controlled concurrency for dispatching work to LLM agents.
Preserves input order in results, captures errors per-task.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable  # noqa: TCH003 -- used at runtime
from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")
R = TypeVar("R")


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
    ) -> list[WorkResult[T, R]]:
        """Execute task_fn on all items with bounded concurrency. Preserves order."""
        if not items:
            return []

        semaphore = asyncio.Semaphore(self.max_workers)
        results: list[WorkResult[T, R]] = [None] * len(items)  # type: ignore[list-item]

        async def _wrapped(index: int, item: T) -> None:
            async with semaphore:
                try:
                    value = await task_fn(item)
                    results[index] = WorkResult(item=item, index=index, success=True, value=value)
                except Exception as exc:
                    results[index] = WorkResult(item=item, index=index, success=False, error=exc)

        await asyncio.gather(*[_wrapped(i, item) for i, item in enumerate(items)])

        return results
