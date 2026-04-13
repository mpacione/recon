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
from textual.widgets import Button, DataTable, Input, Static

from recon.discovery import DiscoveryCandidate, DiscoveryState  # noqa: TCH001
from recon.logging import get_logger
from recon.tui.shell import ReconScreen

_log = get_logger(__name__)

SearchFn = Callable[[DiscoveryState | None], Coroutine[Any, Any, list[DiscoveryCandidate]]]


class DiscoveryScreen(ModalScreen[list[DiscoveryCandidate]]):
    """Interactive competitor discovery with accumulating roster."""

    BINDINGS = [
        Binding("up", "cursor_up", "Up", show=False),
        Binding("down", "cursor_down", "Down", show=False),
        Binding("space", "toggle_current", "Toggle", show=False),
        Binding("escape", "cancel", "Back", show=False),
        Binding("a", "accept_all", "Accept all", show=False),
        Binding("x", "reject_all", "Reject all", show=False),
        Binding("s", "search_more", "Search more", show=False),
        Binding("n", "add_manually", "Add manually", show=False),
        Binding("d", "done", "Done", show=False),
        Binding("delete", "remove_current", "Remove", show=False),
        Binding("backspace", "remove_current", "Remove", show=False),
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
        border: round #3a3a3a;
        background: #000000;
        overflow-y: auto;
    }
    #discovery-candidates {
        height: auto;
        margin: 1 0 0 0;
    }
    .discovery-card {
        margin: 0 0 1 0;
    }
    .discovery-card.accepted {
        border: round #e0a044;
    }
    .discovery-card.rejected {
        border: round #3a3a3a;
        color: #a89984;
    }
    /* Action-bar buttons styled to match the cyberspace.online
       thin-bordered minimal aesthetic. Textual Buttons need at
       least 3 rows to show their label (top chrome + content row +
       bottom chrome), so we use height 3 but set `border: none`
       and `background: transparent` so the chrome rows render as
       empty space. The result is a flat text button with no box. */
    .discovery-actions {
        height: auto;
        margin: 1 0 0 0;
        layout: horizontal;
    }
    .discovery-actions Button {
        height: 3;
        min-width: 0;
        margin: 0 1 0 0;
        padding: 0 1;
        background: transparent;
        color: #a89984;
        border: none;
    }
    .discovery-actions Button:hover {
        background: #1d1d1d;
        color: #efe5c0;
    }
    .discovery-actions Button.-primary {
        color: #e0a044;
    }
    .discovery-actions Button.-primary:hover {
        background: #e0a044;
        color: #000000;
    }
    #roster-summary {
        height: auto;
        margin: 1 0 0 0;
        padding: 1 2;
        border: round #3a3a3a;
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
        self._populate_table()
        if (
            self._search_fn is not None
            and not self._auto_started
            and not self._state.all_candidates
        ):
            self._auto_started = True
            _log.info("DiscoveryScreen: auto-starting initial search on mount")
            self._do_search()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Toggle acceptance when the user presses Enter on a row."""
        index = event.cursor_row
        candidates = self._state.all_candidates
        if 0 <= index < len(candidates):
            self._state.toggle(index)
            self._populate_table()
            self._update_summary()

    def action_cursor_up(self) -> None:
        count = len(self._state.all_candidates)
        if count > 0:
            self._cursor_index = (self._cursor_index - 1) % count

    def action_cursor_down(self) -> None:
        count = len(self._state.all_candidates)
        if count > 0:
            self._cursor_index = (self._cursor_index + 1) % count

    def action_toggle_current(self) -> None:
        """Toggle the candidate at the DataTable cursor position."""
        try:
            table = self.query_one("#discovery-table", DataTable)
            index = table.cursor_row
        except Exception:
            index = self._cursor_index
        candidates = self._state.all_candidates
        if candidates and 0 <= index < len(candidates):
            self._state.toggle(index)
            self._refresh_display()

    def action_cancel(self) -> None:
        """Dismiss the discovery screen (Esc keybind).

        Returns the currently-accepted candidates, matching what the
        Done button does. This is the universal "back out without
        losing work" convention: pressing Escape finalizes whatever
        the user has already accepted rather than throwing away the
        whole round.
        """
        self.dismiss(self._state.accepted_candidates)

    def action_done(self) -> None:
        """Finalize the current accepted roster and close."""
        self.dismiss(self._state.accepted_candidates)

    def action_accept_all(self) -> None:
        self._state.accept_all()
        self._refresh_display()

    def action_reject_all(self) -> None:
        self._state.reject_all()
        self._refresh_display()

    def action_remove_current(self) -> None:
        """Remove the candidate at the cursor entirely (not just reject)."""
        try:
            table = self.query_one("#discovery-table", DataTable)
            index = table.cursor_row
        except Exception:
            return
        candidates = self._state.all_candidates
        if candidates and 0 <= index < len(candidates):
            removed = candidates[index]
            self._state.remove(index)
            self.app.notify(f"Removed: {removed.name}", title="Discovery")
            self._refresh_display()

    def action_search_more(self) -> None:
        if self._search_fn is None:
            self.app.notify(
                "Search function not configured. API key may be missing.",
                title="Cannot search",
                severity="error",
            )
            return
        self._do_search()

    def action_add_manually(self) -> None:
        self._show_manual_inputs()

    def compose(self) -> ComposeResult:
        with Vertical(id="discovery-container"):
            yield Static(
                f"[bold #e0a044]── DISCOVERY ──[/] [#a89984]·[/] "
                f"[#efe5c0]{self._domain}[/]",
                id="discovery-title",
            )
            yield self._build_summary()
            with Vertical(id="discovery-candidates"):
                yield from self._build_candidate_list()
            yield from self._build_roster_summary()
            # Button labels go through Rich markup parsing, so any
            # `[s]`/`[x]` pattern gets eaten as an unknown tag.
            # Escape the open bracket with a backslash so the label
            # renders as a literal key hint.
            with Horizontal(classes="discovery-actions"):
                yield Button("\\[↵] done", id="btn-done", variant="primary")
                yield Button("\\[s] search more", id="btn-search-more")
                yield Button("\\[n] add manually", id="btn-add-manual")
                yield Button("\\[a] accept all", id="btn-accept-all")
                yield Button("\\[x] reject all", id="btn-reject-all")

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
                    "[#a89984]No candidates yet. Press "
                    "[#e0a044]s[/] to search or "
                    "[#e0a044]n[/] to add manually.[/]",
                    id="discovery-empty",
                )
            return

        table = DataTable(id="discovery-table")
        yield table

    def _populate_table(self) -> None:
        """Fill (or refill) the DataTable from the current state.

        Called on mount and after any state change (search round,
        toggle, accept all, reject all).
        """
        try:
            table = self.query_one("#discovery-table", DataTable)
        except Exception:
            return

        table.clear(columns=True)
        table.add_columns("", "Name", "Tier", "URL")
        table.cursor_type = "row"

        for candidate in self._state.all_candidates:
            marker = "✓" if candidate.accepted else "·"
            tier = candidate.suggested_tier.value.capitalize()
            url_short = candidate.url[:40] if candidate.url else ""
            table.add_row(marker, candidate.name, tier, url_short)

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
        """Rebuild the DataTable and summary from current state.

        Much cheaper than a full recompose — just clears and re-adds
        rows. Falls back to recompose if the table isn't mounted yet
        (e.g., first render before any candidates exist).
        """
        try:
            self._populate_table()
            self._update_summary()
        except Exception:
            self._schedule_recompose()

    def _update_summary(self) -> None:
        """Refresh the summary line (accepted / rejected counts)."""
        try:
            summary = self.query_one("#discovery-summary", Static)
            accepted = len(self._state.accepted_candidates)
            rejected = len(self._state.rejected_candidates)
            summary.update(
                f"[#a89984]rounds:[/] [#e0a044]{self._state.round_count}[/]  "
                f"[#3a3a3a]·[/]  [#a89984]accepted:[/] [#e0a044]{accepted}[/]  "
                f"[#3a3a3a]·[/]  [#a89984]rejected:[/] [#e0a044]{rejected}[/]",
            )
        except Exception:
            pass

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
