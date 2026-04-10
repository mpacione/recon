"""Tests for CompetitorBrowserScreen."""

from __future__ import annotations

from typing import Any

from textual.app import App, ComposeResult
from textual.widgets import DataTable, Static

from recon.tui.models.dashboard import DashboardData
from recon.tui.screens.browser import CompetitorBrowserScreen


def _make_rows(count: int = 5) -> list[dict[str, Any]]:
    return [
        {
            "name": f"Competitor {i}",
            "type": "competitor",
            "status": "verified" if i % 2 == 0 else "researched",
            "slug": f"competitor-{i}",
        }
        for i in range(count)
    ]


def _make_data(count: int = 5) -> DashboardData:
    rows = _make_rows(count)
    return DashboardData(
        domain="Developer Tools",
        company_name="Acme Corp",
        total_competitors=count,
        status_counts={"verified": count // 2, "researched": count - count // 2},
        competitor_rows=rows,
    )


class _BrowserTestApp(App):
    CSS = "Screen { background: #000000; }"

    def __init__(self, data: DashboardData) -> None:
        super().__init__()
        self._data = data

    def compose(self) -> ComposeResult:
        yield Static("")

    def on_mount(self) -> None:
        self.push_screen(CompetitorBrowserScreen(data=self._data))


class TestCompetitorBrowserScreen:
    async def test_shows_title_with_count(self) -> None:
        app = _BrowserTestApp(data=_make_data(10))
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            title = app.screen.query_one("#browser-title", Static)
            assert "10" in str(title.content)

    async def test_shows_competitor_table(self) -> None:
        app = _BrowserTestApp(data=_make_data(5))
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            table = app.screen.query_one(DataTable)
            assert table.row_count == 5

    async def test_table_has_columns(self) -> None:
        app = _BrowserTestApp(data=_make_data(3))
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            table = app.screen.query_one(DataTable)
            column_labels = [str(col.label) for col in table.columns.values()]
            assert "Name" in column_labels
            assert "Status" in column_labels

    async def test_empty_data_shows_message(self) -> None:
        app = _BrowserTestApp(data=_make_data(0))
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            empty = app.screen.query_one("#browser-empty", Static)
            assert "No competitors" in str(empty.content)
