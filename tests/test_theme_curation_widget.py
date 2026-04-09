"""Tests for the theme curation TUI widget.

Tests the Textual widget rendering and interaction by verifying
the display format and key handling.
"""

from __future__ import annotations

from recon.themes import DiscoveredTheme
from recon.tui.curation import ThemeCurationModel
from recon.tui.widgets import format_theme_list


def _make_theme(label: str, strength: str = "strong", chunks: int = 10) -> DiscoveredTheme:
    return DiscoveredTheme(
        label=label,
        evidence_chunks=[{"text": f"chunk {i}"} for i in range(chunks)],
        evidence_strength=strength,
        suggested_queries=[label.lower()],
        cluster_center=[],
    )


class TestFormatThemeList:
    def test_renders_enabled_themes_with_checkbox(self) -> None:
        model = ThemeCurationModel.from_themes([_make_theme("AI Theme", "strong", 38)])

        lines = format_theme_list(model)

        assert len(lines) == 1
        assert "[x]" in lines[0]
        assert "AI Theme" in lines[0]
        assert "38" in lines[0]
        assert "strong" in lines[0]

    def test_renders_disabled_themes_unchecked(self) -> None:
        model = ThemeCurationModel.from_themes([_make_theme("Weak Theme", "weak", 5)])

        lines = format_theme_list(model)

        assert len(lines) == 1
        assert "[ ]" in lines[0]
        assert "Weak Theme" in lines[0]

    def test_renders_multiple_themes_in_order(self) -> None:
        themes = [
            _make_theme("Theme A", "strong", 40),
            _make_theme("Theme B", "moderate", 20),
            _make_theme("Theme C", "weak", 5),
        ]
        model = ThemeCurationModel.from_themes(themes)

        lines = format_theme_list(model)

        assert len(lines) == 3
        assert "Theme A" in lines[0]
        assert "Theme B" in lines[1]
        assert "Theme C" in lines[2]

    def test_shows_index_numbers(self) -> None:
        themes = [_make_theme("A"), _make_theme("B")]
        model = ThemeCurationModel.from_themes(themes)

        lines = format_theme_list(model)

        assert "1." in lines[0]
        assert "2." in lines[1]

    def test_empty_model_returns_empty_list(self) -> None:
        model = ThemeCurationModel.from_themes([])

        lines = format_theme_list(model)

        assert lines == []
