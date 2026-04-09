"""Schema system for recon.

Parses recon.yaml into typed Pydantic models. The schema drives prompts,
validation, format constraints, cost estimation, and verification tiers.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path  # noqa: TCH003 -- used at runtime in load_schema_file
from typing import Any, Literal

import yaml
from pydantic import BaseModel, model_validator

FormatType = Literal[
    "table",
    "rated_table",
    "status_table",
    "comparison_table",
    "key_value",
    "prose",
    "bullet_list",
    "numbered_list",
]

VALID_FORMAT_TYPES: frozenset[str] = frozenset(FormatType.__args__)  # type: ignore[attr-defined]


class Identity(BaseModel):
    company_name: str
    products: list[str]
    decision_context: list[str]
    own_product: bool = False


class FormatSpec(BaseModel):
    columns: list[str] = []
    word_count_range: list[int] = []
    rating_scale_ref: str | None = None


class SourcePreferences(BaseModel):
    primary: list[str] = []
    secondary: list[str] = []
    avoid: list[str] = []
    source_recency_days: int | None = None


class VerificationTier(StrEnum):
    STANDARD = "standard"
    VERIFIED = "verified"
    DEEP = "deep"


class SectionDefinition(BaseModel):
    key: str
    title: str
    description: str
    evidence_types: list[str] = []
    allowed_formats: list[str]
    preferred_format: str
    format_spec: FormatSpec | None = None
    source_preferences: SourcePreferences | None = None
    search_guidance: str | None = None
    verification_tier: VerificationTier = VerificationTier.STANDARD

    @model_validator(mode="after")
    def validate_formats(self) -> SectionDefinition:
        invalid = set(self.allowed_formats) - VALID_FORMAT_TYPES
        if invalid:
            msg = f"Invalid format types: {', '.join(sorted(invalid))}"
            raise ValueError(msg)

        if self.preferred_format not in self.allowed_formats:
            msg = f"preferred_format '{self.preferred_format}' must be in allowed_formats {self.allowed_formats}"
            raise ValueError(msg)

        return self


class RatingScale(BaseModel):
    name: str
    values: list[str]
    never_use: list[str] = []


class ReconSchema(BaseModel):
    domain: str
    identity: Identity
    sections: list[SectionDefinition]
    rating_scales: dict[str, RatingScale] = {}

    @model_validator(mode="after")
    def validate_cross_references(self) -> ReconSchema:
        keys = [s.key for s in self.sections]
        duplicates = [k for k in keys if keys.count(k) > 1]
        if duplicates:
            msg = f"Duplicate section keys: {', '.join(set(duplicates))}"
            raise ValueError(msg)

        for section in self.sections:
            if section.format_spec and section.format_spec.rating_scale_ref:
                ref = section.format_spec.rating_scale_ref
                if ref not in self.rating_scales:
                    msg = f"Section '{section.key}' references unknown rating scale '{ref}'"
                    raise ValueError(msg)

        return self

    def get_section(self, key: str) -> SectionDefinition | None:
        """Look up a section by its key."""
        for section in self.sections:
            if section.key == key:
                return section
        return None


def parse_schema(data: dict[str, Any]) -> ReconSchema:
    """Parse a raw dict (from YAML) into a validated ReconSchema."""
    return ReconSchema.model_validate(data)


def load_schema_file(path: Path) -> ReconSchema:
    """Load and parse a recon.yaml file from disk."""
    if not path.exists():
        msg = f"Schema file not found: {path}"
        raise FileNotFoundError(msg)

    raw = yaml.safe_load(path.read_text())
    return parse_schema(raw)
