"""DiscoveryScreen for recon TUI.

Accumulating competitor search. Users toggle candidates on/off,
search for more, view the full roster, and dismiss with accepted
candidates when done.
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable, Coroutine
from typing import Any

from textual import work
from textual.app import ComposeResult  # noqa: TCH002 -- used at runtime
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Static

from recon.discovery import DiscoveryCandidate, DiscoveryState  # noqa: TCH001
from recon.logging import get_logger

_log = get_logger(__name__)

SearchFn = Callable[[DiscoveryState | None], Coroutine[Any, Any, list[DiscoveryCandidate]]]


class DiscoveryScreen(ModalScreen[list[DiscoveryCandidate]]):
    """Interactive competitor discovery with accumulating roster."""

    BINDINGS = [
        Binding("up", "cursor_up", "Up", show=False),
        Binding("down", "cursor_down", "Down", show=False),
        Binding("space", "toggle_current", "Toggle", show=False),
    ]

    DEFAULT_CSS = """
    DiscoveryScreen {
        align: center middle;
    }
    #discovery-container {
        width: 100;
        height: auto;
        max-height: 90%;
        padding: 1 2;
        border: solid #3a3a3a;
        background: #0d0d0d;
        overflow-y: auto;
    }
    .candidate-row {
        height: auto;
        margin: 0 0 1 0;
    }
    .candidate-toggle {
        width: 10;
        margin: 0 1 0 0;
    }
    .candidate-detail {
        width: 1fr;
        height: auto;
    }
    .action-bar {
        height: auto;
        margin: 1 0;
        layout: horizontal;
    }
    .action-bar Button {
        margin: 0 1 0 0;
    }
    #roster-summary {
        height: auto;
        margin: 1 0;
        padding: 1 2;
        border: solid #3a3a3a;
    }
    """

    def __init__(self, state: DiscoveryState, domain: str) -> None:
        super().__init__()
        self._state = state
        self._domain = domain
        self._search_fn: SearchFn | None = None
        self._cursor_index: int = 0
        self._is_searching: bool = False
        self._auto_started: bool = False

    @property
    def state(self) -> DiscoveryState:
        return self._state

    @property
    def cursor_index(self) -> int:
        return self._cursor_index

    def set_search_fn(self, fn: SearchFn) -> None:
        """Wire a search function. Call before push_screen to enable
        auto-start on mount. Safe to call before the screen is mounted
        -- the actual search is deferred until on_mount fires."""
        self._search_fn = fn

    def on_mount(self) -> None:
        _log.info(
            "DiscoveryScreen mounted domain=%s candidates=%d has_search_fn=%s",
            self._domain,
            len(self._state.all_candidates),
            self._search_fn is not None,
        )
        if (
            self._search_fn is not None
            and not self._auto_started
            and not self._state.all_candidates
        ):
            self._auto_started = True
            _log.info("DiscoveryScreen: auto-starting initial search on mount")
            self._do_search()

    def action_cursor_up(self) -> None:
        count = len(self._state.all_candidates)
        if count > 0:
            self._cursor_index = (self._cursor_index - 1) % count

    def action_cursor_down(self) -> None:
        count = len(self._state.all_candidates)
        if count > 0:
            self._cursor_index = (self._cursor_index + 1) % count

    def action_toggle_current(self) -> None:
        candidates = self._state.all_candidates
        if candidates and 0 <= self._cursor_index < len(candidates):
            self._state.toggle(self._cursor_index)
            self._schedule_recompose()

    def compose(self) -> ComposeResult:
        with Vertical(id="discovery-container"):
            yield Static(
                f"[bold #e0a044]── DISCOVERY ──[/] [#a89984]·[/] [#efe5c0]{self._domain}[/]",
                id="discovery-title",
            )
            yield self._build_summary()
            yield Static("")
            yield from self._build_candidate_list()
            yield from self._build_roster_summary()
            yield Static("")
            with Horizontal(classes="action-bar"):
                yield Button("Done", id="btn-done", variant="primary")
                yield Button("Search More", id="btn-search-more")
                yield Button("Add Manually", id="btn-add-manual")
                yield Button("Accept All", id="btn-accept-all")
                yield Button("Reject All", id="btn-reject-all")

    def _build_summary(self) -> Static:
        accepted = len(self._state.accepted_candidates)
        rejected = len(self._state.rejected_candidates)
        return Static(
            f"[#a89984]rounds:[/] [#e0a044]{self._state.round_count}[/]  "
            f"[#3a3a3a]·[/]  [#a89984]accepted:[/] [#e0a044]{accepted}[/]  "
            f"[#3a3a3a]·[/]  [#a89984]rejected:[/] [#e0a044]{rejected}[/]",
            id="discovery-summary",
        )

    def _build_candidate_list(self):
        candidates = self._state.all_candidates
        if not candidates:
            if self._is_searching:
                yield Static(
                    "[#e0a044]Searching the web for competitors...[/]\n"
                    "[#a89984]This usually takes 10-30 seconds.[/]",
                    id="discovery-empty",
                )
            else:
                yield Static(
                    "[#a89984]No candidates yet. Click Search More to find competitors.[/]",
                    id="discovery-empty",
                )
            return

        for i, candidate in enumerate(candidates):
            tier_display = candidate.suggested_tier.value.capitalize()
            with Horizontal(classes="candidate-row", id=f"candidate-{i}"):
                yield Button(
                    "[x]" if candidate.accepted else "[ ]",
                    id=f"btn-toggle-{i}",
                    classes="candidate-toggle",
                )
                yield Static(
                    f"[bold #efe5c0]{candidate.name}[/]  "
                    f"[#a89984]{candidate.url}[/]\n"
                    f"{candidate.blurb}\n"
                    f"[#a89984]Found via: {candidate.provenance}  |  "
                    f"Tier: {tier_display}[/]",
                    classes="candidate-detail",
                )

    def _build_roster_summary(self):
        accepted = self._state.accepted_candidates
        if not accepted:
            return
        names = ", ".join(c.name for c in accepted[:10])
        suffix = f" ... ({len(accepted)} total)" if len(accepted) > 10 else ""
        yield Static(
            f"[bold #e0a044]ACCEPTED ROSTER[/] ({len(accepted)})\n"
            f"[#a89984]{names}{suffix}[/]",
            id="roster-summary",
        )

    def toggle_candidate(self, index: int) -> None:
        self._state.toggle(index)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        _log.info(
            "DiscoveryScreen button pressed id=%s candidates=%d has_search_fn=%s",
            button_id,
            len(self._state.all_candidates),
            self._search_fn is not None,
        )
        if button_id == "btn-done":
            self.dismiss(self._state.accepted_candidates)
        elif button_id == "btn-search-more":
            if self._search_fn is None:
                self.app.notify(
                    "Search function not configured. API key may be missing.",
                    title="Cannot search",
                    severity="error",
                )
                return
            self._do_search()
        elif button_id == "btn-add-manual":
            self._show_manual_inputs()
        elif button_id == "btn-accept-all":
            self._state.accept_all()
            self._refresh_display()
        elif button_id == "btn-reject-all":
            self._state.reject_all()
            self._refresh_display()
        elif button_id.startswith("btn-toggle-"):
            try:
                index = int(button_id.removeprefix("btn-toggle-"))
            except ValueError:
                return
            self._state.toggle(index)
            self._refresh_display()

    @work(exclusive=True)
    async def _do_search(self) -> None:
        if self._search_fn is None:
            _log.warning("DiscoveryScreen._do_search called but _search_fn is None")
            return

        if self._is_searching:
            _log.info("DiscoveryScreen: search already in progress, ignoring")
            return

        self._is_searching = True
        _log.info("DiscoveryScreen: starting search in domain=%s", self._domain)
        await self.recompose()

        try:
            candidates = await self._search_fn(self._state)
        except Exception as exc:
            _log.exception("DiscoveryScreen: search raised exception")
            self._is_searching = False
            self.app.notify(
                f"Search failed: {exc}",
                title="Discovery error",
                severity="error",
                timeout=10,
            )
            await self.recompose()
            return

        _log.info(
            "DiscoveryScreen: search returned %d candidates",
            len(candidates),
        )
        self._is_searching = False

        if candidates:
            self._state.add_round(candidates)
            self.app.notify(
                f"Found {len(candidates)} candidates",
                title="Discovery",
                timeout=3,
            )
        else:
            self.app.notify(
                "Agent returned no candidates. The LLM may need web search "
                "enabled in your Anthropic console, or the domain may be too "
                "narrow. Try Add Manually.",
                title="Discovery",
                severity="warning",
                timeout=10,
            )

        await self.recompose()

    def _refresh_display(self) -> None:
        self._schedule_recompose()

    @work
    async def _schedule_recompose(self) -> None:
        await self.recompose()

    def _show_manual_inputs(self) -> None:
        """Mount inline name + URL inputs for adding a manual candidate.

        Submitting either input commits the entry via
        :meth:`DiscoveryState.add_manual` and tears the inputs back down.
        Pressing Esc on an input dismisses without saving.
        """
        try:
            container = self.query_one("#discovery-container", Vertical)
        except Exception:
            return
        if self.query("#manual-name"):
            return  # already showing

        container.mount(
            Input(
                placeholder="Competitor name",
                id="manual-name",
            ),
        )
        container.mount(
            Input(
                placeholder="URL (optional, https://...)",
                id="manual-url",
            ),
        )
        with contextlib.suppress(Exception):
            self.query_one("#manual-name", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id not in ("manual-name", "manual-url"):
            return
        try:
            name_input = self.query_one("#manual-name", Input)
            url_input = self.query_one("#manual-url", Input)
        except Exception:
            return

        name = name_input.value.strip()
        url = url_input.value.strip()

        if not name:
            # Just tear down without saving
            self._tear_down_manual_inputs()
            return

        self._state.add_manual(
            name=name,
            url=url or f"https://{name.lower().replace(' ', '-')}.example",
            blurb="Manually added competitor",
        )
        self.app.notify(f"Added: {name}", title="Discovery")
        self._tear_down_manual_inputs()
        self._refresh_display()

    def _tear_down_manual_inputs(self) -> None:
        for widget_id in ("#manual-name", "#manual-url"):
            for widget in self.query(widget_id):
                widget.remove()
