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
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Static

from recon.logging import get_logger

_log = get_logger(__name__)


@dataclass
class TemplateResult:
    sections: list[dict[str, Any]]


class TemplateScreen(ModalScreen[TemplateResult]):
    """Research template with toggleable sections and custom prompt."""

    BINDINGS = [
        Binding("escape", "cancel", "Back", show=False),
        Binding("space", "toggle_current", "Toggle", show=False),
        Binding("up", "cursor_up", "Up", show=False),
        Binding("down", "cursor_down", "Down", show=False),
    ]

    DEFAULT_CSS = """
    TemplateScreen {
        align: center middle;
    }
    #template-container {
        width: 85;
        max-height: 38;
        background: #1d1d1d;
        border: round #3a3a3a;
        padding: 1 2;
        overflow-y: auto;
    }
    .section-row {
        height: 1;
    }
    .button-row {
        height: 3;
        margin: 1 0 0 0;
        layout: horizontal;
    }
    .button-row Button {
        margin: 0 1 0 0;
    }
    .section-row-selected {
        height: 1;
        color: #efe5c0;
    }
    .section-row-deselected {
        height: 1;
        color: #a89984;
    }
    """

    def __init__(self, sections: list[dict[str, Any]], domain: str) -> None:
        super().__init__()
        self._sections = [dict(s) for s in sections]
        self._domain = domain
        self._cursor = 0

    def compose(self) -> ComposeResult:
        with Vertical(id="template-container"):
            yield Static(
                "[bold #e0a044]── RESEARCH TEMPLATE ──[/]\n\n"
                f"[#a89984]We designed these sections based on your space. Each competitor\n"
                f"will be researched across the sections you select.[/]",
            )
            yield Static("")

            for i, section in enumerate(self._sections):
                marker = "[x]" if section.get("selected") else "[ ]"
                color = "#efe5c0" if section.get("selected") else "#a89984"
                cursor = ">" if i == self._cursor else " "
                yield Static(
                    f"[#e0a044]{cursor}[/] [{color}]{marker} "
                    f"{section['title']}[/]"
                    f"  [#3a3a3a]{section.get('description', '')}[/]",
                    id=f"section-row-{i}",
                    classes="section-row",
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
            yield Static("")
            with Horizontal(classes="button-row"):
                yield Button("Proceed", id="btn-proceed", variant="primary")
                yield Button("Back", id="btn-back")
            yield Static(
                "[#a89984]space[/] [#e0a044]toggle sections[/] · "
                "[#a89984]↑↓[/] [#e0a044]navigate[/] · "
                "[#a89984]enter in field[/] [#e0a044]add section[/]",
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id == "btn-proceed":
            self.action_submit()
        elif button_id == "btn-back":
            self.action_cancel()

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

    def action_toggle_current(self) -> None:
        if 0 <= self._cursor < len(self._sections):
            self._sections[self._cursor]["selected"] = not self._sections[self._cursor].get("selected", True)
            self._refresh_rows()

    def action_cursor_up(self) -> None:
        if self._sections:
            self._cursor = (self._cursor - 1) % len(self._sections)
            self._refresh_rows()

    def action_cursor_down(self) -> None:
        if self._sections:
            self._cursor = (self._cursor + 1) % len(self._sections)
            self._refresh_rows()

    def _refresh_rows(self) -> None:
        for i, section in enumerate(self._sections):
            try:
                row = self.query_one(f"#section-row-{i}", Static)
                marker = "[x]" if section.get("selected") else "[ ]"
                color = "#efe5c0" if section.get("selected") else "#a89984"
                cursor = ">" if i == self._cursor else " "
                row.update(
                    f"[#e0a044]{cursor}[/] [{color}]{marker} "
                    f"{section['title']}[/]"
                    f"  [#3a3a3a]{section.get('description', '')}[/]"
                )
            except Exception:
                pass

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
