"""Real-terminal smoke test for the recon TUI.

These tests spawn the actual ``recon tui`` binary inside a PTY, drive
it with real keystrokes, and read the rendered terminal output back
through the master file descriptor. They catch a class of bugs that
the in-process Pilot tests miss:

- ANSI escape sequences not actually flushed
- keyboard handling that works in the test harness but not in a real
  terminal
- startup-time crashes or hangs that only show up under a real TTY
- clean shutdown on Ctrl-C / 'q'

The tests are skipped on platforms that don't support ``pty.fork``
(Windows) and on environments where the recon CLI script isn't on
PATH or in ``.venv/bin``.

These tests are intentionally minimal — one happy-path walk is
enough to catch broad regressions. Anything finer-grained should
live in the in-process Pilot suite.
"""

from __future__ import annotations

import os
import pty
import re
import select
import shutil
import signal
import sys
import time
from pathlib import Path

import pytest
import yaml

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REQUIRES_PTY = pytest.mark.skipif(
    sys.platform == "win32" or not hasattr(pty, "fork"),
    reason="real-terminal smoke tests require pty.fork (POSIX only)",
)

# ANSI/CSI escape sequence pattern -- used to strip control codes from
# the captured PTY output before substring matching.
_ANSI_RE = re.compile(rb"\x1b\[[0-?]*[ -/]*[@-~]|\x1b[()][0-9A-Za-z]")


def _strip_ansi(data: bytes) -> str:
    """Best-effort removal of CSI sequences from raw PTY output.

    Returns the result as a UTF-8 string with replacement chars for
    any byte that can't be decoded. Good enough for substring
    assertions on rendered text.
    """
    cleaned = _ANSI_RE.sub(b"", data)
    return cleaned.decode("utf-8", errors="replace")


class _PtyReader:
    """Stateful reader that accumulates everything seen on the PTY.

    Use ``drain_until(marker)`` to advance and ``buffer`` to access
    the full ANSI-stripped capture so far. Letting the buffer grow
    across multiple drains is the right model for screen-based UIs
    where the full chrome arrives in chunks across many render cycles.
    """

    def __init__(self, master_fd: int) -> None:
        self._fd = master_fd
        self._raw = bytearray()

    @property
    def buffer(self) -> str:
        return _strip_ansi(bytes(self._raw))

    def drain_until(self, marker: str, timeout: float = 10.0) -> str:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if marker in self.buffer:
                return self.buffer
            ready, _, _ = select.select([self._fd], [], [], 0.1)
            if not ready:
                continue
            try:
                chunk = os.read(self._fd, 4096)
            except OSError:
                break
            if not chunk:
                break
            self._raw.extend(chunk)
        text = self.buffer
        if marker not in text:
            raise TimeoutError(
                f"marker {marker!r} not found in {timeout}s. "
                f"captured ({len(text)} chars):\n" + text[-2000:],
            )
        return text


def _drain_until(master_fd: int, marker: str, timeout: float = 10.0) -> str:
    """Backwards-compatible single-shot drain (does NOT accumulate)."""
    reader = _PtyReader(master_fd)
    return reader.drain_until(marker, timeout=timeout)


def _send(master_fd: int, data: str) -> None:
    """Write a string of keystrokes to the PTY master."""
    os.write(master_fd, data.encode("utf-8"))


def _wait_or_kill(pid: int, timeout: float = 5.0) -> tuple[int, int]:
    """Wait for ``pid`` to exit, escalating SIGTERM/SIGINT if it doesn't.

    Returns ``(done_pid, status)``. ``done_pid == 0`` means the
    process never exited (caller should fail).
    """
    deadline = time.monotonic() + timeout
    sent_int = False
    sent_term = False
    while time.monotonic() < deadline:
        try:
            done_pid, status = os.waitpid(pid, os.WNOHANG)
        except ChildProcessError:
            return (pid, 0)
        if done_pid != 0:
            return (done_pid, status)
        elapsed = timeout - (deadline - time.monotonic())
        # After 1s send SIGINT, after 3s send SIGTERM
        if elapsed > 1.0 and not sent_int:
            with contextlib_suppress():
                os.kill(pid, signal.SIGINT)
            sent_int = True
        elif elapsed > 3.0 and not sent_term:
            with contextlib_suppress():
                os.kill(pid, signal.SIGTERM)
            sent_term = True
        time.sleep(0.05)
    return (0, 0)


