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
from recon.tui.widgets import ChecklistItem, button_label

_log = get_logger(__name__)


@dataclass
class TemplateResult:
    sections: list[dict[str, Any]]


class TemplateScreen(ReconScreen):
    """Full-screen research template — v4 SCHEMA tab."""

    tab_key = "schema"
    flow_step = 2

    BINDINGS = [
        # Row nav — matches the web SCHEMA tab's `↑↓ NAV` hint.
        Binding("j", "cursor_down", "down", show=False),
        Binding("k", "cursor_up", "up", show=False),
        Binding("down", "cursor_down", "down", show=False),
        Binding("up", "cursor_up", "up", show=False),
        # Space / Enter toggle the row under the cursor.
        Binding("space", "toggle_selected", "toggle", show=False),
        Binding("enter", "toggle_selected", "toggle", show=False),
        # Flow + bulk actions — `n` advances, `a` / `d` swap all.
        Binding("n", "submit", "next", show=False),
        Binding("a", "select_all", "all", show=False),
        Binding("d", "deselect_all", "none", show=False),
        Binding("escape", "cancel", "Back", show=False),
    ]

    keybind_hints = (
        "[#DDEDC4]↑↓[/] nav · [#DDEDC4]space[/] toggle · "
        "[#DDEDC4]a[/] all · [#DDEDC4]d[/] none · "
        "[#DDEDC4]n[/] next · [#DDEDC4]esc[/] back"
    )

    DEFAULT_CSS = """
    TemplateScreen {
        background: #000000;
    }
    #template-container {
        width: 100%;
        padding: 1 2;
        overflow-y: auto;
    }
    ChecklistItem.is-cursor {
        background: #2e2b27;
    }
    #template-actions {
        dock: bottom;
        height: 3;
        padding: 0 2;
        layout: horizontal;
        background: #000000;
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
        # Row under the keyboard cursor. Highlighted with the
        # `is-cursor` class so space/enter know which row to toggle.
        self._cursor: int = 0

    def compose_body(self) -> ComposeResult:
        from recon.tui.primitives import Card

        with Vertical(id="template-container"):
            # Sections card — matches the web SCHEMA tab's "DOSSIER
            # SCHEMA" block with selection count in the meta slot.
            selected_count = sum(1 for s in self._sections if s.get("selected"))
            sections_meta = f"{selected_count} / {len(self._sections)} selected"
            with Card(title="DOSSIER SCHEMA", meta=sections_meta, id="sections-card"):
                yield Static(
                    f"[#a59a86]Sections researched for each competitor in the "
                    f"[#DDEDC4]{self._domain}[/] space.[/]"
                )
                yield Static("")
                for i, section in enumerate(self._sections):
                    yield ChecklistItem(
                        label=section["title"],
                        description=section.get("description", ""),
                        selected=section.get("selected", False),
                        index=i,
                    )

            # Custom-section card — separates the "add" affordance from
            # the existing list, matching the web UI's disabled
            # "Add section" row styling.
            with Card(title="ADD SECTION", id="custom-section-card"):
                yield Static(
                    "[#a59a86]Describe a custom section to add to the dossier.[/]\n"
                    '[#787266]e.g. "Developer experience — API docs, SDKs, and community"[/]'
                )
                yield Input(
                    placeholder="Describe a custom section...",
                    id="custom-section-input",
                )

        with Horizontal(id="template-actions"):
            yield Button(button_label("PROCEED", "N"), id="btn-proceed", variant="primary")
            yield Button(button_label("SELECT ALL", "A"), id="btn-select-all")
            yield Button(button_label("DESELECT ALL", "D"), id="btn-deselect-all")
            yield Button(button_label("BACK", "Esc"), id="btn-back")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id == "btn-proceed":
            self.action_submit()
        elif button_id == "btn-back":
            self.action_cancel()
        elif button_id == "btn-select-all":
            self._set_all_selected(True)
        elif button_id == "btn-deselect-all":
            self._set_all_selected(False)

    def _set_all_selected(self, selected: bool) -> None:
        for section in self._sections:
            section["selected"] = selected
        for item in self.query(ChecklistItem):
            if item._selected != selected:
                item._selected = selected
                item.refresh()

    def on_checklist_item_toggled(self, event: ChecklistItem.Toggled) -> None:
        if 0 <= event.index < len(self._sections):
            self._sections[event.index]["selected"] = event.selected
        # Clicking a row should also move the keyboard cursor there so
        # subsequent j/k keystrokes continue from the clicked position.
        self._cursor = event.index
        self._refresh_cursor()
        self._refresh_meta()

    # -- keyboard row nav -------------------------------------------------

    def action_cursor_down(self) -> None:
        if not self._sections:
            return
        self._cursor = (self._cursor + 1) % len(self._sections)
        self._refresh_cursor()

    def action_cursor_up(self) -> None:
        if not self._sections:
            return
        self._cursor = (self._cursor - 1) % len(self._sections)
        self._refresh_cursor()

    def action_toggle_selected(self) -> None:
        if not self._sections:
            return
        idx = self._cursor
        new_state = not self._sections[idx].get("selected", False)
        self._sections[idx]["selected"] = new_state
        # Find the matching ChecklistItem and flip it too so the row
        # glyph stays in sync.
        for item in self.query(ChecklistItem):
            if item._index == idx:
                item._selected = new_state
                item.refresh()
                break
        self._refresh_meta()

    def action_select_all(self) -> None:
        self._set_all_selected(True)
        self._refresh_meta()

    def action_deselect_all(self) -> None:
        self._set_all_selected(False)
        self._refresh_meta()

    def _refresh_cursor(self) -> None:
        """Re-apply the `is-cursor` class to exactly one row."""
        for item in self.query(ChecklistItem):
            if item._index == self._cursor:
                item.add_class("is-cursor")
            else:
                item.remove_class("is-cursor")

    def _refresh_meta(self) -> None:
        """Update the card's selection-count meta in-place."""
        # Card stores title/meta as border_title; we rebuild the
        # string so the "X / Y selected" count stays live.
        selected = sum(1 for s in self._sections if s.get("selected"))
        total = len(self._sections)
        try:
            card = self.query_one("#sections-card")
        except Exception:
            return
        card.border_title = f"DOSSIER SCHEMA   ·   {selected} / {total} selected"

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
