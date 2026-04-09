"""Workspace management for recon.

The workspace is the user-facing data layer: markdown profiles with YAML
frontmatter, schema definition, project config. Designed to be an
Obsidian vault or part of one.
"""

from __future__ import annotations

import re
from pathlib import Path  # noqa: TCH003 -- used at runtime
from typing import Any

import frontmatter
import yaml

from recon.schema import ReconSchema, load_schema_file


def _slugify(name: str) -> str:
    """Convert a display name to a filesystem-safe slug."""
    slug = name.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    return re.sub(r"-+", "-", slug).strip("-")


def _make_default_schema(
    domain: str,
    company_name: str,
    products: list[str],
) -> dict[str, Any]:
    """Build a minimal valid schema dict for workspace init."""
    return {
        "domain": domain,
        "identity": {
            "company_name": company_name,
            "products": products,
            "decision_context": [],
        },
        "rating_scales": {},
        "sections": [
            {
                "key": "overview",
                "title": "Overview",
                "description": "High-level company and product summary.",
                "allowed_formats": ["prose"],
                "preferred_format": "prose",
            },
        ],
    }


class Workspace:
    """Manages a recon workspace directory."""

    def __init__(self, root: Path, schema: ReconSchema | None = None) -> None:
        self.root = root
        self.schema = schema

    @classmethod
    def init(
        cls,
        root: Path,
        domain: str = "",
        company_name: str = "",
        products: list[str] | None = None,
    ) -> Workspace:
        """Initialize a new workspace directory structure."""
        root.mkdir(parents=True, exist_ok=True)
        (root / "competitors").mkdir(exist_ok=True)
        (root / ".recon").mkdir(exist_ok=True)
        (root / ".recon" / "logs").mkdir(exist_ok=True)

        schema_path = root / "recon.yaml"
        if not schema_path.exists() and domain:
            schema_dict = _make_default_schema(
                domain=domain,
                company_name=company_name,
                products=products or [],
            )
            schema_path.write_text(yaml.dump(schema_dict, default_flow_style=False, sort_keys=False))

        schema = load_schema_file(schema_path) if schema_path.exists() else None
        return cls(root=root, schema=schema)

    @classmethod
    def open(cls, root: Path) -> Workspace:
        """Open an existing workspace."""
        schema_path = root / "recon.yaml"
        schema = load_schema_file(schema_path)
        return cls(root=root, schema=schema)

    @property
    def competitors_dir(self) -> Path:
        return self.root / "competitors"

    def create_profile(
        self,
        name: str,
        own_product: bool = False,
    ) -> Path:
        """Create a new competitor/own-product profile markdown file."""
        slug = _slugify(name)
        profile_path = self.competitors_dir / f"{slug}.md"

        if profile_path.exists():
            msg = f"Profile already exists: {profile_path}"
            raise FileExistsError(msg)

        profile_type = "own_product" if own_product else "competitor"
        post = frontmatter.Post(
            content="",
            **{
                "name": name,
                "type": profile_type,
                "research_status": "scaffold",
                "domain": self.schema.domain if self.schema else "",
            },
        )
        profile_path.write_text(frontmatter.dumps(post))
        return profile_path

    def list_profiles(self) -> list[dict[str, Any]]:
        """List all profiles with their frontmatter metadata."""
        profiles = []
        for path in sorted(self.competitors_dir.glob("*.md")):
            post = frontmatter.load(str(path))
            meta = dict(post.metadata)
            meta["_path"] = path
            meta["_slug"] = path.stem
            profiles.append(meta)
        return profiles

    def _slug_for_name(self, name: str, profiles: list[dict[str, Any]] | None = None) -> str:
        """Find the slug for a profile by its display name."""
        if profiles is None:
            profiles = self.list_profiles()
        for p in profiles:
            if p.get("name") == name:
                return p["_slug"]
        return _slugify(name)

    def read_profile(self, slug: str) -> dict[str, Any] | None:
        """Read a profile by slug. Returns frontmatter dict or None."""
        path = self.competitors_dir / f"{slug}.md"
        if not path.exists():
            return None
        post = frontmatter.load(str(path))
        meta = dict(post.metadata)
        meta["_content"] = post.content
        meta["_path"] = path
        return meta
