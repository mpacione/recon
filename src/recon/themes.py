"""Theme discovery for recon.

Themes emerge from K-means clustering on chunk embeddings. Users curate
after discovery (toggle, rename, investigate). No user-defined themes
in the wizard -- they come from the data.

Cluster labels can be generated two ways:
1. Mechanical: top frequency terms from the cluster (no API cost, low quality).
2. LLM-generated: short strategic label via a single LLM call per cluster
   (small API cost, much higher quality). Enabled by passing an LLMClient
   to ThemeDiscovery.
"""

from __future__ import annotations

import asyncio
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from recon.llm import LLMClient  # noqa: TCH001
from recon.logging import get_logger

_log = get_logger(__name__)


@dataclass(frozen=True)
class DiscoveredTheme:
    label: str
    evidence_chunks: list[dict[str, Any]]
    evidence_strength: str
    suggested_queries: list[str]
    cluster_center: list[float] = field(default_factory=list)


_STOP_WORDS = frozenset(
    ["the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "is", "it", "this", "that", "with", "from", "by", "as", "are", "was", "were", "be", "been", "have", "has", "had", "do", "does", "did", "will", "would", "shall", "should", "can", "could", "may", "might", "must", "not", "no"]
)


def _label_cluster(texts: list[str], top_n: int = 3) -> str:
    """Generate a label for a cluster from its most common meaningful terms."""
    if not texts:
        return "Unnamed Theme"

    words: list[str] = []
    for text in texts:
        cleaned = re.sub(r"[^\w\s]", "", text.lower())
        words.extend(w for w in cleaned.split() if w not in _STOP_WORDS and len(w) > 2)

    if not words:
        return "Unnamed Theme"

    counter = Counter(words)
    top_terms = [term for term, _ in counter.most_common(top_n)]
    return " / ".join(term.capitalize() for term in top_terms)


def _evidence_strength(chunk_count: int, total_chunks: int) -> str:
    """Classify evidence strength based on cluster size relative to total."""
    if total_chunks == 0:
        return "weak"
    ratio = chunk_count / total_chunks
    if ratio >= 0.2:
        return "strong"
    if ratio >= 0.1:
        return "moderate"
    return "weak"


def _generate_queries(texts: list[str], label: str) -> list[str]:
    """Generate suggested retrieval queries from cluster content."""
    queries = [label]

    words: list[str] = []
    for text in texts[:10]:
        cleaned = re.sub(r"[^\w\s]", "", text.lower())
        words.extend(w for w in cleaned.split() if w not in _STOP_WORDS and len(w) > 3)

    counter = Counter(words)
    top_bigrams = [term for term, _ in counter.most_common(5)]
    if len(top_bigrams) >= 2:
        queries.append(f"{top_bigrams[0]} {top_bigrams[1]}")
    if len(top_bigrams) >= 4:
        queries.append(f"{top_bigrams[2]} {top_bigrams[3]}")

    return queries


_SOURCES_HEADER_RE = re.compile(r"^\s*#+\s*Sources\b", re.IGNORECASE | re.MULTILINE)


def _strip_sources(text: str) -> str:
    """Drop the Sources section from a chunk so clustering focuses on content."""
    match = _SOURCES_HEADER_RE.search(text)
    if match:
        return text[: match.start()].rstrip()
    return text


_LABEL_SYSTEM_PROMPT = """\
You are a competitive intelligence analyst. Given excerpts from multiple \
competitor profiles in the same thematic cluster, propose a short label \
(2 to 5 words) capturing the strategic pattern they share.

Rules:
- 2 to 5 words only.
- Title case.
- No trailing punctuation.
- Focus on the pattern, not individual companies.
- Prefer strategic concepts (e.g. "Open Source Moats", "Platform Consolidation", \
"Enterprise Compliance Arms Race") over mechanical ones (e.g. "Search Engines").

Return ONLY the label text. No explanation, no JSON, no quotes."""


def _clean_label(raw: str, fallback: str) -> str:
    """Clean an LLM label response into a short title-case string."""
    if not raw or not raw.strip():
        return fallback
    line = raw.strip().splitlines()[0].strip()
    line = line.strip('"\'` ').rstrip(".,:;")
    if not line or len(line) > 80:
        return fallback
    return line


class ThemeDiscovery:
    """Discovers themes from K-means clustering on chunk embeddings."""

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self._llm_client = llm_client

    def discover(
        self,
        chunks: list[dict[str, Any]],
        n_themes: int = 5,
    ) -> list[DiscoveredTheme]:
        """Discover themes by clustering chunk embeddings."""
        if not chunks:
            return []

        embeddings = np.array([c["embedding"] for c in chunks])
        actual_k = min(n_themes, len(chunks))

        if actual_k < 2:
            cleaned = [_strip_sources(c["text"]) for c in chunks]
            fallback = _label_cluster(cleaned)
            label = self._llm_label(cleaned, fallback)
            return [
                DiscoveredTheme(
                    label=label,
                    evidence_chunks=chunks,
                    evidence_strength=_evidence_strength(len(chunks), len(chunks)),
                    suggested_queries=_generate_queries(cleaned, label),
                    cluster_center=embeddings.mean(axis=0).tolist(),
                ),
            ]

        labels, centers = self._kmeans(embeddings, actual_k)

        clusters: dict[int, list[dict[str, Any]]] = {}
        for i, label_id in enumerate(labels):
            clusters.setdefault(label_id, []).append(chunks[i])

        themes: list[DiscoveredTheme] = []
        for cluster_id in sorted(clusters, key=lambda k: len(clusters[k]), reverse=True):
            cluster_chunks = clusters[cluster_id]
            cleaned = [_strip_sources(c["text"]) for c in cluster_chunks]
            fallback = _label_cluster(cleaned)
            label = self._llm_label(cleaned, fallback)
            strength = _evidence_strength(len(cluster_chunks), len(chunks))
            queries = _generate_queries(cleaned, label)

            themes.append(
                DiscoveredTheme(
                    label=label,
                    evidence_chunks=cluster_chunks,
                    evidence_strength=strength,
                    suggested_queries=queries,
                    cluster_center=centers[cluster_id].tolist(),
                ),
            )

        return themes

    def _llm_label(self, cleaned_texts: list[str], fallback: str) -> str:
        """Ask the LLM for a short strategic label for this cluster.

        Returns `fallback` (mechanical label) if no LLM client is configured
        or the call fails.
        """
        if self._llm_client is None or not cleaned_texts:
            return fallback

        excerpts = "\n\n---\n\n".join(
            text[:800] for text in cleaned_texts[:8] if text.strip()
        )
        if not excerpts:
            return fallback

        user_prompt = (
            "Excerpts from this cluster:\n\n"
            f"{excerpts}\n\n"
            "Return the 2-5 word label only."
        )

        try:
            response = asyncio.run(
                self._llm_client.complete(
                    system_prompt=_LABEL_SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                    max_tokens=30,
                ),
            )
        except RuntimeError:
            _log.warning(
                "ThemeDiscovery._llm_label called inside a running event loop; "
                "falling back to mechanical label",
            )
            return fallback
        except Exception:
            _log.exception("ThemeDiscovery._llm_label LLM call failed")
            return fallback

        label = _clean_label(response.text, fallback)
        _log.info("ThemeDiscovery LLM label: %r (fallback was %r)", label, fallback)
        return label

    def _kmeans(
        self,
        data: np.ndarray,
        k: int,
        max_iterations: int = 100,
    ) -> tuple[list[int], np.ndarray]:
        """Simple K-means implementation (avoids sklearn dependency)."""
        rng = np.random.default_rng(42)
        n_samples = data.shape[0]

        indices = rng.choice(n_samples, size=k, replace=False)
        centers = data[indices].copy()

        labels = np.zeros(n_samples, dtype=int)

        for _ in range(max_iterations):
            distances = np.linalg.norm(data[:, np.newaxis] - centers[np.newaxis, :], axis=2)
            new_labels = np.argmin(distances, axis=1)

            if np.array_equal(new_labels, labels):
                break
            labels = new_labels

            for j in range(k):
                mask = labels == j
                if mask.any():
                    centers[j] = data[mask].mean(axis=0)

        return labels.tolist(), centers
