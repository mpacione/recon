"""Persistent interactive shell for the recon CLI.

``recon cli`` drops the user into a prompt_toolkit REPL where they
can type the same subcommands they'd type at a zsh prompt, but in a
warm Python process. Benefits:

- No re-import cost per command (the slowest part of a cold one-shot).
- Command history across the session via ``~/.recon/cli_history``.
- Tab-completion over the full subcommand vocabulary.
- A prompt that mirrors the TUI header (``recon · <ws> ❯ ``).

Design notes:

- Every line the user types is parsed with :func:`shlex.split` and
  dispatched through Click's :meth:`main.main(standalone_mode=False)`
  just like a one-shot invocation. That keeps the two surfaces
  byte-identical — a command in the REPL behaves exactly like the
  same command at zsh.
- A loaded workspace is preserved across commands by auto-injecting
  ``--workspace <path>`` into every dispatch unless the user passed
  their own ``--workspace``.
- Special tokens that don't dispatch to Click: ``exit`` / ``quit`` /
  ``q`` (leave), ``help`` (command list), ``clear`` (wipe screen),
  ``cd <path>`` (change loaded workspace).
- ``Ctrl+C`` during a command aborts that command and re-prompts;
  ``Ctrl+C`` at an empty prompt is a no-op; ``Ctrl+D`` exits.
"""

from __future__ import annotations

import shlex
import sys
import traceback
from pathlib import Path
from typing import TYPE_CHECKING

import click
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style

from recon.logging import get_logger

if TYPE_CHECKING:
    from rich.console import Console

_log = get_logger(__name__)


# ---------------------------------------------------------------------
# Prompt styling — the subset of our palette prompt_toolkit can render
# ---------------------------------------------------------------------

_PROMPT_STYLE = Style.from_dict({
    "recon":  "#ede5c4 bold",     # the word "recon"
    "sep":    "#686359",          # dim separator dot
    "ws":     "#a59a86",          # workspace label
    "chevron":"#ffffff bold",     # the ❯ input boundary
})


def _format_prompt(workspace: Path | None) -> FormattedText:
    """Build the prompt line — ``recon ❯`` or ``recon · ws ❯``.

    Mirrors the TUI :class:`ReconHeaderBar` vocabulary so a user
    flipping between the two sees the same identity.
    """
    parts: list[tuple[str, str]] = [("class:recon", "recon")]
    if workspace is not None:
        parts.append(("class:sep", "  ·  "))
        parts.append(("class:ws", workspace.name))
    parts.append(("class:chevron", "  ❯  "))
    return FormattedText(parts)


# ---------------------------------------------------------------------
# Main entry
# ---------------------------------------------------------------------


def run_shell(
    workspace_path: str | None,
    *,
    main_group: click.Group | None = None,
    console: Console | None = None,
) -> None:
    """Enter the persistent recon REPL.

    ``main_group`` defaults to :data:`recon.cli.main` but is
    injectable for tests. ``console`` is the Rich console used for
    banners / error rendering; each dispatched command builds its own
    internal console via ``ctx.obj`` (the existing CLI contract).
    """
    from recon.cli_ui import build_console

    if main_group is None:
        from recon.cli import main as main_group

    if console is None:
        console = build_console()

    if not sys.stdin.isatty():
        console.print(
            "[error]recon cli needs a real terminal.[/error] "
            "[dim]Run it from an interactive shell; for one-shot commands "
            "just use `recon <subcommand>`.[/dim]",
        )
        sys.exit(1)

    workspace = _resolve_workspace(workspace_path)
    history_path = Path.home() / ".recon" / "cli_history"
    history_path.parent.mkdir(parents=True, exist_ok=True)

    command_names = _collect_command_names(main_group)
    completer = WordCompleter(
        command_names + ["exit", "quit", "help", "clear", "cd"],
        ignore_case=True,
    )

    key_bindings = KeyBindings()

    @key_bindings.add("c-l")
    def _clear(event):  # noqa: ANN001 -- prompt_toolkit signature
        event.app.renderer.clear()

    session: PromptSession = PromptSession(
        history=FileHistory(str(history_path)),
        completer=completer,
        style=_PROMPT_STYLE,
        key_bindings=key_bindings,
    )

    _print_banner(console, workspace)

    while True:
        try:
            line = session.prompt(_format_prompt(workspace))
        except KeyboardInterrupt:
            # Ctrl+C on an empty prompt — loop back, don't exit.
            continue
        except EOFError:
            # Ctrl+D — clean exit.
            console.print("[dim]goodbye.[/dim]")
            return

        stripped = line.strip()
        if not stripped:
            continue

        try:
            tokens = shlex.split(stripped)
        except ValueError as exc:
            console.print(f"[error]parse error:[/error] {exc}")
            continue

        # Special tokens — handled in-process, not via Click dispatch.
        action = _maybe_handle_special(tokens, console, workspace)
        if action is _BREAK:
            console.print("[dim]goodbye.[/dim]")
            return
        if isinstance(action, _ChangeWorkspace):
            workspace = action.new
            continue
        if action is _HANDLED:
            continue

        # Click dispatch — inject --workspace if absent, then run as if
        # the tokens had been typed at zsh.
        tokens = _inject_workspace(tokens, workspace)
        _dispatch_click(main_group, tokens, console)


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------


# Sentinel objects for the _maybe_handle_special return protocol.
_HANDLED = object()
_BREAK = object()


class _ChangeWorkspace:
    __slots__ = ("new",)

    def __init__(self, new: Path | None) -> None:
        self.new = new


