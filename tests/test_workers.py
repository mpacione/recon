"""Tests for the async worker pool.

The worker pool provides semaphore-controlled concurrency for dispatching
work to LLM agents. Supports configurable concurrency and error handling.
"""

import asyncio

from recon.workers import PipelineCancelledError, WorkerPool


class TestWorkerPoolPause:
    async def test_pause_event_unset_blocks_dispatch_until_resumed(self) -> None:
        ran: list[int] = []

        async def task(item: int) -> int:
            ran.append(item)
            return item

        pause_event = asyncio.Event()
        # Start paused -- nothing should run until we set it
        # (set = running, cleared = paused)

        pool = WorkerPool(max_workers=2)

        async def resume_after_delay() -> None:
            await asyncio.sleep(0.05)
            assert ran == [], "tasks should not run while paused"
            pause_event.set()

        resume_task = asyncio.create_task(resume_after_delay())

        outcomes = await pool.run(task, [1, 2, 3], pause_event=pause_event)
        await resume_task

        assert sorted(ran) == [1, 2, 3]
        assert all(o.success for o in outcomes)

    async def test_pause_event_set_runs_normally(self) -> None:
        ran: list[int] = []

        async def task(item: int) -> int:
            ran.append(item)
            return item

        pause_event = asyncio.Event()
        pause_event.set()

        pool = WorkerPool(max_workers=2)
        outcomes = await pool.run(task, [1, 2, 3], pause_event=pause_event)

        assert sorted(ran) == [1, 2, 3]
        assert all(o.success for o in outcomes)

    async def test_no_pause_event_runs_normally(self) -> None:
        ran: list[int] = []

        async def task(item: int) -> int:
            ran.append(item)
            return item

        pool = WorkerPool(max_workers=2)
        outcomes = await pool.run(task, [1, 2, 3])

        assert sorted(ran) == [1, 2, 3]
        assert all(o.success for o in outcomes)


class TestWorkerPoolCancellation:
    async def test_cancel_event_set_before_start_skips_all_tasks(self) -> None:
        ran: list[int] = []

        async def task(item: int) -> int:
            ran.append(item)
            return item

        event = asyncio.Event()
        event.set()

        pool = WorkerPool(max_workers=2)
        outcomes = await pool.run(task, [1, 2, 3, 4], cancel_event=event)

        assert ran == []
        assert all(not o.success for o in outcomes)
        assert all(o.error is not None for o in outcomes)

    async def test_cancel_event_mid_run_stops_dispatching(self) -> None:
        ran: list[int] = []
        event = asyncio.Event()

        async def task(item: int) -> int:
            ran.append(item)
            if item == 2:
                event.set()
            await asyncio.sleep(0.01)
            return item

        pool = WorkerPool(max_workers=1)
        outcomes = await pool.run(task, [1, 2, 3, 4, 5], cancel_event=event)

        # Items 1 and 2 should have started; 3/4/5 should be cancelled
        # (item 2 sets the event while the semaphore holds 3/4/5)
        assert 1 in ran
        assert 2 in ran
        # At least one task should have been cancelled
        cancelled = [o for o in outcomes if not o.success]
        assert len(cancelled) >= 1

    async def test_cancel_event_cancels_inflight_tasks(self) -> None:
        started = asyncio.Event()
        task_cancelled = asyncio.Event()
        event = asyncio.Event()

        async def task(item: int) -> int:
            started.set()
            try:
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                task_cancelled.set()
                raise
            return item

        pool = WorkerPool(max_workers=1)
        run_task = asyncio.create_task(pool.run(task, [1], cancel_event=event))

        await started.wait()
        event.set()
        outcomes = await asyncio.wait_for(run_task, timeout=1)

        assert task_cancelled.is_set()
        assert len(outcomes) == 1
        assert outcomes[0].success is False
        assert isinstance(outcomes[0].error, PipelineCancelledError)

    async def test_no_cancel_event_all_tasks_run(self) -> None:
        ran: list[int] = []

        async def task(item: int) -> int:
            ran.append(item)
            return item

        pool = WorkerPool(max_workers=2)
        outcomes = await pool.run(task, [1, 2, 3])

        assert sorted(ran) == [1, 2, 3]
        assert all(o.success for o in outcomes)


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
