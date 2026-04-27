"""Research Template screen for recon TUI (Screen 5).

Shows system-proposed sections based on the space. User toggles
on/off and can add custom sections via a prompt field.
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
from typing import Any

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Static

from recon.logging import get_logger
from recon.tui.shell import ReconScreen
from recon.tui.widgets import ChecklistItem, action_button, button_label

_log = get_logger(__name__)


@dataclass
class TemplateResult:
    sections: list[dict[str, Any]]


@dataclass
class SectionEditorResult:
    title: str
    description: str


class _SectionEditorModal(ModalScreen[SectionEditorResult | None]):
    DEFAULT_CSS = """
    _SectionEditorModal {
        align: center middle;
    }
    #section-editor {
        width: 88;
        height: auto;
        padding: 1 2;
        border: solid #3a3a3a;
        background: #000000;
    }
    #section-editor Input {
        margin: 0 0 1 0;
    }
    #section-editor-actions {
        height: 3;
        layout: horizontal;
    }
    #section-editor-actions Button {
        margin: 0 1 0 0;
    }
    """

    def __init__(self, title: str, description: str, mode: str) -> None:
        super().__init__()
        self._title = title
        self._description = description
        self._mode = mode

    def compose(self) -> ComposeResult:
        with Vertical(id="section-editor"):
            heading = "ADD SECTION" if self._mode == "add" else "EDIT SECTION"
            yield Static(f"[bold #DDEDC4]▒ {heading} ▒[/]")
            yield Static(
                "[#a59a86]Edit the section title and the research prompt used to guide this dimension.[/]"
            )
            yield Static("")
            yield Input(value=self._title, placeholder="Section title", id="editor-title")
            yield Input(
                value=self._description,
                placeholder="Prompt-style description of what to research and think about",
                id="editor-description",
            )
            with Horizontal(id="section-editor-actions"):
                yield Button(button_label("SAVE", "Enter"), id="editor-save", variant="primary")
                yield Button(button_label("CANCEL", "Esc"), id="editor-cancel")

    def on_mount(self) -> None:
        self.query_one("#editor-title", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "editor-save":
            self.action_submit()
        elif event.button.id == "editor-cancel":
            self.dismiss(None)

    def on_input_submitted(self, _event: Input.Submitted) -> None:
        self.action_submit()

    def action_submit(self) -> None:
        title = self.query_one("#editor-title", Input).value.strip()
        description = self.query_one("#editor-description", Input).value.strip()
        if not title or not description:
            self.app.notify("Title and description are required", severity="warning")
            return
        self.dismiss(SectionEditorResult(title=title, description=description))


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
        # Enter toggles the row under the cursor. Space advances to the
        # next top-level screen.
        Binding("enter", "toggle_selected", "toggle", show=False),
        Binding("space", "next", "next", show=False),
        # Bulk actions — `a` / `d` swap all.
        Binding("a", "select_all", "all", show=False),
        Binding("d", "deselect_all", "none", show=False),
        Binding("e", "edit_selected", "edit section", show=False),
        Binding("m", "show_add_section", "add section", show=False),
        Binding("escape", "cancel", "Back", show=False),
    ]

    keybind_hints = (
        "[#DDEDC4]↑↓[/] nav · [#DDEDC4]↲[/] toggle · "
        "[#DDEDC4]a[/] all · [#DDEDC4]d[/] none · "
        "[#DDEDC4]e[/] edit · [#DDEDC4]m[/] add section · "
        "[#DDEDC4]space[/] next · [#DDEDC4]esc[/] back"
    )

    DEFAULT_CSS = """
    TemplateScreen {
        background: #000000;
    }
    #template-container {
        width: 100%;
        padding: 0;
        overflow-y: auto;
    }
    #custom-section-card {
        margin-top: 1;
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

    def __init__(
        self,
        sections: list[dict[str, Any]],
        domain: str,
        *,
        next_tab: str | None = None,
    ) -> None:
        super().__init__()
        self._sections = [dict(s) for s in sections]
        self._domain = domain
        self._next_tab = next_tab
        # Row under the keyboard cursor. Highlighted with the
        # `is-cursor` class so space/enter know which row to toggle.
        self._cursor: int = 0

    def on_mount(self) -> None:
        self.call_after_refresh(self._after_recompose)

    def compose_body(self) -> ComposeResult:
        from recon.tui.primitives import Card

        selected_section = self._current_section()
        selected_meta = self._section_detail_meta(selected_section)
        with Vertical(id="template-container"):
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
                        description="",
                        selected=section.get("selected", False),
                        index=i,
                    )

            with Card(
                title="SECTION DETAIL",
                meta=selected_meta,
                id="section-detail-card",
            ):
                yield Static(
                    f"[#DDEDC4]{selected_section.get('title', 'No section selected')}[/]",
                    id="section-detail-title",
                )
                yield Static("")
                yield Static(
                    f"[#787266]{selected_section.get('description', '')}[/]",
                    id="section-detail-description",
                )
                yield Static("")
                yield action_button("EDIT SECTION", "E", button_id="btn-edit-section")

            with Card(title="ADD NEW SECTION", id="custom-section-card"):
                yield Static(
                    "[#a59a86]Add a custom section or dimension to the dossier.[/]"
                )
                yield Static("")
                yield action_button("ADD SECTION", "M", button_id="btn-add-section")

        with Horizontal(id="template-actions"):
            yield action_button("BACK", "Esc", button_id="btn-back")
            yield action_button("SELECT ALL", "A", button_id="btn-select-all")
            yield action_button("DESELECT ALL", "D", button_id="btn-deselect-all")
            yield Static("", classes="action-spacer")
            yield action_button("NEXT", "Space", button_id="btn-next", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id == "btn-back":
            self.action_cancel()
        elif button_id == "btn-select-all":
            self._set_all_selected(True)
        elif button_id == "btn-deselect-all":
            self._set_all_selected(False)
        elif button_id == "btn-edit-section":
            self.action_edit_selected()
        elif button_id == "btn-add-section":
            self.action_show_add_section()
        elif button_id == "btn-next":
            self.action_next()

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
        self._refresh_section_detail()

    # -- keyboard row nav -------------------------------------------------

    def action_cursor_down(self) -> None:
        if not self._sections:
            return
        self._cursor = (self._cursor + 1) % len(self._sections)
        self._refresh_cursor()
        self._refresh_section_detail()

    def action_cursor_up(self) -> None:
        if not self._sections:
            return
        self._cursor = (self._cursor - 1) % len(self._sections)
        self._refresh_cursor()
        self._refresh_section_detail()

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
        self._refresh_section_detail()

    def action_select_all(self) -> None:
        self._set_all_selected(True)
        self._refresh_meta()
        self._refresh_section_detail()

    def action_deselect_all(self) -> None:
        self._set_all_selected(False)
        self._refresh_meta()
        self._refresh_section_detail()

    def action_show_add_section(self) -> None:
        self.app.push_screen(
            _SectionEditorModal(
                title="",
                description="",
                mode="add",
            ),
            self._handle_add_section_result,
        )

    def action_edit_selected(self) -> None:
        if not self._sections:
            return
        section = self._sections[self._cursor]
        self.app.push_screen(
            _SectionEditorModal(
                title=str(section.get("title", "")),
                description=str(section.get("description", "")),
                mode="edit",
            ),
            self._handle_edit_section_result,
        )

    def _refresh_cursor(self) -> None:
        """Re-apply the `is-cursor` class to exactly one row."""
        for item in self.query(ChecklistItem):
            if item._index == self._cursor:
                item.add_class("is-cursor")
            else:
                item.remove_class("is-cursor")

    def _refresh_meta(self) -> None:
        """Update the card's selection-count meta in-place."""
        selected = sum(1 for s in self._sections if s.get("selected"))
        total = len(self._sections)
        with contextlib.suppress(Exception):
            head = self.query_one("#sections-card .card-head", Static)
            head.update(
                f"[#a59a86]DOSSIER SCHEMA[/] [#686359]·[/] [#787266]{selected} / {total} selected[/]"
            )

    def _refresh_section_detail(self) -> None:
        section = self._current_section()
        status = "enabled" if section.get("selected") else "disabled"
        with contextlib.suppress(Exception):
            head = self.query_one("#section-detail-card .card-head", Static)
            head.update(
                f"[#a59a86]SECTION DETAIL[/] [#686359]·[/] "
                f"[#787266]{section.get('title', 'No section selected')} - {status}[/]"
            )
        with contextlib.suppress(Exception):
            self.query_one("#section-detail-title", Static).update(
                f"[#DDEDC4]{section.get('title', 'No section selected')}[/]"
            )
        with contextlib.suppress(Exception):
            self.query_one("#section-detail-description", Static).update(
                f"[#787266]{section.get('description', '')}[/]"
            )

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_next(self) -> None:
        if self._next_tab is None:
            self.action_submit()
            return
        with contextlib.suppress(Exception):
            self.app._update_schema_sections(self._sections)  # type: ignore[attr-defined]
        with contextlib.suppress(Exception):
            self.app.action_goto_tab(self._next_tab)

    def action_submit(self) -> None:
        self.dismiss(TemplateResult(sections=list(self._sections)))

    def _add_custom_section(self, title: str, description: str) -> None:
        """Add a custom section from user prompt."""
        import re

        key = re.sub(r"[^\w]+", "_", title.lower()).strip("_")
        existing_keys = {str(section.get("key", "")) for section in self._sections}
        base_key = key or "custom_section"
        suffix = 2
        while key in existing_keys:
            key = f"{base_key}_{suffix}"
            suffix += 1

        self._sections.append({
            "key": key,
            "title": title,
            "description": description,
            "selected": True,
            "allowed_formats": ["prose", "bullet_list", "key_value"],
            "preferred_format": "prose",
        })
        _log.info("added custom section key=%s title=%s", key, title)
        self._cursor = len(self._sections) - 1

    def _handle_add_section_result(self, result: object | None) -> None:
        if not isinstance(result, SectionEditorResult):
            return
        self._add_custom_section(result.title, result.description)
        self.app.notify("Added section", severity="information")
        self._schedule_recompose()

    def _handle_edit_section_result(self, result: object | None) -> None:
        if not isinstance(result, SectionEditorResult):
            return
        if not (0 <= self._cursor < len(self._sections)):
            return
        section = self._sections[self._cursor]
        section["title"] = result.title
        section["description"] = result.description
        self.app.notify("Updated section", severity="information")
        self._schedule_recompose()

    @work
    async def _schedule_recompose(self) -> None:
        await self.recompose()
        self.call_after_refresh(self._after_recompose)

    def _after_recompose(self) -> None:
        self._refresh_cursor()
        self._refresh_meta()
        self._refresh_section_detail()

    def _current_section(self) -> dict[str, Any]:
        if not self._sections:
            return {}
        return self._sections[self._cursor]

    @staticmethod
    def _section_detail_meta(section: dict[str, Any]) -> str:
        title = section.get("title", "No section selected")
        status = "enabled" if section.get("selected") else "disabled"
        return f"{title} - {status}"
