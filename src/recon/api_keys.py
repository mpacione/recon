"""API key management for recon.

Loads keys from workspace .env, global ~/.recon/.env, and environment
variables. Saves keys to workspace .env. Keys persist across sessions.

Obvious placeholder values such as ``sk-ant-new`` are ignored so a
fresh workspace scaffold does not shadow a real user key saved at the
app level.
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


def normalize_api_key(value: str | None) -> str:
    """Normalize a raw API key value from env vars or .env files."""
    if value is None:
        return ""
    cleaned = value.strip()
    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in {'"', "'"}:
        cleaned = cleaned[1:-1].strip()
    return cleaned


def is_placeholder_api_key(value: str | None) -> bool:
    """Return True for obvious placeholder or fake keys."""
    cleaned = normalize_api_key(value).lower()
    if not cleaned:
        return True

    obvious_literals = {
        'sk-ant-new',
        'sk-ant-test',
        'sk-ant-placeholder',
        'changeme',
        'your-key-here',
        'your_api_key_here',
    }
    if cleaned in obvious_literals:
        return True

    placeholder_fragments = (
        'placeholder',
        'your-key',
        'your_key',
        'replace-me',
        'replace_me',
        'example',
        'dummy',
    )
    return any(fragment in cleaned for fragment in placeholder_fragments)


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
        value = normalize_api_key(value)
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
        workspace_value = workspace_raw.get(env_var)
        env_value = normalize_api_key(os.environ.get(env_var))
        global_value = global_raw.get(env_var)

        value = None
        if workspace_value and not is_placeholder_api_key(workspace_value):
            value = workspace_value
        elif env_value and not is_placeholder_api_key(env_value):
            value = env_value
        elif global_value and not is_placeholder_api_key(global_value):
            value = global_value

        if value:
            merged[short_name] = value

    return merged


def save_api_key(
    key_name: str,
    key_value: str,
    workspace_root: Path,
    global_env_dir: Path | None = None,
) -> None:
    """Save an API key to BOTH workspace .env and global ~/.recon/.env.

    Writing to both means the key is available for this project AND
    automatically picked up by future new projects without re-entry.
    Preserves existing keys. Creates .env files if they don't exist.
    """
    env_var = _REVERSE_KEY_MAP.get(key_name)
    if env_var is None:
        msg = f"Unknown key name: {key_name}. Must be one of: {list(_REVERSE_KEY_MAP)}"
        raise ValueError(msg)

    # Save to workspace .env
    _write_key_to_env(env_var, key_value, workspace_root / ".env")

    # Also save to global ~/.recon/.env for future projects
    global_dir = global_env_dir or _DEFAULT_GLOBAL_DIR
    global_dir.mkdir(parents=True, exist_ok=True)
    _write_key_to_env(env_var, key_value, global_dir / ".env")


def _write_key_to_env(env_var: str, value: str, env_path: Path) -> None:
    """Write a single key to an .env file, preserving other keys."""
    env_path.parent.mkdir(parents=True, exist_ok=True)
    existing = _parse_env_file(env_path)
    existing[env_var] = value
    lines = [f"{k}={v}\n" for k, v in sorted(existing.items())]
    env_path.write_text("".join(lines))


def mask_api_key(key: str) -> str:
    """Mask the middle of an API key for display."""
    if not key:
        return ""
    if len(key) <= 10:
        return key[:2] + "···" + key[-2:]
    return key[:6] + "···" + key[-4:]
