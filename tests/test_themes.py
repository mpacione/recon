"""Tests for theme discovery.

Themes emerge from K-means clustering on chunk embeddings, not from
user-defined categories. Users curate (toggle, rename, investigate)
after discovery.
"""

from unittest.mock import AsyncMock

import numpy as np

from recon.llm import LLMResponse
from recon.themes import (
    DiscoveredTheme,
    ThemeDiscovery,
    _clean_label,
    _label_cluster,
    _strip_sources,
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
    async def test_discovers_themes_from_clusters(self) -> None:
        chunks = _make_chunks_with_embeddings(30)

        discovery = ThemeDiscovery()
        themes = await discovery.discover(chunks, n_themes=3)

        assert len(themes) == 3
        assert all(isinstance(t, DiscoveredTheme) for t in themes)

    async def test_each_theme_has_label(self) -> None:
        chunks = _make_chunks_with_embeddings(30)

        discovery = ThemeDiscovery()
        themes = await discovery.discover(chunks, n_themes=3)

        for theme in themes:
            assert len(theme.label) > 0

    async def test_each_theme_has_evidence_chunks(self) -> None:
        chunks = _make_chunks_with_embeddings(30)

        discovery = ThemeDiscovery()
        themes = await discovery.discover(chunks, n_themes=3)

        for theme in themes:
            assert len(theme.evidence_chunks) > 0

    async def test_each_theme_has_evidence_strength(self) -> None:
        chunks = _make_chunks_with_embeddings(30)

        discovery = ThemeDiscovery()
        themes = await discovery.discover(chunks, n_themes=3)

        for theme in themes:
            assert theme.evidence_strength in ("strong", "moderate", "weak")

    async def test_themes_ranked_by_evidence(self) -> None:
        chunks = _make_chunks_with_embeddings(30)

        discovery = ThemeDiscovery()
        themes = await discovery.discover(chunks, n_themes=3)

        sizes = [len(t.evidence_chunks) for t in themes]
        assert sizes == sorted(sizes, reverse=True)

    async def test_handles_fewer_chunks_than_themes(self) -> None:
        chunks = _make_chunks_with_embeddings(2)

        discovery = ThemeDiscovery()
        themes = await discovery.discover(chunks, n_themes=5)

        assert len(themes) <= 2

    async def test_empty_chunks(self) -> None:
        discovery = ThemeDiscovery()
        themes = await discovery.discover([], n_themes=3)

        assert themes == []

    async def test_generates_retrieval_queries(self) -> None:
        chunks = _make_chunks_with_embeddings(30)

        discovery = ThemeDiscovery()
        themes = await discovery.discover(chunks, n_themes=3)

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


class TestStripSources:
    def test_strips_sources_header(self) -> None:
        text = "Overview paragraph.\n\n## Sources\n- [Doc](https://example.com)"
        result = _strip_sources(text)
        assert result == "Overview paragraph."

    def test_strips_case_insensitive(self) -> None:
        text = "Body\n\n# sources\n- ref"
        assert _strip_sources(text) == "Body"

    def test_noop_when_no_sources(self) -> None:
        text = "Just prose, no sources list."
        assert _strip_sources(text) == text


class TestCleanLabel:
    def test_strips_quotes_and_punctuation(self) -> None:
        assert _clean_label('"Platform Consolidation."', "fallback") == "Platform Consolidation"

    def test_keeps_first_line_only(self) -> None:
        assert _clean_label("Enterprise Lock-in\nSome extra explanation", "fallback") == "Enterprise Lock-in"

    def test_falls_back_when_empty(self) -> None:
        assert _clean_label("", "fallback") == "fallback"
        assert _clean_label("   ", "fallback") == "fallback"

    def test_falls_back_when_too_long(self) -> None:
        long_text = "x" * 200
        assert _clean_label(long_text, "fallback") == "fallback"


class TestLLMLabeling:
    def _mock_llm(self, label_text: str) -> AsyncMock:
        client = AsyncMock()
        client.complete = AsyncMock(
            return_value=LLMResponse(
                text=label_text,
                input_tokens=50,
                output_tokens=10,
                model="claude-haiku-4-5",
                stop_reason="end_turn",
            ),
        )
        return client

    async def test_uses_llm_label_when_client_provided(self) -> None:
        chunks = _make_chunks_with_embeddings(30)
        llm = self._mock_llm("Platform Consolidation")

        discovery = ThemeDiscovery(llm_client=llm)
        themes = await discovery.discover(chunks, n_themes=3)

        assert llm.complete.call_count == 3
        assert all(t.label == "Platform Consolidation" for t in themes)

    async def test_falls_back_to_mechanical_on_llm_error(self) -> None:
        chunks = _make_chunks_with_embeddings(30)
        llm = AsyncMock()
        llm.complete = AsyncMock(side_effect=RuntimeError("API down"))

        discovery = ThemeDiscovery(llm_client=llm)
        themes = await discovery.discover(chunks, n_themes=3)

        assert len(themes) == 3
        for theme in themes:
            assert theme.label != "Platform Consolidation"
            assert len(theme.label) > 0

    async def test_no_llm_calls_when_client_absent(self) -> None:
        chunks = _make_chunks_with_embeddings(30)

        discovery = ThemeDiscovery()
        themes = await discovery.discover(chunks, n_themes=3)

        assert len(themes) == 3
