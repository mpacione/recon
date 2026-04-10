"""CompetitorSelectorScreen for recon TUI.

Modal screen for selecting specific competitors from the workspace.
Used by RunPlannerScreen for operations that target a subset of
competitors (update specific, diff update specific).
"""

from __future__ import annotations

from textual.app import ComposeResult  # noqa: TCH002 -- used at runtime
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static


class CompetitorSelectorScreen(ModalScreen[list[str]]):
    """Checkbox list of competitors with select all / done."""

    DEFAULT_CSS = """
    CompetitorSelectorScreen {
        align: center middle;
    }
    #selector-container {
        width: 70;
        height: auto;
        max-height: 80%;
        padding: 1 2;
        border: solid #3a3a3a;
        background: #0d0d0d;
        overflow-y: auto;
    }
    .selector-item {
        height: auto;
        padding: 0 1;
    }
    .action-bar {
        height: auto;
        margin: 1 0;
        layout: horizontal;
    }
    .action-bar Button {
        margin: 0 1 0 0;
    }
    """

    def __init__(self, competitors: list[str]) -> None:
        super().__init__()
        self._competitors = list(competitors)
        self._selected_flags = [True] * len(competitors)

    @property
    def selected(self) -> list[str]:
        return [
            name
            for name, flag in zip(self._competitors, self._selected_flags, strict=True)
            if flag
        ]

    def toggle(self, index: int) -> None:
        if 0 <= index < len(self._selected_flags):
            self._selected_flags[index] = not self._selected_flags[index]

    def select_all(self) -> None:
        self._selected_flags = [True] * len(self._competitors)

    def compose(self) -> ComposeResult:
        with Vertical(id="selector-container"):
            yield Static(
                f"[bold #e0a044]SELECT COMPETITORS[/]  ({len(self._competitors)} available)",
                id="selector-title",
            )
            yield Static("")
            for i, name in enumerate(self._competitors):
                checkbox = "[x]" if self._selected_flags[i] else "[ ]"
                yield Static(
                    f"{checkbox} {name}",
                    classes="selector-item",
                    id=f"selector-{i}",
                )
            yield Static("")
            with Vertical(classes="action-bar"):
                yield Button("Done", id="btn-done", variant="primary")
                yield Button("Select All", id="btn-select-all")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-done":
            self.dismiss(self.selected)
        elif event.button.id == "btn-select-all":
            self.select_all()
