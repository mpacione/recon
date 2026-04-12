"""Tests for the TUI dashboard screen.

The dashboard shows workspace status: competitor count, research status
breakdown, and a competitor table.
"""

from pathlib import Path

import frontmatter as fm
import pytest

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

    def test_section_statuses_from_schema(self, tmp_workspace: Path) -> None:
        ws = Workspace.open(tmp_workspace)
        ws.create_profile("Alpha")

        data = build_dashboard_data(ws)

        assert data.total_sections > 0
        assert len(data.section_statuses) == data.total_sections
        for ss in data.section_statuses:
            assert ss.total == 1

    def test_section_statuses_only_count_researched_sections(
        self, tmp_workspace: Path
    ) -> None:
        """Per-section completion must read section_status frontmatter,
        not just research_status. This is the BUG-2 fix from the audit.
        """
        import frontmatter as fm

        ws = Workspace.open(tmp_workspace)
        ws.create_profile("Alpha")
        ws.create_profile("Beta")

        # Alpha: overview researched, nothing else
        path = ws.competitors_dir / "alpha.md"
        post = fm.load(str(path))
        post.content = "## Overview\n\nResearch.\n"
        post["research_status"] = "researched"
        post["section_status"] = {
            "overview": {"status": "researched", "researched_at": "2026-04-10"},
        }
        path.write_text(fm.dumps(post))

        # Beta: scaffold (no section_status at all)
        # The minimal schema only has 1 section ("overview"), so:
        #   overview: 1 of 2 (Alpha)
        data = build_dashboard_data(ws)
        statuses = {s.key: s for s in data.section_statuses}
        assert statuses["overview"].completed == 1
        assert statuses["overview"].total == 2

    def test_dashboard_reads_cost_history_from_state_store(
        self, tmp_workspace: Path
    ) -> None:
        """build_dashboard_data should populate total_cost / run_count
        from the workspace state.db. BUG-9 fix from the audit.
        """
        import asyncio

        from recon.state import StateStore

        async def seed_state() -> None:
            store = StateStore(db_path=tmp_workspace / ".recon" / "state.db")
            await store.initialize()
            run_id = await store.create_run(operation="test", parameters={})
            await store.record_cost(
                run_id=run_id,
                model="claude-sonnet-4-5",
                input_tokens=1000,
                output_tokens=500,
                cost_usd=0.42,
            )
            run_id2 = await store.create_run(operation="test", parameters={})
            await store.record_cost(
                run_id=run_id2,
                model="claude-sonnet-4-5",
                input_tokens=2000,
                output_tokens=1000,
                cost_usd=0.85,
            )

        asyncio.run(seed_state())

        ws = Workspace.open(tmp_workspace)
        data = build_dashboard_data(ws)

        assert data.run_count == 2
        assert data.total_cost == pytest.approx(1.27, abs=0.01)
        assert data.last_run_cost == pytest.approx(0.85, abs=0.01)

    def test_section_statuses_ignore_failed_status(
        self, tmp_workspace: Path
    ) -> None:
        import frontmatter as fm

        ws = Workspace.open(tmp_workspace)
        ws.create_profile("Alpha")

        path = ws.competitors_dir / "alpha.md"
        post = fm.load(str(path))
        post.content = "## Overview\n\nPartial.\n"
        post["research_status"] = "researched"
        post["section_status"] = {
            "overview": {"status": "failed"},
        }
        path.write_text(fm.dumps(post))

        data = build_dashboard_data(ws)
        statuses = {s.key: s for s in data.section_statuses}
        assert statuses["overview"].completed == 0

    def test_estimate_full_run_cost_produces_nonzero(self, tmp_workspace: Path) -> None:
        ws = Workspace.open(tmp_workspace)
        ws.create_profile("Alpha")
        ws.create_profile("Beta")

        from recon.tui.screens.dashboard import _estimate_full_run_cost

        estimate = _estimate_full_run_cost(ws)

        assert estimate > 0

    def test_read_cost_summary_works_inside_async_loop(
        self, tmp_workspace: Path
    ) -> None:
        """_read_cost_summary must return real data even when called from
        inside a running event loop (the TUI context). Previously it
        silently returned zeros because asyncio.run() can't nest."""
        import asyncio

        from recon.state import StateStore
        from recon.tui.models.dashboard import _read_cost_summary

        async def seed_and_read() -> dict:
            store = StateStore(db_path=tmp_workspace / ".recon" / "state.db")
            await store.initialize()
            run_id = await store.create_run(operation="test", parameters={})
            await store.record_cost(
                run_id=run_id,
                model="claude-sonnet-4-5",
                input_tokens=1000,
                output_tokens=500,
                cost_usd=0.42,
            )
            return _read_cost_summary(ws)

        ws = Workspace.open(tmp_workspace)
        result = asyncio.run(seed_and_read())

        assert result["total_cost"] == pytest.approx(0.42, abs=0.01)
        assert result["run_count"] == 1

    def test_enriched_defaults(self, tmp_workspace: Path) -> None:
        ws = Workspace.open(tmp_workspace)

        data = build_dashboard_data(ws)

        assert data.theme_count == 0
        assert data.index_chunks == 0
        assert data.total_cost == 0.0
        assert data.run_count == 0
