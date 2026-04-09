"""Tests for theme discovery.

Themes emerge from K-means clustering on chunk embeddings, not from
user-defined categories. Users curate (toggle, rename, investigate)
after discovery.
"""

import numpy as np

from recon.themes import (
    DiscoveredTheme,
    ThemeDiscovery,
    _label_cluster,
)


def _make_chunks_with_embeddings(n: int = 20) -> list[dict]:
    """Create mock chunks with synthetic embeddings in 3 clusters."""
    rng = np.random.default_rng(42)
    chunks = []

    centers = [
        np.array([1.0, 0.0, 0.0]),
        np.array([0.0, 1.0, 0.0]),
        np.array([0.0, 0.0, 1.0]),
    ]

    texts = [
        ["AI code generation is transforming developer workflows", "Code completion using LLMs", "Automated coding assistants"],
        ["Enterprise compliance and security certifications", "SOC2 and HIPAA governance", "Audit trails and admin controls"],
        ["Developer experience and onboarding friction", "Time to first value metrics", "Self-serve product-led growth"],
    ]

    for i in range(n):
        cluster = i % 3
        embedding = centers[cluster] + rng.normal(0, 0.1, 3)
        text_options = texts[cluster]
        chunks.append({
            "text": text_options[i % len(text_options)],
            "embedding": embedding.tolist(),
            "metadata": {"name": f"Competitor{i}", "section": "Overview"},
        })

    return chunks


class TestThemeDiscovery:
    def test_discovers_themes_from_clusters(self) -> None:
        chunks = _make_chunks_with_embeddings(30)

        discovery = ThemeDiscovery()
        themes = discovery.discover(chunks, n_themes=3)

        assert len(themes) == 3
        assert all(isinstance(t, DiscoveredTheme) for t in themes)

    def test_each_theme_has_label(self) -> None:
        chunks = _make_chunks_with_embeddings(30)

        discovery = ThemeDiscovery()
        themes = discovery.discover(chunks, n_themes=3)

        for theme in themes:
            assert len(theme.label) > 0

    def test_each_theme_has_evidence_chunks(self) -> None:
        chunks = _make_chunks_with_embeddings(30)

        discovery = ThemeDiscovery()
        themes = discovery.discover(chunks, n_themes=3)

        for theme in themes:
            assert len(theme.evidence_chunks) > 0

    def test_each_theme_has_evidence_strength(self) -> None:
        chunks = _make_chunks_with_embeddings(30)

        discovery = ThemeDiscovery()
        themes = discovery.discover(chunks, n_themes=3)

        for theme in themes:
            assert theme.evidence_strength in ("strong", "moderate", "weak")

    def test_themes_ranked_by_evidence(self) -> None:
        chunks = _make_chunks_with_embeddings(30)

        discovery = ThemeDiscovery()
        themes = discovery.discover(chunks, n_themes=3)

        sizes = [len(t.evidence_chunks) for t in themes]
        assert sizes == sorted(sizes, reverse=True)

    def test_handles_fewer_chunks_than_themes(self) -> None:
        chunks = _make_chunks_with_embeddings(2)

        discovery = ThemeDiscovery()
        themes = discovery.discover(chunks, n_themes=5)

        assert len(themes) <= 2

    def test_empty_chunks(self) -> None:
        discovery = ThemeDiscovery()
        themes = discovery.discover([], n_themes=3)

        assert themes == []

    def test_generates_retrieval_queries(self) -> None:
        chunks = _make_chunks_with_embeddings(30)

        discovery = ThemeDiscovery()
        themes = discovery.discover(chunks, n_themes=3)

        for theme in themes:
            assert len(theme.suggested_queries) > 0


class TestClusterLabeling:
    def test_labels_from_common_terms(self) -> None:
        texts = [
            "AI code generation for developers",
            "automated code completion using AI",
            "AI-powered code suggestions",
        ]

        label = _label_cluster(texts)

        assert len(label) > 0
        assert any(word in label.lower() for word in ["code", "ai"])

    def test_handles_empty_cluster(self) -> None:
        label = _label_cluster([])

        assert label == "Unnamed Theme"
