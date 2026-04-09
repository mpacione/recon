"""TUI wizard for recon workspace creation.

Standalone Textual App that guides the user through 4 phases:
Identity -> Sections -> Sources -> Review. Produces a schema dict
that the CLI writes to recon.yaml.

This is a standalone App (not a Screen) because the wizard runs
before any workspace exists -- there is no ReconApp context.
"""

from __future__ import annotations

from pathlib import Path  # noqa: TCH003 -- used at runtime
from typing import Any

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Checkbox, Footer, Header, Input, SelectionList, Static

from recon.tui.theme import RECON_CSS
from recon.wizard import DecisionContext, DefaultSections, WizardPhase, WizardState

_PHASE_LABELS = {
    WizardPhase.IDENTITY: "Identity",
    WizardPhase.SECTIONS: "Sections",
    WizardPhase.SOURCES: "Sources",
    WizardPhase.REVIEW: "Review",
}

_PHASE_ORDER = list(_PHASE_LABELS.keys())

WIZARD_CSS = """
#phase-indicator {
    padding: 1 2;
}

#phase-content {
    padding: 1 2;
}

.wizard-label {
    margin: 1 0 0 0;
}

#btn-continue, #btn-confirm {
    margin: 1 1 0 0;
}

#btn-back {
    margin: 1 1 0 0;
}

.button-row {
    height: auto;
    margin: 1 0 0 0;
}

SelectionList {
    height: auto;
    max-height: 14;
    margin: 1 0;
}
"""


class _IdentityPhase(Vertical):
    def compose(self) -> ComposeResult:
        ctx_items = [(ctx.value, idx) for idx, ctx in enumerate(DecisionContext)]

        yield Static("[#a89984]Company name[/]", classes="wizard-label")
        yield Input(placeholder="e.g. Acme Corp", id="input-company")
        yield Static("[#a89984]Products (comma-separated)[/]", classes="wizard-label")
        yield Input(placeholder="e.g. Acme CI, Acme Deploy", id="input-products")
        yield Static("[#a89984]Domain description[/]", classes="wizard-label")
        yield Input(placeholder="e.g. CI/CD Tools", id="input-domain")
        yield Static("[#a89984]Decision context (Space to toggle)[/]", classes="wizard-label")
        yield SelectionList(*ctx_items, id="ctx-selection")
        yield Checkbox("Research own products through the same lens", id="cb-own-product")
        with Horizontal(classes="button-row"):
            yield Button("Continue", id="btn-continue", variant="primary")


class _SectionsPhase(Vertical):
    def __init__(self, selected_keys: set[str]) -> None:
        super().__init__()
        self._selected_keys = selected_keys

    def compose(self) -> ComposeResult:
        items = [
            (f"{s['title']} -- {s['description']}", s["key"], s["key"] in self._selected_keys)
            for s in DefaultSections.ALL
        ]
        yield Static(f"[#a89984]Select sections ({len(self._selected_keys)} recommended)[/]")
        yield SelectionList(*items, id="section-selection")
        with Horizontal(classes="button-row"):
            yield Button("Back", id="btn-back")
            yield Button("Continue", id="btn-continue", variant="primary")


class _SourcesPhase(Vertical):
    def __init__(self, state: WizardState) -> None:
        super().__init__()
        self._state = state

    def compose(self) -> ComposeResult:
        yield Static("[#a89984]Source preferences (defaults shown, accept to continue)[/]")
        yield Static("")
        for section in DefaultSections.ALL:
            key = section["key"]
            if key not in self._state.selected_section_keys:
                continue
            sources = self._state.get_source_preferences(key)
            primary = ", ".join(sources.get("primary", []))
            yield Static(f"[bold]{section['title']}[/]")
            yield Static(f"  [#a89984]Primary:[/] {primary}")
            yield Static("")
        with Horizontal(classes="button-row"):
            yield Button("Back", id="btn-back")
            yield Button("Accept Defaults", id="btn-continue", variant="primary")


