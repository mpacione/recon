"""Dynamic schema design for recon.

Phase (a): LLM selects from a predefined pool of ~15 sections
based on the user's description and competitor list.

Phase (c): Custom section generation from a user's freeform prompt.
"""

from __future__ import annotations

import re
from typing import Any

from recon.llm import LLMClient  # noqa: TCH001
from recon.logging import get_logger
from recon.section_library import all_sections

_log = get_logger(__name__)


SECTION_POOL: list[dict[str, str]] = [
    {
        "key": str(section["key"]),
        "title": str(section["title"]),
        "description": str(section["description"]),
        "when_relevant": str(section.get("when_relevant", "often relevant")),
    }
    for section in all_sections()
]

_POOL_BY_KEY = {s["key"]: s for s in SECTION_POOL}

_DEFAULT_SECTIONS = [
    "overview",
    "capabilities",
    "pricing",
    "customer_segments",
    "distribution_gtm",
    "integration",
    "enterprise",
    "head_to_head",
    "strategic_notes",
]

_SELECT_SYSTEM_PROMPT = """\
You are a competitive intelligence research planner. Given a description of a \
company and its competitors, select the most relevant research sections from \
the available pool.

Return ONLY a comma-separated list of section keys. No explanation, no JSON.

Available sections:
{pool_description}

Rules:
- Select 5-8 sections that are most relevant to this specific space.
- Always include: overview, pricing, customer_segments.
- Only include sections that will produce meaningful differentiated research.
- Prefer sections that highlight competitive dynamics in this specific industry."""

_CUSTOM_SECTION_PROMPT = """\
You are designing a research section for a competitive intelligence report. \
Given the user's description, create a structured section definition.

Return exactly three lines:
key: snake_case_identifier
title: Short Title (2-5 words)
description: One sentence describing what to research

No other text. No explanation."""


async def design_sections(
    description: str,
    competitors: list[str],
    llm_client: LLMClient,
) -> list[dict[str, Any]]:
    """Select relevant sections from the pool for this space.

    Uses the LLM to choose which sections are relevant. Falls back
    to a sensible default if the LLM call fails.
    """
    pool_desc = "\n".join(
        f"- {s['key']}: {s['title']} — {s['description']} (relevant for: {s['when_relevant']})"
        for s in SECTION_POOL
    )

    system_prompt = _SELECT_SYSTEM_PROMPT.format(pool_description=pool_desc)
    competitor_list = ", ".join(competitors[:20])
    user_prompt = (
        f"Company/space: {description}\n"
        f"Competitors found: {competitor_list}\n\n"
        f"Which sections should we research?"
    )

    try:
        response = await llm_client.complete(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=200,
        )
        selected_keys = _parse_key_list(response.text)
    except Exception:
        _log.exception("design_sections LLM call failed, using defaults")
        selected_keys = list(_DEFAULT_SECTIONS)

    # Always include overview
    if "overview" not in selected_keys:
        selected_keys.insert(0, "overview")

    # Build section list from pool
    sections: list[dict[str, Any]] = []
    seen: set[str] = set()
    for key in selected_keys:
        if key in _POOL_BY_KEY and key not in seen:
            seen.add(key)
            section = dict(_POOL_BY_KEY[key])
            section["selected"] = True
            sections.append(section)

    # If nothing matched, fall back to defaults
    if len(sections) < 3:
        sections = []
        for key in _DEFAULT_SECTIONS:
            if key in _POOL_BY_KEY:
                section = dict(_POOL_BY_KEY[key])
                section["selected"] = True
                sections.append(section)

    return sections


async def create_custom_section(
    description: str,
    llm_client: LLMClient,
) -> dict[str, Any]:
    """Generate a section definition from a user's freeform prompt.

    Returns a dict with key, title, description, selected=True.
    Falls back to a mechanical extraction if the LLM call fails.
    """
    try:
        response = await llm_client.complete(
            system_prompt=_CUSTOM_SECTION_PROMPT,
            user_prompt=description,
            max_tokens=100,
        )
        return _parse_section_response(response.text, description)
    except Exception:
        _log.exception("create_custom_section LLM call failed, using fallback")
        return _fallback_section(description)


def _parse_key_list(text: str) -> list[str]:
    """Parse a comma-separated list of section keys from LLM response."""
    cleaned = text.strip().lower()
    # Handle various formats: comma-separated, newline-separated, numbered
    keys = re.split(r"[,\n]+", cleaned)
    return [
        k.strip().strip("- .0123456789)")
        for k in keys
        if k.strip() and not k.strip().startswith("#")
    ]


def _parse_section_response(text: str, original: str) -> dict[str, Any]:
    """Parse the 3-line section definition from LLM response."""
    result: dict[str, Any] = {"selected": True}

    for line in text.strip().splitlines():
        line = line.strip()
        if line.lower().startswith("key:"):
            result["key"] = line.split(":", 1)[1].strip()
        elif line.lower().startswith("title:"):
            result["title"] = line.split(":", 1)[1].strip()
        elif line.lower().startswith("description:"):
            result["description"] = line.split(":", 1)[1].strip()

    if "key" not in result or "title" not in result:
        return _fallback_section(original)

    if "description" not in result:
        result["description"] = original

    return result


def _fallback_section(description: str) -> dict[str, Any]:
    """Mechanical fallback when LLM is unavailable."""
    words = description.strip().split()
    title = " ".join(w.capitalize() for w in words[:5])
    key = re.sub(r"[^\w]+", "_", title.lower()).strip("_")
    return {
        "key": key,
        "title": title,
        "description": description,
        "selected": True,
    }
