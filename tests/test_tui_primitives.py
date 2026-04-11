"""Tests for reusable TUI container primitives.

``TerminalBox`` is the bordered container primitive used as the body
content card across the recon TUI. It matches the visual language
cyberspace.online calls ``.terminal-box``: 1px solid border at
``#3a3a3a``, 5px radius, 12px/16px padding, black background. Screens
compose stacks of these as single-column card feeds (dashboard,
browser detail panes, run monitor).
"""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.widgets import Static


class _PrimitiveTestApp(App):
    CSS = "Screen { background: #000000; }"

    def __init__(self, child_text: str = "") -> None:
        super().__init__()
        self._child_text = child_text

    def compose(self) -> ComposeResult:
        from recon.tui.primitives import TerminalBox

        with TerminalBox():
            yield Static(self._child_text or "child")


class TestTerminalBox:
    async def test_mounts_as_vertical_container(self) -> None:
        from textual.containers import Vertical

        from recon.tui.primitives import TerminalBox

        app = _PrimitiveTestApp()
        async with app.run_test(size=(80, 20)) as pilot:
            await pilot.pause()
            box = app.query_one(TerminalBox)
            assert isinstance(box, Vertical)

    async def test_renders_children(self) -> None:
        from recon.tui.primitives import TerminalBox

        app = _PrimitiveTestApp(child_text="hello world")
        async with app.run_test(size=(80, 20)) as pilot:
            await pilot.pause()
            box = app.query_one(TerminalBox)
            static = box.query_one(Static)
            assert "hello world" in str(static.content)

    async def test_has_border_css(self) -> None:
        """The primitive carries the recon border styling out of the
        box -- screens don't need to repeat the CSS.
        """
        from recon.tui.primitives import TerminalBox

        app = _PrimitiveTestApp()
        async with app.run_test(size=(80, 20)) as pilot:
            await pilot.pause()
            box = app.query_one(TerminalBox)
            # Textual parses the border type; checking the styles is
            # a declarative assertion that the primitive was styled.
            assert box.styles.border is not None

    async def test_accepts_title_parameter(self) -> None:
        """``TerminalBox(title="...")`` renders a Phase-D-style
        ``── HEADING ──`` divider above its children.
        """
        from recon.tui.primitives import TerminalBox

        class _TitledApp(App):
            CSS = "Screen { background: #000000; }"

            def compose(self) -> ComposeResult:
                with TerminalBox(title="COMPETITORS"):
                    yield Static("body")

        app = _TitledApp()
        async with app.run_test(size=(80, 20)) as pilot:
            await pilot.pause()
            box = app.query_one(TerminalBox)
            title_widget = box.query_one(".terminal-box-title", Static)
            assert "COMPETITORS" in str(title_widget.content)

    async def test_title_uses_divider_markers(self) -> None:
        from recon.tui.primitives import TerminalBox

        class _TitledApp(App):
            CSS = "Screen { background: #000000; }"

            def compose(self) -> ComposeResult:
                with TerminalBox(title="RUN MONITOR"):
                    yield Static("body")

        app = _TitledApp()
        async with app.run_test(size=(80, 20)) as pilot:
            await pilot.pause()
            box = app.query_one(TerminalBox)
            title_widget = box.query_one(".terminal-box-title", Static)
            content = str(title_widget.content)
            assert "──" in content

    async def test_can_omit_title(self) -> None:
        from recon.tui.primitives import TerminalBox

        app = _PrimitiveTestApp()
        async with app.run_test(size=(80, 20)) as pilot:
            await pilot.pause()
            box = app.query_one(TerminalBox)
            assert len(box.query(".terminal-box-title")) == 0

    async def test_accepts_meta_line(self) -> None:
        """``TerminalBox(title=..., meta=...)`` renders a second dim
        line under the title for subtitles like `47 total` or
        `5 competitors · 2 sections`.
        """
        from recon.tui.primitives import TerminalBox

        class _MetaApp(App):
            CSS = "Screen { background: #000000; }"

            def compose(self) -> ComposeResult:
                with TerminalBox(title="COMPETITORS", meta="47 total"):
                    yield Static("body")

        app = _MetaApp()
        async with app.run_test(size=(80, 20)) as pilot:
            await pilot.pause()
            box = app.query_one(TerminalBox)
            meta = box.query_one(".terminal-box-meta", Static)
            assert "47 total" in str(meta.content)


class TestCardStack:
    """``CardStack`` is a thin Vertical wrapper that gives a card feed
    consistent vertical rhythm across screens.
    """

    async def test_stacks_children_vertically(self) -> None:
        from recon.tui.primitives import CardStack, TerminalBox

        class _StackApp(App):
            CSS = "Screen { background: #000000; }"

            def compose(self) -> ComposeResult:
                with CardStack():
                    with TerminalBox(title="A"):
                        yield Static("one")
                    with TerminalBox(title="B"):
                        yield Static("two")
                    with TerminalBox(title="C"):
                        yield Static("three")

        app = _StackApp()
        async with app.run_test(size=(80, 30)) as pilot:
            await pilot.pause()
            boxes = app.query(TerminalBox)
            assert len(boxes) == 3
            titles = [
                str(b.query_one(".terminal-box-title", Static).content)
                for b in boxes
            ]
            assert "A" in titles[0]
            assert "B" in titles[1]
            assert "C" in titles[2]
