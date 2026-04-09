"""Tests for theme curation data model.

The curation model manages theme selection state: toggle on/off,
rename, and track which themes the user wants to synthesize.
"""

from __future__ import annotations

from recon.themes import DiscoveredTheme
from recon.tui.curation import ThemeCurationEntry, ThemeCurationModel


def _make_theme(label: str, strength: str = "strong", chunks: int = 10) -> DiscoveredTheme:
    return DiscoveredTheme(
        label=label,
        evidence_chunks=[{"text": f"chunk {i}"} for i in range(chunks)],
        evidence_strength=strength,
        suggested_queries=[label.lower()],
        cluster_center=[],
    )


class TestThemeCurationEntry:
    def test_created_from_discovered_theme(self) -> None:
        theme = _make_theme("Platform Consolidation", strength="strong", chunks=38)

        entry = ThemeCurationEntry.from_theme(theme)

        assert entry.label == "Platform Consolidation"
        assert entry.evidence_strength == "strong"
        assert entry.chunk_count == 38
        assert entry.enabled is True

    def test_strong_themes_enabled_by_default(self) -> None:
        entry = ThemeCurationEntry.from_theme(_make_theme("Strong Theme", strength="strong"))
        assert entry.enabled is True

    def test_moderate_themes_enabled_by_default(self) -> None:
        entry = ThemeCurationEntry.from_theme(_make_theme("Moderate Theme", strength="moderate"))
        assert entry.enabled is True

    def test_weak_themes_disabled_by_default(self) -> None:
        entry = ThemeCurationEntry.from_theme(_make_theme("Weak Theme", strength="weak"))
        assert entry.enabled is False


class TestThemeCurationModel:
    def test_builds_from_discovered_themes(self) -> None:
        themes = [
            _make_theme("Platform Consolidation", "strong", 38),
            _make_theme("Agentic Shift", "strong", 31),
            _make_theme("Vertical Specialization", "weak", 12),
        ]

        model = ThemeCurationModel.from_themes(themes)

        assert len(model.entries) == 3
        assert model.entries[0].label == "Platform Consolidation"
        assert model.entries[2].enabled is False

    def test_toggle_changes_enabled_state(self) -> None:
        themes = [_make_theme("Theme A")]
        model = ThemeCurationModel.from_themes(themes)

        model.toggle(0)

        assert model.entries[0].enabled is False

        model.toggle(0)

        assert model.entries[0].enabled is True

    def test_toggle_out_of_range_is_noop(self) -> None:
        model = ThemeCurationModel.from_themes([_make_theme("Theme A")])

        model.toggle(99)

        assert model.entries[0].enabled is True

    def test_rename_changes_label(self) -> None:
        model = ThemeCurationModel.from_themes([_make_theme("Old Name")])

        model.rename(0, "New Name")

        assert model.entries[0].label == "New Name"

    def test_rename_out_of_range_is_noop(self) -> None:
        model = ThemeCurationModel.from_themes([_make_theme("Theme A")])

        model.rename(99, "New Name")

        assert model.entries[0].label == "Theme A"

    def test_selected_returns_enabled_entries(self) -> None:
        themes = [
            _make_theme("Enabled Theme", "strong"),
            _make_theme("Weak Theme", "weak"),
        ]
        model = ThemeCurationModel.from_themes(themes)

        selected = model.selected()

        assert len(selected) == 1
        assert selected[0].label == "Enabled Theme"

    def test_selected_count(self) -> None:
        themes = [
            _make_theme("A", "strong"),
            _make_theme("B", "strong"),
            _make_theme("C", "weak"),
        ]
        model = ThemeCurationModel.from_themes(themes)

        assert model.selected_count == 2

    def test_to_discovered_themes_returns_selected_with_updated_labels(self) -> None:
        original = [
            _make_theme("Original A", "strong", 10),
            _make_theme("Original B", "weak", 5),
        ]
        model = ThemeCurationModel.from_themes(original)
        model.rename(0, "Renamed A")

        result = model.to_discovered_themes()

        assert len(result) == 1
        assert result[0].label == "Renamed A"
        assert result[0].evidence_strength == "strong"
        assert result[0].suggested_queries == original[0].suggested_queries
