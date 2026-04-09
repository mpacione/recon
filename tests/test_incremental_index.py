"""Tests for incremental indexing.

Incremental indexing uses file hashes stored in the state DB to skip
unchanged profiles, re-index modified ones, and remove deleted ones.
"""

from __future__ import annotations

import asyncio
from pathlib import Path  # noqa: TCH003 -- used at runtime

import chromadb
import frontmatter
import pytest
import yaml

from recon.incremental import IncrementalIndexer
from recon.index import IndexManager
from recon.state import StateStore
from recon.workspace import Workspace

MINIMAL_SCHEMA = {
    "domain": "Developer Tools",
    "identity": {
        "company_name": "Acme Corp",
        "products": ["Acme IDE"],
        "decision_context": [],
    },
    "rating_scales": {},
    "sections": [
        {
            "key": "overview",
            "title": "Overview",
            "description": "High-level summary.",
            "allowed_formats": ["prose"],
            "preferred_format": "prose",
        },
    ],
}


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture()
def workspace(tmp_path: Path) -> Workspace:
    ws_dir = tmp_path / "ws"
    ws_dir.mkdir()
    (ws_dir / "competitors").mkdir()
    (ws_dir / ".recon").mkdir()
    (ws_dir / ".recon" / "logs").mkdir()
    (ws_dir / "recon.yaml").write_text(yaml.dump(MINIMAL_SCHEMA))
    return Workspace.open(ws_dir)


@pytest.fixture()
def state_store(tmp_path: Path) -> StateStore:
    store = StateStore(db_path=tmp_path / "state.db")
    _run(store.initialize())
    return store


@pytest.fixture()
def index_manager() -> IndexManager:
    client = chromadb.EphemeralClient()
    return IndexManager(client=client)


def _create_profile(ws: Workspace, name: str, content: str) -> Path:
    ws.create_profile(name)
    path = ws.competitors_dir / f"{name.lower()}.md"
    post = frontmatter.load(str(path))
    post.content = content
    post["research_status"] = "researched"
    path.write_text(frontmatter.dumps(post))
    return path


class TestIncrementalIndexer:
    def test_indexes_new_files(
        self,
        workspace: Workspace,
        state_store: StateStore,
        index_manager: IndexManager,
    ) -> None:
        _create_profile(workspace, "Alpha", "## Overview\n\nAlpha is a code tool.\n")

        indexer = IncrementalIndexer(
            workspace=workspace,
            index_manager=index_manager,
            state_store=state_store,
        )
        result = _run(indexer.index())

        assert result.indexed > 0
        assert result.skipped == 0
        assert index_manager.collection_count() > 0

    def test_skips_unchanged_files(
        self,
        workspace: Workspace,
        state_store: StateStore,
        index_manager: IndexManager,
    ) -> None:
        _create_profile(workspace, "Alpha", "## Overview\n\nAlpha is a code tool.\n")

        indexer = IncrementalIndexer(
            workspace=workspace,
            index_manager=index_manager,
            state_store=state_store,
        )
        _run(indexer.index())
        result = _run(indexer.index())

        assert result.indexed == 0
        assert result.skipped == 1

    def test_reindexes_modified_files(
        self,
        workspace: Workspace,
        state_store: StateStore,
        index_manager: IndexManager,
    ) -> None:
        _create_profile(workspace, "Alpha", "## Overview\n\nAlpha is a code tool.\n")

        indexer = IncrementalIndexer(
            workspace=workspace,
            index_manager=index_manager,
            state_store=state_store,
        )
        _run(indexer.index())

        path = workspace.competitors_dir / "alpha.md"
        post = frontmatter.load(str(path))
        post.content = "## Overview\n\nAlpha is a completely new AI platform.\n"
        path.write_text(frontmatter.dumps(post))

        result = _run(indexer.index())

        assert result.indexed == 1
        assert result.skipped == 0

    def test_handles_mix_of_new_and_unchanged(
        self,
        workspace: Workspace,
        state_store: StateStore,
        index_manager: IndexManager,
    ) -> None:
        _create_profile(workspace, "Alpha", "## Overview\n\nAlpha is a code tool.\n")

        indexer = IncrementalIndexer(
            workspace=workspace,
            index_manager=index_manager,
            state_store=state_store,
        )
        _run(indexer.index())

        _create_profile(workspace, "Beta", "## Overview\n\nBeta is a project tool.\n")

        result = _run(indexer.index())

        assert result.indexed == 1
        assert result.skipped == 1

    def test_force_reindexes_everything(
        self,
        workspace: Workspace,
        state_store: StateStore,
        index_manager: IndexManager,
    ) -> None:
        _create_profile(workspace, "Alpha", "## Overview\n\nAlpha is a code tool.\n")
        _create_profile(workspace, "Beta", "## Overview\n\nBeta is a project tool.\n")

        indexer = IncrementalIndexer(
            workspace=workspace,
            index_manager=index_manager,
            state_store=state_store,
        )
        _run(indexer.index())
        result = _run(indexer.index(force=True))

        assert result.indexed == 2
        assert result.skipped == 0

    def test_skips_empty_profiles(
        self,
        workspace: Workspace,
        state_store: StateStore,
    ) -> None:
        client = chromadb.EphemeralClient()
        clean_index = IndexManager(client=client)
        clean_index.clear()
        workspace.create_profile("Empty")

        indexer = IncrementalIndexer(
            workspace=workspace,
            index_manager=clean_index,
            state_store=state_store,
        )
        result = _run(indexer.index())

        assert result.indexed == 0
        assert result.skipped == 0
        assert clean_index.collection_count() == 0
