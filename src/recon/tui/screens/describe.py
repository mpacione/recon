"""DescribeScreen for recon TUI (Screen 2).

Single freeform description field + API key management. Replaces the
4-step wizard. Uses buttons and tab navigation so keybinds don't
conflict with text input.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Input, Static, TextArea

from recon.api_keys import load_api_keys, mask_api_key, save_api_key
from recon.logging import get_logger
from recon.tui.shell import ReconScreen

_log = get_logger(__name__)


@dataclass
class DescribeResult:
    output_dir: Path
    description: str
    api_keys: dict[str, str]


class DescribeScreen(ReconScreen):
    """Full-screen project setup — v4 SCHEMA tab (shares key with Template).

    Replaces the 4-step wizard. Uses buttons + tab navigation. No
    single-letter keybinds since the screen has text input fields.
    """

    tab_key = "schema"

    BINDINGS = [
        Binding("escape", "cancel", "Back", show=False),
    ]

    show_log_pane = False
    show_activity_feed = False
    show_run_status_bar = False
    flow_step = 0

    keybind_hints = "[#DDEDC4]esc[/] back"

    DEFAULT_CSS = """
    DescribeScreen {
        background: #000000;
    }
    #describe-container {
        width: 100%;
        height: auto;
        padding: 1 2;
        overflow-y: auto;
    }
    #describe-area {
        height: 4;
        border: solid #3a3a3a;
        background: #000000;
    }
    #describe-area:focus {
        border: solid #DDEDC4;
    }
    .api-key-row {
        height: 1;
        margin: 0 0;
    }
    .api-key-input {
        height: 3;
        margin: 0 0;
    }
    .button-row {
        height: 3;
        margin: 1 0 0 0;
        layout: horizontal;
    }
    .button-row Button {
        margin: 0 1 0 0;
    }
    """

    def __init__(self, output_dir: Path) -> None:
        super().__init__()
        self._output_dir = output_dir
        self._editing_keys = False

    def compose_body(self) -> ComposeResult:
        keys = load_api_keys(workspace_root=self._output_dir)

        with Vertical(id="describe-container"):
            yield Static(
                "[bold #DDEDC4]── DESCRIBE YOUR SPACE ──[/]\n\n"
                "[#a59a86]Describe your company, product, or the competitive space you want\n"
                "to research. A sentence or two is enough — we'll figure out the rest.[/]",
            )
            yield Static("")
            yield TextArea(id="describe-area")
            yield Static("")
            yield Static(
                "[bold #DDEDC4]── API KEYS ──[/] "
                "[#a59a86]stored in .env (persists across sessions)[/]",
                id="api-keys-header",
            )
            yield Static("")

            # API key status (non-editing state)
            yield Static(
                self._render_key_status(keys),
                id="api-key-status",
            )

            # API key edit fields (hidden initially)
            yield Input(
                placeholder="Anthropic API key (sk-ant-...)",
                id="input-anthropic-key",
                password=True,
                classes="api-key-input",
            )
            yield Input(
                placeholder="Google AI API key (optional)",
                id="input-google-key",
                password=True,
                classes="api-key-input",
            )

            yield Static("")
            with Horizontal(classes="button-row"):
                yield Button("Continue", id="btn-continue", variant="primary")
                yield Button("Edit API Keys", id="btn-edit-keys")
                yield Button("Back", id="btn-back")

    def on_mount(self) -> None:
        # Hide key inputs initially, show status
        self._set_key_edit_mode(False)
        # Do NOT pre-fill password inputs — loading masked keys into
        # editable fields risks overwriting good keys with stale values.
        # The status display shows whether keys are saved.
        # When the user clicks Edit API Keys, they enter fresh values.

    def _render_key_status(self, keys: dict[str, str]) -> str:
        anthropic = self._key_line("Anthropic", keys.get("anthropic"))
        google = self._key_line("Google AI", keys.get("google_ai"))
        return f"{anthropic}\n{google}"

    def _key_line(self, label: str, value: str | None) -> str:
        if value:
            masked = mask_api_key(value)
            return f"  [#a59a86]{label:12s}[/] [#DDEDC4]{masked}[/]  [#DDEDC4]saved[/]"
        return f"  [#a59a86]{label:12s}[/] [#3a3a3a]{'·' * 25}[/]  [#a59a86]not set[/]"

    def _set_key_edit_mode(self, editing: bool) -> None:
        self._editing_keys = editing
        try:
            status = self.query_one("#api-key-status", Static)
            anthropic_input = self.query_one("#input-anthropic-key", Input)
            google_input = self.query_one("#input-google-key", Input)
            edit_btn = self.query_one("#btn-edit-keys", Button)

            status.display = not editing
            anthropic_input.display = editing
            google_input.display = editing
            edit_btn.label = "Save Keys" if editing else "Edit API Keys"
        except Exception:
            pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id == "btn-continue":
            self.action_submit()
        elif button_id == "btn-edit-keys":
            if self._editing_keys:
                self._save_keys()
                self._set_key_edit_mode(False)
            else:
                self._set_key_edit_mode(True)
                try:
                    self.query_one("#input-anthropic-key", Input).focus()
                except Exception:
                    pass
        elif button_id == "btn-back":
            self.action_cancel()

    def _save_keys(self) -> None:
        try:
            anthropic_val = self.query_one("#input-anthropic-key", Input).value.strip()
            google_val = self.query_one("#input-google-key", Input).value.strip()

            self._output_dir.mkdir(parents=True, exist_ok=True)

            if anthropic_val:
                save_api_key("anthropic", anthropic_val, workspace_root=self._output_dir)
            if google_val:
                save_api_key("google_ai", google_val, workspace_root=self._output_dir)

            # Refresh status display
            keys = load_api_keys(workspace_root=self._output_dir)
            self.query_one("#api-key-status", Static).update(
                self._render_key_status(keys)
            )
            self.app.notify("API keys saved", severity="information")
        except Exception as exc:
            _log.exception("failed to save API keys")
            self.app.notify(f"Failed to save keys: {exc}", severity="error")

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

        # Only save keys if user explicitly edited them via the button
        # Do NOT auto-save on Continue — prevents overwriting good keys
        # with stale pre-filled values
        if self._editing_keys:
            self._save_keys()

        # Load keys from disk (global + workspace), not from input fields
        keys = load_api_keys(workspace_root=self._output_dir)

        self.dismiss(
            DescribeResult(
                output_dir=self._output_dir,
                description=description,
                api_keys=keys,
            ),
        )
