"""ThemeCurationScreen for recon TUI.

Pipeline gate at Phase 5b. Discovered themes are presented for
user curation: toggle on/off, rename, investigate topics. Pipeline
resumes when user confirms. Pushed via push_screen_wait from
RunScreen's pipeline worker.
"""

from __future__ import annotations

from textual.app import ComposeResult  # noqa: TCH002 -- used at runtime
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from recon.themes import DiscoveredTheme  # noqa: TCH001
from recon.tui.models.curation import ThemeCurationModel  # noqa: TCH001


class ThemeCurationScreen(ModalScreen[list[DiscoveredTheme]]):
    """Interactive theme curation gate for the pipeline."""

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
        background: #0d0d0d;
        overflow-y: auto;
    }
    .theme-entry {
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
                f"[bold #e0a044]THEME CURATION[/]  "
                f"{len(self._model.entries)} themes discovered, "
                f"{self._model.selected_count} selected",
                id="curation-title",
            )
            yield Static("")

            for i, entry in enumerate(self._model.entries):
                checkbox = "[x]" if entry.enabled else "[ ]"
                yield Static(
                    f"{checkbox} [bold #efe5c0]{i + 1}. {entry.label}[/]  "
                    f"[#a89984]({entry.chunk_count} chunks, "
                    f"{entry.evidence_strength})[/]",
                    classes="theme-entry",
                    id=f"theme-{i}",
                )

            yield Static("")
            yield Static(
                "[#a89984][Space] Toggle  [E] Edit name  "
                "[V] View evidence  [+] Investigate topic[/]"
            )
            yield Static("")
            with Horizontal(classes="action-bar"):
                yield Button(
                    "Done -- synthesize selected",
                    id="btn-done",
                    variant="primary",
                )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-done":
            self.dismiss(self._model.to_discovered_themes())
