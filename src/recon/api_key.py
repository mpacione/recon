"""Backward-compatible Anthropic API key helpers.

This shim preserves the older ``recon.api_key`` import surface while
the integration branch standardizes on ``recon.api_keys`` for
multi-provider key management.
"""

from __future__ import annotations

import os
from pathlib import Path

from recon.api_keys import (
    _DEFAULT_GLOBAL_DIR,
    _write_key_to_env,
    is_placeholder_api_key,
    normalize_api_key,
)


def app_config_dir() -> Path:
    """Return the per-user recon config directory."""
    return _DEFAULT_GLOBAL_DIR


def app_env_path() -> Path:
    """Return the per-user recon env file path."""
    return app_config_dir() / ".env"


def load_app_api_key() -> str | None:
    """Load the Anthropic API key from the per-user app config."""
    if not app_env_path().exists():
        return None
    for line in app_env_path().read_text().splitlines():
        if line.startswith("ANTHROPIC_API_KEY="):
            key = normalize_api_key(line.split("=", 1)[1])
            if is_placeholder_api_key(key):
                return None
            return key or None
    return None


def save_app_api_key(api_key: str) -> None:
    """Write the Anthropic API key to the per-user app config."""
    key = normalize_api_key(api_key)
    app_config_dir().mkdir(parents=True, exist_ok=True)
    _write_key_to_env("ANTHROPIC_API_KEY", key, app_env_path())


def load_workspace_api_key(workspace_root: Path) -> str | None:
    """Load the Anthropic API key for a workspace.

    Resolution order:
    1. Workspace-local ``.env`` override
    2. Shell environment ``ANTHROPIC_API_KEY``
    3. App-level ``~/.recon/.env``
    """
    workspace_env = workspace_root / ".env"
    if workspace_env.exists():
        for line in workspace_env.read_text().splitlines():
            if line.startswith("ANTHROPIC_API_KEY="):
                key = normalize_api_key(line.split("=", 1)[1])
                if not is_placeholder_api_key(key):
                    return key or None

    env_key = normalize_api_key(os.environ.get("ANTHROPIC_API_KEY"))
    if env_key and not is_placeholder_api_key(env_key):
        return env_key

    return load_app_api_key()


def workspace_has_api_key(workspace_root: Path) -> bool:
    """Cheap presence check for Anthropic API key access."""
    return load_workspace_api_key(workspace_root) is not None