class _ReviewPhase(Vertical):
    def __init__(self, state: WizardState) -> None:
        super().__init__()
        self._state = state

    def compose(self) -> ComposeResult:
        sections = [
            s["title"] for s in DefaultSections.ALL
            if s["key"] in self._state.selected_section_keys
        ]
        section_list = "\n".join(f"  {s}" for s in sections)

        yield Static("[bold #e0a044]Review your workspace configuration[/]")
        yield Static(f"[#a89984]Domain:[/] {self._state.domain}")
        yield Static(f"[#a89984]Company:[/] {self._state.company_name}")
        yield Static(f"[#a89984]Products:[/] {', '.join(self._state.products)}")
        yield Static(f"[#a89984]Own-product research:[/] {'Yes' if self._state.own_product else 'No'}")
        yield Static("")
        yield Static(f"[#a89984]Sections ({len(sections)}):[/]")
        yield Static(section_list)
        yield Static("")
        yield Static("[#a89984]Anthropic API key (required for research)[/]")
        yield Input(placeholder="sk-ant-...", id="input-api-key", password=True)
        yield Static("")
        with Horizontal(classes="button-row"):
            yield Button("Back", id="btn-back")
            yield Button("Create Workspace", id="btn-confirm", variant="primary")


class WizardApp(App):
    """Standalone Textual App for guided workspace creation."""

    TITLE = "recon -- workspace wizard"
    CSS = RECON_CSS + WIZARD_CSS

    BINDINGS = [
        Binding("ctrl+c", "quit", "Cancel"),
        Binding("escape", "go_back", "Back"),
    ]

    def __init__(self, output_dir: Path) -> None:
        super().__init__()
        self.output_dir = output_dir
        self.state = WizardState()
        self.result_schema: dict[str, Any] | None = None
        self.api_key: str = ""

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield Static(self._indicator_text(), id="phase-indicator")
        yield Vertical(id="phase-content")
        yield Footer()

    def on_mount(self) -> None:
        self._refresh_phase()

    def _indicator_text(self) -> str:
        idx = _PHASE_ORDER.index(self.state.phase) + 1
        label = _PHASE_LABELS[self.state.phase]
        return f"[bold #e0a044]Step {idx} of 4 -- {label}[/]"

    def _refresh_phase(self) -> None:
        self.query_one("#phase-indicator", Static).update(self._indicator_text())
        container = self.query_one("#phase-content", Vertical)
        container.remove_children()

        phase_widget = self._build_phase_widget()
        container.mount(phase_widget)

    def _build_phase_widget(self) -> Vertical:
        if self.state.phase == WizardPhase.IDENTITY:
            return _IdentityPhase()
        if self.state.phase == WizardPhase.SECTIONS:
            return _SectionsPhase(self.state.selected_section_keys)
        if self.state.phase == WizardPhase.SOURCES:
            return _SourcesPhase(self.state)
        return _ReviewPhase(self.state)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id

        if button_id == "btn-continue":
            self._handle_continue()
        elif button_id == "btn-back":
            self.state.go_back()
            self._refresh_phase()
        elif button_id == "btn-confirm":
            self._sync_sections_state()
            self.api_key = self.query_one("#input-api-key", Input).value.strip()
            self.result_schema = self.state.to_schema_dict()
            self.exit()

    def _handle_continue(self) -> None:
        if self.state.phase == WizardPhase.IDENTITY:
            if not self._harvest_identity():
                return
        elif self.state.phase == WizardPhase.SECTIONS:
            self._sync_sections_state()

        self.state.advance()
        self._refresh_phase()

    def _harvest_identity(self) -> bool:
        company = self.query_one("#input-company", Input).value.strip()
        if not company:
            self.notify("Company name is required", severity="error")
            return False

        products_raw = self.query_one("#input-products", Input).value
        products = [p.strip() for p in products_raw.split(",") if p.strip()]
        if not products:
            products = [""]

        domain = self.query_one("#input-domain", Input).value.strip()
        if not domain:
            domain = "General"

        ctx_list = self.query_one("#ctx-selection", SelectionList)
        selected_indices = list(ctx_list.selected)
        contexts_enum = list(DecisionContext)
        selected_contexts = [contexts_enum[idx] for idx in selected_indices if idx < len(contexts_enum)]
        if not selected_contexts:
            selected_contexts = [DecisionContext.GENERAL]

        own_product = self.query_one("#cb-own-product", Checkbox).value

        self.state.set_identity(
            company_name=company,
            products=products,
            domain=domain,
            decision_contexts=selected_contexts,
            own_product=own_product,
        )
        return True

    def _sync_sections_state(self) -> None:
        try:
            section_list = self.query_one("#section-selection", SelectionList)
        except Exception:
            return

        selected_keys = set(section_list.selected)
        all_keys = {s["key"] for s in DefaultSections.ALL}

        for key in all_keys:
            in_selected = key in selected_keys
            in_state = key in self.state.selected_section_keys
            if in_selected != in_state:
                self.state.toggle_section(key)

    def action_go_back(self) -> None:
        if self.state.phase == WizardPhase.IDENTITY:
            self.exit()
        else:
            self.state.go_back()
            self._refresh_phase()
