"""Workspace-local provenance logging for recon.

Persists run and discovery audit trails under ``.recon/`` so projects
remain portable, inspectable, and restart-safe.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

import yaml

from recon.llm import LLMResponse

_URL_RE = re.compile(r"https?://[^\s)\]>]+")


def extract_urls(text: str) -> list[str]:
    """Extract and deduplicate URLs from freeform text."""
    seen: set[str] = set()
    urls: list[str] = []
    for match in _URL_RE.findall(text):
        if match not in seen:
            seen.add(match)
            urls.append(match)
    return urls


def _jsonable(value: Any) -> Any:
    """Best-effort conversion to a JSON/YAML-friendly shape."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value):
        return {k: _jsonable(v) for k, v in asdict(value).items()}
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v) for v in value]
    if hasattr(value, "model_dump"):
        try:
            return _jsonable(value.model_dump())
        except Exception:
            pass
    if hasattr(value, "to_dict"):
        try:
            return _jsonable(value.to_dict())
        except Exception:
            pass
    if hasattr(value, "__dict__"):
        try:
            return {
                k: _jsonable(v)
                for k, v in vars(value).items()
                if not k.startswith("_")
            }
        except Exception:
            pass
    return str(value)


def _timestamp() -> str:
    return dt.datetime.now(dt.UTC).isoformat()


class ProvenanceRecorder:
    """Append-only provenance writer rooted in a workspace."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    @classmethod
    def for_run(cls, workspace_root: Path, run_id: str) -> ProvenanceRecorder:
        return cls(workspace_root / ".recon" / "runs" / run_id)

    @classmethod
    def for_discovery(cls, workspace_root: Path) -> ProvenanceRecorder:
        return cls(workspace_root / ".recon" / "discovery")

    def write_yaml(self, name: str, payload: dict[str, Any]) -> None:
        path = self.root / name
        existing: dict[str, Any] = {}
        if path.exists():
            try:
                loaded = yaml.safe_load(path.read_text()) or {}
                if isinstance(loaded, dict):
                    existing = loaded
            except Exception:
                existing = {}
        path.write_text(
            yaml.safe_dump(
                _jsonable({**existing, **payload}),
                sort_keys=False,
                allow_unicode=False,
            ),
        )

    def append_jsonl(self, name: str, payload: dict[str, Any]) -> None:
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(_jsonable(payload), ensure_ascii=True) + "\n")

    def record_llm_call(
        self,
        *,
        actor: str,
        system_prompt: str,
        user_prompt: str,
        tools: list[dict[str, Any]] | None,
        response: LLMResponse,
        context: dict[str, Any] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        self.append_jsonl(
            "llm_calls.jsonl",
            {
                "timestamp": _timestamp(),
                "actor": actor,
                "context": context or {},
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "tools": tools or [],
                "response": {
                    "model": response.model,
                    "stop_reason": response.stop_reason,
                    "input_tokens": response.input_tokens,
                    "output_tokens": response.output_tokens,
                    "text": response.text,
                    "content_blocks": response.content_blocks,
                    "metadata": response.metadata,
                },
                "extra": extra or {},
            },
        )

    def record_sources(
        self,
        *,
        actor: str,
        context: dict[str, Any] | None = None,
        cited_urls: list[str] | None = None,
        selected_urls: list[str] | None = None,
        source_results: list[dict[str, Any]] | None = None,
        notes: str = "",
        extra: dict[str, Any] | None = None,
    ) -> None:
        self.append_jsonl(
            "sources.jsonl",
            {
                "timestamp": _timestamp(),
                "actor": actor,
                "context": context or {},
                "cited_urls": cited_urls or [],
                "selected_urls": selected_urls or [],
                "source_results": source_results or [],
                "notes": notes,
                "extra": extra or {},
            },
        )

    def record_discovery_search(
        self,
        *,
        provider: str,
        domain: str,
        round_count: int,
        system_prompt: str,
        user_prompt: str,
        tools: list[dict[str, Any]] | None,
        response: LLMResponse,
        candidates: list[dict[str, Any]],
    ) -> None:
        self.append_jsonl(
            "searches.jsonl",
            {
                "timestamp": _timestamp(),
                "provider": provider,
                "domain": domain,
                "round_count": round_count,
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "tools": tools or [],
                "response": {
                    "model": response.model,
                    "stop_reason": response.stop_reason,
                    "input_tokens": response.input_tokens,
                    "output_tokens": response.output_tokens,
                    "text": response.text,
                    "content_blocks": response.content_blocks,
                    "metadata": response.metadata,
                },
                "candidates": candidates,
            },
        )
