"""Tests for the index and retrieve system.

Index: chunk markdown profiles by section, embed with fastembed, store in ChromaDB.
Retrieve: semantic search per query, aggregate by competitor.
"""


import chromadb
import pytest

from recon.index import IndexManager, chunk_markdown


@pytest.fixture()
def index_manager() -> IndexManager:
    """Create an IndexManager with an ephemeral client for testing."""
    client = chromadb.EphemeralClient()
    return IndexManager(client=client)


class TestChunker:
    def test_chunks_by_section(self) -> None:
        content = (
            "## Overview\n\nThis is the overview section with some content.\n\n"
            "## Capabilities\n\nCapability details here.\n"
        )

        chunks = chunk_markdown(content, source_path="competitors/alpha.md")

        assert len(chunks) == 2
        assert chunks[0].section == "Overview"
        assert chunks[1].section == "Capabilities"

    def test_chunk_includes_metadata(self) -> None:
        content = "## Overview\n\nSome content about the product.\n"

        chunks = chunk_markdown(content, source_path="competitors/alpha.md")

        assert chunks[0].source_path == "competitors/alpha.md"
        assert chunks[0].section == "Overview"
        assert "Some content about the product" in chunks[0].text

    def test_skips_empty_sections(self) -> None:
        content = "## Overview\n\n## Capabilities\n\nActual content.\n"

        chunks = chunk_markdown(content, source_path="competitors/alpha.md")

        assert len(chunks) == 1
        assert chunks[0].section == "Capabilities"

    def test_handles_no_sections(self) -> None:
        content = "Just plain text without any headings."

        chunks = chunk_markdown(content, source_path="competitors/alpha.md")

        assert len(chunks) == 1
        assert chunks[0].section == "content"

    def test_long_section_splits_into_chunks(self) -> None:
        long_text = " ".join(["word"] * 600)
        content = f"## Overview\n\n{long_text}\n"

        chunks = chunk_markdown(content, source_path="alpha.md", max_chunk_tokens=200)

        assert len(chunks) > 1
        assert all(c.section == "Overview" for c in chunks)

    def test_preserves_frontmatter_in_metadata(self) -> None:
        content = "## Overview\n\nContent.\n"

        chunks = chunk_markdown(
            content,
            source_path="competitors/alpha.md",
            frontmatter_meta={"name": "Alpha", "domain": "DevTools"},
        )

        assert chunks[0].metadata["name"] == "Alpha"
        assert chunks[0].metadata["domain"] == "DevTools"


class TestIndexManager:
    def test_indexes_chunks(self, index_manager: IndexManager) -> None:
        chunks = chunk_markdown(
            "## Overview\n\nSome content about alpha product.\n",
            source_path="competitors/alpha.md",
        )

        index_manager.add_chunks(chunks)
        count = index_manager.collection_count()

        assert count == 1

    def test_retrieves_relevant_chunks(self, index_manager: IndexManager) -> None:
        chunks_a = chunk_markdown(
            "## Overview\n\nAlpha is an AI code generation tool for developers.\n",
            source_path="competitors/alpha.md",
            frontmatter_meta={"name": "Alpha"},
        )
        chunks_b = chunk_markdown(
            "## Overview\n\nBeta is a project management platform for teams.\n",
            source_path="competitors/beta.md",
            frontmatter_meta={"name": "Beta"},
        )

        index_manager.add_chunks(chunks_a + chunks_b)

        results = index_manager.retrieve("AI code generation", n_results=5)

        assert len(results) > 0
        assert any("Alpha" in str(r) or "code generation" in r["text"].lower() for r in results)

    def test_clears_collection(self, index_manager: IndexManager) -> None:
        chunks = chunk_markdown(
            "## Overview\n\nContent.\n",
            source_path="alpha.md",
        )
        index_manager.add_chunks(chunks)
        assert index_manager.collection_count() > 0

        index_manager.clear()
        assert index_manager.collection_count() == 0

    def test_empty_retrieval(self, index_manager: IndexManager) -> None:
        results = index_manager.retrieve("anything", n_results=5)

        assert results == []
