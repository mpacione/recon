"""Cost Confirmation screen for recon TUI (Screen 6).

Shows itemized cost breakdown, model selection, worker count.
Explicit "are you sure" gate before spending money.
"""

from __future__ import annotations

from dataclasses import dataclass

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Static

from recon.cost import estimate_full_run, get_model_pricing, list_available_models
from recon.logging import get_logger
from recon.tui.shell import ReconScreen
from recon.tui.widgets import RadioItem

_log = get_logger(__name__)


@dataclass
class ConfirmResult:
    model_name: str
    workers: int


class ConfirmScreen(ReconScreen):
    """Full-screen cost confirmation with model choice and worker count."""

    BINDINGS = [
        Binding("escape", "cancel", "Back", show=False),
    ]

    keybind_hints = "[#e0a044]esc[/] back"

    DEFAULT_CSS = """
    ConfirmScreen {
        background: #000000;
    }
    #confirm-container {
        width: 100%;
        height: auto;
        padding: 1 2;
    }
    .model-btn {
        height: 3;
        width: 100%;
        background: transparent;
        color: #a89984;
        border: none;
        text-align: left;
        padding: 0 1;
        min-width: 0;
    }
    .model-btn:hover {
        background: #1d1d1d;
        color: #efe5c0;
    }
    .model-btn:focus {
        background: #1d1d1d;
        color: #e0a044;
    }
    .confirm-actions {
        height: 3;
        margin: 1 0 0 0;
        layout: horizontal;
    }
    .confirm-actions Button {
        margin: 0 1 0 0;
    }
    .worker-row {
        height: 3;
        layout: horizontal;
    }
    .worker-row Button {
        min-width: 5;
        margin: 0 1 0 0;
    }
    """

    show_log_pane = False
    show_activity_feed = False
    show_run_status_bar = False

    def __init__(
        self,
        competitor_count: int,
        section_count: int,
        initial_model: str = "sonnet",
        initial_workers: int = 5,
    ) -> None:
        super().__init__()
        self._competitor_count = competitor_count
        self._section_count = section_count
        self._models = list_available_models()
        self._model_names = [m["name"] for m in self._models]
        self._selected_model = (
            self._model_names.index(initial_model)
            if initial_model in self._model_names
            else 0
        )
        self._workers = initial_workers

    @property
    def _current_model_name(self) -> str:
        return str(self._model_names[self._selected_model])

    def compose_body(self) -> ComposeResult:
        with Vertical(id="confirm-container"):
            yield Static(self._render_cost_breakdown(), id="cost-breakdown")
            yield Static("")
            yield Static("[bold #e0a044]── MODEL ──[/]")
            for i, model in enumerate(self._models):
                yield RadioItem(
                    label=self._model_label(i),
                    selected=(i == self._selected_model),
                    index=i,
                )
            yield Static("")
            yield Static("[bold #e0a044]── WORKERS ──[/]")
            with Horizontal(classes="worker-row"):
                yield Button("-", id="btn-fewer-workers")
                yield Static(
                    f"  [#e0a044]{self._workers}[/]  ",
                    id="worker-count",
                )
                yield Button("+", id="btn-more-workers")
            yield Static("")
            with Horizontal(classes="confirm-actions"):
                yield Button(
                    "Start Research",
                    id="btn-start",
                    variant="primary",
                )
                yield Button("Back", id="btn-back")

    def _render_cost_breakdown(self) -> str:
        pricing = get_model_pricing(self._current_model_name)
        total = estimate_full_run(
            pricing=pricing,
            section_count=self._section_count,
            competitor_count=self._competitor_count,
        )
        section_calls = self._section_count * self._competitor_count
        research_cost = pricing.calculate_cost(2000, 800) * section_calls
        enrich_cost = pricing.calculate_cost(2000, 800) * self._competitor_count * 3
        themes_cost = pricing.calculate_cost(3000, 1500) * 5
        summary_cost = pricing.calculate_cost(3000, 1500) * 6

        return (
            f"[bold #e0a044]── READY TO RESEARCH ──[/]\n\n"
            f"[#efe5c0]This will research {self._competitor_count} competitors "
            f"across {self._section_count} sections each.[/]\n\n"
            f"  [#a89984]Research:[/]     [#efe5c0]{section_calls} section calls[/]"
            f"          [#e0a044]~${research_cost:.2f}[/]\n"
            f"  [#a89984]Enrichment:[/]   [#efe5c0]{self._competitor_count} profiles x 3 passes[/]"
            f"    [#e0a044]~${enrich_cost:.2f}[/]\n"
            f"  [#a89984]Themes:[/]       [#efe5c0]5 themes[/]"
            f"                  [#e0a044]~${themes_cost:.2f}[/]\n"
            f"  [#a89984]Summaries:[/]    [#efe5c0]5 themes + 1 executive[/]"
            f"    [#e0a044]~${summary_cost:.2f}[/]\n"
            f"                                     {'─' * 14}\n"
            f"  [#efe5c0]Estimated total:[/]"
            f"                    [bold #e0a044]~${total:.2f}[/]"
        )

    def _model_label(self, index: int) -> str:
        model = self._models[index]
        name = str(model["name"]).capitalize()
        inp = model["input_price_per_million"]
        out = model["output_price_per_million"]
        model_total = estimate_full_run(
            pricing=get_model_pricing(str(model["name"])),
            section_count=self._section_count,
            competitor_count=self._competitor_count,
        )
        desc = str(model.get("description", ""))
        return f"{name:8s}  ${inp}/{out} per M tokens  ~${model_total:.2f}  {desc}"

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id == "btn-start":
            self.action_submit()
        elif button_id == "btn-back":
            self.action_cancel()
        elif button_id == "btn-fewer-workers":
            self._workers = max(1, self._workers - 1)
            self._refresh_workers()
        elif button_id == "btn-more-workers":
            self._workers = min(20, self._workers + 1)
            self._refresh_workers()

    def on_radio_item_selected(self, event: RadioItem.Selected) -> None:
        self._selected_model = event.index
        for item in self.query(RadioItem):
            item.set_selected(item._index == event.index)
        self._refresh_cost()

    def _refresh_workers(self) -> None:
        try:
            self.query_one("#worker-count", Static).update(
                f"  [#e0a044]{self._workers}[/]  "
            )
        except Exception:
            pass

    def _refresh_cost(self) -> None:
        try:
            self.query_one("#cost-breakdown", Static).update(
                self._render_cost_breakdown()
            )
        except Exception:
            pass

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_submit(self) -> None:
        self.dismiss(ConfirmResult(
            model_name=self._current_model_name,
            workers=self._workers,
        ))

