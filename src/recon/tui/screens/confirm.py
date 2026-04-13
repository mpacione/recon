"""Cost Confirmation screen for recon TUI (Screen 6).

Shows itemized cost breakdown, model selection, worker count.
Explicit "are you sure" gate before spending money.
"""

from __future__ import annotations

from dataclasses import dataclass

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static

from recon.cost import estimate_full_run, get_model_pricing, list_available_models
from recon.logging import get_logger

_log = get_logger(__name__)


@dataclass
class ConfirmResult:
    model_name: str
    workers: int


class ConfirmScreen(ModalScreen[ConfirmResult]):
    """Cost confirmation with model choice and worker count."""

    BINDINGS = [
        Binding("escape", "cancel", "Back", show=False),
        Binding("enter", "submit", "Start", show=False, priority=True),
        Binding("up", "prev_model", "Previous model", show=False),
        Binding("down", "next_model", "Next model", show=False),
        Binding("left", "fewer_workers", "Fewer workers", show=False),
        Binding("right", "more_workers", "More workers", show=False),
    ]

    DEFAULT_CSS = """
    ConfirmScreen {
        align: center middle;
    }
    #confirm-container {
        width: 75;
        max-height: 30;
        background: #1d1d1d;
        border: round #3a3a3a;
        padding: 1 2;
    }
    """

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

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-container"):
            yield Static(self._render_content(), id="confirm-body")

    def _render_content(self) -> str:
        model_name = self._current_model_name
        pricing = get_model_pricing(model_name)

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

        lines = [
            "[bold #e0a044]── READY TO RESEARCH ──[/]",
            "",
            f"[#efe5c0]This will research {self._competitor_count} competitors "
            f"across {self._section_count} sections each.[/]",
            "",
            f"  [#a89984]Research:[/]     [#efe5c0]{section_calls} section calls[/]"
            f"          [#e0a044]~${research_cost:.2f}[/]",
            f"  [#a89984]Enrichment:[/]   [#efe5c0]{self._competitor_count} profiles x 3 passes[/]"
            f"    [#e0a044]~${enrich_cost:.2f}[/]",
            f"  [#a89984]Themes:[/]       [#efe5c0]5 themes[/]"
            f"                  [#e0a044]~${themes_cost:.2f}[/]",
            f"  [#a89984]Summaries:[/]    [#efe5c0]5 themes + 1 executive[/]"
            f"    [#e0a044]~${summary_cost:.2f}[/]",
            f"                                     {'─' * 14}",
            f"  [#efe5c0]Estimated total:[/]"
            f"                    [bold #e0a044]~${total:.2f}[/]",
            "",
            "[bold #e0a044]── MODEL ──[/]",
            "",
        ]

        for i, model in enumerate(self._models):
            marker = "●" if i == self._selected_model else "○"
            name = str(model["name"]).capitalize()
            inp = model["input_price_per_million"]
            out = model["output_price_per_million"]
            model_total = estimate_full_run(
                pricing=get_model_pricing(str(model["name"])),
                section_count=self._section_count,
                competitor_count=self._competitor_count,
            )
            desc = str(model.get("description", ""))
            selected_color = "#efe5c0" if i == self._selected_model else "#a89984"
            lines.append(
                f"  [{selected_color}]{marker} {name:8s}  "
                f"${inp}/{out} per M tokens  "
                f"~${model_total:.2f}  {desc}[/]"
            )

        lines.extend([
            "",
            f"[#a89984]Workers:[/] [#e0a044][{self._workers}][/]  "
            f"[#3a3a3a]← → to adjust[/]",
            "",
            "[#a89984]enter[/] [#e0a044]start research[/] · "
            "[#a89984]esc[/] [#e0a044]go back[/]",
        ])

        return "\n".join(lines)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_submit(self) -> None:
        self.dismiss(ConfirmResult(
            model_name=self._current_model_name,
            workers=self._workers,
        ))

    def action_prev_model(self) -> None:
        self._selected_model = (self._selected_model - 1) % len(self._models)
        self._refresh()

    def action_next_model(self) -> None:
        self._selected_model = (self._selected_model + 1) % len(self._models)
        self._refresh()

    def action_fewer_workers(self) -> None:
        self._workers = max(1, self._workers - 1)
        self._refresh()

    def action_more_workers(self) -> None:
        self._workers = min(20, self._workers + 1)
        self._refresh()

    def _refresh(self) -> None:
        try:
            body = self.query_one("#confirm-body", Static)
            body.update(self._render_content())
        except Exception:
            pass
