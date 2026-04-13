"""Research Template screen for recon TUI (Screen 5).

Shows system-proposed sections based on the space. User toggles
on/off and can add custom sections via a prompt field.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Input, Static

from recon.logging import get_logger
from recon.tui.shell import ReconScreen
from recon.tui.widgets import ChecklistItem

_log = get_logger(__name__)


@dataclass
class TemplateResult:
    sections: list[dict[str, Any]]


class TemplateScreen(ReconScreen):
    """Full-screen research template with toggleable sections."""

    flow_step = 2

    BINDINGS = [
        Binding("escape", "cancel", "Back", show=False),
    ]

    keybind_hints = "[#e0a044]esc[/] back"

    DEFAULT_CSS = """
    TemplateScreen {
        background: #000000;
    }
    #template-container {
        width: 100%;
        padding: 1 2;
        overflow-y: auto;
    }
    #template-actions {
        dock: bottom;
        height: 3;
        padding: 0 2;
        layout: horizontal;
        background: #1a1a1a;
    }
    #template-actions Button {
        margin: 0 1 0 0;
    }
    """

    show_log_pane = False
    show_activity_feed = False
    show_run_status_bar = False

    def __init__(self, sections: list[dict[str, Any]], domain: str) -> None:
        super().__init__()
        self._sections = [dict(s) for s in sections]
        self._domain = domain

    def compose_body(self) -> ComposeResult:
        with Vertical(id="template-container"):
            yield Static(
                "[bold #e0a044]── RESEARCH TEMPLATE ──[/]\n\n"
                f"[#a89984]We designed these sections based on your space. Each competitor\n"
                f"will be researched across the sections you select.[/]",
            )
            yield Static("")

            for i, section in enumerate(self._sections):
                yield ChecklistItem(
                    label=section["title"],
                    description=section.get("description", ""),
                    selected=section.get("selected", False),
                    index=i,
                )

            yield Static("")
            yield Static(
                "[bold #e0a044]── ADD YOUR OWN ──[/]\n"
                "[#a89984]Describe a section you'd like added and we'll create it.\n"
                'e.g. "Compare open-source vs proprietary firmware approaches"\n'
                'e.g. "Materials compatibility — which filaments each printer supports"[/]',
            )
            yield Static("")
            yield Input(
                placeholder="Describe a custom section...",
                id="custom-section-input",
            )

        with Horizontal(id="template-actions"):
            yield Button("Proceed", id="btn-proceed", variant="primary")
            yield Button("Back", id="btn-back")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id == "btn-proceed":
            self.action_submit()
        elif button_id == "btn-back":
            self.action_cancel()

    def on_checklist_item_toggled(self, event: ChecklistItem.Toggled) -> None:
        if 0 <= event.index < len(self._sections):
            self._sections[event.index]["selected"] = event.selected

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Enter in the custom section field adds the section."""
        if event.input.id == "custom-section-input":
            text = event.input.value.strip()
            if text:
                self._add_custom_section(text)
                event.input.value = ""
                self.app.notify(f"Added section", severity="information")
                # Recompose to show the new section
                self._schedule_recompose()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_submit(self) -> None:
        # Check if there's custom section text to add first
        try:
            custom_input = self.query_one("#custom-section-input", Input)
            custom_text = custom_input.value.strip()
            if custom_text:
                self._add_custom_section(custom_text)
                custom_input.value = ""
        except Exception:
            pass

        self.dismiss(TemplateResult(sections=list(self._sections)))

    def _add_custom_section(self, description: str) -> None:
        """Add a custom section from user prompt."""
        import re

        words = description.strip().split()
        title = " ".join(w.capitalize() for w in words[:5])
        key = re.sub(r"[^\w]+", "_", title.lower()).strip("_")

        self._sections.append({
            "key": key,
            "title": title,
            "description": description,
            "selected": True,
        })
        _log.info("added custom section key=%s title=%s", key, title)

    @work
    async def _schedule_recompose(self) -> None:
        await self.recompose()
