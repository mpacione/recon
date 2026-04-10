"""Index and retrieve system for recon.

Chunks markdown profiles by section, embeds with fastembed via ChromaDB's
built-in embedding, and provides semantic retrieval.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import Any

import chromadb

from recon.logging import get_logger

_log = get_logger(__name__)


@dataclass
class Chunk:
    text: str
    section: str
    source_path: str
    metadata: dict[str, Any] = field(default_factory=dict)
    chunk_index: int = 0


class Chunker:
    """Not used directly -- see chunk_markdown function."""


def chunk_markdown(
    content: str,
    source_path: str,
    max_chunk_tokens: int = 500,
    frontmatter_meta: dict[str, Any] | None = None,
) -> list[Chunk]:
    """Split markdown content into chunks by section heading."""
    meta = frontmatter_meta or {}
    sections = _split_by_heading(content)

    if not sections:
        text = content.strip()
        if not text:
            return []
        chunks = _split_long_text(text, max_chunk_tokens)
        return [
            Chunk(
                text=chunk_text,
                section="content",
                source_path=source_path,
                metadata=dict(meta),
                chunk_index=i,
            )
            for i, chunk_text in enumerate(chunks)
        ]

    all_chunks: list[Chunk] = []
    for section_title, section_text in sections:
        text = section_text.strip()
        if not text:
            continue

        sub_chunks = _split_long_text(text, max_chunk_tokens)
        for i, chunk_text in enumerate(sub_chunks):
            all_chunks.append(
                Chunk(
                    text=chunk_text,
                    section=section_title,
                    source_path=source_path,
                    metadata=dict(meta),
                    chunk_index=i,
                )
            )

    return all_chunks


def _split_by_heading(content: str) -> list[tuple[str, str]]:
    """Split content by markdown headings (## or ###)."""
    pattern = re.compile(r"^(#{2,4})\s+(.+)$", re.MULTILINE)
    matches = list(pattern.finditer(content))

    if not matches:
        return []

    sections: list[tuple[str, str]] = []
    for i, match in enumerate(matches):
        title = match.group(2).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        sections.append((title, content[start:end]))

    return sections


def _split_long_text(text: str, max_tokens: int) -> list[str]:
    """Split text into chunks of roughly max_tokens (approximated as words)."""
    words = text.split()
    if len(words) <= max_tokens:
        return [text]

    chunks: list[str] = []
    for i in range(0, len(words), max_tokens):
        chunk = " ".join(words[i : i + max_tokens])
        if chunk.strip():
            chunks.append(chunk)

    return chunks


_COLLECTION_NAME = "recon_profiles"


class IndexManager:
    """Manages ChromaDB vector index for profile chunks."""

    def __init__(
        self,
        persist_dir: str | None = None,
        client: chromadb.ClientAPI | None = None,
    ) -> None:
        if client is not None:
            self._client = client
        elif persist_dir:
            self._client = chromadb.PersistentClient(path=persist_dir)
        else:
            self._client = chromadb.EphemeralClient()

        self._collection = self._client.get_or_create_collection(
            name=_COLLECTION_NAME,
        )

    def add_chunks(self, chunks: list[Chunk]) -> None:
        """Add chunks to the vector index."""
        if not chunks:
            return

        ids = [uuid.uuid4().hex[:16] for _ in chunks]
        documents = [c.text for c in chunks]
        metadatas = [
            {
                "section": c.section,
                "source_path": c.source_path,
                "chunk_index": c.chunk_index,
                **{k: str(v) for k, v in c.metadata.items()},
            }
            for c in chunks
        ]

        self._collection.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
        )
        _log.debug(
            "index added %d chunks (collection now %d)",
            len(chunks),
            self._collection.count(),
        )

    def retrieve(self, query: str, n_results: int = 10) -> list[dict[str, Any]]:
        """Retrieve relevant chunks by semantic search."""
        if self._collection.count() == 0:
            _log.debug("index retrieve called but collection is empty")
            return []
        _log.debug("index retrieve query=%r n_results=%d", query[:80], n_results)

        results = self._collection.query(
            query_texts=[query],
            n_results=min(n_results, self._collection.count()),
        )

        output: list[dict[str, Any]] = []
        if results and results["documents"]:
            for i, doc in enumerate(results["documents"][0]):
                entry: dict[str, Any] = {"text": doc}
                if results["metadatas"]:
                    entry["metadata"] = results["metadatas"][0][i]
                if results["distances"]:
                    entry["distance"] = results["distances"][0][i]
                output.append(entry)

        return output

    def collection_count(self) -> int:
        """Return the number of chunks in the index."""
        return self._collection.count()

    def clear(self) -> None:
        """Clear all chunks from the index."""
        self._client.delete_collection(_COLLECTION_NAME)
        self._collection = self._client.get_or_create_collection(
            name=_COLLECTION_NAME,
        )

    def close(self) -> None:
        """Release ChromaDB system resources held by this manager.

        Drops the collection / client references and clears
        ChromaDB's process-wide system-instance cache so the
        underlying Rust segment readers release their file handles.
        Safe to call multiple times.
        """
        try:
            from chromadb.api.client import SharedSystemClient

            SharedSystemClient.clear_system_cache()
        except Exception:  # noqa: BLE001 -- never let cleanup raise
            pass
        self._collection = None  # type: ignore[assignment]
        self._client = None  # type: ignore[assignment]
