"""Tests for the SQLite state store.

The state store tracks runs, tasks, verification results, file hashes,
and cost history. All operations are async (aiosqlite).
"""

from pathlib import Path

import pytest

from recon.state import CompetitorStatus, RunStatus, StateStore


@pytest.fixture()
async def store(tmp_path: Path) -> StateStore:
    """Create and initialize a state store in a temp directory."""
    s = StateStore(tmp_path / ".recon" / "state.db")
    await s.initialize()
    return s


class TestStateStoreInit:
    async def test_creates_database_file(self, tmp_path: Path) -> None:
        db_path = tmp_path / "state.db"
        store = StateStore(db_path)
        await store.initialize()

        assert db_path.exists()

    async def test_initialize_is_idempotent(self, tmp_path: Path) -> None:
        db_path = tmp_path / "state.db"
        store = StateStore(db_path)
        await store.initialize()
        await store.initialize()

        assert db_path.exists()


class TestRunManagement:
    async def test_creates_run(self, store: StateStore) -> None:
        run_id = await store.create_run(operation="research", parameters={"target": "all"})

        assert run_id is not None
        assert len(run_id) > 0

    async def test_gets_run(self, store: StateStore) -> None:
        run_id = await store.create_run(operation="research")

        run = await store.get_run(run_id)

        assert run is not None
        assert run["run_id"] == run_id
        assert run["operation"] == "research"
        assert run["status"] == RunStatus.PLANNING.value

    async def test_updates_run_status(self, store: StateStore) -> None:
        run_id = await store.create_run(operation="research")

        await store.update_run_status(run_id, RunStatus.RUNNING)

        run = await store.get_run(run_id)
        assert run["status"] == RunStatus.RUNNING.value

    async def test_lists_runs(self, store: StateStore) -> None:
        await store.create_run(operation="research")
        await store.create_run(operation="enrich")

        runs = await store.list_runs()

        assert len(runs) == 2
        operations = {r["operation"] for r in runs}
        assert operations == {"research", "enrich"}

    async def test_get_missing_run_returns_none(self, store: StateStore) -> None:
        assert await store.get_run("nonexistent") is None


class TestTaskManagement:
    async def test_creates_task(self, store: StateStore) -> None:
        run_id = await store.create_run(operation="research")

        task_id = await store.create_task(
            run_id=run_id,
            competitor_slug="github-copilot",
            section_key="overview",
        )

        assert task_id is not None

    async def test_gets_task(self, store: StateStore) -> None:
        run_id = await store.create_run(operation="research")
        task_id = await store.create_task(
            run_id=run_id,
            competitor_slug="github-copilot",
            section_key="overview",
        )

        task = await store.get_task(task_id)

        assert task is not None
        assert task["competitor_slug"] == "github-copilot"
        assert task["section_key"] == "overview"
        assert task["status"] == CompetitorStatus.PENDING.value

    async def test_updates_task_status(self, store: StateStore) -> None:
        run_id = await store.create_run(operation="research")
        task_id = await store.create_task(
            run_id=run_id,
            competitor_slug="github-copilot",
            section_key="overview",
        )

        await store.update_task_status(task_id, CompetitorStatus.RESEARCHING)

        task = await store.get_task(task_id)
        assert task["status"] == CompetitorStatus.RESEARCHING.value

    async def test_lists_tasks_for_run(self, store: StateStore) -> None:
        run_id = await store.create_run(operation="research")
        await store.create_task(run_id=run_id, competitor_slug="alpha", section_key="overview")
        await store.create_task(run_id=run_id, competitor_slug="beta", section_key="overview")

        tasks = await store.list_tasks(run_id=run_id)

        assert len(tasks) == 2

    async def test_lists_tasks_filtered_by_status(self, store: StateStore) -> None:
        run_id = await store.create_run(operation="research")
        t1 = await store.create_task(run_id=run_id, competitor_slug="alpha", section_key="overview")
        await store.create_task(run_id=run_id, competitor_slug="beta", section_key="overview")
        await store.update_task_status(t1, CompetitorStatus.VERIFIED)

        pending_tasks = await store.list_tasks(run_id=run_id, status=CompetitorStatus.PENDING)

        assert len(pending_tasks) == 1
        assert pending_tasks[0]["competitor_slug"] == "beta"


class TestFileHashes:
    async def test_stores_file_hash(self, store: StateStore) -> None:
        await store.set_file_hash("competitors/alpha.md", "abc123")

        stored = await store.get_file_hash("competitors/alpha.md")

        assert stored == "abc123"

    async def test_updates_file_hash(self, store: StateStore) -> None:
        await store.set_file_hash("competitors/alpha.md", "abc123")
        await store.set_file_hash("competitors/alpha.md", "def456")

        stored = await store.get_file_hash("competitors/alpha.md")

        assert stored == "def456"

    async def test_returns_none_for_unknown_file(self, store: StateStore) -> None:
        assert await store.get_file_hash("nonexistent.md") is None

    async def test_checks_if_file_changed(self, store: StateStore) -> None:
        await store.set_file_hash("competitors/alpha.md", "abc123")

        assert await store.has_file_changed("competitors/alpha.md", "abc123") is False
        assert await store.has_file_changed("competitors/alpha.md", "xyz789") is True
        assert await store.has_file_changed("competitors/new.md", "abc123") is True


class TestCostHistory:
    async def test_records_cost(self, store: StateStore) -> None:
        run_id = await store.create_run(operation="research")

        await store.record_cost(
            run_id=run_id,
            model="claude-sonnet-4-20250514",
            input_tokens=1000,
            output_tokens=500,
            cost_usd=0.0045,
        )

        costs = await store.get_run_costs(run_id)

        assert len(costs) == 1
        assert costs[0]["input_tokens"] == 1000
        assert costs[0]["output_tokens"] == 500
        assert costs[0]["cost_usd"] == 0.0045

    async def test_accumulates_run_total(self, store: StateStore) -> None:
        run_id = await store.create_run(operation="research")
        await store.record_cost(run_id=run_id, model="claude-sonnet-4-20250514", input_tokens=1000, output_tokens=500, cost_usd=0.005)
        await store.record_cost(run_id=run_id, model="claude-sonnet-4-20250514", input_tokens=2000, output_tokens=800, cost_usd=0.010)

        total = await store.get_run_total_cost(run_id)

        assert total == pytest.approx(0.015)
