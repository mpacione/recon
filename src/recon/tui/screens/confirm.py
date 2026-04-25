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
from recon.tui.widgets import RadioItem, button_label

_log = get_logger(__name__)


@dataclass
class ConfirmResult:
    model_name: str
    workers: int


class ConfirmScreen(ReconScreen):
    """Full-screen cost confirmation — v4 PLAN tab."""

    tab_key = "plan"
    flow_step = 3

    BINDINGS = [
        # Model nav — j/k walk the radio options.
        Binding("j", "cursor_down", "down", show=False),
        Binding("k", "cursor_up", "up", show=False),
        Binding("down", "cursor_down", "down", show=False),
        Binding("up", "cursor_up", "up", show=False),
        # Worker stepper — +/- match the web PLAN tab's controls.
        Binding("plus", "more_workers", "more workers", show=False),
        Binding("equals_sign", "more_workers", "more workers", show=False),
        Binding("minus", "fewer_workers", "fewer workers", show=False),
        # Flow — `n` advances, `esc` goes back.
        Binding("n", "submit", "run", show=False),
        Binding("escape", "cancel", "Back", show=False),
    ]

    keybind_hints = (
        "[#DDEDC4]↑↓[/] model · [#DDEDC4]+/-[/] workers · "
        "[#DDEDC4]n[/] run · [#DDEDC4]esc[/] back"
    )

    DEFAULT_CSS = """
    ConfirmScreen {
        background: #000000;
    }
    #confirm-container {
        width: 100%;
        height: auto;
        padding: 1 2;
    }
    #confirm-actions {
        dock: bottom;
        height: 3;
        padding: 0 2;
        layout: horizontal;
        background: #000000;
    }
    #confirm-actions Button {
        margin: 0 1 0 0;
    }
    #workers-row {
        height: 1;
        width: 100%;
    }
    """

    show_log_pane = False
    show_activity_feed = False
    show_run_status_bar = False

    def __init__(
        self,
        competitor_count: int,
        section_count: int,
        section_names: list[str] | None = None,
        initial_model: str = "sonnet",
        initial_workers: int = 5,
    ) -> None:
        super().__init__()
        self._competitor_count = competitor_count
        self._section_count = section_count
        self._section_names = section_names or []
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
        from recon.tui.primitives import Card

        with Vertical(id="confirm-container"):
            # Research brief card (top) — matches the web PLAN tab's
            # "RESEARCH BRIEF" section.
            brief_meta = f"{self._competitor_count} comp's · {self._section_count} sections"
            with Card(title="RESEARCH BRIEF", meta=brief_meta, id="brief-card"):
                yield Static(self._render_cost_breakdown(), id="cost-breakdown")

            # AI models card (middle) — matches the web PLAN tab's
            # "AI MODELS" section with the estimated-total meta.
            pricing = get_model_pricing(self._current_model_name)
            total = estimate_full_run(
                pricing=pricing,
                section_count=self._section_count,
                competitor_count=self._competitor_count,
            )
            models_meta = f"EST COST · base ${total:.2f}"
            with Card(title="AI MODELS", meta=models_meta, id="models-card"):
                for i, model in enumerate(self._models):
                    yield RadioItem(
                        label=self._model_label(i),
                        selected=(i == self._selected_model),
                        index=i,
                    )
                yield Static("")
                # Workers — single-line stat + shaded bar visual,
                # matching the web PLAN tab's ``▓▓▓▓▓░░░░░ 5 parallel``
                # indicator. `+` / `-` keys drive the value (see
                # action_more_workers / action_fewer_workers).
                yield Static(self._render_workers_row(), id="workers-row")

        with Horizontal(id="confirm-actions"):
            yield Button(
                button_label("RUN", "N"),
                id="btn-start",
                variant="primary",
            )
            yield Button(button_label("BACK", "Esc"), id="btn-back")

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

        # Estimated wall-clock time: ~15s per section call + ~10s per enrich pass
        est_seconds = section_calls * 15 + self._competitor_count * 3 * 10 + 60
        est_minutes = max(1, est_seconds // 60)

        section_list = ""
        if self._section_names:
            names = ", ".join(self._section_names)
            section_list = f"\n  [#a59a86]Sections:[/]  [#DDEDC4]{names}[/]\n"

        return (
            f"[bold #DDEDC4]── READY TO RESEARCH ──[/]\n\n"
            f"[#DDEDC4]This will research {self._competitor_count} competitors "
            f"across {self._section_count} sections each.[/]"
            f"{section_list}\n"
            f"  [#a59a86]Research:[/]     [#DDEDC4]{section_calls} section calls[/]"
            f"          [#DDEDC4]~${research_cost:.2f}[/]\n"
            f"  [#a59a86]Enrichment:[/]   [#DDEDC4]{self._competitor_count} profiles x 3 passes[/]"
            f"    [#DDEDC4]~${enrich_cost:.2f}[/]\n"
            f"  [#a59a86]Themes:[/]       [#DDEDC4]5 themes[/]"
            f"                  [#DDEDC4]~${themes_cost:.2f}[/]\n"
            f"  [#a59a86]Summaries:[/]    [#DDEDC4]5 themes + 1 executive[/]"
            f"    [#DDEDC4]~${summary_cost:.2f}[/]\n"
            f"                                     {'─' * 14}\n"
            f"  [#DDEDC4]Estimated total:[/]"
            f"                    [bold #DDEDC4]~${total:.2f}[/]\n"
            f"  [#a59a86]Estimated time:[/]"
            f"                    [#DDEDC4]~{est_minutes} min[/]"
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

    def _render_workers_row(self) -> str:
        """Single-line ``WORKERS ▓▓▓▓▓░░░░░ 5 parallel`` display.

        Mirrors the web PLAN tab's visual. Keyboard ``+/-`` drive the
        count; no buttons (they kept stealing focus from the radio
        list and fought the Horizontal layout engine).
        """
        max_workers = 10
        bar_width = 10
        clamped = max(1, min(max_workers, self._workers))
        filled = max(0, min(bar_width, round(bar_width * clamped / max_workers)))
        bar = "▓" * filled + "░" * (bar_width - filled)
        return (
            "[#DDEDC4]WORKERS[/]   "
            f"[#DDEDC4]{bar}[/]   "
            f"[#DDEDC4]{self._workers}[/] "
            "[#787266]parallel   [/]"
            "[#787266](press [/][#DDEDC4]+[/][#787266] / [/][#DDEDC4]-[/][#787266] to change)[/]"
        )

    def on_radio_item_selected(self, event: RadioItem.Selected) -> None:
        self._selected_model = event.index
        for item in self.query(RadioItem):
            item.set_selected(item._index == event.index)
        self._refresh_cost()

    # -- keyboard ---------------------------------------------------------

    def action_cursor_down(self) -> None:
        if not self._models:
            return
        self._selected_model = (self._selected_model + 1) % len(self._models)
        self._apply_model_selection()

    def action_cursor_up(self) -> None:
        if not self._models:
            return
        self._selected_model = (self._selected_model - 1) % len(self._models)
        self._apply_model_selection()

    def _apply_model_selection(self) -> None:
        """Sync the visible RadioItems to the in-memory selection."""
        for item in self.query(RadioItem):
            item.set_selected(item._index == self._selected_model)
        self._refresh_cost()

    def action_more_workers(self) -> None:
        self._workers = min(20, self._workers + 1)
        self._refresh_workers()

    def action_fewer_workers(self) -> None:
        self._workers = max(1, self._workers - 1)
        self._refresh_workers()

    def _refresh_workers(self) -> None:
        try:
            self.query_one("#workers-row", Static).update(self._render_workers_row())
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
