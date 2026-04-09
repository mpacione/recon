"""Prompt composer for recon.

Assembles prompts from composable fragments: base system prompt +
per-section fragment + example output. All prompts are generated
from schema metadata at composition time -- no static prompt files.
"""

from __future__ import annotations

from recon.schema import ReconSchema  # noqa: TCH001 -- used at runtime


def compose_system_prompt(schema: ReconSchema) -> str:
    """Compose the base system prompt from schema metadata."""
    return f"""You are a competitive intelligence research agent analyzing the {schema.domain} landscape.

Your research must be:
- Factual and evidence-based
- Sourced with URLs and access dates
- Current (prefer sources from the last 12 months)

Rules:
- Never use emoji anywhere in your output
- Every factual claim must have a source citation
- Include a Sources section at the end listing all references
- Use the exact format types specified for each section
- If information is unavailable, state that explicitly rather than speculating"""


def compose_research_prompt(
    schema: ReconSchema,
    section_key: str,
    competitor_name: str,
) -> str:
    """Compose a research prompt for a specific section and competitor."""
    section = schema.get_section(section_key)
    if section is None:
        msg = f"Unknown section key: '{section_key}'"
        raise KeyError(msg)

    parts: list[str] = []

    parts.append(f"Research the **{section.title}** section for **{competitor_name}**.")
    parts.append(f"\n{section.description}")

    if section.evidence_types:
        parts.append(f"\nEvidence types to include: {', '.join(section.evidence_types)}.")

    parts.append(f"\nOutput format: {section.preferred_format}")
    parts.append(f"Allowed formats: {', '.join(section.allowed_formats)}")

    if section.format_spec:
        spec = section.format_spec

        if spec.columns:
            parts.append(f"\nTable columns: {' | '.join(spec.columns)}")

        if spec.word_count_range:
            parts.append(f"\nTarget word count: {spec.word_count_range[0]}-{spec.word_count_range[1]} words.")

        if spec.rating_scale_ref:
            scale = schema.rating_scales.get(spec.rating_scale_ref)
            if scale:
                parts.append(f"\nRating scale ({scale.name}): {', '.join(scale.values)}")
                if scale.never_use:
                    parts.append(f"Never use: {', '.join(scale.never_use)}")

    if section.source_preferences:
        prefs = section.source_preferences

        if prefs.primary:
            parts.append(f"\nPreferred sources: {', '.join(prefs.primary)}")
        if prefs.secondary:
            parts.append(f"Secondary sources: {', '.join(prefs.secondary)}")
        if prefs.avoid:
            parts.append(f"Avoid: {', '.join(prefs.avoid)}")

    if section.search_guidance:
        parts.append(f"\nSearch guidance: {section.search_guidance}")

    return "\n".join(parts)
