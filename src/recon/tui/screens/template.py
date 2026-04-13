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

_log = get_logger(__name__)


@dataclass
class TemplateResult:
    sections: list[dict[str, Any]]


class TemplateScreen(ReconScreen):
    """Full-screen research template with toggleable sections."""

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
        height: auto;
        padding: 1 2;
        overflow-y: auto;
    }
    .section-toggle {
        height: 3;
        width: 100%;
        background: transparent;
        color: #a89984;
        border: none;
        text-align: left;
        padding: 0 1;
        min-width: 0;
    }
    .section-toggle:hover {
        background: #1d1d1d;
        color: #efe5c0;
    }
    .section-toggle:focus {
        background: #1d1d1d;
        color: #e0a044;
    }
    .button-row {
        height: 3;
        margin: 1 0 0 0;
        layout: horizontal;
    }
    .button-row Button {
        margin: 0 1 0 0;
    }
    """

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
                marker = "x" if section.get("selected") else " "
                label = (
                    f"\\[{marker}] {section['title']}  "
                    f"{section.get('description', '')}"
                )
                yield Button(
                    label,
                    id=f"btn-section-{i}",
                    classes="section-toggle",
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

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id == "btn-proceed":
            self.action_submit()
        elif button_id == "btn-back":
            self.action_cancel()
        elif button_id.startswith("btn-section-"):
            try:
                index = int(button_id.removeprefix("btn-section-"))
                self._toggle_section(index)
            except ValueError:
                pass

    def _toggle_section(self, index: int) -> None:
        if 0 <= index < len(self._sections):
            self._sections[index]["selected"] = not self._sections[index].get("selected", True)
            # Update button label
            try:
                btn = self.query_one(f"#btn-section-{index}", Button)
                section = self._sections[index]
                marker = "x" if section.get("selected") else " "
                btn.label = (
                    f"\\[{marker}] {section['title']}  "
                    f"{section.get('description', '')}"
                )
            except Exception:
                pass

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
