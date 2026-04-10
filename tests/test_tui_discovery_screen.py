"""Tests for DiscoveryScreen."""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.widgets import Button, Static

from recon.discovery import CompetitorTier, DiscoveryCandidate, DiscoveryState
from recon.tui.screens.discovery import DiscoveryScreen


def _make_candidates(count: int = 3) -> list[DiscoveryCandidate]:
    return [
        DiscoveryCandidate(
            name=f"Competitor {i}",
            url=f"https://competitor-{i}.com",
            blurb=f"Description for competitor {i}",
            provenance="G2 search",
            suggested_tier=CompetitorTier.ESTABLISHED,
        )
        for i in range(count)
    ]


def _make_state(candidates: list[DiscoveryCandidate] | None = None) -> DiscoveryState:
    state = DiscoveryState()
    if candidates:
        state.add_round(candidates)
    return state


class _DiscoveryTestApp(App):
    CSS = "Screen { background: #000000; }"
    dismissed_result: list[DiscoveryCandidate] | None = None

    def __init__(self, state: DiscoveryState) -> None:
        super().__init__()
        self._state = state

    def compose(self) -> ComposeResult:
        yield Static("")

    def on_mount(self) -> None:
        def on_dismiss(result: list[DiscoveryCandidate] | None) -> None:
            self.dismissed_result = result

        self.push_screen(
            DiscoveryScreen(state=self._state, domain="Developer Tools"),
            on_dismiss,
        )


class TestDiscoveryScreen:
    async def test_mounts_with_domain_title(self) -> None:
        app = _DiscoveryTestApp(state=_make_state(_make_candidates(3)))
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            title = app.screen.query_one("#discovery-title", Static)
            assert "Developer Tools" in str(title.content)

    async def test_shows_candidate_count(self) -> None:
        app = _DiscoveryTestApp(state=_make_state(_make_candidates(5)))
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            summary = app.screen.query_one("#discovery-summary", Static)
            assert "5" in str(summary.content)

    async def test_shows_candidates_list(self) -> None:
        app = _DiscoveryTestApp(state=_make_state(_make_candidates(3)))
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            items = app.screen.query(".candidate-item")
            assert len(items) == 3

    async def test_toggle_candidate(self) -> None:
        state = _make_state(_make_candidates(2))
        app = _DiscoveryTestApp(state=state)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, DiscoveryScreen)
            screen.toggle_candidate(0)
            assert not state.all_candidates[0].accepted

    async def test_done_dismisses_with_accepted(self) -> None:
        candidates = _make_candidates(3)
        state = _make_state(candidates)
        state.toggle(1)
        app = _DiscoveryTestApp(state=state)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            app.screen.query_one("#btn-done", Button).press()
            await pilot.pause()
            assert app.dismissed_result is not None
            assert len(app.dismissed_result) == 2

    async def test_empty_state_shows_message(self) -> None:
        app = _DiscoveryTestApp(state=_make_state())
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            empty_msg = app.screen.query_one("#discovery-empty", Static)
            assert empty_msg is not None

    async def test_has_search_more_button(self) -> None:
        app = _DiscoveryTestApp(state=_make_state(_make_candidates(3)))
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            btn = app.screen.query_one("#btn-search-more", Button)
            assert btn is not None

    async def test_has_add_manually_button(self) -> None:
        app = _DiscoveryTestApp(state=_make_state(_make_candidates(3)))
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            btn = app.screen.query_one("#btn-add-manual", Button)
            assert btn is not None

    async def test_cursor_navigation_and_space_toggle(self) -> None:
        state = _make_state(_make_candidates(3))
        app = _DiscoveryTestApp(state=state)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, DiscoveryScreen)
            assert screen.cursor_index == 0
            assert state.all_candidates[0].accepted
            await pilot.press("space")
            await pilot.pause()
            assert not state.all_candidates[0].accepted
            await pilot.press("down")
            assert screen.cursor_index == 1
            await pilot.press("space")
            await pilot.pause()
            assert not state.all_candidates[1].accepted

    async def test_cursor_wraps(self) -> None:
        state = _make_state(_make_candidates(3))
        app = _DiscoveryTestApp(state=state)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, DiscoveryScreen)
            await pilot.press("up")
            assert screen.cursor_index == 2

    async def test_search_more_adds_candidates(self) -> None:
        new_batch = [
            DiscoveryCandidate(
                name="NewCo",
                url="https://newco.com",
                blurb="A new competitor",
                provenance="search",
                suggested_tier=CompetitorTier.EMERGING,
            ),
        ]

        async def mock_search(state: DiscoveryState | None = None) -> list[DiscoveryCandidate]:
            return new_batch

        state = _make_state(_make_candidates(2))
        app = _DiscoveryTestApp(state=state)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, DiscoveryScreen)
            screen.set_search_fn(mock_search)
            app.screen.query_one("#btn-search-more", Button).press()
            await pilot.pause()
            await pilot.pause()
            assert len(state.all_candidates) == 3
