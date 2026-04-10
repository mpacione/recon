"""DiscoveryScreen for recon TUI.

Accumulating competitor search. Users toggle candidates on/off,
search for more, view the full roster, and dismiss with accepted
candidates when done.
"""

from __future__ import annotations

from textual.app import ComposeResult  # noqa: TCH002 -- used at runtime
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from recon.discovery import DiscoveryCandidate, DiscoveryState  # noqa: TCH001


class DiscoveryScreen(ModalScreen[list[DiscoveryCandidate]]):
    """Interactive competitor discovery with accumulating roster."""

    DEFAULT_CSS = """
    DiscoveryScreen {
        align: center middle;
    }
    #discovery-container {
        width: 90;
        height: auto;
        max-height: 90%;
        padding: 1 2;
        border: solid #3a3a3a;
        background: #0d0d0d;
        overflow-y: auto;
    }
    .candidate-item {
        height: auto;
        padding: 0 1;
        margin: 0 0 1 0;
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

    @property
    def state(self) -> DiscoveryState:
        return self._state

    def compose(self) -> ComposeResult:
        with Vertical(id="discovery-container"):
            yield Static(
                f"[bold #e0a044]DISCOVERY[/] -- {self._domain}",
                id="discovery-title",
            )
            yield self._build_summary()
            yield Static("")
            yield from self._build_candidate_list()
            yield from self._build_roster_summary()
            yield Static("")
            with Vertical(classes="action-bar"):
                yield Button("Done", id="btn-done", variant="primary")
                yield Button("Accept All", id="btn-accept-all")
                yield Button("Reject All", id="btn-reject-all")

    def _build_summary(self) -> Static:
        accepted = len(self._state.accepted_candidates)
        rejected = len(self._state.rejected_candidates)
        return Static(
            f"[#a89984]{accepted} accepted, {rejected} rejected[/]",
            id="discovery-summary",
        )

    def _build_candidate_list(self):
        candidates = self._state.all_candidates
        if not candidates:
            yield Static(
                "[#a89984]No candidates yet. Use Search More to find competitors.[/]",
                id="discovery-empty",
            )
            return

        for i, candidate in enumerate(candidates):
            checkbox = "[x]" if candidate.accepted else "[ ]"
            tier_display = candidate.suggested_tier.value.capitalize()
            yield Static(
                f"{checkbox} [bold #efe5c0]{candidate.name}[/]  "
                f"[#a89984]{candidate.url}[/]\n"
                f"    {candidate.blurb}\n"
                f"    [#a89984]Found via: {candidate.provenance}  |  "
                f"Tier: {tier_display}[/]",
                classes="candidate-item",
                id=f"candidate-{i}",
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
        if event.button.id == "btn-done":
            self.dismiss(self._state.accepted_candidates)
        elif event.button.id == "btn-accept-all":
            self._state.accept_all()
            self._refresh_display()
        elif event.button.id == "btn-reject-all":
            self._state.reject_all()
            self._refresh_display()

    def _refresh_display(self) -> None:
        container = self.query_one("#discovery-container", Vertical)
        container.remove_children()
        container.mount_all(list(self.compose_children()))

    def compose_children(self) -> ComposeResult:
        yield Static(
            f"[bold #e0a044]DISCOVERY[/] -- {self._domain}",
            id="discovery-title",
        )
        yield self._build_summary()
        yield Static("")
        yield from self._build_candidate_list()
        yield from self._build_roster_summary()
        yield Static("")
        with Vertical(classes="action-bar"):
            yield Button("Done", id="btn-done", variant="primary")
            yield Button("Accept All", id="btn-accept-all")
            yield Button("Reject All", id="btn-reject-all")
