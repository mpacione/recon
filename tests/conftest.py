"""Shared test fixtures for recon."""

import contextlib
import copy
from pathlib import Path

import pytest
import yaml


@pytest.fixture(autouse=True)
def _clear_chromadb_system_cache():
    """Drop ChromaDB's process-wide system-instance cache after each test.

    ChromaDB caches a SharedSystemClient per persist_dir for the
    process lifetime. When tests use ``PersistentClient`` against a
    pytest tmp_path that gets removed after the test, the cached
    Rust segment readers can hold stale file handles open and a
    later test then crashes with "Failed to pull logs from the log
    store" or SQLITE_CANTOPEN. Clearing the cache between tests
    forces a fresh client on the next access and releases the
    underlying handles.
    """
    yield
    with contextlib.suppress(Exception):
        from chromadb.api.client import SharedSystemClient

        SharedSystemClient.clear_system_cache()

MINIMAL_SCHEMA_DICT = {
    "domain": "Developer Tools",
    "identity": {
        "company_name": "Acme Corp",
        "products": ["Acme IDE"],
        "decision_context": ["build-vs-buy"],
    },
    "rating_scales": {
        "capability": {
            "name": "Capability Rating",
            "values": ["1", "2", "3", "4", "5"],
            "never_use": ["emoji", "stars"],
        },
    },
    "sections": [
        {
            "key": "overview",
            "title": "Overview",
            "description": "High-level company and product summary.",
            "evidence_types": ["factual", "analytical"],
            "allowed_formats": ["prose"],
            "preferred_format": "prose",
        },
    ],
}


@pytest.fixture()
def minimal_schema_dict() -> dict:
    """Return a minimal valid schema as a dict (deep copy, safe to mutate)."""
    return copy.deepcopy(MINIMAL_SCHEMA_DICT)


@pytest.fixture()
def tmp_workspace(tmp_path: Path) -> Path:
    """Create a temporary workspace directory with a minimal recon.yaml."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "competitors").mkdir()
    (workspace / ".recon").mkdir()
    (workspace / ".recon" / "logs").mkdir()
    schema_path = workspace / "recon.yaml"
    schema_path.write_text(yaml.dump(MINIMAL_SCHEMA_DICT, default_flow_style=False))
    return workspace
