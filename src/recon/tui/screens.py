"""TUI screen data and logic for recon.

Separates data preparation from rendering so screens can be tested
without running the Textual app.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from recon.workspace import Workspace  # noqa: TCH001


@dataclass
class DashboardData:
    domain: str
    company_name: str
    total_competitors: int
    status_counts: dict[str, int]
    competitor_rows: list[dict[str, Any]]


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

    return DashboardData(
        domain=domain,
        company_name=company_name,
        total_competitors=len(profiles),
        status_counts=status_counts,
        competitor_rows=rows,
    )
