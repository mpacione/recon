"""WizardScreen for recon TUI.

Guides workspace creation inside ReconApp as a pushable Screen.
Mirrors WizardApp logic but dismisses with a WizardResult instead
of exiting the application, so the user stays in the TUI from
start to finish.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path  # noqa: TCH003 -- used at runtime
from typing import Any

from textual.app import ComposeResult  # noqa: TCH002 -- used at runtime
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, SelectionList, Static

from recon.logging import get_logger
from recon.tui.widgets import button_label
from recon.wizard import DecisionContext, DefaultSections, WizardPhase, WizardState

_log = get_logger(__name__)

_PHASE_LABELS = {
    WizardPhase.IDENTITY: "Identity",
    WizardPhase.SECTIONS: "Sections",
    WizardPhase.SOURCES: "Sources",
    WizardPhase.REVIEW: "Review",
}

_PHASE_ORDER = list(_PHASE_LABELS.keys())


@dataclass
class WizardResult:
    output_dir: Path
    schema: dict[str, Any] | None
    api_key: str


class _IdentityPhase(Vertical):
    def compose(self) -> ComposeResult:
        ctx_items = [(ctx.value, idx) for idx, ctx in enumerate(DecisionContext)]

        yield Static("[#a59a86]Company name[/]", classes="wizard-label")
        yield Input(placeholder="e.g. Acme Corp", id="input-company")
        yield Static("[#a59a86]Products (comma-separated)[/]", classes="wizard-label")
        yield Input(placeholder="e.g. Acme CI, Acme Deploy", id="input-products")
        yield Static("[#a59a86]Domain description[/]", classes="wizard-label")
        yield Input(placeholder="e.g. CI/CD Tools", id="input-domain")
        yield Static("[#a59a86]Decision context (Space to toggle)[/]", classes="wizard-label")
        yield SelectionList(*ctx_items, id="ctx-selection")
        yield Checkbox("Research own products through the same lens", id="cb-own-product")
        with Horizontal(classes="button-row"):
            yield Button(button_label("CONTINUE"), id="btn-continue", variant="primary")


class _SectionsPhase(Vertical):
    def __init__(self, selected_keys: set[str]) -> None:
        super().__init__()
        self._selected_keys = selected_keys

    def compose(self) -> ComposeResult:
        items = [
            (f"{s['title']} -- {s['description']}", s["key"], s["key"] in self._selected_keys)
            for s in DefaultSections.ALL
        ]
        yield Static(f"[#a59a86]Select sections ({len(self._selected_keys)} recommended)[/]")
        yield SelectionList(*items, id="section-selection")
        with Horizontal(classes="button-row"):
            yield Button(button_label("BACK", "Esc"), id="btn-back")
            yield Button(button_label("CONTINUE"), id="btn-continue", variant="primary")


class _SourcesPhase(Vertical):
    def __init__(self, state: WizardState) -> None:
        super().__init__()
        self._state = state

    def compose(self) -> ComposeResult:
        yield Static("[#a59a86]Source preferences (defaults shown, accept to continue)[/]")
        yield Static("")
        for section in DefaultSections.ALL:
            key = section["key"]
            if key not in self._state.selected_section_keys:
                continue
            sources = self._state.get_source_preferences(key)
            primary = ", ".join(sources.get("primary", []))
            yield Static(f"[bold]{section['title']}[/]")
            yield Static(f"  [#a59a86]Primary:[/] {primary}")
            yield Static("")
        with Horizontal(classes="button-row"):
            yield Button(button_label("BACK", "Esc"), id="btn-back")
            yield Button(button_label("ACCEPT DEFAULTS"), id="btn-continue", variant="primary")


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

        yield Static("[bold #DDEDC4]Review your workspace configuration[/]")
        yield Static(f"[#a59a86]Domain:[/] {self._state.domain}")
        yield Static(f"[#a59a86]Company:[/] {self._state.company_name}")
        yield Static(f"[#a59a86]Products:[/] {', '.join(self._state.products)}")
        yield Static(
            f"[#a59a86]Own-product research:[/] {'Yes' if self._state.own_product else 'No'}"
        )
        yield Static("")
        yield Static(f"[#a59a86]Sections ({len(sections)}):[/]")
        yield Static(section_list)
        yield Static("")
        yield Static("[#a59a86]Anthropic API key (required for research)[/]")
        yield Input(placeholder="sk-ant-...", id="input-api-key", password=True)
        yield Static("")
        with Horizontal(classes="button-row"):
            yield Button(button_label("BACK", "Esc"), id="btn-back")
            yield Button(button_label("CREATE WORKSPACE"), id="btn-confirm", variant="primary")


class WizardScreen(ModalScreen[WizardResult]):
    """Workspace wizard as a pushable Screen. Dismisses with WizardResult."""

    BINDINGS = [
        Binding("escape", "go_back", "Back", show=False),
    ]

    DEFAULT_CSS = """
    WizardScreen {
        align: center middle;
    }
    #wizard-container {
        width: 90;
        height: auto;
        max-height: 90%;
        padding: 1 2;
        border: solid #3a3a3a;
        background: #000000;
        overflow-y: auto;
    }
    #phase-indicator {
        padding: 0 0 1 0;
    }
    .wizard-label {
        margin: 1 0 0 0;
    }
    .button-row {
        height: auto;
        margin: 1 0 0 0;
    }
    .button-row Button {
        margin: 0 1 0 0;
    }
    SelectionList {
        height: auto;
        max-height: 14;
        margin: 1 0;
    }
    """

    def __init__(self, output_dir: Path) -> None:
        super().__init__()
        self._output_dir = output_dir
        self.state = WizardState()
        self._api_key: str = ""

    def compose(self) -> ComposeResult:
        with Vertical(id="wizard-container"):
            yield Static(self._indicator_text(), id="phase-indicator")
            yield Vertical(id="phase-content")

    def on_mount(self) -> None:
        _log.info("WizardScreen mounted, phase=%s", self.state.phase)
        self._refresh_phase()

    def _indicator_text(self) -> str:
        idx = _PHASE_ORDER.index(self.state.phase) + 1
        label = _PHASE_LABELS[self.state.phase]
        # Render a 4-dot progress meter that highlights the current step
        dots = []
        for i in range(1, 5):
            if i < idx:
                dots.append("[#DDEDC4]●[/]")
            elif i == idx:
                dots.append("[#DDEDC4]●[/]")
            else:
                dots.append("[#3a3a3a]○[/]")
        meter = " ".join(dots)
        return f"[bold #DDEDC4]▒ WIZARD ▒ {label}[/]  {meter}  [#a59a86]step {idx}/4[/]"

    def _refresh_phase(self) -> None:
        try:
            self.query_one("#phase-indicator", Static).update(self._indicator_text())
        except Exception:
            return

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
        _log.debug("WizardScreen button pressed id=%s phase=%s", button_id, self.state.phase)

        if button_id == "btn-continue":
            self._handle_continue()
        elif button_id == "btn-back":
            self.state.go_back()
            self._refresh_phase()
        elif button_id == "btn-confirm":
            self._sync_sections_state()
            try:
                self._api_key = self.query_one("#input-api-key", Input).value.strip()
            except Exception:
                self._api_key = ""
            result = WizardResult(
                output_dir=self._output_dir,
                schema=self.state.to_schema_dict(),
                api_key=self._api_key,
            )
            self.dismiss(result)

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
            self.app.notify("Company name is required", severity="error")
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
        selected_contexts = [
            contexts_enum[idx] for idx in selected_indices if idx < len(contexts_enum)
        ]
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
            self.dismiss(
                WizardResult(output_dir=self._output_dir, schema=None, api_key="")
            )
        else:
            self.state.go_back()
            self._refresh_phase()
