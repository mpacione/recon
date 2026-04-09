"""Tests for the TUI dashboard screen.

The dashboard shows workspace status: competitor count, research status
breakdown, and a competitor table.
"""

from pathlib import Path

import frontmatter as fm

from recon.tui.screens import build_dashboard_data
from recon.workspace import Workspace


class TestDashboardData:
    def test_builds_from_workspace(self, tmp_workspace: Path) -> None:
        ws = Workspace.open(tmp_workspace)
        ws.create_profile("Alpha")
        ws.create_profile("Beta")

        data = build_dashboard_data(ws)

        assert data.domain == "Developer Tools"
        assert data.total_competitors == 2
        assert "scaffold" in data.status_counts

    def test_empty_workspace(self, tmp_workspace: Path) -> None:
        ws = Workspace.open(tmp_workspace)

        data = build_dashboard_data(ws)

        assert data.total_competitors == 0
        assert data.status_counts == {}

    def test_mixed_statuses(self, tmp_workspace: Path) -> None:
        ws = Workspace.open(tmp_workspace)

        path_a = ws.create_profile("Alpha")
        post = fm.load(str(path_a))
        post["research_status"] = "verified"
        path_a.write_text(fm.dumps(post))

        ws.create_profile("Beta")

        data = build_dashboard_data(ws)

        assert data.status_counts.get("verified") == 1
        assert data.status_counts.get("scaffold") == 1

    def test_competitor_rows(self, tmp_workspace: Path) -> None:
        ws = Workspace.open(tmp_workspace)
        ws.create_profile("Alpha Corp")
        ws.create_profile("Beta Inc")

        data = build_dashboard_data(ws)

        assert len(data.competitor_rows) == 2
        names = [r["name"] for r in data.competitor_rows]
        assert "Alpha Corp" in names
        assert "Beta Inc" in names
