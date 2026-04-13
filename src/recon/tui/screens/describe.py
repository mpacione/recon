"""DescribeScreen for recon TUI (Screen 2).

Single freeform description field + API key status. Replaces the
4-step wizard. The user describes their company or space in 1-2
sentences and the system parses out structured fields.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Static, TextArea

from recon.api_keys import load_api_keys, mask_api_key, save_api_key
from recon.logging import get_logger

_log = get_logger(__name__)


@dataclass
class DescribeResult:
    output_dir: Path
    description: str
    api_keys: dict[str, str]


class DescribeScreen(ModalScreen[DescribeResult]):
    """Single-screen project setup. Replaces the 4-step wizard."""

    BINDINGS = [
        Binding("escape", "cancel", "Back", show=False),
        Binding("enter", "submit", "Continue", show=False, priority=True),
    ]

    DEFAULT_CSS = """
    DescribeScreen {
        align: center middle;
    }
    #describe-container {
        width: 80;
        max-height: 30;
        background: #1d1d1d;
        border: round #3a3a3a;
        padding: 1 2;
    }
    #describe-area {
        height: 4;
        border: solid #3a3a3a;
        background: #000000;
    }
    #describe-area:focus {
        border: solid #e0a044;
    }
    .api-key-row {
        height: 1;
        margin: 0 0;
    }
    """

    def __init__(self, output_dir: Path) -> None:
        super().__init__()
        self._output_dir = output_dir

    def compose(self) -> ComposeResult:
        keys = load_api_keys(workspace_root=self._output_dir)

        anthropic_status = self._key_status("anthropic", keys)
        google_status = self._key_status("google_ai", keys)

        with Vertical(id="describe-container"):
            yield Static(
                "[bold #e0a044]── DESCRIBE YOUR SPACE ──[/]\n\n"
                "[#a89984]Describe your company, product, or the competitive space you want\n"
                "to research. A sentence or two is enough — we'll figure out the rest.[/]",
            )
            yield Static("")
            yield TextArea(id="describe-area")
            yield Static("")
            yield Static(
                "[bold #e0a044]── API KEYS ──[/] "
                "[#a89984]stored in .env (persists across sessions)[/]"
            )
            yield Static("")
            yield Static(
                f"  [#a89984]Anthropic[/]   {anthropic_status}",
                classes="api-key-row",
            )
            yield Static(
                f"  [#a89984]Google AI[/]   {google_status}",
                classes="api-key-row",
            )
            yield Static("")
            yield Static(
                "[#a89984]enter[/] [#e0a044]continue[/] · "
                "[#a89984]a[/] [#e0a044]edit API keys[/] · "
                "[#a89984]esc[/] [#e0a044]back[/]",
            )

    def _key_status(self, key_name: str, keys: dict[str, str]) -> str:
        value = keys.get(key_name)
        if value:
            masked = mask_api_key(value)
            return f"[#efe5c0]{masked}[/]  [#98971a]\\u2713  saved[/]"
        return "[#3a3a3a]·······························[/]  [#a89984]not set[/]"

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_submit(self) -> None:
        try:
            area = self.query_one("#describe-area", TextArea)
        except Exception:
            return

        description = area.text.strip()
        if not description:
            self.app.notify("Please describe your space first.", severity="warning")
            return

        keys = load_api_keys(workspace_root=self._output_dir)

        self.dismiss(
            DescribeResult(
                output_dir=self._output_dir,
                description=description,
                api_keys=keys,
            ),
        )
