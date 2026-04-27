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
    # One of "done" (has output), "ready" (recon.yaml exists, no
    # output yet), "new" (path exists but not set up), or "missing"
    # (directory no longer on disk). Mirrors TUI welcome screen so
    # both UIs agree on what each recent project looks like.
    status: str = "new"


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
    kind: str           # "exec_summary" | "theme" | "distilled" | "dossier" | "other"


class ResultsResponse(BaseModel):
    workspace_path: str
    executive_summary_path: str | None = None
    executive_summary_preview: str = ""
    theme_files: list[ThemeFileModel] = Field(default_factory=list)
    output_files: list[OutputFileModel] = Field(default_factory=list)
    total_cost: float = 0.0
    provenance: "RunProvenanceModel | None" = None


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
    # Empty string = "global-only write" (Settings overlay with no active project).
    path: str = ""
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
    name: str = Field(..., min_length=1, max_length=200)
    url: str | None = Field(default=None, max_length=2048)
    blurb: str | None = Field(default=None, max_length=2000)
    own_product: bool = False


# ---------------------------------------------------------------------------
# /api/discover — LLM-powered competitor search
# ---------------------------------------------------------------------------


class DiscoverRequest(BaseModel):
    path: str
    # Optional seed names the agent should steer toward / away from.
    seeds: list[str] = Field(default_factory=list)
    # If true, use the fake LLM client (same mode as the run screen).
    # Lets us exercise the endpoint without consuming API budget.
    use_fake_llm: bool = False


class DiscoveredCandidate(BaseModel):
    name: str
    url: str | None = None
    blurb: str | None = None
    tier: str = "competitor"


class DiscoverResponse(BaseModel):
    candidates: list[DiscoveredCandidate] = Field(default_factory=list)
    domain: str = ""
    # Whether the agent actually used web search or fell back to
    # training-data mode. Surfaced so the UI can tell the user
    # "these may be stale" when web search was unavailable.
    used_web_search: bool = True
    message: str | None = None


# ---------------------------------------------------------------------------
# /api/template
# ---------------------------------------------------------------------------


class TemplateSectionModel(BaseModel):
    key: str
    title: str
    description: str
    selected: bool = False
    when_relevant: str = ""
    allowed_formats: list[str] = Field(default_factory=list)
    preferred_format: str = "prose"


class TemplateResponse(BaseModel):
    sections: list[TemplateSectionModel] = Field(default_factory=list)


class PutTemplateRequest(BaseModel):
    path: str
    section_keys: list[str] = Field(default_factory=list)
    sections: list[TemplateSectionModel] = Field(default_factory=list)


class DiscoveryAuditResponse(BaseModel):
    search_count: int = 0
    last_searched_at: str = ""
    last_candidate_count: int = 0
    last_provider: str = ""


class RunProvenanceModel(BaseModel):
    run_id: str
    status: str = ""
    llm_call_count: int = 0
    source_entry_count: int = 0
    manifest_path: str = ""
    llm_calls_path: str = ""
    sources_path: str = ""


# ---------------------------------------------------------------------------
# /api/confirm
# ---------------------------------------------------------------------------


class ModelOption(BaseModel):
    name: str = ""
    id: str
    label: str
    input_price_per_million: float
    output_price_per_million: float
    description: str
    estimated_total: float
    recommended: bool = False


class PlanSettingsResponse(BaseModel):
    model_name: str = "sonnet"
    workers: int = 5
    verification_mode: str = "standard"


class UpdatePlanSettingsRequest(BaseModel):
    path: str
    model_name: str | None = None
    workers: int | None = None
    verification_mode: str | None = None


class StartRunRequest(BaseModel):
    path: str
    # Hook for a future real-LLM toggle. Ignored by the prototype —
    # the web endpoint currently always uses the fake client.
    use_fake_llm: bool = True
    model: str | None = None
    workers: int | None = None
    verification_mode: str | None = None


class StartRunResponse(BaseModel):
    run_id: str
    events_url: str
    use_fake_llm: bool = True


# ---------------------------------------------------------------------------
# Run history + state
# ---------------------------------------------------------------------------


class RunSummary(BaseModel):
    """One entry in the run history list shown on the Runs tab."""
    run_id: str
    status: str  # "planned" | "running" | "complete" | "failed" | "cancelled"
    created_at: str
    updated_at: str
    total_cost_usd: float = 0.0
    task_count: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    model: str = ""


class RunListResponse(BaseModel):
    runs: list[RunSummary] = Field(default_factory=list)


class RunStateResponse(BaseModel):
    """Current state of a single run — used by the slide-over to reattach
    when the user reloads mid-run. The frontend subscribes to the SSE
    stream for live updates but this endpoint gives the snapshot."""
    run_id: str
    status: str
    created_at: str
    updated_at: str
    total_cost_usd: float = 0.0
    task_count: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    running_tasks: int = 0
    model: str = ""
    events_url: str = ""


class ConfirmResponse(BaseModel):
    competitor_count: int
    estimate_competitor_count: int = 0
    section_keys: list[str] = Field(default_factory=list)
    section_names: list[str] = Field(default_factory=list)
    cost_by_stage: dict[str, float] = Field(default_factory=dict)
    estimated_total: float = 0.0
    eta_seconds: int = 0
    model_options: list[ModelOption] = Field(default_factory=list)
    default_model: str = "sonnet"
    default_workers: int = 5
    default_verification_mode: str = "standard"
    research_per_company: float = 0.0
    enrichment_per_company: float = 0.0
    total_cost_per_company: float = 0.0
    verification_uplift_per_company: float = 0.0
    fixed_themes: float = 0.0
    fixed_summary: float = 0.0
    fixed_total: float = 0.0
    blended_per_company: float = 0.0
    current_tracked_spend: float = 0.0
    run_count: int = 0


ResultsResponse.model_rebuild()
