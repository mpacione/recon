"""SQLite state store for recon.

Tracks runs, tasks, verification results, file hashes, and cost history.
All operations are async via aiosqlite.
"""

from __future__ import annotations

import datetime as dt
import uuid
from enum import StrEnum
from pathlib import Path  # noqa: TCH003 -- used at runtime
from typing import Any

import aiosqlite


class RunStatus(StrEnum):
    IDLE = "idle"
    PLANNING = "planning"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPING = "stopping"
    CANCELLED = "cancelled"


class CompetitorStatus(StrEnum):
    PENDING = "pending"
    RESEARCHING = "researching"
    VERIFYING = "verifying"
    ENRICHING = "enriching"
    VERIFIED = "verified"
    INDEXED = "indexed"
    FAILED = "failed"


_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    operation TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'planning',
    parameters TEXT DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS tasks (
    task_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(run_id),
    competitor_slug TEXT NOT NULL,
    section_key TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS file_hashes (
    file_path TEXT PRIMARY KEY,
    hash TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS verification_results (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES tasks(task_id),
    competitor_slug TEXT NOT NULL,
    section_key TEXT NOT NULL,
    source_url TEXT,
    claim_text TEXT NOT NULL,
    agent TEXT NOT NULL,
    status TEXT NOT NULL,
    evidence_summary TEXT,
    verified_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS cost_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES runs(run_id),
    model TEXT NOT NULL,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    cost_usd REAL NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


class StateStore:
    """Async SQLite state store for pipeline state management."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    async def initialize(self) -> None:
        """Create the database and tables if they don't exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.db_path) as db:
            await db.executescript(_SCHEMA_SQL)

    def _connect(self) -> aiosqlite.Connection:
        """Create a new connection context manager."""
        conn = aiosqlite.connect(self.db_path)
        return conn

    async def _execute_returning_rows(self, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        """Execute a query and return all rows as dicts."""
        async with self._connect() as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def _execute_returning_one(self, query: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        """Execute a query and return a single row as dict or None."""
        async with self._connect() as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(query, params)
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def _execute_write(self, query: str, params: tuple[Any, ...] = ()) -> None:
        """Execute a write query and commit."""
        async with self._connect() as db:
            await db.execute(query, params)
            await db.commit()

    async def create_run(
        self,
        operation: str,
        parameters: dict[str, Any] | None = None,
    ) -> str:
        """Create a new pipeline run. Returns run_id."""
        import json

        run_id = uuid.uuid4().hex[:12]
        await self._execute_write(
            "INSERT INTO runs (run_id, operation, parameters) VALUES (?, ?, ?)",
            (run_id, operation, json.dumps(parameters or {})),
        )
        return run_id

    async def get_run(self, run_id: str) -> dict[str, Any] | None:
        """Get a run by ID."""
        return await self._execute_returning_one("SELECT * FROM runs WHERE run_id = ?", (run_id,))

    async def update_run_status(self, run_id: str, status: RunStatus) -> None:
        """Update a run's status."""
        await self._execute_write(
            "UPDATE runs SET status = ?, updated_at = datetime('now') WHERE run_id = ?",
            (status.value, run_id),
        )

    async def recover_interrupted_runs(
        self,
        *,
        max_age_seconds: int | None = None,
        exclude_run_ids: set[str] | None = None,
        reason: str = "Recovered after the previous process exited before finalizing the run.",
    ) -> list[str]:
        """Finalize non-terminal runs left behind by a dead process.

        A run can be stranded as ``running`` if the terminal process is
        killed, the app shuts down mid-worker, or a previous bug exits
        before writing a terminal state. This method converts old
        planning/running/paused/stopping rows to ``cancelled`` and, when
        possible, updates the matching provenance ``run.yaml``.
        """
        statuses = (
            RunStatus.PLANNING.value,
            RunStatus.RUNNING.value,
            RunStatus.PAUSED.value,
            RunStatus.STOPPING.value,
        )
        params: list[Any] = list(statuses)
        clauses = [f"status IN ({','.join('?' for _ in statuses)})"]

        if max_age_seconds is not None:
            seconds = max(0, int(max_age_seconds))
            clauses.append("updated_at <= datetime('now', ?)")
            params.append(f"-{seconds} seconds")

        if exclude_run_ids:
            excluded = sorted(exclude_run_ids)
            clauses.append(f"run_id NOT IN ({','.join('?' for _ in excluded)})")
            params.extend(excluded)

        rows = await self._execute_returning_rows(
            f"SELECT run_id FROM runs WHERE {' AND '.join(clauses)}",
            tuple(params),
        )
        run_ids = [str(row["run_id"]) for row in rows]
        if not run_ids:
            return []

        await self._execute_write(
            f"UPDATE runs SET status = ?, updated_at = datetime('now') "
            f"WHERE run_id IN ({','.join('?' for _ in run_ids)})",
            (RunStatus.CANCELLED.value, *run_ids),
        )
        self._write_recovery_provenance(run_ids, reason=reason)
        return run_ids

    def _write_recovery_provenance(self, run_ids: list[str], *, reason: str) -> None:
        """Best-effort update for ``.recon/runs/<id>/run.yaml`` files."""
        workspace_root = self._workspace_root_from_db_path()
        if workspace_root is None:
            return

        try:
            import yaml
        except Exception:
            return

        now = dt.datetime.now(dt.UTC).isoformat()
        for run_id in run_ids:
            run_path = workspace_root / ".recon" / "runs" / run_id / "run.yaml"
            if not run_path.exists():
                continue
            try:
                data = yaml.safe_load(run_path.read_text()) or {}
                if not isinstance(data, dict):
                    data = {}
                data.update({
                    "run_id": run_id,
                    "workspace_root": str(workspace_root),
                    "status": RunStatus.CANCELLED.value,
                    "cancelled_at": now,
                    "recovered_at": now,
                    "recovery_reason": reason,
                })
                run_path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))
            except Exception:
                continue

    def _workspace_root_from_db_path(self) -> Path | None:
        """Infer workspace root for the default ``.recon/state.db`` layout."""
        if self.db_path.name != "state.db":
            return None
        recon_dir = self.db_path.parent
        if recon_dir.name != ".recon":
            return None
        return recon_dir.parent

    async def list_runs(self) -> list[dict[str, Any]]:
        """List all runs, most recent first.

        Tie-breaks on ROWID so runs created in the same second still
        report a stable ordering (later insert = earlier in the list).
        """
        return await self._execute_returning_rows(
            "SELECT * FROM runs ORDER BY created_at DESC, ROWID DESC",
        )

    async def create_task(
        self,
        run_id: str,
        competitor_slug: str,
        section_key: str,
    ) -> str:
        """Create a new task within a run. Returns task_id."""
        task_id = uuid.uuid4().hex[:12]
        await self._execute_write(
            "INSERT INTO tasks (task_id, run_id, competitor_slug, section_key) VALUES (?, ?, ?, ?)",
            (task_id, run_id, competitor_slug, section_key),
        )
        return task_id

    async def get_task(self, task_id: str) -> dict[str, Any] | None:
        """Get a task by ID."""
        return await self._execute_returning_one("SELECT * FROM tasks WHERE task_id = ?", (task_id,))

    async def update_task_status(self, task_id: str, status: CompetitorStatus) -> None:
        """Update a task's status."""
        await self._execute_write(
            "UPDATE tasks SET status = ?, updated_at = datetime('now') WHERE task_id = ?",
            (status.value, task_id),
        )

    async def list_tasks(
        self,
        run_id: str,
        status: CompetitorStatus | None = None,
    ) -> list[dict[str, Any]]:
        """List tasks for a run, optionally filtered by status."""
        query = "SELECT * FROM tasks WHERE run_id = ?"
        params: list[Any] = [run_id]
        if status is not None:
            query += " AND status = ?"
            params.append(status.value)
        query += " ORDER BY created_at"
        return await self._execute_returning_rows(query, tuple(params))

    async def record_verification(
        self,
        task_id: str,
        competitor_slug: str,
        section_key: str,
        claim_text: str,
        agent: str,
        status: str,
        source_url: str | None = None,
        evidence_summary: str | None = None,
    ) -> str:
        """Record a verification result for a claim."""
        result_id = uuid.uuid4().hex[:12]
        await self._execute_write(
            """INSERT INTO verification_results
               (id, task_id, competitor_slug, section_key, source_url, claim_text, agent, status, evidence_summary)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (result_id, task_id, competitor_slug, section_key, source_url, claim_text, agent, status, evidence_summary),
        )
        return result_id

    async def get_verification_results(
        self,
        task_id: str | None = None,
        competitor_slug: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get verification results, filtered by task or competitor."""
        if task_id is not None:
            return await self._execute_returning_rows(
                "SELECT * FROM verification_results WHERE task_id = ? ORDER BY verified_at",
                (task_id,),
            )
        if competitor_slug is not None:
            return await self._execute_returning_rows(
                "SELECT * FROM verification_results WHERE competitor_slug = ? ORDER BY verified_at",
                (competitor_slug,),
            )
        return await self._execute_returning_rows(
            "SELECT * FROM verification_results ORDER BY verified_at",
        )

    async def set_file_hash(self, file_path: str, file_hash: str) -> None:
        """Store or update a file's content hash for incremental processing."""
        await self._execute_write(
            """INSERT INTO file_hashes (file_path, hash) VALUES (?, ?)
               ON CONFLICT(file_path) DO UPDATE SET hash = ?, updated_at = datetime('now')""",
            (file_path, file_hash, file_hash),
        )

    async def get_file_hash(self, file_path: str) -> str | None:
        """Get a file's stored hash, or None if not tracked."""
        row = await self._execute_returning_one("SELECT hash FROM file_hashes WHERE file_path = ?", (file_path,))
        return row["hash"] if row else None

    async def has_file_changed(self, file_path: str, current_hash: str) -> bool:
        """Check if a file's hash differs from what's stored."""
        stored = await self.get_file_hash(file_path)
        if stored is None:
            return True
        return stored != current_hash

    async def record_cost(
        self,
        run_id: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
    ) -> None:
        """Record an API call's cost."""
        await self._execute_write(
            "INSERT INTO cost_history (run_id, model, input_tokens, output_tokens, cost_usd) VALUES (?, ?, ?, ?, ?)",
            (run_id, model, input_tokens, output_tokens, cost_usd),
        )

    async def get_run_costs(self, run_id: str) -> list[dict[str, Any]]:
        """Get all cost records for a run."""
        return await self._execute_returning_rows(
            "SELECT * FROM cost_history WHERE run_id = ? ORDER BY created_at",
            (run_id,),
        )

    async def get_run_total_cost(self, run_id: str) -> float:
        """Get total cost in USD for a run."""
        row = await self._execute_returning_one(
            "SELECT COALESCE(SUM(cost_usd), 0.0) as total FROM cost_history WHERE run_id = ?",
            (run_id,),
        )
        return float(row["total"]) if row else 0.0

    async def get_workspace_total_cost(self) -> float:
        """Get total cost in USD across every run in this workspace."""
        row = await self._execute_returning_one(
            "SELECT COALESCE(SUM(cost_usd), 0.0) as total FROM cost_history",
        )
        return float(row["total"]) if row else 0.0

    async def get_workspace_run_summary(self) -> dict[str, Any]:
        """Aggregate run history: count, total cost, last run cost.

        Used by the dashboard to show "$X across N runs" without
        loading every cost row.
        """
        runs = await self.list_runs()
        total_cost = await self.get_workspace_total_cost()
        last_run_cost = 0.0
        last_run_id = None
        if runs:
            # list_runs orders DESC by created_at, so [0] is most recent
            last_run_id = runs[0]["run_id"]
            last_run_cost = await self.get_run_total_cost(last_run_id)
        return {
            "run_count": len(runs),
            "total_cost": total_cost,
            "last_run_cost": last_run_cost,
            "last_run_id": last_run_id,
        }
