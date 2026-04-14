"""Pydantic schemas for the recon web API.

Schema-first per CLAUDE.md: every API response is a typed model.
Schemas live here rather than co-located with the routes so the
frontend can consult one file (and so future contract tests have a
single import target).
"""

from __future__ import annotations

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# /api/health
# ---------------------------------------------------------------------------


class HealthResponse(BaseModel):
    ok: bool
    version: str


# ---------------------------------------------------------------------------
# /api/recents
# ---------------------------------------------------------------------------


class RecentProjectModel(BaseModel):
    path: str
    name: str
    last_opened: str


class RecentProjectsResponse(BaseModel):
    projects: list[RecentProjectModel] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# /api/workspace
# ---------------------------------------------------------------------------


class WorkspaceResponse(BaseModel):
    path: str
    domain: str
    company_name: str
    products: list[str] = Field(default_factory=list)
    competitor_count: int = 0
    section_count: int = 0
    total_cost: float = 0.0
    api_keys: dict[str, bool] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# /api/dashboard
# ---------------------------------------------------------------------------


class CompetitorRow(BaseModel):
    name: str
    type: str = "competitor"
    status: str = "unknown"
    slug: str = ""


class SectionStatusModel(BaseModel):
    key: str
    title: str
    completed: int = 0
    total: int = 0


class DashboardResponse(BaseModel):
    domain: str
    company_name: str
    total_competitors: int = 0
    status_counts: dict[str, int] = Field(default_factory=dict)
    competitor_rows: list[CompetitorRow] = Field(default_factory=list)
    section_statuses: list[SectionStatusModel] = Field(default_factory=list)
    total_sections: int = 0
    theme_count: int = 0
    themes_selected: int = 0
    index_chunks: int = 0
    last_indexed: str = ""
    total_cost: float = 0.0
    last_run_cost: float = 0.0
    run_count: int = 0


# ---------------------------------------------------------------------------
# /api/results
# ---------------------------------------------------------------------------


class ThemeFileModel(BaseModel):
    name: str           # slug (from filename without .md)
    title: str          # human-readable from the markdown's first H1, falls back to slug
    path: str           # absolute path to the file
    distilled_path: str | None = None  # themes/distilled/<slug>.md if present


class OutputFileModel(BaseModel):
    name: str
    path: str
    kind: str           # "exec_summary" | "theme" | "distilled" | "other"


class ResultsResponse(BaseModel):
    workspace_path: str
    executive_summary_path: str | None = None
    executive_summary_preview: str = ""
    theme_files: list[ThemeFileModel] = Field(default_factory=list)
    output_files: list[OutputFileModel] = Field(default_factory=list)
    total_cost: float = 0.0


# ---------------------------------------------------------------------------
# POST /api/workspaces
# ---------------------------------------------------------------------------


class CreateWorkspaceRequest(BaseModel):
    description: str = Field(..., min_length=1)
    path: str | None = None  # If omitted, derived from company_name slug
    company_name: str | None = None  # If omitted, heuristically extracted
    domain: str | None = None  # If omitted, falls back to description
    products: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# /api/api-keys
# ---------------------------------------------------------------------------


class SaveApiKeyRequest(BaseModel):
    path: str
    name: str  # Logical provider name: "anthropic" | "google_ai"
    value: str = Field(..., min_length=1)


# ---------------------------------------------------------------------------
# /api/competitors
# ---------------------------------------------------------------------------


class CompetitorModel(BaseModel):
    name: str
    slug: str
    type: str = "competitor"
    status: str = "scaffold"
    url: str | None = None
    blurb: str | None = None


class CompetitorListResponse(BaseModel):
    competitors: list[CompetitorModel] = Field(default_factory=list)


class CreateCompetitorRequest(BaseModel):
    path: str
    name: str = Field(..., min_length=1)
    url: str | None = None
    blurb: str | None = None
    own_product: bool = False
