"""API key management for recon.

Loads keys from workspace .env, global ~/.recon/.env, and environment
variables. Saves keys to workspace .env. Keys persist across sessions.
"""

from __future__ import annotations

import os
from pathlib import Path

_KEY_MAP = {
    "ANTHROPIC_API_KEY": "anthropic",
    "GOOGLE_AI_API_KEY": "google_ai",
}

_REVERSE_KEY_MAP = {v: k for k, v in _KEY_MAP.items()}

_DEFAULT_GLOBAL_DIR = Path.home() / ".recon"


def _parse_env_file(path: Path) -> dict[str, str]:
    """Parse a .env file into a dict of raw env var name → value."""
    if not path.exists():
        return {}
    result: dict[str, str] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("\"'")
        if key and value:
            result[key] = value
    return result


def load_api_keys(
    workspace_root: Path,
    global_env_dir: Path | None = None,
) -> dict[str, str]:
    """Load API keys from workspace .env, global .env, and env vars.

    Priority (highest first):
    1. Workspace .env
    2. Environment variables
    3. Global ~/.recon/.env

    Returns a dict of short names ("anthropic", "google_ai") → key values.
    """
    global_dir = global_env_dir or _DEFAULT_GLOBAL_DIR

    global_raw = _parse_env_file(global_dir / ".env")
    workspace_raw = _parse_env_file(workspace_root / ".env")

    merged: dict[str, str] = {}

    for env_var, short_name in _KEY_MAP.items():
        value = (
            workspace_raw.get(env_var)
            or os.environ.get(env_var)
            or global_raw.get(env_var)
        )
        if value:
            merged[short_name] = value

    return merged


def save_api_key(
    key_name: str,
    key_value: str,
    workspace_root: Path,
) -> None:
    """Save an API key to the workspace .env file.

    Preserves existing keys. Creates the .env file if it doesn't exist.
    """
    env_var = _REVERSE_KEY_MAP.get(key_name)
    if env_var is None:
        msg = f"Unknown key name: {key_name}. Must be one of: {list(_REVERSE_KEY_MAP)}"
        raise ValueError(msg)

    env_path = workspace_root / ".env"
    existing = _parse_env_file(env_path)
    existing[env_var] = key_value

    lines = [f"{k}={v}\n" for k, v in sorted(existing.items())]
    env_path.write_text("".join(lines))


def mask_api_key(key: str) -> str:
    """Mask the middle of an API key for display."""
    if not key:
        return ""
    if len(key) <= 10:
        return key[:2] + "···" + key[-2:]
    return key[:6] + "···" + key[-4:]
