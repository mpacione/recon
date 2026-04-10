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

    return DashboardData(
        domain=domain,
        company_name=company_name,
        total_competitors=len(profiles),
        status_counts=status_counts,
        competitor_rows=rows,
        section_statuses=section_statuses,
        total_sections=total_sections,
    )


def _build_section_statuses(schema: object, profiles: list[dict[str, Any]]) -> list[SectionStatus]:
    sections = getattr(schema, "sections", [])
    total_profiles = len(profiles)
    result: list[SectionStatus] = []
    for section in sections:
        key = section.key if hasattr(section, "key") else str(section)
        title = section.title if hasattr(section, "title") else key
        completed = sum(
            1
            for p in profiles
            if p.get("research_status") not in ("scaffold", None, "unknown")
        )
        result.append(SectionStatus(
            key=key,
            title=title,
            completed=completed,
            total=total_profiles,
        ))
    return result
