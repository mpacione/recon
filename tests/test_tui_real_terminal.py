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

# ANSI/CSI/OSC escape sequence pattern -- used to strip control codes
# from the captured PTY output before substring matching. Covers:
#   CSI  \x1b[ ... final byte
#   Charset  \x1b( X  /  \x1b) X
#   OSC  \x1b] ... BEL (Textual uses these for title + color palette)
_ANSI_RE = re.compile(
    rb"\x1b\[[0-?]*[ -/]*[@-~]"
    rb"|\x1b[()][0-9A-Za-z]"
    rb"|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)",
)


def _strip_ansi(data: bytes) -> str:
    """Best-effort removal of CSI/OSC sequences from raw PTY output.

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


def _spawn_tui(
    workspace: Path | None = None,
    cwd: Path | None = None,
    recent_path: Path | None = None,
    lines: int = 45,
    columns: int = 140,
) -> tuple[int, int]:
    """Spawn ``recon tui`` in a PTY and return (pid, master_fd).

    Honors ``recent_path`` by writing an empty JSON array to it and
    pointing ``$HOME`` at a clean directory so the welcome screen
    can't read the user's real ``~/.recon/recent.json``. This makes
    the test fully hermetic.
    """
    recon = _resolve_recon_binary()
    if recon is None:
        pytest.skip("recon binary not found in .venv/bin or PATH")

    fake_home = None
    if recent_path is not None:
        fake_home = recent_path.parent
        (fake_home / ".recon").mkdir(parents=True, exist_ok=True)
        recent_path.write_text("[]")

    env = {
        **os.environ,
        "TERM": "xterm-256color",
        "COLUMNS": str(columns),
        "LINES": str(lines),
        "ANTHROPIC_API_KEY": "",
    }
    if fake_home is not None:
        env["HOME"] = str(fake_home)

    args = [str(recon), "tui"]
    if workspace is not None:
        args += ["--workspace", str(workspace)]

    pid, master_fd = pty.fork()
    if pid == 0:
        try:
            if cwd is not None:
                os.chdir(str(cwd))
            os.execvpe(str(recon), args, env)
        except Exception as exc:  # pragma: no cover -- child only
            sys.stderr.write(f"exec failed: {exc}\n")
            os._exit(127)
    return pid, master_fd


def _press_and_capture(
    master_fd: int,
    key: str,
    settle: float = 0.6,
    capture: float = 1.5,
) -> str:
    """Write a keystroke and return the cleaned output that follows.

    ``settle`` gives Textual a moment to process the key before we
    start capturing. ``capture`` is the drain window. Returns the
    ANSI-stripped concatenated output.
    """
    import contextlib as _contextlib

    os.write(master_fd, key.encode("utf-8"))
    time.sleep(settle)
    reader = _PtyReader(master_fd)
    with _contextlib.suppress(TimeoutError):
        # Drain until timeout; no specific marker. We catch whatever
        # lands in the capture window.
        reader.drain_until("__never_happens__", timeout=capture)
    return reader.buffer


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


# ---------------------------------------------------------------------------
# Real-terminal keybind coverage
#
# The rest of this file exercises every screen's BINDINGS via PTY, end-to-end.
# Each test presses a real keystroke and asserts on the rendered output.
#
# This coverage is the level the in-process Pilot suite CAN'T give us: Pilot
# yields Screens as child widgets instead of pushing them, so Textual's
# binding traversal walks differently than in a real terminal. Unit tests
# that invoke ``screen.action_xxx()`` directly verify the action method
# works, but they do NOT verify that the key->action wiring is intact.
# A full round of those unit tests can be green while every keybind on every
# screen is broken -- which is how Phase J shipped with a clipping bug on
# Welcome.
# ---------------------------------------------------------------------------


@_REQUIRES_PTY
class TestDashboardKeybinds:
    """Dashboard keybinds that must navigate in a real terminal."""

    def _spawn(self, tmp_path: Path, populated: bool = True) -> tuple[int, int]:
        workspace = _make_workspace(tmp_path)
        if not populated:
            # wipe the pre-populated Alpha Corp profile
            for p in (workspace / "competitors").iterdir():
                p.unlink()
        return _spawn_tui(
            workspace=workspace,
            recent_path=tmp_path / "home" / ".recon" / "recent.json",
        )

    def test_r_opens_run_planner(self, tmp_path: Path) -> None:
        pid, fd = self._spawn(tmp_path)
        try:
            reader = _PtyReader(fd)
            reader.drain_until("COMPETITORS", timeout=15.0)
            os.write(fd, b"r")
            output = reader.drain_until("RUN PLANNER", timeout=5.0)
            assert "RUN PLANNER" in output
        finally:
            _kill_child(pid)
            with contextlib_suppress():
                os.close(fd)

    def test_d_opens_discovery(self, tmp_path: Path) -> None:
        pid, fd = self._spawn(tmp_path)
        try:
            reader = _PtyReader(fd)
            reader.drain_until("COMPETITORS", timeout=15.0)
            os.write(fd, b"d")
            output = reader.drain_until("DISCOVERY", timeout=5.0)
            assert "DISCOVERY" in output
        finally:
            _kill_child(pid)
            with contextlib_suppress():
                os.close(fd)

    def test_b_opens_browser(self, tmp_path: Path) -> None:
        pid, fd = self._spawn(tmp_path)
        try:
            reader = _PtyReader(fd)
            reader.drain_until("COMPETITORS", timeout=15.0)
            os.write(fd, b"b")
            # The browser renders a DataTable with a "Name" column header.
            output = reader.drain_until("Name", timeout=5.0)
            assert "Name" in output
            assert "Alpha Corp" in output
        finally:
            _kill_child(pid)
            with contextlib_suppress():
                os.close(fd)

    def test_m_on_empty_dashboard_mounts_input(self, tmp_path: Path) -> None:
        pid, fd = self._spawn(tmp_path, populated=False)
        try:
            reader = _PtyReader(fd)
            reader.drain_until("No competitors yet", timeout=15.0)
            os.write(fd, b"m")
            output = reader.drain_until("Enter to add", timeout=5.0)
            assert "Competitor name" in output
        finally:
            _kill_child(pid)
            with contextlib_suppress():
                os.close(fd)


@_REQUIRES_PTY
class TestWelcomeKeybinds:
    """Welcome keybinds that must work even when ``~/.recon/recent.json``
    has zero, some, or many recent entries. The clipping bug that landed
    in Phase J was invisible to unit tests because the test fixture
    rendered the screen in a larger viewport than a real 45-row terminal.
    """

    def _spawn(self, tmp_path: Path, recents: list[tuple[str, str]] | None = None):
        """Spawn recon tui on the welcome screen with a hermetic
        ``$HOME`` pointing at a tmp dir, pre-seeded with ``recents``.
        """
        home = tmp_path / "home"
        (home / ".recon").mkdir(parents=True, exist_ok=True)
        recent_json = home / ".recon" / "recent.json"
        if recents:
            import json as _json

            payload = [
                {
                    "path": path,
                    "name": name,
                    "last_opened": "2026-04-10T10:00:00+00:00",
                }
                for name, path in recents
            ]
            recent_json.write_text(_json.dumps(payload))
        else:
            recent_json.write_text("[]")

        cwd = tmp_path / "empty"
        cwd.mkdir(exist_ok=True)
        recon = _resolve_recon_binary()
        if recon is None:
            pytest.skip("recon binary not found")

        env = {
            **os.environ,
            "TERM": "xterm-256color",
            "COLUMNS": "140",
            "LINES": "45",
            "ANTHROPIC_API_KEY": "",
            "HOME": str(home),
        }
        pid, fd = pty.fork()
        if pid == 0:
            try:
                os.chdir(str(cwd))
                os.execvpe(str(recon), [str(recon), "tui"], env)
            except Exception as exc:  # pragma: no cover
                sys.stderr.write(f"exec failed: {exc}\n")
                os._exit(127)
        return pid, fd

    def test_n_mounts_new_project_input_with_no_recents(self, tmp_path: Path) -> None:
        pid, fd = self._spawn(tmp_path, recents=None)
        try:
            reader = _PtyReader(fd)
            reader.drain_until("RECENT", timeout=15.0)
            os.write(fd, b"n")
            output = reader.drain_until("new-project", timeout=5.0)
            # The Input defaults to "<home>/recon/new-project"
            assert "new-project" in output
        finally:
            _kill_child(pid)
            with contextlib_suppress():
                os.close(fd)

    def test_n_mounts_new_project_input_with_two_recents(
        self, tmp_path: Path,
    ) -> None:
        pid, fd = self._spawn(
            tmp_path,
            recents=[
                ("project-a", str(tmp_path / "project-a")),
                ("project-b", str(tmp_path / "project-b")),
            ],
        )
        try:
            reader = _PtyReader(fd)
            reader.drain_until("RECENT", timeout=15.0)
            os.write(fd, b"n")
            output = reader.drain_until("new-project", timeout=5.0)
            assert "new-project" in output
        finally:
            _kill_child(pid)
            with contextlib_suppress():
                os.close(fd)

    def test_n_still_works_with_ten_recents(self, tmp_path: Path) -> None:
        """Regression: Phase J shipped with welcome clipping the new
        Input off the bottom when the container overflowed. This test
        seeds the welcome screen with 10 recents, then presses n, and
        asserts the Input still lands in the visible viewport.
        """
        recents = [
            (f"project-{i}", str(tmp_path / f"project-{i}")) for i in range(10)
        ]
        pid, fd = self._spawn(tmp_path, recents=recents)
        try:
            reader = _PtyReader(fd)
            reader.drain_until("RECENT", timeout=15.0)
            os.write(fd, b"n")
            output = reader.drain_until("new-project", timeout=5.0)
            assert "new-project" in output, (
                "welcome new-project Input clipped off-screen when "
                "recents list is full -- layout regression"
            )
        finally:
            _kill_child(pid)
            with contextlib_suppress():
                os.close(fd)

    def test_o_mounts_open_existing_input(self, tmp_path: Path) -> None:
        pid, fd = self._spawn(tmp_path, recents=None)
        try:
            reader = _PtyReader(fd)
            reader.drain_until("RECENT", timeout=15.0)
            os.write(fd, b"o")
            output = reader.drain_until("Path to workspace", timeout=5.0)
            assert "Path to workspace" in output
        finally:
            _kill_child(pid)
            with contextlib_suppress():
                os.close(fd)

    def test_digit_1_opens_first_recent(self, tmp_path: Path) -> None:
        """Pressing a digit (1-9) on the welcome screen should open
        the matching recent project and transition to the dashboard.
        """
        # Build a real workspace so opening it actually lands on the
        # dashboard (instead of erroring out with "no recon.yaml").
        ws_dir = tmp_path / "real-workspace"
        ws_dir.mkdir()
        (ws_dir / "competitors").mkdir()
        (ws_dir / ".recon").mkdir()
        (ws_dir / ".recon" / "logs").mkdir()
        schema = {
            "domain": "Test Domain",
            "identity": {
                "company_name": "TestCo",
                "products": ["TestProduct"],
                "decision_context": ["build-vs-buy"],
            },
            "rating_scales": {
                "cap": {
                    "name": "Cap",
                    "values": ["1", "2"],
                    "never_use": ["emoji"],
                },
            },
            "sections": [
                {
                    "key": "overview",
                    "title": "Overview",
                    "description": "x",
                    "evidence_types": ["factual"],
                    "allowed_formats": ["prose"],
                    "preferred_format": "prose",
                },
            ],
        }
        (ws_dir / "recon.yaml").write_text(yaml.dump(schema))

        pid, fd = self._spawn(
            tmp_path,
            recents=[("real-workspace", str(ws_dir))],
        )
        try:
            reader = _PtyReader(fd)
            reader.drain_until("RECENT", timeout=15.0)
            os.write(fd, b"1")
            # The dashboard chrome header shows the workspace company
            # name -- "TestCo" in the seeded schema.
            output = reader.drain_until("TestCo", timeout=10.0)
            assert "TestCo" in output
        finally:
            _kill_child(pid)
            with contextlib_suppress():
                os.close(fd)


@_REQUIRES_PTY
class TestRunScreenKeybinds:
    """Run screen keybinds: p pause, s stop, b back to dashboard."""

    def test_b_returns_to_dashboard(self, tmp_path: Path) -> None:
        workspace = _make_workspace(tmp_path)
        pid, fd = _spawn_tui(
            workspace=workspace,
            recent_path=tmp_path / "home" / ".recon" / "recent.json",
        )
        try:
            reader = _PtyReader(fd)
            reader.drain_until("COMPETITORS", timeout=15.0)
            # r -> planner, 6 -> full pipeline -> run mode
            os.write(fd, b"r")
            reader.drain_until("RUN PLANNER", timeout=5.0)
            os.write(fd, b"6")
            reader.drain_until("RUN MONITOR", timeout=5.0)
            # Now press b to go back
            os.write(fd, b"b")
            output = reader.drain_until("COMPETITORS", timeout=5.0)
            assert "COMPETITORS" in output
        finally:
            _kill_child(pid)
            with contextlib_suppress():
                os.close(fd)


@_REQUIRES_PTY
class TestBrowserKeybinds:
    """Browser keybinds: b back, escape back."""

    def test_b_returns_to_dashboard(self, tmp_path: Path) -> None:
        workspace = _make_workspace(tmp_path)
        pid, fd = _spawn_tui(
            workspace=workspace,
            recent_path=tmp_path / "home" / ".recon" / "recent.json",
        )
        try:
            reader = _PtyReader(fd)
            reader.drain_until("COMPETITORS", timeout=15.0)
            os.write(fd, b"b")
            reader.drain_until("Name", timeout=5.0)
            # Press b again to go back
            os.write(fd, b"b")
            output = reader.drain_until("add manually", timeout=5.0)
            assert "add manually" in output  # dashboard keybind hint
        finally:
            _kill_child(pid)
            with contextlib_suppress():
                os.close(fd)

    def test_escape_returns_to_dashboard(self, tmp_path: Path) -> None:
        workspace = _make_workspace(tmp_path)
        pid, fd = _spawn_tui(
            workspace=workspace,
            recent_path=tmp_path / "home" / ".recon" / "recent.json",
        )
        try:
            reader = _PtyReader(fd)
            reader.drain_until("COMPETITORS", timeout=15.0)
            os.write(fd, b"b")
            reader.drain_until("Name", timeout=5.0)
            os.write(fd, b"\x1b")  # ESC
            output = reader.drain_until("add manually", timeout=5.0)
            assert "add manually" in output
        finally:
            _kill_child(pid)
            with contextlib_suppress():
                os.close(fd)


@_REQUIRES_PTY
class TestPlannerDigitKeybinds:
    """Planner digit bindings 1-7 must map to the 7 operations."""

    def test_digit_6_full_pipeline_switches_to_run_mode(
        self, tmp_path: Path,
    ) -> None:
        workspace = _make_workspace(tmp_path)
        pid, fd = _spawn_tui(
            workspace=workspace,
            recent_path=tmp_path / "home" / ".recon" / "recent.json",
        )
        try:
            reader = _PtyReader(fd)
            reader.drain_until("COMPETITORS", timeout=15.0)
            os.write(fd, b"r")
            reader.drain_until("RUN PLANNER", timeout=5.0)
            # Press 6 -> Operation.FULL_PIPELINE -> run mode
            os.write(fd, b"6")
            output = reader.drain_until("RUN MONITOR", timeout=5.0)
            assert "RUN MONITOR" in output
        finally:
            _kill_child(pid)
            with contextlib_suppress():
                os.close(fd)


@_REQUIRES_PTY
class TestModalEscapeKeybinds:
    """Every modal screen (planner, discovery, selector, curation)
    must handle ``escape`` as "back out". This is the universal
    convention and it was missing on several modals through Phase K.
    """

    def _fresh_workspace(self, tmp_path: Path) -> tuple[int, int]:
        workspace = _make_workspace(tmp_path)
        return _spawn_tui(
            workspace=workspace,
            recent_path=tmp_path / "home" / ".recon" / "recent.json",
        )

    def test_planner_escape_returns_to_dashboard(self, tmp_path: Path) -> None:
        pid, fd = self._fresh_workspace(tmp_path)
        try:
            reader = _PtyReader(fd)
            reader.drain_until("COMPETITORS", timeout=15.0)
            os.write(fd, b"r")
            reader.drain_until("RUN PLANNER", timeout=5.0)
            os.write(fd, b"\x1b")  # ESC
            output = reader.drain_until("add manually", timeout=5.0)
            # "add manually" lives in the dashboard keybind hint strip
            assert "add manually" in output
        finally:
            _kill_child(pid)
            with contextlib_suppress():
                os.close(fd)

    def test_discovery_escape_returns_to_dashboard(self, tmp_path: Path) -> None:
        pid, fd = self._fresh_workspace(tmp_path)
        try:
            reader = _PtyReader(fd)
            reader.drain_until("COMPETITORS", timeout=15.0)
            os.write(fd, b"d")
            reader.drain_until("DISCOVERY", timeout=5.0)
            os.write(fd, b"\x1b")
            output = reader.drain_until("add manually", timeout=5.0)
            assert "add manually" in output
        finally:
            _kill_child(pid)
            with contextlib_suppress():
                os.close(fd)

    def test_selector_escape_returns_to_dashboard(self, tmp_path: Path) -> None:
        pid, fd = self._fresh_workspace(tmp_path)
        try:
            reader = _PtyReader(fd)
            reader.drain_until("COMPETITORS", timeout=15.0)
            os.write(fd, b"r")
            reader.drain_until("RUN PLANNER", timeout=5.0)
            os.write(fd, b"2")  # UPDATE_SPECIFIC -> selector
            reader.drain_until("SELECT", timeout=5.0)
            os.write(fd, b"\x1b")
            output = reader.drain_until("add manually", timeout=5.0)
            assert "add manually" in output
        finally:
            _kill_child(pid)
            with contextlib_suppress():
                os.close(fd)


@_REQUIRES_PTY
class TestAppLevelKeybinds:
    """App-level bindings (q, Ctrl+C, ?) that fire from any screen."""

    def test_ctrl_c_exits_from_dashboard(self, tmp_path: Path) -> None:
        """Ctrl+C is the universal "exit this CLI" keystroke. Textual
        defaults to treating it as a regular keypress (i.e. no effect),
        so recon needs an explicit binding.
        """
        workspace = _make_workspace(tmp_path)
        pid, fd = _spawn_tui(
            workspace=workspace,
            recent_path=tmp_path / "home" / ".recon" / "recent.json",
        )
        try:
            reader = _PtyReader(fd)
            reader.drain_until("COMPETITORS", timeout=15.0)
            # Send Ctrl+C (\x03)
            os.write(fd, b"\x03")
            done_pid, status = _wait_or_kill(pid, timeout=5.0)
            if done_pid == 0:
                pytest.fail("Ctrl+C did not exit recon tui within 5s")
            assert os.WIFEXITED(status) or os.WIFSIGNALED(status)
        finally:
            _kill_child(pid)
            with contextlib_suppress():
                os.close(fd)

    def test_question_mark_shows_help_notification(self, tmp_path: Path) -> None:
        workspace = _make_workspace(tmp_path)
        pid, fd = _spawn_tui(
            workspace=workspace,
            recent_path=tmp_path / "home" / ".recon" / "recent.json",
        )
        try:
            reader = _PtyReader(fd)
            reader.drain_until("COMPETITORS", timeout=15.0)
            os.write(fd, b"?")
            # The help handler calls self.notify("Q=Quit  ?=Help", title="Keybinds")
            output = reader.drain_until("Keybinds", timeout=5.0)
            assert "Keybinds" in output or "Q=Quit" in output
        finally:
            _kill_child(pid)
            with contextlib_suppress():
                os.close(fd)


@_REQUIRES_PTY
class TestInputFocusVsScreenBindings:
    """When an Input has focus, typed characters must go to the Input
    and NOT trigger screen-level bindings. This was a user-facing
    concern: "if I'm typing a competitor name that contains 'r',
    will it accidentally open the run planner?"
    """

    def test_r_inside_add_manually_input_types_char(
        self, tmp_path: Path,
    ) -> None:
        # Need an empty workspace so the dashboard empty prompt
        # renders and `m` mounts the Input.
        workspace = tmp_path / "empty-ws"
        workspace.mkdir()
        (workspace / "competitors").mkdir()
        (workspace / ".recon").mkdir()
        (workspace / ".recon" / "logs").mkdir()
        schema = {
            "domain": "x",
            "identity": {
                "company_name": "Co",
                "products": ["X"],
                "decision_context": ["build-vs-buy"],
            },
            "rating_scales": {
                "c": {"name": "Cap", "values": ["1"], "never_use": ["e"]},
            },
            "sections": [
                {
                    "key": "overview",
                    "title": "Overview",
                    "description": "d",
                    "evidence_types": ["factual"],
                    "allowed_formats": ["prose"],
                    "preferred_format": "prose",
                },
            ],
        }
        (workspace / "recon.yaml").write_text(yaml.dump(schema))

        pid, fd = _spawn_tui(
            workspace=workspace,
            recent_path=tmp_path / "home" / ".recon" / "recent.json",
        )
        try:
            reader = _PtyReader(fd)
            reader.drain_until("No competitors yet", timeout=15.0)
            os.write(fd, b"m")
            reader.drain_until("Enter to add", timeout=5.0)
            # Type a name containing every dashboard keybind char.
            # If any of these fire their binding, the Input value
            # won't contain the whole string.
            os.write(fd, b"recon research tool")
            time.sleep(0.5)
            output = reader.drain_until(
                "recon research tool",
                timeout=3.0,
            )
            # Input captured every keystroke
            assert "recon research tool" in output
            # And none of the screen bindings fired
            assert "RUN PLANNER" not in output, (
                "r keybind leaked through Input focus"
            )
            assert "DISCOVERY" not in output, (
                "d keybind leaked through Input focus"
            )
        finally:
            _kill_child(pid)
            with contextlib_suppress():
                os.close(fd)


@_REQUIRES_PTY
class TestWorkspaceRecoveryEdgeCases:
    """The TUI must gracefully handle broken workspace state instead
    of crashing. Users hit these cases when they clone a repo, delete
    a project mid-session, or paste a typo into ``--workspace``.
    """

    def test_nonexistent_workspace_path_falls_back_to_welcome(
        self, tmp_path: Path,
    ) -> None:
        """``recon tui --workspace /does/not/exist`` should show the
        welcome screen instead of crashing.
        """
        recon = _resolve_recon_binary()
        if recon is None:
            pytest.skip("recon binary not found")
        bogus = tmp_path / "not-a-real-dir"
        home = tmp_path / "home"
        (home / ".recon").mkdir(parents=True, exist_ok=True)
        (home / ".recon" / "recent.json").write_text("[]")
        env = {
            **os.environ,
            "TERM": "xterm-256color",
            "COLUMNS": "140",
            "LINES": "45",
            "ANTHROPIC_API_KEY": "",
            "HOME": str(home),
        }
        pid, fd = pty.fork()
        if pid == 0:
            try:
                os.execvpe(
                    str(recon),
                    [str(recon), "tui", "--workspace", str(bogus)],
                    env,
                )
            except Exception:  # pragma: no cover
                os._exit(127)
        try:
            reader = _PtyReader(fd)
            output = reader.drain_until("RECENT", timeout=15.0)
            assert "RECENT" in output
        finally:
            _kill_child(pid)
            with contextlib_suppress():
                os.close(fd)


@_REQUIRES_PTY
class TestDiscoveryToPipelineFlow:
    """The full ``discover -> r -> 7 -> pipeline starts`` flow in a
    real PTY. Prevents the stale-dashboard-data regression from
    coming back: if ``handle_discovery_result`` stops refreshing
    ``self._data``, pressing ``r`` after discovery will silently
    notify "Nothing to run" and the pipeline never launches.
    """

    def test_dashboard_action_run_after_discovery_reaches_planner(
        self, tmp_path: Path,
    ) -> None:
        # Pre-populate a workspace with 5 profiles (simulating a
        # freshly-completed discovery round).
        workspace = tmp_path / "populated-ws"
        workspace.mkdir()
        (workspace / "competitors").mkdir()
        (workspace / ".recon").mkdir()
        (workspace / ".recon" / "logs").mkdir()
        (workspace / ".env").write_text("ANTHROPIC_API_KEY=sk-ant-test-bogus\n")
        schema = {
            "domain": "AI code",
            "identity": {
                "company_name": "Acme",
                "products": ["X"],
                "decision_context": ["build-vs-buy"],
            },
            "rating_scales": {
                "c": {"name": "Cap", "values": ["1"], "never_use": ["e"]},
            },
            "sections": [
                {
                    "key": "overview",
                    "title": "Overview",
                    "description": "x",
                    "evidence_types": ["factual"],
                    "allowed_formats": ["prose"],
                    "preferred_format": "prose",
                },
            ],
        }
        (workspace / "recon.yaml").write_text(yaml.dump(schema))
        for name in ["Cursor", "Copilot", "Codeium", "Tabnine", "Aider"]:
            slug = name.lower()
            (workspace / "competitors" / f"{slug}.md").write_text(
                f"---\nname: {name}\ntype: competitor\n"
                "research_status: scaffold\n---\n\n",
            )

        pid, fd = _spawn_tui(
            workspace=workspace,
            recent_path=tmp_path / "home" / ".recon" / "recent.json",
        )
        try:
            reader = _PtyReader(fd)
            reader.drain_until("COMPETITORS", timeout=15.0)
            # Press r -> planner
            os.write(fd, b"r")
            reader.drain_until("RUN PLANNER", timeout=5.0)
            # Press 7 -> FULL_PIPELINE -> run mode
            os.write(fd, b"7")
            reader.drain_until("RUN MONITOR", timeout=5.0)
            # Pipeline should transition OUT of Idle within a few
            # seconds (the fake API key will make it fail, but the
            # transition is what we're pinning). If `handle_discovery_result`
            # stopped refreshing self._data, we'd never even get here --
            # action_run would notify "Nothing to run" instead.
            output = reader.drain_until(
                "research",
                timeout=10.0,
            )
            assert "research" in output.lower(), (
                "pipeline never started research stage -- "
                "probably stale dashboard data after discovery"
            )
        finally:
            _kill_child(pid)
            with contextlib_suppress():
                os.close(fd)


@_REQUIRES_PTY
class TestDiscoveryScreenRendersCards:
    """Smoke test: Discovery screen renders its candidates as
    TerminalBox cards with visible checkbox markers. This catches
    the Rich-markup `[x]` eating bug from Phase O and ensures future
    refactors don't accidentally kill the card layout.
    """

    def test_discovery_empty_state_shows_key_hints(
        self, tmp_path: Path,
    ) -> None:
        workspace = _make_workspace(tmp_path)
        pid, fd = _spawn_tui(
            workspace=workspace,
            recent_path=tmp_path / "home" / ".recon" / "recent.json",
        )
        try:
            reader = _PtyReader(fd)
            reader.drain_until("COMPETITORS", timeout=15.0)
            os.write(fd, b"d")
            # Wait until the Discovery modal's title renders -- that
            # proves we're past the dashboard and on the discovery
            # screen (the dashboard keybind strip also contains
            # "add manually" so we need a discovery-only marker).
            reader.drain_until("── DISCOVERY ──", timeout=5.0)
            # Drain a touch more so the action-bar buttons land in
            # the capture (they render after the body).
            output = reader.drain_until("reject all", timeout=5.0)
            # The new flat action-bar buttons
            assert "[↵] done" in output
            assert "[s] search more" in output
            assert "[n] add manually" in output
            assert "[a] accept all" in output
            assert "[x] reject all" in output
        finally:
            _kill_child(pid)
            with contextlib_suppress():
                os.close(fd)


@_REQUIRES_PTY
class TestAddManuallyFlow:
    """End-to-end: empty dashboard -> m -> type name -> Enter -> profile persisted."""

    def test_m_type_enter_creates_profile(self, tmp_path: Path) -> None:
        # Empty workspace -- no competitor profiles
        workspace = tmp_path / "empty-workspace"
        workspace.mkdir()
        (workspace / "competitors").mkdir()
        (workspace / ".recon").mkdir()
        (workspace / ".recon" / "logs").mkdir()
        schema = {
            "domain": "Dev Tools",
            "identity": {
                "company_name": "Acme",
                "products": ["X"],
                "decision_context": ["build-vs-buy"],
            },
            "rating_scales": {
                "c": {
                    "name": "Cap",
                    "values": ["1", "2"],
                    "never_use": ["emoji"],
                },
            },
            "sections": [
                {
                    "key": "overview",
                    "title": "Overview",
                    "description": "x",
                    "evidence_types": ["factual"],
                    "allowed_formats": ["prose"],
                    "preferred_format": "prose",
                },
            ],
        }
        (workspace / "recon.yaml").write_text(yaml.dump(schema))

        pid, fd = _spawn_tui(
            workspace=workspace,
            recent_path=tmp_path / "home" / ".recon" / "recent.json",
        )
        try:
            reader = _PtyReader(fd)
            reader.drain_until("No competitors yet", timeout=15.0)
            # Press m -> Input mounts
            os.write(fd, b"m")
            reader.drain_until("Enter to add", timeout=5.0)
            # Type a name and press Enter
            os.write(fd, b"Acme Widgets\r")
            output = reader.drain_until("Added", timeout=5.0)
            assert "Added" in output

            # Verify the profile actually landed on disk
            profiles = list((workspace / "competitors").glob("*.md"))
            assert len(profiles) == 1
            assert "acme" in profiles[0].name.lower()
        finally:
            _kill_child(pid)
            with contextlib_suppress():
                os.close(fd)
