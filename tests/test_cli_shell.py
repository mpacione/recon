"""Tests for the ``recon cli`` persistent shell.

The prompt_toolkit session needs a real TTY and is not worth mocking;
these tests exercise the stateless helpers directly instead
(``_inject_workspace``, ``_maybe_handle_special``, ``_dispatch_click``).
Together they cover the REPL's behavior without spinning the event
loop.
"""

from __future__ import annotations

from pathlib import Path

import click
import pytest
from click.testing import CliRunner

from recon.cli_ui.shell import (
    _BREAK,
    _HANDLED,
    _ChangeWorkspace,
    _collect_command_names,
    _dispatch_click,
    _inject_workspace,
    _maybe_handle_special,
)


# ---------------------------------------------------------------------
# _inject_workspace
# ---------------------------------------------------------------------


class TestInjectWorkspace:
    def test_no_workspace_leaves_tokens_untouched(self) -> None:
        assert _inject_workspace(["plan"], None) == ["plan"]

    def test_adds_workspace_after_subcommand(self, tmp_path: Path) -> None:
        result = _inject_workspace(["plan"], tmp_path)
        assert result == ["plan", "--workspace", str(tmp_path)]

    def test_preserves_user_supplied_workspace(self, tmp_path: Path) -> None:
        tokens = ["plan", "--workspace", "/other/path", "--n", "3"]
        result = _inject_workspace(tokens, tmp_path)
        # User's --workspace wins; we don't duplicate.
        assert result == tokens

    def test_flag_goes_after_subcommand(self, tmp_path: Path) -> None:
        result = _inject_workspace(["plan", "--n", "3"], tmp_path)
        # --workspace injected between subcommand and its own args.
        assert result == [
            "plan",
            "--workspace",
            str(tmp_path),
            "--n",
            "3",
        ]


# ---------------------------------------------------------------------
# _maybe_handle_special
# ---------------------------------------------------------------------


class TestMaybeHandleSpecial:
    def _console(self):
        from rich.console import Console

        return Console(record=True, width=80)

    def test_exit_returns_break(self) -> None:
        assert _maybe_handle_special(["exit"], self._console(), None) is _BREAK

    def test_quit_returns_break(self) -> None:
        assert _maybe_handle_special(["quit"], self._console(), None) is _BREAK

    def test_q_returns_break(self) -> None:
        assert _maybe_handle_special(["q"], self._console(), None) is _BREAK

    def test_vim_style_q_returns_break(self) -> None:
        assert _maybe_handle_special([":q"], self._console(), None) is _BREAK

    def test_help_consumes_and_prints(self) -> None:
        console = self._console()
        result = _maybe_handle_special(["help"], console, None)
        assert result is _HANDLED
        # The help text must include at least one real command name
        # so a user can discover the vocabulary.
        assert "plan" in console.export_text()

    def test_clear_is_handled(self) -> None:
        assert _maybe_handle_special(["clear"], self._console(), None) is _HANDLED

    def test_cd_requires_argument(self) -> None:
        console = self._console()
        result = _maybe_handle_special(["cd"], console, None)
        assert result is _HANDLED
        assert "usage: cd" in console.export_text()

    def test_cd_to_missing_path_errors(self, tmp_path: Path) -> None:
        console = self._console()
        bad = tmp_path / "does-not-exist"
        result = _maybe_handle_special(["cd", str(bad)], console, None)
        assert result is _HANDLED
        assert "not a directory" in console.export_text()

    def test_cd_to_existing_dir_changes_workspace(self, tmp_path: Path) -> None:
        result = _maybe_handle_special(["cd", str(tmp_path)], self._console(), None)
        assert isinstance(result, _ChangeWorkspace)
        assert result.new == tmp_path.resolve()

    def test_unknown_command_passes_through(self) -> None:
        assert _maybe_handle_special(["plan"], self._console(), None) is None


# ---------------------------------------------------------------------
# _collect_command_names
# ---------------------------------------------------------------------


class TestCollectCommandNames:
    def test_returns_non_hidden_subcommands(self) -> None:
        from recon.cli import main

        names = _collect_command_names(main)
        # Sanity: the main v4 tab commands are all non-hidden.
        assert "plan" in names
        assert "schema" in names
        assert "comps" in names
        assert "agents" in names
        assert "output" in names
        # Our new `cli` command must also be in the vocabulary.
        assert "cli" in names

    def test_excludes_hidden_commands(self) -> None:
        from recon.cli import main

        names = _collect_command_names(main)
        # Click commands marked hidden=True shouldn't appear in
        # the REPL's auto-complete list.
        ctx = click.Context(main)
        hidden = [
            n for n in main.list_commands(ctx)
            if main.get_command(ctx, n).hidden
        ]
        for h in hidden:
            assert h not in names


# ---------------------------------------------------------------------
# _dispatch_click — integration with the real CLI group
# ---------------------------------------------------------------------


class TestDispatchClick:
    """The dispatch function must swallow ``click.UsageError`` and
    ``click.ClickException`` so the REPL survives.
    """

    def _console(self):
        from rich.console import Console

        return Console(record=True, width=80)

    def test_unknown_command_surfaces_error_without_raising(self) -> None:
        from recon.cli import main

        console = self._console()
        # Should not raise.
        _dispatch_click(main, ["definitely-not-a-command"], console)
        # Click emits something useful — "No such command" or similar.
        text = console.export_text().lower()
        assert "command" in text or "usage" in text

    def test_help_path_does_not_crash_repl(self) -> None:
        from recon.cli import main

        console = self._console()
        # `--help` used to tear down the shell via SystemExit; the
        # dispatcher has to swallow it.
        _dispatch_click(main, ["plan", "--help"], console)

    def test_command_crash_is_contained(self, monkeypatch) -> None:
        """If an unexpected exception leaks out of a command, the
        dispatcher must log + print the error and return normally so
        the REPL loop keeps going.
        """

        @click.group()
        def group() -> None:
            pass

        @group.command()
        def boom() -> None:
            raise RuntimeError("boom!")

        console = self._console()
        _dispatch_click(group, ["boom"], console)
        assert "crashed" in console.export_text().lower()


# ---------------------------------------------------------------------
# End-to-end smoke: the `cli` Click command registers and prints help
# ---------------------------------------------------------------------


class TestCliCommandRegistration:
    def test_cli_alias_launches_tui(self) -> None:
        """``recon cli`` is a shorthand for ``recon tui`` — the
        full-screen interactive TUI. The help text must name the TUI
        explicitly so users who remember "CLI" still find it.
        """
        from recon.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["cli", "--help"])
        assert result.exit_code == 0
        assert "tui" in result.output.lower()
        assert "--workspace" in result.output

    def test_repl_help_mentions_interactive_shell(self) -> None:
        """The typed REPL moved to ``recon repl`` — verify it's still
        registered and that its help text explains the tradeoff.
        """
        from recon.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["repl", "--help"])
        assert result.exit_code == 0
        assert "repl" in result.output.lower() or "prompt" in result.output.lower()
        assert "--workspace" in result.output
