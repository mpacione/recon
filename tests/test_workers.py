"""Tests for the async worker pool.

The worker pool provides semaphore-controlled concurrency for dispatching
work to LLM agents. Supports configurable concurrency and error handling.
"""

import asyncio

from recon.workers import WorkerPool


class TestWorkerPool:
    async def test_executes_tasks(self) -> None:
        results: list[str] = []

        async def task(item: str) -> str:
            results.append(item)
            return f"done-{item}"

        pool = WorkerPool(max_workers=3)
        outcomes = await pool.run(task, ["a", "b", "c"])

        assert len(outcomes) == 3
        assert all(o.success for o in outcomes)
        assert {o.value for o in outcomes} == {"done-a", "done-b", "done-c"}

    async def test_respects_concurrency_limit(self) -> None:
        active = 0
        max_active = 0

        async def task(item: int) -> int:
            nonlocal active, max_active
            active += 1
            max_active = max(max_active, active)
            await asyncio.sleep(0.01)
            active -= 1
            return item

        pool = WorkerPool(max_workers=2)
        await pool.run(task, list(range(6)))

        assert max_active <= 2

    async def test_handles_task_errors(self) -> None:
        async def task(item: str) -> str:
            if item == "bad":
                msg = "Something went wrong"
                raise ValueError(msg)
            return f"ok-{item}"

        pool = WorkerPool(max_workers=3)
        outcomes = await pool.run(task, ["good", "bad", "fine"])

        successes = [o for o in outcomes if o.success]
        failures = [o for o in outcomes if not o.success]

        assert len(successes) == 2
        assert len(failures) == 1
        assert failures[0].error is not None
        assert "Something went wrong" in str(failures[0].error)

    async def test_preserves_order(self) -> None:
        async def task(item: int) -> int:
            await asyncio.sleep(0.01 * (3 - item))
            return item * 10

        pool = WorkerPool(max_workers=5)
        outcomes = await pool.run(task, [0, 1, 2])

        assert [o.item for o in outcomes] == [0, 1, 2]

    async def test_empty_input(self) -> None:
        async def task(item: str) -> str:
            return item

        pool = WorkerPool(max_workers=3)
        outcomes = await pool.run(task, [])

        assert outcomes == []

    async def test_single_item(self) -> None:
        async def task(item: str) -> str:
            return f"result-{item}"

        pool = WorkerPool(max_workers=3)
        outcomes = await pool.run(task, ["only"])

        assert len(outcomes) == 1
        assert outcomes[0].value == "result-only"