def _maybe_handle_special(
    tokens: list[str],
    console: Console,
    workspace: Path | None,
) -> object:
    """Handle REPL-only commands that never reach Click.

    Returns one of: ``None`` (pass through to Click), :data:`_HANDLED`
    (consumed, re-prompt), :data:`_BREAK` (exit the loop), or a
    :class:`_ChangeWorkspace` instance (swap the loaded workspace).
    """
    head = tokens[0].lower()

    if head in {"exit", "quit", "q", ":q"}:
        return _BREAK

    if head == "help":
        _print_help(console)
        return _HANDLED

    if head == "clear":
        # `Ctrl+L` binding handles the fast path; `clear` typed out
        # does the equivalent via ANSI.
        console.clear()
        return _HANDLED

    if head == "cd":
        if len(tokens) != 2:
            console.print("[error]usage: cd <workspace-path>[/error]")
            return _HANDLED
        target = Path(tokens[1]).expanduser().resolve()
        if not target.exists() or not target.is_dir():
            console.print(f"[error]{target} is not a directory[/error]")
            return _HANDLED
        console.print(f"[dim]workspace → {target}[/dim]")
        return _ChangeWorkspace(target)

    return None


def _inject_workspace(tokens: list[str], workspace: Path | None) -> list[str]:
    """Auto-add ``--workspace <path>`` when the user didn't pass their own.

    Only applied to the child subcommand, so we insert after the
    subcommand name. Not all commands accept ``--workspace`` (e.g.
    ``init``, ``serve``, ``tui``) — Click will reject the extra option
    and the user can just retry. Keeping this naive is fine for v1.
    """
    if workspace is None:
        return tokens
    if "--workspace" in tokens:
        return tokens
    # Insert the flag AFTER the subcommand name so Click routes it to
    # the right parser. E.g. ``plan --n 3`` → ``plan --workspace <ws> --n 3``.
    head, *rest = tokens
    return [head, "--workspace", str(workspace), *rest]


def _dispatch_click(
    main_group: click.Group,
    tokens: list[str],
    console: Console,
) -> None:
    """Run ``tokens`` as if they had been typed at zsh.

    Uses ``standalone_mode=False`` so Click's ``SystemExit`` on
    help / bad args becomes a normal return path and doesn't tear
    down the REPL.
    """
    try:
        main_group.main(
            args=tokens,
            prog_name="recon",
            standalone_mode=False,
        )
    except click.UsageError as exc:
        console.print(f"[error]{exc.format_message()}[/error]")
    except click.ClickException as exc:
        console.print(f"[error]{exc.format_message()}[/error]")
    except SystemExit:
        # Click's ``--help`` path still calls sys.exit even in
        # standalone_mode=False under some versions. Swallow it.
        pass
    except KeyboardInterrupt:
        console.print("[dim]^C[/dim]")
    except Exception:  # noqa: BLE001 -- REPL must keep running
        _log.exception("shell dispatch crashed")
        console.print("[error]command crashed — see log for traceback[/error]")
        if _is_debug():
            traceback.print_exc(file=sys.stderr)


def _resolve_workspace(workspace_path: str | None) -> Path | None:
    if workspace_path is None:
        return None
    path = Path(workspace_path).expanduser().resolve()
    if not path.exists():
        return None
    return path


def _collect_command_names(group: click.Group) -> list[str]:
    # ``list_commands`` is the Click public API for enumerating
    # subcommands. Filter hidden ones — they aren't user-facing
    # vocabulary.
    ctx = click.Context(group)
    return [
        name
        for name in group.list_commands(ctx)
        if not group.get_command(ctx, name).hidden
    ]


def _print_banner(console: Console, workspace: Path | None) -> None:
    console.print()
    console.print("[accent]recon[/accent] [dim]·[/dim] [body]interactive shell[/body]")
    if workspace is not None:
        console.print(f"[dim]workspace:[/dim] [body]{workspace}[/body]")
    else:
        console.print(
            "[dim]no workspace loaded[/dim]  "
            "[muted]`cd <path>` to load one, or run `init <dir>` to create one[/muted]",
        )
    console.print(
        "[dim]type[/dim] [accent]help[/accent] [dim]for commands,[/dim] "
        "[accent]exit[/accent] [dim]or[/dim] [accent]^D[/accent] [dim]to leave[/dim]",
    )
    console.print()


def _print_help(console: Console) -> None:
    console.print()
    console.print("[accent]Shell commands[/accent]")
    console.print("  [body]exit[/body] | [body]quit[/body] | [body]^D[/body]    leave the shell")
    console.print("  [body]cd <path>[/body]              switch the loaded workspace")
    console.print("  [body]clear[/body] | [body]^L[/body]           clear the screen")
    console.print("  [body]help[/body]                   show this list")
    console.print()
    console.print("[accent]Recon commands[/accent] [dim](type `<cmd> --help` for details)[/dim]")
    console.print(
        "  [body]plan[/body] · [body]schema[/body] · [body]comps[/body] · "
        "[body]agents[/body] · [body]output[/body] · [body]status[/body]",
    )
    console.print(
        "  [body]discover[/body] · [body]research[/body] · [body]run[/body] · "
        "[body]synthesize[/body] · [body]distill[/body] · [body]summarize[/body]",
    )
    console.print(
        "  [body]init[/body] · [body]add[/body] · [body]index[/body] · "
        "[body]retrieve[/body] · [body]tag[/body] · [body]diff[/body] · [body]rerun[/body]",
    )
    console.print()


def _is_debug() -> bool:
    import os

    return os.environ.get("RECON_DEBUG", "").lower() in {"1", "true", "yes"}
