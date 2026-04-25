"""RunPlannerScreen for recon TUI.

The 7-option menu from operations.md. Shows workspace stats, lets
the user pick an operation, shows cost estimate, and confirms.
"""

from __future__ import annotations

from enum import StrEnum

from textual.app import ComposeResult  # noqa: TCH002 -- used at runtime
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from recon.logging import get_logger
from recon.tui.widgets import button_label

_log = get_logger(__name__)


class Operation(StrEnum):
    ADD_NEW = "add_new"
    UPDATE_SPECIFIC = "update_specific"
    UPDATE_ALL = "update_all"
    DIFF_SPECIFIC = "diff_specific"
    DIFF_ALL = "diff_all"
    RERUN_FAILED = "rerun_failed"
    FULL_PIPELINE = "full_pipeline"


_OPERATION_LABELS: dict[Operation, tuple[str, str]] = {
    Operation.ADD_NEW: (
        "Add new competitors",
        "discover then research the new ones",
    ),
    Operation.UPDATE_SPECIFIC: (
        "Update specific",
        "re-research selected profiles in full",
    ),
    Operation.UPDATE_ALL: (
        "Update all",
        "re-research every profile in full",
    ),
    Operation.DIFF_SPECIFIC: (
        "Diff specific",
        "refresh stale sections for selected profiles",
    ),
    Operation.DIFF_ALL: (
        "Diff all",
        "refresh stale sections across the full workspace",
    ),
    Operation.RERUN_FAILED: (
        "Re-run failed",
        "retry sections marked failed",
    ),
    Operation.FULL_PIPELINE: (
        "Full pipeline",
        "research → verify → enrich → index → themes → synthesize → deliver",
    ),
}


_OPERATION_BY_NUMBER = {str(i + 1): op for i, op in enumerate(Operation)}


class RunPlannerScreen(ModalScreen[Operation | None]):
    """7-option run planner with cost estimate."""

    BINDINGS = [
        *(
            Binding(str(i + 1), f"select_{i + 1}", f"Option {i + 1}", show=False)
            for i in range(7)
        ),
        Binding("escape", "cancel", "Back", show=False),
    ]

    DEFAULT_CSS = """
    RunPlannerScreen {
        align: center middle;
    }
    #planner-container {
        width: 90;
        height: auto;
        max-height: 95%;
        padding: 1 2;
        border: solid #3a3a3a;
        background: #000000;
    }
    #planner-header {
        height: auto;
        margin: 0 0 1 0;
    }
    #planner-options {
        height: auto;
        margin: 0;
    }
    .operation-row {
        width: 100%;
        height: 3;
        margin: 0 0 0 0;
        padding: 0 1;
        border: none;
        background: transparent;
        color: #DDEDC4;
    }
    .operation-row:hover {
        background: #000000;
    }
    .action-bar {
        height: auto;
        margin: 1 0 0 0;
        layout: horizontal;
    }
    .action-bar Button {
        margin: 0 1 0 0;
    }
    #planner-hint {
        height: auto;
        margin: 1 0 0 0;
        color: #a59a86;
    }
    """

    def __init__(
        self,
        competitor_count: int,
        section_count: int,
        estimated_full_run_cost: float = 0.0,
    ) -> None:
        super().__init__()
        self._competitor_count = competitor_count
        self._section_count = section_count
        self._estimated_full_run_cost = estimated_full_run_cost
        self._selected: Operation | None = None

    @property
    def selected(self) -> Operation | None:
        return self._selected

    def select_operation(self, operation: Operation) -> None:
        self._selected = operation

    def compose(self) -> ComposeResult:
        with Vertical(id="planner-container"):
            with Vertical(id="planner-header"):
                yield Static("[bold #DDEDC4]── RUN PLANNER ──[/]", id="planner-title")
                yield Static(
                    f"[#a59a86]workspace: {self._competitor_count} competitors · "
                    f"{self._section_count} sections[/]",
                    id="planner-stats",
                )
                if self._estimated_full_run_cost > 0:
                    per_competitor = (
                        self._estimated_full_run_cost / self._competitor_count
                        if self._competitor_count
                        else 0.0
                    )
                    yield Static(
                        f"[#a59a86]est. full run: "
                        f"[#DDEDC4]${self._estimated_full_run_cost:.2f}[/]"
                        f"  (~${per_competitor:.2f} per competitor)[/]",
                        id="planner-cost",
                    )

            with Vertical(id="planner-options"):
                operations = list(Operation)
                for i, op in enumerate(operations):
                    label, description = _OPERATION_LABELS[op]
                    yield Button(
                        button_label(f"{label}  — {description}", str(i + 1)),
                        id=f"btn-op-{i}",
                        classes="operation-row",
                    )

            with Horizontal(classes="action-bar"):
                yield Button(button_label("BACK", "Esc"), id="btn-back")
            yield Static(
                "[#a59a86]press a number 1-7 or click an option to run[/]",
                id="planner-hint",
            )

    def _select_by_number(self, number: str) -> None:
        op = _OPERATION_BY_NUMBER.get(number)
        if op:
            self._selected = op
            self.dismiss(self._selected)

    def action_select_1(self) -> None:
        self._select_by_number("1")

    def action_select_2(self) -> None:
        self._select_by_number("2")

    def action_select_3(self) -> None:
        self._select_by_number("3")

    def action_select_4(self) -> None:
        self._select_by_number("4")

    def action_select_5(self) -> None:
        self._select_by_number("5")

    def action_select_6(self) -> None:
        self._select_by_number("6")

    def action_select_7(self) -> None:
        self._select_by_number("7")

    def action_cancel(self) -> None:
        """Dismiss the planner without a selection (Esc keybind)."""
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        _log.info("RunPlannerScreen button pressed id=%s", button_id)
        if button_id.startswith("btn-op-"):
            try:
                index = int(button_id.removeprefix("btn-op-"))
            except ValueError:
                return
            operations = list(Operation)
            if 0 <= index < len(operations):
                self._selected = operations[index]
                self.dismiss(self._selected)
        elif button_id == "btn-back":
            self.dismiss(None)
