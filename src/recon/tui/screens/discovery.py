"""DiscoveryScreen for recon TUI.

Full-screen competitor search. Users toggle candidates on/off,
search for more, view the full roster, and proceed when ready.
Uses buttons for actions so keybinds don't conflict with input.
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable, Coroutine
from typing import Any

from textual import work
from textual.app import ComposeResult  # noqa: TCH002 -- used at runtime
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, DataTable, Input, Static

from recon.discovery import DiscoveryCandidate, DiscoveryState  # noqa: TCH001
from recon.logging import get_logger
from recon.tui.shell import ReconScreen

_log = get_logger(__name__)

SearchFn = Callable[[DiscoveryState | None], Coroutine[Any, Any, list[DiscoveryCandidate]]]

_SPINNER_FRAMES = ["|", "/", "-", "\\"]


class DiscoveryScreen(ReconScreen):
    """Full-screen competitor discovery with button-driven actions."""

    BINDINGS = [
        Binding("space", "toggle_current", "Toggle", show=False),
        Binding("escape", "cancel", "Back", show=False),
        Binding("delete", "toggle_current", "Toggle", show=False),
        Binding("backspace", "toggle_current", "Toggle", show=False),
    ]

    keybind_hints = (
        "[#e0a044]space[/] toggle · "
        "[#e0a044]↑↓[/] navigate · "
        "[#e0a044]esc[/] back"
    )

    DEFAULT_CSS = """
    DiscoveryScreen {
        background: #000000;
    }
    #discovery-container {
        width: 100%;
        height: auto;
        padding: 1 2;
        background: #000000;
        overflow-y: auto;
    }
    #discovery-candidates {
        height: auto;
        margin: 1 0 0 0;
    }
    .discovery-actions {
        height: 3;
        margin: 1 0;
        layout: horizontal;
    }
    .discovery-actions Button {
        height: 3;
        min-width: 0;
        margin: 0 1 0 0;
        padding: 0 1;
    }
    #roster-summary {
        height: auto;
        margin: 1 0 0 0;
        padding: 1 2;
        border: round #3a3a3a;
    }
    .api-key-input {
        height: 3;
        margin: 0 0;
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
        self._spinner_frame: int = 0

    @property
    def state(self) -> DiscoveryState:
        return self._state

    @property
    def cursor_index(self) -> int:
        return self._cursor_index

    def set_search_fn(self, fn: SearchFn) -> None:
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

        # Spinner tick during search
        self.set_interval(0.15, self._spinner_tick, name="spinner")

    def _spinner_tick(self) -> None:
        if self._is_searching:
            self._spinner_frame = (self._spinner_frame + 1) % len(_SPINNER_FRAMES)
            self._update_search_status()

    def _update_search_status(self) -> None:
        try:
            progress = self.query_one("#search-progress", Static)
            if self._is_searching:
                frame = _SPINNER_FRAMES[self._spinner_frame]
                progress.update(
                    f"[bold #e0a044]── SEARCH ──[/] "
                    f"[#a89984]round {self._state.round_count + 1}[/]\n"
                    f"[#e0a044]{frame}[/]  [#a89984]searching for competitors...[/]"
                )
            elif self._state.round_count > 0:
                progress.update(
                    f"[bold #e0a044]── SEARCH ──[/] "
                    f"[#98971a]{self._state.round_count} rounds complete[/]"
                )
            else:
                progress.update(
                    "[bold #e0a044]── SEARCH ──[/]"
                )
        except Exception:
            pass

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
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
        self.dismiss(self._state.accepted_candidates)

    def action_done(self) -> None:
        self.dismiss(self._state.accepted_candidates)

    def action_accept_all(self) -> None:
        self._state.accept_all()
        self._refresh_display()

    def action_reject_all(self) -> None:
        self._state.reject_all()
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

    def compose_body(self) -> ComposeResult:
        with Vertical(id="discovery-container"):
            yield Static(
                f"[bold #e0a044]── COMPETITOR DISCOVERY ──[/] "
                f"[#a89984]·[/] [#efe5c0]{self._domain}[/]",
                id="discovery-title",
            )
            yield self._build_search_progress()
            yield self._build_summary()

            # Action buttons — visible, near the content
            with Horizontal(classes="discovery-actions"):
                yield Button(
                    "Done — proceed to next step",
                    id="btn-done", variant="primary",
                )
                yield Button("Search More", id="btn-search-more")
                yield Button("Add Manually", id="btn-add-manual")
                yield Button("Accept All", id="btn-accept-all")
                yield Button("Reject All", id="btn-reject-all")

            with Vertical(id="discovery-candidates"):
                yield from self._build_candidate_list()
            yield from self._build_roster_summary()

    def _build_search_progress(self) -> Static:
        if self._is_searching:
            frame = _SPINNER_FRAMES[self._spinner_frame]
            return Static(
                f"[bold #e0a044]── SEARCH ──[/] "
                f"[#a89984]round {self._state.round_count + 1}[/]\n"
                f"[#e0a044]{frame}[/]  [#a89984]searching for competitors...[/]",
                id="search-progress",
            )
        if self._state.round_count > 0:
            return Static(
                f"[bold #e0a044]── SEARCH ──[/] "
                f"[#98971a]{self._state.round_count} rounds complete[/]",
                id="search-progress",
            )
        return Static(
            "[bold #e0a044]── SEARCH ──[/]",
            id="search-progress",
        )

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
                    "[#a89984]No candidates yet. Click "
                    "[#e0a044]Search More[/] or "
                    "[#e0a044]Add Manually[/].[/]",
                    id="discovery-empty",
                )
            return

        table = DataTable(id="discovery-table")
        yield table

    def _populate_table(self) -> None:
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
        _log.info("DiscoveryScreen button pressed id=%s", button_id)
        if button_id == "btn-done":
            self.dismiss(self._state.accepted_candidates)
        elif button_id == "btn-search-more":
            self.action_search_more()
        elif button_id == "btn-add-manual":
            self._show_manual_inputs()
        elif button_id == "btn-accept-all":
            self._state.accept_all()
            self._refresh_display()
        elif button_id == "btn-reject-all":
            self._state.reject_all()
            self._refresh_display()

    @work(exclusive=True)
    async def _do_search(self) -> None:
        if self._search_fn is None:
            return

        if self._is_searching:
            return

        self._is_searching = True
        self._update_search_status()

        try:
            candidates = await self._search_fn(self._state)
        except Exception as exc:
            _log.exception("DiscoveryScreen: search raised exception")
            self._is_searching = False
            self._update_search_status()
            self.app.notify(
                f"Search failed: {exc}",
                title="Discovery error",
                severity="error",
                timeout=10,
            )
            return

        _log.info("DiscoveryScreen: search returned %d candidates", len(candidates))
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
                "No candidates found. Try different search terms or Add Manually.",
                title="Discovery",
                severity="warning",
                timeout=10,
            )

        self._update_search_status()
        await self.recompose()

    def _refresh_display(self) -> None:
        try:
            self._populate_table()
            self._update_summary()
        except Exception:
            self._schedule_recompose()

    def _update_summary(self) -> None:
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
        try:
            container = self.query_one("#discovery-container", Vertical)
        except Exception:
            return
        if self.query("#manual-name"):
            return

        container.mount(
            Input(placeholder="Competitor name", id="manual-name"),
        )
        container.mount(
            Input(placeholder="URL (optional, https://...)", id="manual-url"),
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
