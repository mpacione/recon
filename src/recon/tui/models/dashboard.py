"""Dashboard data model for recon TUI.

Separates data preparation from rendering so screens can be tested
without running the Textual app.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from recon.workspace import Workspace  # noqa: TCH001


@dataclass
class SectionStatus:
    key: str
    title: str
    completed: int
    total: int


@dataclass
class DashboardData:
    domain: str
    company_name: str
    total_competitors: int
    status_counts: dict[str, int]
    competitor_rows: list[dict[str, Any]]
    section_statuses: list[SectionStatus] = field(default_factory=list)
    total_sections: int = 0
    theme_count: int = 0
    themes_selected: int = 0
    index_chunks: int = 0
    last_indexed: str = ""
    total_cost: float = 0.0
    last_run_cost: float = 0.0
    run_count: int = 0


def build_dashboard_data(workspace: Workspace) -> DashboardData:
    """Build dashboard display data from workspace state."""
    schema = workspace.schema
    domain = schema.domain if schema else "Unknown"
    company_name = schema.identity.company_name if schema else "Unknown"

    profiles = workspace.list_profiles()
    status_counts: dict[str, int] = {}
    rows: list[dict[str, Any]] = []

    for p in profiles:
        status = p.get("research_status", "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
        rows.append({
            "name": p.get("name", "Unknown"),
            "type": p.get("type", "competitor"),
            "status": status,
            "slug": p.get("_slug", ""),
        })

    section_statuses = _build_section_statuses(schema, profiles) if schema else []
    total_sections = len(schema.sections) if schema else 0

    cost_summary = _read_cost_summary(workspace)

    return DashboardData(
        domain=domain,
        company_name=company_name,
        total_competitors=len(profiles),
        status_counts=status_counts,
        competitor_rows=rows,
        section_statuses=section_statuses,
        total_sections=total_sections,
        total_cost=cost_summary["total_cost"],
        last_run_cost=cost_summary["last_run_cost"],
        run_count=cost_summary["run_count"],
    )


_ZERO_COST_SUMMARY: dict[str, Any] = {"run_count": 0, "total_cost": 0.0, "last_run_cost": 0.0}


def _read_cost_summary(workspace: Workspace) -> dict[str, Any]:
    """Read run/cost aggregates from the workspace's state.db.

    Synchronous wrapper around the async StateStore. Works both from
    a plain synchronous context (``asyncio.run``) and from inside a
    running event loop (spawns a thread so the nested coroutine gets
    its own loop). Returns zeros if the state DB is missing or
    unreadable -- the dashboard should never crash because of
    state-store gymnastics.
    """
    import asyncio
    import concurrent.futures

    db_path = workspace.root / ".recon" / "state.db"
    if not db_path.exists():
        return dict(_ZERO_COST_SUMMARY)

    from recon.state import StateStore

    async def _read() -> dict[str, Any]:
        store = StateStore(db_path=db_path)
        await store.initialize()
        return await store.get_workspace_run_summary()

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        # No event loop running — safe to use asyncio.run()
        try:
            return asyncio.run(_read())
        except Exception:
            return dict(_ZERO_COST_SUMMARY)

    # Inside a running event loop — run in a separate thread
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(asyncio.run, _read())
            return future.result(timeout=5.0)
    except Exception:
        return dict(_ZERO_COST_SUMMARY)


def _build_section_statuses(schema: object, profiles: list[dict[str, Any]]) -> list[SectionStatus]:
    """Per-section completion counts.

    A section is "completed" for a profile only if its
    ``section_status[<key>].status == "researched"`` in the profile's
    frontmatter. This honors the per-section tracking the diff/rerun
    work added; previously every section was reported as complete
    whenever the profile's overall ``research_status`` was non-scaffold,
    which produced misleading dashboards.
    """
    sections = getattr(schema, "sections", [])
    total_profiles = len(profiles)
    result: list[SectionStatus] = []
    for section in sections:
        key = section.key if hasattr(section, "key") else str(section)
        title = section.title if hasattr(section, "title") else key
        completed = 0
        for profile in profiles:
            section_status = profile.get("section_status") or {}
            if not isinstance(section_status, dict):
                continue
            entry = section_status.get(key) or {}
            if isinstance(entry, dict) and entry.get("status") == "researched":
                completed += 1
        result.append(
            SectionStatus(
                key=key,
                title=title,
                completed=completed,
                total=total_profiles,
            ),
        )
    return result
