"""Theme curation data model for recon TUI.

Manages theme selection state during the pipeline gate at Phase 5b.
Users toggle themes on/off, rename them, and confirm the final set
before synthesis proceeds.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from recon.themes import DiscoveredTheme  # noqa: TCH001 -- used at runtime


@dataclass
class ThemeCurationEntry:
    label: str
    evidence_strength: str
    chunk_count: int
    enabled: bool
    suggested_queries: list[str] = field(default_factory=list)
    cluster_center: list[float] = field(default_factory=list)
    evidence_chunks: list[dict] = field(default_factory=list)

    @classmethod
    def from_theme(cls, theme: DiscoveredTheme) -> ThemeCurationEntry:
        default_enabled = theme.evidence_strength != "weak"
        return cls(
            label=theme.label,
            evidence_strength=theme.evidence_strength,
            chunk_count=len(theme.evidence_chunks),
            enabled=default_enabled,
            suggested_queries=list(theme.suggested_queries),
            cluster_center=list(theme.cluster_center),
            evidence_chunks=list(theme.evidence_chunks),
        )


class ThemeCurationModel:
    """Manages the list of theme entries with toggle/rename operations."""

    def __init__(self, entries: list[ThemeCurationEntry]) -> None:
        self.entries = entries

    @classmethod
    def from_themes(cls, themes: list[DiscoveredTheme]) -> ThemeCurationModel:
        entries = [ThemeCurationEntry.from_theme(t) for t in themes]
        return cls(entries=entries)

    def toggle(self, index: int) -> None:
        if 0 <= index < len(self.entries):
            self.entries[index].enabled = not self.entries[index].enabled

    def rename(self, index: int, new_label: str) -> None:
        if 0 <= index < len(self.entries):
            self.entries[index].label = new_label

    def selected(self) -> list[ThemeCurationEntry]:
        return [e for e in self.entries if e.enabled]

    @property
    def selected_count(self) -> int:
        return sum(1 for e in self.entries if e.enabled)

    def to_discovered_themes(self) -> list[DiscoveredTheme]:
        """Convert selected entries back to DiscoveredTheme objects."""
        return [
            DiscoveredTheme(
                label=entry.label,
                evidence_chunks=entry.evidence_chunks,
                evidence_strength=entry.evidence_strength,
                suggested_queries=entry.suggested_queries,
                cluster_center=entry.cluster_center,
            )
            for entry in self.entries
            if entry.enabled
        ]