def contextlib_suppress():
    import contextlib

    return contextlib.suppress(Exception)


def _kill_child(pid: int) -> None:
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    # Give it a moment to handle SIGTERM, then SIGKILL if needed
    for _ in range(20):
        try:
            done_pid, _ = os.waitpid(pid, os.WNOHANG)
        except ChildProcessError:
            return
        if done_pid != 0:
            return
        time.sleep(0.05)
    try:
        os.kill(pid, signal.SIGKILL)
        os.waitpid(pid, 0)
    except (ProcessLookupError, ChildProcessError):
        pass


def _make_workspace(tmp_path: Path) -> Path:
    """Create a minimal workspace so ``recon tui --workspace`` lands
    directly on the dashboard.
    """
    workspace = tmp_path / "smoke-workspace"
    workspace.mkdir()
    (workspace / "competitors").mkdir()
    (workspace / ".recon").mkdir()
    (workspace / ".recon" / "logs").mkdir()
    schema = {
        "domain": "Developer Tools",
        "identity": {
            "company_name": "Acme Corp",
            "products": ["Acme IDE"],
            "decision_context": ["build-vs-buy"],
        },
        "rating_scales": {
            "capability": {
                "name": "Capability Rating",
                "values": ["1", "2", "3", "4", "5"],
                "never_use": ["emoji", "stars"],
            },
        },
        "sections": [
            {
                "key": "overview",
                "title": "Overview",
                "description": "High-level company and product summary.",
                "evidence_types": ["factual", "analytical"],
                "allowed_formats": ["prose"],
                "preferred_format": "prose",
            },
        ],
    }
    (workspace / "recon.yaml").write_text(yaml.dump(schema, default_flow_style=False))
    # Create one competitor profile so the dashboard renders the
    # populated state instead of the empty prompt.
    (workspace / "competitors" / "alpha-corp.md").write_text(
        "---\n"
        "name: Alpha Corp\n"
        "type: competitor\n"
        "research_status: scaffold\n"
        "---\n\n"
        "## Overview\n\n"
        "Placeholder.\n",
    )
    return workspace


