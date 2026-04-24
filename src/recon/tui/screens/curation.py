"""ThemeCurationScreen for recon TUI.

Pipeline gate at Phase 5b. Discovered themes are presented for
user curation: toggle on/off, rename, investigate topics. Pipeline
resumes when user confirms. Pushed via push_screen_wait from
RunScreen's pipeline worker.
"""

from __future__ import annotations

from textual import work
from textual.app import ComposeResult  # noqa: TCH002 -- used at runtime
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from recon.logging import get_logger
from recon.themes import DiscoveredTheme  # noqa: TCH001
from recon.tui.models.curation import ThemeCurationModel  # noqa: TCH001
from recon.tui.widgets import button_label

_log = get_logger(__name__)


class ThemeCurationScreen(ModalScreen[list[DiscoveredTheme]]):
    """Interactive theme curation gate for the pipeline."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    DEFAULT_CSS = """
    ThemeCurationScreen {
        align: center middle;
    }
    #curation-container {
        width: 80;
        height: auto;
        max-height: 90%;
        padding: 1 2;
        border: solid #3a3a3a;
        background: #000000;
        overflow-y: auto;
    }
    .theme-entry {
        width: 100%;
        height: auto;
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
    """

    def __init__(self, model: ThemeCurationModel) -> None:
        super().__init__()
        self._model = model

    @property
    def model(self) -> ThemeCurationModel:
        return self._model

    def toggle_theme(self, index: int) -> None:
        self._model.toggle(index)

    def compose(self) -> ComposeResult:
        with Vertical(id="curation-container"):
            yield Static(
                f"[bold #DDEDC4]── THEME CURATION ──[/]  "
                f"[#DDEDC4]{len(self._model.entries)}[/] discovered  "
                f"[#3a3a3a]·[/]  "
                f"[#DDEDC4]{self._model.selected_count}[/] selected",
                id="curation-title",
            )
            yield Static(
                "[#a59a86]toggle themes to choose what gets synthesized[/]",
                id="curation-hint",
            )
            yield Static("")

            for i, _entry in enumerate(self._model.entries):
                yield Button(
                    self._theme_label(i),
                    id=f"theme-{i}",
                    classes="theme-entry",
                )

            yield Static("")
            with Horizontal(classes="action-bar"):
                yield Button(
                    button_label("DONE — SYNTHESIZE SELECTED"),
                    id="btn-done",
                    variant="primary",
                )
                yield Button(button_label("SELECT ALL"), id="btn-select-all-themes")
                yield Button(button_label("CLEAR ALL"), id="btn-clear-all-themes")
                yield Button(button_label("CANCEL", "Esc"), id="btn-cancel-curation")

    def _theme_label(self, index: int) -> str:
        entry = self._model.entries[index]
        # Open bracket in Rich markup must be escaped, otherwise the
        # parser eats `[x]` as an unknown tag and the marker silently
        # disappears.
        checkbox = (
            "[#DDEDC4]\\[x][/]" if entry.enabled else "[#3a3a3a]\\[ ][/]"
        )
        return (
            f"{checkbox}  {index + 1}. {entry.label}  "
            f"({entry.chunk_count} chunks, {entry.evidence_strength})"
        )

    def action_cancel(self) -> None:
        """Dismiss curation with an empty selection (Esc keybind).

        Pipeline treats an empty theme list as "skip synthesis" so
        pressing Escape is a safe way to bail out of the gate without
        losing the run.
        """
        self.dismiss([])

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        _log.info("ThemeCurationScreen button pressed id=%s", button_id)
        if button_id == "btn-done":
            self.dismiss(self._model.to_discovered_themes())
        elif button_id == "btn-cancel-curation":
            self.dismiss([])
        elif button_id == "btn-select-all-themes":
            for entry in self._model.entries:
                entry.enabled = True
            self._schedule_recompose()
        elif button_id == "btn-clear-all-themes":
            for entry in self._model.entries:
                entry.enabled = False
            self._schedule_recompose()
        elif button_id.startswith("theme-"):
            try:
                index = int(button_id.removeprefix("theme-"))
            except ValueError:
                return
            self._model.toggle(index)
            self._schedule_recompose()

    @work
    async def _schedule_recompose(self) -> None:
        await self.recompose()
