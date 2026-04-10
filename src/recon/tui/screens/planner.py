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
        "Add to the workspace and research from scratch",
    ),
    Operation.UPDATE_SPECIFIC: (
        "Update specific competitors",
        "Re-research selected profiles in full",
    ),
    Operation.UPDATE_ALL: (
        "Update all competitors",
        "Re-research every profile in full",
    ),
    Operation.DIFF_SPECIFIC: (
        "Diff update -- specific",
        "Check what changed externally, update stale sections for selected profiles",
    ),
    Operation.DIFF_ALL: (
        "Diff update -- all",
        "Check what changed externally, update stale sections across the full workspace",
    ),
    Operation.RERUN_FAILED: (
        "Re-run failed / disputed",
        "Retry anything that errored or failed verification",
    ),
    Operation.FULL_PIPELINE: (
        "Full pipeline",
        "End-to-end: research, verify, enrich, synthesize",
    ),
}


_OPERATION_BY_NUMBER = {str(i + 1): op for i, op in enumerate(Operation)}


class RunPlannerScreen(ModalScreen[Operation | None]):
    """7-option run planner with cost estimate."""

    BINDINGS = [
        Binding(str(i + 1), f"select_{i + 1}", f"Option {i + 1}", show=False)
        for i in range(7)
    ]

    DEFAULT_CSS = """
    RunPlannerScreen {
        align: center middle;
    }
    #planner-container {
        width: 70;
        height: auto;
        max-height: 90%;
        padding: 1 2;
        border: solid #3a3a3a;
        background: #0d0d0d;
        overflow-y: auto;
    }
    .operation-button {
        width: 100%;
        height: auto;
        margin: 0 0 1 0;
    }
    .action-bar {
        height: auto;
        margin: 1 0;
        layout: horizontal;
    }
    .action-bar Button {
        margin: 0 1 0 0;
    }
    """

    def __init__(self, competitor_count: int, section_count: int) -> None:
        super().__init__()
        self._competitor_count = competitor_count
        self._section_count = section_count
        self._selected: Operation | None = None

    @property
    def selected(self) -> Operation | None:
        return self._selected

    def select_operation(self, operation: Operation) -> None:
        self._selected = operation

    def compose(self) -> ComposeResult:
        with Vertical(id="planner-container"):
            yield Static("[bold #e0a044]RUN PLANNER[/]", id="planner-title")
            yield Static(
                f"[#a89984]Workspace: {self._competitor_count} competitors, "
                f"{self._section_count} sections[/]",
                id="planner-stats",
            )
            yield Static("")
            yield Static("[#efe5c0]What do you want to do?[/]")
            yield Static("")

            operations = list(Operation)
            for i, op in enumerate(operations):
                label, description = _OPERATION_LABELS[op]
                yield Button(
                    f"[{i + 1}]  {label}  —  {description}",
                    id=f"btn-op-{i}",
                    classes="operation-button",
                )

            yield Static("")
            with Horizontal(classes="action-bar"):
                yield Button("Back", id="btn-back")

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

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
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
