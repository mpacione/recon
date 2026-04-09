"""Incremental indexing for recon.

Uses file content hashes stored in the state DB to skip unchanged profiles
during re-indexing. Only new or modified files are re-chunked and embedded.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from recon.index import IndexManager, chunk_markdown  # noqa: TCH001 -- used at runtime
from recon.state import StateStore  # noqa: TCH001 -- used at runtime
from recon.workspace import Workspace  # noqa: TCH001 -- used at runtime


@dataclass(frozen=True)
class IndexResult:
    indexed: int
    skipped: int
    total_chunks: int


class IncrementalIndexer:
    """Indexes workspace profiles incrementally using file hash tracking."""

    def __init__(
        self,
        workspace: Workspace,
        index_manager: IndexManager,
        state_store: StateStore,
    ) -> None:
        self._workspace = workspace
        self._index = index_manager
        self._state = state_store

    async def index(self, force: bool = False) -> IndexResult:
        """Index profiles, skipping unchanged files unless force=True."""
        profiles = self._workspace.list_profiles()

        indexed = 0
        skipped = 0
        total_chunks = 0

        for profile_meta in profiles:
            slug = profile_meta["_slug"]
            full = self._workspace.read_profile(slug)
            if not full or not full.get("_content", "").strip():
                continue

            path = str(profile_meta["_path"])
            content = full["_content"]
            current_hash = hashlib.sha256(content.encode()).hexdigest()

            if not force:
                changed = await self._state.has_file_changed(path, current_hash)
                if not changed:
                    skipped += 1
                    continue

            chunks = chunk_markdown(
                content=content,
                source_path=path,
                frontmatter_meta={k: v for k, v in profile_meta.items() if not k.startswith("_")},
            )

            if chunks:
                self._index.add_chunks(chunks)
                total_chunks += len(chunks)

            await self._state.set_file_hash(path, current_hash)
            indexed += 1

        return IndexResult(indexed=indexed, skipped=skipped, total_chunks=total_chunks)