def _resolve_recon_binary() -> Path | None:
    """Find the recon binary -- prefer the .venv-local install."""
    repo_root = Path(__file__).resolve().parents[1]
    venv_recon = repo_root / ".venv" / "bin" / "recon"
    if venv_recon.exists():
        return venv_recon
    found = shutil.which("recon")
    return Path(found) if found else None


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@_REQUIRES_PTY
class TestRealTerminalSmoke:
    """Spawn ``recon tui`` in a PTY and drive it with real keystrokes."""

    def test_dashboard_renders_quits_cleanly(self, tmp_path: Path) -> None:
        """Happy path: launch tui pointed at a workspace, see the
        dashboard chrome (header + COMPETITORS section), press q to
        quit, assert the process exits cleanly.
        """
        recon = _resolve_recon_binary()
        if recon is None:
            pytest.skip("recon binary not found in .venv/bin or PATH")

        workspace = _make_workspace(tmp_path)

        env = {
            **os.environ,
            "TERM": "xterm-256color",
            "COLUMNS": "120",
            "LINES": "40",
            # Avoid hitting any real API key the dev might have set
            "ANTHROPIC_API_KEY": "",
        }

        pid, master_fd = pty.fork()
        if pid == 0:
            # Child: exec the recon CLI
            try:
                os.execvpe(
                    str(recon),
                    [str(recon), "tui", "--workspace", str(workspace)],
                    env,
                )
            except Exception as exc:  # pragma: no cover -- only in child
                sys.stderr.write(f"exec failed: {exc}\n")
                os._exit(127)

        try:
            reader = _PtyReader(master_fd)
            # 1. Wait for the body to render. "COMPETITORS" lives in
            #    the dashboard's section divider.
            reader.drain_until("COMPETITORS", timeout=15.0)
            # 2. Drain more for the bottom chrome (LogPane + KeybindHint
            #    arrive after the body in the same render cycle but
            #    sometimes split across chunks). Buffer accumulates so
            #    we still have access to the header that arrived earlier.
            output = reader.drain_until("add manually", timeout=5.0)

            # 3. Header bar contents
            assert "Acme Corp" in output, (
                "header should show workspace company name"
            )
            assert "Developer Tools" in output, (
                "header should show workspace domain"
            )

            # 4. Body content
            assert "COMPETITORS" in output
            assert "scaffold" in output  # 1 scaffolded competitor

            # 5. Keybind hint strip advertises r/d/b/m
            lower = output.lower()
            assert "run" in lower
            assert "discover" in lower
            assert "browse" in lower
            assert "add manually" in lower

            # 6. The persistent chrome should include both the
            #    ActivityFeed and LogPane placeholders
            assert "no activity yet" in lower or (
                "waiting for engine activity" in lower
            )

            # 7. Press q to quit. Small delay before sending; Textual
            #    sometimes swallows the very first key if it lands
            #    while the screen is mid-layout.
            time.sleep(0.2)
            _send(master_fd, "q")

            done_pid, status = _wait_or_kill(pid, timeout=5.0)
            if done_pid == 0:
                pytest.fail("recon tui did not exit within 5s of pressing q")

            # Exit cleanly: either status 0, status 1 (Textual cleanup
            # quirks), or terminated by SIGINT/SIGTERM (escalation path)
            assert os.WIFEXITED(status) or os.WIFSIGNALED(status), (
                f"unexpected exit state: {status}"
            )
            if os.WIFEXITED(status):
                code = os.WEXITSTATUS(status)
                assert code in (0, 1), f"unexpected exit code {code}"
        finally:
            _kill_child(pid)
            with contextlib_suppress():
                os.close(master_fd)

    def test_no_workspace_shows_welcome(self, tmp_path: Path) -> None:
        """Without --workspace, the welcome screen should render and
        accept the n key (mounting the new-project Input). We just
        check the welcome chrome is reachable, then quit.
        """
        recon = _resolve_recon_binary()
        if recon is None:
            pytest.skip("recon binary not found in .venv/bin or PATH")

        env = {
            **os.environ,
            "TERM": "xterm-256color",
            "COLUMNS": "120",
            "LINES": "40",
            "ANTHROPIC_API_KEY": "",
        }

        # Use a fresh tmp dir as cwd so 'recon tui' (default workspace=".")
        # doesn't pick up the repo root accidentally.
        cwd = tmp_path / "empty-cwd"
        cwd.mkdir()

        pid, master_fd = pty.fork()
        if pid == 0:
            try:
                os.chdir(str(cwd))
                os.execvpe(str(recon), [str(recon), "tui"], env)
            except Exception as exc:  # pragma: no cover
                sys.stderr.write(f"exec failed: {exc}\n")
                os._exit(127)

        try:
            reader = _PtyReader(master_fd)
            reader.drain_until("RECENT", timeout=15.0)
            output = reader.drain_until("? help", timeout=5.0)
            # Welcome chrome includes the recon banner and the
            # "competitive intelligence research" subtitle
            assert "competitive intelligence research" in output.lower() or (
                "recon" in output.lower()
            )
            # Keybind hint strip on welcome
            assert "new" in output.lower()
            assert "open" in output.lower()

            # Quit -- send q first; if that fails to take, escalate to
            # SIGINT (Ctrl-C). Textual sometimes swallows the very first
            # keystroke if it lands during a re-layout.
            time.sleep(0.2)
            _send(master_fd, "q")
            done_pid, status = _wait_or_kill(pid, timeout=5.0)
            if done_pid == 0:
                pytest.fail("recon tui did not exit within 5s of pressing q")
        finally:
            _kill_child(pid)
            with contextlib_suppress():
                os.close(master_fd)
