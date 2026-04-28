"""``recon agents`` — run history with per-run progress, cost, timing."""

from __future__ import annotations

import asyncio
from datetime import datetime

from rich.console import Console
from rich.table import Table
from rich.text import Text

from recon.cli_ui.renderables import card, shaded_bar, tab_breadcrumb
from recon.web.schemas import RunListResponse, RunSummary
from recon.workspace import Workspace

_STATE_STYLE = {
    "complete":  "accent",
    "completed": "accent",
    "running":   "accent",
    "planned":   "dim",
    "paused":    "muted",
    "failed":    "error",
    "cancelled": "dim",
}


async def _list_runs(ws: Workspace) -> RunListResponse:
    from recon.state import StateStore

    store = StateStore(db_path=ws.root / ".recon" / "state.db")
    await store.initialize()
    await store.recover_interrupted_runs(max_age_seconds=60)
    rows = await store.list_runs()
    summaries: list[RunSummary] = []
    for row in rows:
        run_id = row["run_id"]
        tasks = await store.list_tasks(run_id)
        completed = sum(1 for t in tasks if t["status"] == "researched")
        failed = sum(1 for t in tasks if t["status"] == "failed")
        cost = await store.get_run_total_cost(run_id)
        summaries.append(
            RunSummary(
                run_id=run_id,
                status=row.get("status", "unknown"),
                created_at=str(row.get("created_at", "")),
                updated_at=str(row.get("updated_at", "")),
                total_cost_usd=float(cost),
                task_count=len(tasks),
                completed_tasks=completed,
                failed_tasks=failed,
                model=row.get("model", "") or "",
            ),
        )
    return RunListResponse(runs=summaries)


def agents_data(ws: Workspace) -> RunListResponse:
    """Assemble the agents-tab DTO (synchronous wrapper)."""
    return asyncio.run(_list_runs(ws))


def _fmt_time(iso: str) -> str:
    if not iso:
        return "—"
    try:
        # SQLite timestamps land as "YYYY-MM-DD HH:MM:SS".
        dt = datetime.fromisoformat(iso.replace(" ", "T"))
        return dt.strftime("%m/%d %H:%M")
    except ValueError:
        return iso[:16]


def render_agents(ws: Workspace, console: Console) -> RunListResponse:
    """Print the AGENTS card and return the DTO."""
    return render_agents_body(ws, console, show_breadcrumb=True)


def render_agents_body(
    ws: Workspace,
    console: Console,
    *,
    show_breadcrumb: bool = True,
    footer: str | None = None,
    limit: int | None = None,
) -> RunListResponse:
    data = agents_data(ws)
    runs = data.runs if limit is None else data.runs[:limit]

    if show_breadcrumb:
        console.print(tab_breadcrumb(active="agents"))
        console.print()

    if not runs:
        body = Text(
            "No runs yet. Kick one off: recon research --all",
            style="subdued",
        )
        console.print(
            card(
                body,
                title="AGENTS · RUN HISTORY",
                meta="0 runs",
                footer=footer or "json:  recon agents --json",
            )
        )
        return data

    rows = Table.grid(padding=(0, 2), pad_edge=False, expand=True)
    rows.add_column(width=12, no_wrap=True)   # run_id
    rows.add_column(min_width=9, no_wrap=True)  # status
    rows.add_column(width=24, no_wrap=True)     # bar
    rows.add_column(width=8, justify="right", no_wrap=True)   # tasks
    rows.add_column(justify="right", no_wrap=True)  # cost
    rows.add_column(width=12, no_wrap=True)     # time

    for r in runs:
        status = r.status.lower()
        style = _STATE_STYLE.get(status, "body")
        pct = (r.completed_tasks / r.task_count * 100) if r.task_count else 0.0
        rows.add_row(
            Text(r.run_id[:10], style="dim"),
            Text(status.upper(), style=style),
            shaded_bar(pct, 24),
            Text(f"{r.completed_tasks}/{r.task_count}", style="body"),
            Text(f"${r.total_cost_usd:>5.2f}", style="accent"),
            Text(_fmt_time(r.updated_at or r.created_at), style="dim"),
        )

    meta_bits = [f"{len(data.runs)} run{'s' if len(data.runs) != 1 else ''}"]
    if limit is not None and limit < len(data.runs):
        meta_bits.append(f"showing {limit}")
    console.print(
        card(
            rows,
            title="AGENTS · RUN HISTORY",
            meta=" · ".join(meta_bits),
            footer=footer or "back:  recon comps   ·   next:  recon output   ·   json:  recon agents --json",
        )
    )
    return data
