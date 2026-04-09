"""Shared test fixtures for recon."""

import copy
from pathlib import Path

import pytest
import yaml

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
    schema_path = workspace / "recon.yaml"
    schema_path.write_text(yaml.dump(MINIMAL_SCHEMA_DICT, default_flow_style=False))
    return workspace
