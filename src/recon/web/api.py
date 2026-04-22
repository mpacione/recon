"""FastAPI app for the recon web UI.

Phase 1: serves the SPA shell + a minimal health endpoint. Subsequent
phases add the read-only state API, discovery, template, run, and
results endpoints (see ``design/web-ui-spec.md`` §4 for the full route
table).
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

import yaml

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse

from recon.web.events_bridge import EventBridge
from recon.web.schemas import (
    CompetitorListResponse,
    CompetitorModel,
    CompetitorRow,
    ConfirmResponse,
    CreateCompetitorRequest,
    CreateWorkspaceRequest,
    DashboardResponse,
    DiscoverRequest,
    DiscoverResponse,
    DiscoveredCandidate,
    HealthResponse,
    ModelOption,
    OutputFileModel,
    PutTemplateRequest,
    RecentProjectModel,
    RecentProjectsResponse,
    ResultsResponse,
    RunListResponse,
    RunStateResponse,
    RunSummary,
    SaveApiKeyRequest,
    SectionStatusModel,
    StartRunRequest,
    StartRunResponse,
    TemplateResponse,
    TemplateSectionModel,
    ThemeFileModel,
    WorkspaceResponse,
)

_STATIC_DIR = Path(__file__).parent / "static"

# Default parent for newly-created workspaces when the request doesn't
# pin one. We used to put workspaces in ~/recon which collides with
# the v1 recon source checkout on developer machines — that was a
# real bug report. Tests monkeypatch this to redirect into tmp_path.
_DEFAULT_WORKSPACES_PARENT = Path.home() / "recon-workspaces"

# Confirm-screen cost model. Mirrors the numbers in design/v2-spec.md
# §Screen 6. These are rough per-call/per-profile/per-theme averages
# and will be tightened when we wire real cost telemetry back in.
_COST_PER_SECTION_USD = 0.30
_COST_PER_ENRICH_PROFILE_USD = 0.30
_COST_PER_THEME_USD = 0.30
_COST_PER_SUMMARY_USD = 0.30
_DEFAULT_THEME_COUNT = 5
_ENRICHMENT_PASSES = 3

# Wall-clock ETA model: per research-section seconds, divided by
# worker count. Enrichment + synthesis add fixed overhead.
_SECONDS_PER_SECTION = 15.0
_ENRICHMENT_OVERHEAD_S = 60.0
_SYNTHESIS_OVERHEAD_S = 45.0


def _project_status(path_str: str) -> str:
    """Classify a recent project by its on-disk state.

    Mirrors ``WelcomeScreen._project_status`` from the TUI so both UIs
    surface the same status on the recent-projects list. Returning a
    plain string keeps the API stable if we ever want to grow the set
    of states; the UI maps strings to markers/colors.

    - ``missing``: directory is no longer on disk (broken recent).
    - ``done``:    ``output/`` exists and has at least one artifact.
    - ``ready``:   workspace is configured (``recon.yaml``) but no
                   output yet — user can resume into run/confirm.
    - ``new``:     path exists but neither condition above applies.
    """
    project_path = Path(path_str)
    if not project_path.exists():
        return "missing"
    output_dir = project_path / "output"
    if output_dir.exists() and any(output_dir.iterdir()):
        return "done"
    if (project_path / "recon.yaml").exists():
        return "ready"
    return "new"

# Canonical Claude 4 tier list for the Confirm screen. Prices are in
# USD per million tokens. Keep in sync with recon.cost.ModelPricing.
_MODEL_CATALOG: list[dict] = [
    {
        "id": "claude-sonnet-4-20250514",
        "label": "Sonnet 4",
        "description": "recommended",
        "input_price_per_million": 3.0,
        "output_price_per_million": 15.0,
        "recommended": True,
    },
    {
        "id": "claude-opus-4-20250805",
        "label": "Opus 4",
        "description": "deeper analysis",
        "input_price_per_million": 15.0,
        "output_price_per_million": 75.0,
        "recommended": False,
    },
    {
        "id": "claude-haiku-4-20250514",
        "label": "Haiku 4",
        "description": "faster, less depth",
        "input_price_per_million": 0.8,
        "output_price_per_million": 4.0,
        "recommended": False,
    },
]
# Sonnet = baseline for the cost model; other tiers scale the total
# by the ratio of their blended price to Sonnet's.
_BASELINE_MODEL_ID = "claude-sonnet-4-20250514"

# Provider names recognized by the api-keys endpoints. Mirrors
# recon.api_keys._KEY_MAP keys (the lowercase aliases).
_RECOGNIZED_API_KEY_NAMES: frozenset[str] = frozenset({"anthropic", "google_ai"})

# Cap the executive-summary preview so the JSON payload stays small
# even for runs that produced huge summaries. The full file is
# available via /api/files (Phase 7).
_PREVIEW_MAX_CHARS = 2000

# Strip yaml frontmatter from the start of a markdown file when
# generating a preview; users want prose, not metadata.
_FRONTMATTER_RE = re.compile(r"^---\n.*?\n---\n", re.DOTALL)
# First H1 header (used as the human-readable theme title).
_H1_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)


def _package_version() -> str:
    """Return the recon-cli package version, or ``"unknown"`` if unavailable.

    During editable installs (``pip install -e .``) the version is
    always available; the fallback is just defensive.
    """
    try:
        return version("recon-cli")
    except PackageNotFoundError:  # pragma: no cover - defensive
        return "unknown"


def create_app() -> FastAPI:
    """Build a FastAPI app instance.

    A factory rather than a module-level singleton so tests can spin
    up isolated apps (see ``tests/web/test_api_smoke.py``) and the
    server can pick up code changes on reload.
    """
    # One bridge per app instance. The bridge subscribes to the
    # process-wide event bus once and fans events to N async clients.
    # Created here so the lifespan handler can close it cleanly on
    # shutdown.
    bridge = EventBridge()

    @asynccontextmanager
    async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            bridge.close()

    app = FastAPI(
        title="recon",
        description="Local web UI for the recon competitive intelligence CLI.",
        version=_package_version(),
        # Disable the default docs UIs — this is a private, local-only
        # surface and the route table lives in design/web-ui-spec.md.
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=_lifespan,
    )
    app.state.event_bridge = bridge

    app.mount(
        "/static",
        StaticFiles(directory=str(_STATIC_DIR)),
        name="static",
    )

    @app.get("/api/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        """Liveness check. Used by the CLI to confirm the server booted."""
        return HealthResponse(ok=True, version=_package_version())

    @app.get("/api/recents", response_model=RecentProjectsResponse)
    async def recents() -> RecentProjectsResponse:
        """Return recent projects from ~/.recon/recent.json.

        Reuses the TUI's RecentProjectsManager so both UIs see the
        same list. Conftest overrides ``_DEFAULT_RECENT_PATH`` per
        test so this never touches the real file in the test suite.

        Note: The Phase 2 spec flags lifting RecentProjectsManager
        out of tui/ into a top-level module so the web layer doesn't
        depend on tui/. Tracked in design/web-ui-spec.md §9.
        """
        from recon.tui.screens.welcome import (
            _DEFAULT_RECENT_PATH,
            RecentProjectsManager,
        )

        manager = RecentProjectsManager(_DEFAULT_RECENT_PATH)
        projects = manager.load()
        return RecentProjectsResponse(
            projects=[
                RecentProjectModel(
                    path=p.path,
                    name=p.name,
                    last_opened=p.last_opened,
                    status=_project_status(p.path),
                )
                for p in projects
            ],
        )

    @app.get("/api/workspace", response_model=WorkspaceResponse)
    async def workspace(path: str = Query(..., description="Workspace directory path")) -> WorkspaceResponse:
        """Workspace metadata: domain, company, sections, costs, API keys."""
        ws = _open_workspace(path)
        schema = ws.schema
        domain = schema.domain if schema else ""
        company_name = schema.identity.company_name if schema else ""
        products = list(schema.identity.products) if schema else []
        section_count = len(schema.sections) if schema else 0

        cost_summary = _safe_cost_summary(ws)

        return WorkspaceResponse(
            path=str(ws.root),
            domain=domain,
            company_name=company_name,
            products=products,
            competitor_count=len(ws.list_profiles()),
            section_count=section_count,
            total_cost=cost_summary["total_cost"],
            api_keys=_load_api_key_status(ws.root),
        )

    @app.get("/api/dashboard", response_model=DashboardResponse)
    async def dashboard(path: str = Query(..., description="Workspace directory path")) -> DashboardResponse:
        """Full dashboard data — same shape the TUI dashboard renders."""
        from recon.tui.models.dashboard import build_dashboard_data

        ws = _open_workspace(path)
        data = build_dashboard_data(ws)
        return DashboardResponse(
            domain=data.domain,
            company_name=data.company_name,
            total_competitors=data.total_competitors,
            status_counts=data.status_counts,
            competitor_rows=[
                CompetitorRow(**row) for row in data.competitor_rows
            ],
            section_statuses=[
                SectionStatusModel(
                    key=s.key, title=s.title,
                    completed=s.completed, total=s.total,
                )
                for s in data.section_statuses
            ],
            total_sections=data.total_sections,
            theme_count=data.theme_count,
            themes_selected=data.themes_selected,
            index_chunks=data.index_chunks,
            last_indexed=data.last_indexed,
            total_cost=data.total_cost,
            last_run_cost=data.last_run_cost,
            run_count=data.run_count,
        )

    @app.get("/api/results", response_model=ResultsResponse)
    async def results(path: str = Query(..., description="Workspace directory path")) -> ResultsResponse:
        """Post-run summary: exec summary preview + theme/output files."""
        ws = _open_workspace(path)
        return _build_results_response(ws.root)

    @app.post("/api/reveal")
    async def reveal_in_finder(payload: dict[str, str]) -> dict[str, bool]:
        """Open a file or directory in the host's file manager.

        Constrained to paths under the workspace root so we never hand
        ``open`` an attacker-controlled path. macOS uses ``open -R`` to
        reveal (select) the target; other platforms fall through to the
        OS opener.
        """
        workspace_raw = payload.get("path", "")
        target_raw = payload.get("target", "")
        if not workspace_raw or not target_raw:
            raise HTTPException(status_code=400, detail="path and target required")
        ws = _open_workspace(workspace_raw)
        target = Path(target_raw).resolve()
        try:
            target.relative_to(ws.root.resolve())
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="target outside workspace") from exc
        if not target.exists():
            raise HTTPException(status_code=404, detail=f"{target} does not exist")

        import subprocess
        import sys

        if sys.platform == "darwin":
            subprocess.Popen(["open", "-R", str(target)])  # noqa: S603,S607
        elif sys.platform.startswith("linux"):
            subprocess.Popen(["xdg-open", str(target.parent)])  # noqa: S603,S607
        elif sys.platform.startswith("win"):
            subprocess.Popen(["explorer", f"/select,{target}"])  # noqa: S603,S607
        else:
            raise HTTPException(status_code=501, detail=f"reveal not supported on {sys.platform}")
        return {"ok": True}

    @app.post("/api/workspaces", response_model=WorkspaceResponse, status_code=201)
    async def create_workspace(payload: CreateWorkspaceRequest) -> WorkspaceResponse:
        """Create a workspace from a freeform description.

        Description parsing in Phase 5 is heuristic-only (offline) so
        the flow works without an API key. LLM-backed parsing arrives
        with the discovery agent in a later phase.
        """
        from recon.workspace import Workspace

        # Safety: cap description length so the heuristic slug can't
        # blow past filesystem limits (255 chars on most filesystems,
        # with margin for parent path). A hostile or truncated paste
        # should 400, not 500.
        if len(payload.description) > 1000:
            raise HTTPException(
                status_code=400,
                detail="description too long (max 1000 characters)",
            )

        company_name = payload.company_name or _heuristic_company_name(payload.description)
        domain = payload.domain or payload.description
        # Clamp the slug to 60 chars — long enough for readable names,
        # short enough to stay well under the 255-char filesystem cap
        # even with a -99 collision suffix.
        slug = _slugify_for_path(company_name)[:60].rstrip("-") or "project"

        if payload.path:
            # Resolve to catch ../ escapes and fail early on invalid
            # paths. The filesystem's permission model is the real
            # gate on where writes can happen — this resolve just
            # keeps errors readable (OSError → 400, not 500).
            try:
                target = Path(payload.path).expanduser().resolve(strict=False)
            except (OSError, RuntimeError) as exc:
                raise HTTPException(
                    status_code=400,
                    detail=f"invalid path: {exc}",
                ) from exc
            # Explicit path: a collision is a user error worth surfacing.
            if (target / "recon.yaml").exists():
                raise HTTPException(
                    status_code=409,
                    detail=f"workspace already exists at {target}",
                )
        else:
            # Derived path: never fail on collision. Auto-suffix until we
            # find a free slug so repeat "new project" clicks from the
            # same description land in fresh directories instead of
            # surfacing a raw 409. The user can see and override the
            # final path in the workspace header after creation.
            target = _DEFAULT_WORKSPACES_PARENT / slug
            suffix = 2
            while (target / "recon.yaml").exists() or target.exists():
                target = _DEFAULT_WORKSPACES_PARENT / f"{slug}-{suffix}"
                suffix += 1
                if suffix > 100:  # safety valve; shouldn't ever hit
                    raise HTTPException(
                        status_code=500,
                        detail=(
                            f"too many existing workspaces matching "
                            f"{slug!r}; pick an explicit path"
                        ),
                    )

        try:
            ws = Workspace.init(
                root=target,
                domain=domain,
                company_name=company_name,
                products=payload.products,
            )
        except OSError as exc:
            # Filesystem issues (ENAMETOOLONG, EACCES, etc) become a
            # readable 400 instead of crashing the request.
            raise HTTPException(
                status_code=400,
                detail=f"could not create workspace: {exc}",
            ) from exc

        return WorkspaceResponse(
            path=str(ws.root),
            domain=domain,
            company_name=company_name,
            products=list(payload.products),
            competitor_count=0,
            section_count=len(ws.schema.sections) if ws.schema else 0,
            total_cost=0.0,
            api_keys=_load_api_key_status(ws.root),
        )

    @app.get("/api/api-keys")
    async def get_api_keys(path: str = Query(..., description="Workspace directory path")) -> dict[str, bool]:
        """Return a presence map of saved provider keys for the workspace."""
        ws = _open_workspace(path)
        return _load_api_key_status(ws.root)

    @app.get("/api/api-keys/global")
    async def get_global_api_keys() -> dict[str, bool]:
        """Return a presence map for keys saved in the global ``~/.recon/.env``.

        Used by the describe screen to avoid prompting the user for
        keys they've already saved in a prior workspace. We never
        return the key VALUES — only whether they exist — so this
        endpoint is safe to call before any workspace exists.
        """
        from recon.api_keys import _DEFAULT_GLOBAL_DIR, _parse_env_file

        global_env = _parse_env_file(_DEFAULT_GLOBAL_DIR / ".env")
        return {
            "anthropic": bool(global_env.get("ANTHROPIC_API_KEY")),
            "google_ai": bool(global_env.get("GOOGLE_AI_API_KEY")),
        }

    @app.get("/api/competitors", response_model=CompetitorListResponse)
    async def list_competitors(path: str = Query(..., description="Workspace directory path")) -> CompetitorListResponse:
        """Return every profile on disk for this workspace."""
        ws = _open_workspace(path)
        return CompetitorListResponse(
            competitors=[_profile_to_model(row) for row in ws.list_profiles()],
        )

    @app.post("/api/competitors", response_model=CompetitorModel, status_code=201)
    async def create_competitor(payload: CreateCompetitorRequest) -> CompetitorModel:
        """Create a competitor profile. Returns 409 if the slug exists."""
        ws = _open_workspace(payload.path)

        # Normalize + validate inputs that Pydantic can't catch:
        #   - trim whitespace (" " alone would slugify to "" and land
        #     on disk as /.md)
        #   - reject javascript:/data:/vbscript: URLs to prevent a
        #     stored-XSS vector when the URL is rendered as <a href>
        name = payload.name.strip()
        if not name:
            raise HTTPException(
                status_code=422,
                detail="name cannot be empty or whitespace",
            )
        url = payload.url
        if url:
            url = url.strip()
            lower = url.lower()
            if lower.startswith(("javascript:", "data:", "vbscript:", "file:")):
                raise HTTPException(
                    status_code=422,
                    detail="url must be http(s)",
                )
            # Allow bare domains (lenient) but if a scheme is present
            # it must be http/https.
            if "://" in lower and not lower.startswith(("http://", "https://")):
                raise HTTPException(
                    status_code=422,
                    detail="url must be http(s)",
                )

        try:
            profile_path = ws.create_profile(
                name, own_product=payload.own_product,
            )
        except FileExistsError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except OSError as exc:
            raise HTTPException(
                status_code=400,
                detail=f"could not create competitor: {exc}",
            ) from exc

        if url or payload.blurb:
            _attach_candidate_metadata(profile_path, url, payload.blurb)

        # Round-trip through list_profiles so the response reflects the
        # persisted frontmatter (including anything Workspace populated
        # on create).
        matches = [p for p in ws.list_profiles() if p["_path"] == profile_path]
        meta = matches[0] if matches else {
            "name": payload.name,
            "_slug": profile_path.stem,
            "type": "own_product" if payload.own_product else "competitor",
            "research_status": "scaffold",
        }
        return _profile_to_model(meta, url=payload.url, blurb=payload.blurb)

    @app.post("/api/discover", response_model=DiscoverResponse)
    async def discover_competitors(payload: DiscoverRequest) -> DiscoverResponse:
        """Run the LLM competitor-discovery agent and return candidates.

        This is the missing link the web UI used to lack: the welcome
        copy promises "recon discovers competitors" but the discover
        screen was manual-add-only. This endpoint drives
        :class:`recon.discovery.DiscoveryAgent` (or
        :class:`recon.gemini_discovery.GeminiDiscoveryAgent`) with
        whatever API keys the user has saved.

        Priority:
          1. fake LLM client if ``use_fake_llm`` is set (prototype
             escape hatch; useful for UI demos)
          2. Gemini if ``GOOGLE_AI_API_KEY`` is available
          3. Anthropic if ``ANTHROPIC_API_KEY`` is available

        Returns the candidate list as plain JSON — the caller decides
        which ones to keep. No state is persisted here; the existing
        POST /api/competitors endpoint is still the write path.
        """
        ws = _open_workspace(payload.path)

        from recon.api_keys import load_api_keys
        from recon.discovery import DiscoveryAgent, DiscoveryState

        schema = ws.schema
        domain = ""
        if schema is not None:
            domain = schema.domain or (
                schema.identity.company_name if schema.identity else ""
            )
        if not domain:
            domain = "unknown domain"

        if payload.use_fake_llm:
            # Fake path — useful for UI demos without spending API budget.
            from recon.web.fake_llm import FakeLLMClient

            agent: Any = DiscoveryAgent(
                llm_client=FakeLLMClient(),
                domain=domain,
                seed_competitors=payload.seeds or None,
                use_web_search=False,
            )
            used_web_search = False
        else:
            keys = load_api_keys(ws.root)
            google_key = keys.get("google_ai")
            anthropic_key = keys.get("anthropic")
            agent = None
            used_web_search = False

            if google_key:
                try:
                    from recon.gemini_discovery import GeminiDiscoveryAgent

                    agent = GeminiDiscoveryAgent(
                        api_key=google_key,
                        domain=domain,
                        seed_competitors=payload.seeds or None,
                    )
                    used_web_search = True
                except Exception:  # noqa: BLE001 -- non-fatal
                    import logging as _logging

                    _logging.getLogger(__name__).exception(
                        "Gemini discovery agent init failed",
                    )
                    agent = None

            if agent is None and anthropic_key:
                from recon.client_factory import create_llm_client

                os.environ["ANTHROPIC_API_KEY"] = anthropic_key
                try:
                    client = create_llm_client()
                except Exception as exc:  # noqa: BLE001
                    raise HTTPException(
                        status_code=500,
                        detail=f"could not create LLM client: {exc}",
                    ) from exc
                agent = DiscoveryAgent(
                    llm_client=client,
                    domain=domain,
                    seed_competitors=payload.seeds or None,
                )
                used_web_search = True

            if agent is None:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "No API key configured. Save an Anthropic or "
                        "Google AI key in the describe step (or set "
                        "ANTHROPIC_API_KEY / GOOGLE_AI_API_KEY in your "
                        "environment) before running discovery."
                    ),
                )

        try:
            state = DiscoveryState()
            results = await agent.search(state)
        except Exception as exc:  # noqa: BLE001 -- surface to the UI
            import logging as _logging

            _logging.getLogger(__name__).exception(
                "discovery agent failed for workspace=%s", ws.root,
            )
            raise HTTPException(
                status_code=502,
                detail=f"discovery failed: {exc}",
            ) from exc

        candidates = [
            DiscoveredCandidate(
                name=c.name,
                url=c.url or None,
                blurb=c.blurb or None,
                tier=str(c.suggested_tier) if c.suggested_tier else "competitor",
            )
            for c in results
        ]
        return DiscoverResponse(
            candidates=candidates,
            domain=domain,
            used_web_search=used_web_search,
        )

    @app.delete("/api/competitors/{slug}", status_code=204)
    async def delete_competitor(slug: str, path: str = Query(..., description="Workspace directory path")):
        """Remove a profile by slug. Path-traversal attempts return 400."""
        if "/" in slug or "\\" in slug or ".." in slug:
            raise HTTPException(status_code=400, detail="invalid slug")
        ws = _open_workspace(path)
        profile_path = ws.competitors_dir / f"{slug}.md"
        resolved = profile_path.resolve()
        # Double-check the resolved path is still inside competitors/
        # — belt-and-braces defense against symlink tricks.
        if ws.competitors_dir.resolve() not in resolved.parents:
            raise HTTPException(status_code=400, detail="invalid slug")
        if not profile_path.exists():
            raise HTTPException(status_code=404, detail=f"no profile: {slug}")
        profile_path.unlink()
        # FastAPI returns an empty 204 when the handler returns None.
        return None

    @app.get("/api/template", response_model=TemplateResponse)
    async def get_template(path: str = Query(..., description="Workspace directory path")) -> TemplateResponse:
        """Return the full section pool with per-section selected flag.

        The pool is ``DefaultSections.ALL``. A section is "selected"
        iff it appears in the workspace's recon.yaml.
        """
        from recon.wizard import DefaultSections

        ws = _open_workspace(path)
        selected_keys = (
            {s.key for s in ws.schema.sections} if ws.schema else set()
        )
        sections = [
            TemplateSectionModel(
                key=s["key"],
                title=s["title"],
                description=s["description"],
                selected=s["key"] in selected_keys,
                allowed_formats=list(s.get("allowed_formats", [])),
                preferred_format=s.get("preferred_format", "prose"),
            )
            for s in DefaultSections.ALL
        ]
        # Any custom sections already selected but not in the pool
        # (future custom-section support) get surfaced too.
        known = {s.key for s in sections}
        if ws.schema is not None:
            for section in ws.schema.sections:
                if section.key in known:
                    continue
                sections.append(
                    TemplateSectionModel(
                        key=section.key,
                        title=section.title,
                        description=section.description,
                        selected=True,
                        allowed_formats=list(section.allowed_formats),
                        preferred_format=section.preferred_format,
                    ),
                )
        return TemplateResponse(sections=sections)

    @app.put("/api/template", response_model=TemplateResponse)
    async def put_template(payload: PutTemplateRequest) -> TemplateResponse:
        """Replace the workspace's selected section list.

        Unknown keys cause a 400 and the yaml stays untouched, so
        callers don't corrupt state on a typo.
        """
        from recon.wizard import DefaultSections

        ws = _open_workspace(payload.path)
        pool = {s["key"]: s for s in DefaultSections.ALL}
        unknown = [k for k in payload.section_keys if k not in pool]
        if unknown:
            raise HTTPException(
                status_code=400,
                detail=f"unknown section keys: {sorted(unknown)}",
            )

        schema_path = ws.root / "recon.yaml"
        raw = yaml.safe_load(schema_path.read_text()) or {}
        raw["sections"] = [dict(pool[key]) for key in payload.section_keys]
        schema_path.write_text(
            yaml.dump(raw, default_flow_style=False, sort_keys=False),
        )

        return await get_template(str(ws.root))  # type: ignore[return-value]

    @app.get("/api/confirm", response_model=ConfirmResponse)
    async def get_confirm(path: str = Query(..., description="Workspace directory path")) -> ConfirmResponse:
        """Cost breakdown, model options, and ETA for the Confirm screen."""
        ws = _open_workspace(path)
        profiles = ws.list_profiles()
        competitor_count = len(profiles)

        sections = ws.schema.sections if ws.schema else []
        section_keys = [s.key for s in sections]
        section_names = [s.title for s in sections]
        section_count = len(sections)

        cost_by_stage = _estimate_cost_by_stage(competitor_count, section_count)
        estimated_total = sum(cost_by_stage.values())
        eta_seconds = _estimate_eta_seconds(competitor_count, section_count)

        baseline = next(
            m for m in _MODEL_CATALOG if m["id"] == _BASELINE_MODEL_ID
        )
        baseline_blended = (
            baseline["input_price_per_million"]
            + baseline["output_price_per_million"]
        )

        model_options: list[ModelOption] = []
        for entry in _MODEL_CATALOG:
            blended = (
                entry["input_price_per_million"]
                + entry["output_price_per_million"]
            )
            scale = blended / baseline_blended if baseline_blended else 1.0
            model_options.append(
                ModelOption(
                    id=entry["id"],
                    label=entry["label"],
                    input_price_per_million=entry["input_price_per_million"],
                    output_price_per_million=entry["output_price_per_million"],
                    description=entry["description"],
                    estimated_total=round(estimated_total * scale, 2),
                    recommended=entry["recommended"],
                ),
            )

        return ConfirmResponse(
            competitor_count=competitor_count,
            section_keys=section_keys,
            section_names=section_names,
            cost_by_stage=cost_by_stage,
            estimated_total=round(estimated_total, 2),
            eta_seconds=eta_seconds,
            model_options=model_options,
            default_model=_BASELINE_MODEL_ID,
            default_workers=5,
        )

    @app.post("/api/api-keys")
    async def save_api_key_endpoint(payload: SaveApiKeyRequest) -> dict[str, bool]:
        """Save a provider key to the workspace .env file.

        Validates the provider name against the recognized set so we
        don't write arbitrary attacker-controlled env vars.
        """
        if payload.name not in _RECOGNIZED_API_KEY_NAMES:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"unknown api key name: {payload.name!r}. "
                    f"recognized: {sorted(_RECOGNIZED_API_KEY_NAMES)}"
                ),
            )
        ws = _open_workspace(payload.path)
        from recon.api_keys import save_api_key

        save_api_key(payload.name, payload.value, ws.root)
        return _load_api_key_status(ws.root)

    @app.post("/api/runs")
    async def start_run(payload: StartRunRequest) -> StartRunResponse:
        """Kick off a pipeline run and return the run_id for SSE subscription.

        Prototype behaviour: the LLM client is ALWAYS a deterministic
        fake (see :mod:`recon.web.fake_llm`). Real-LLM mode is gated
        behind a follow-up release — letting the "Start research"
        button in the UI cost money before the surrounding flow is
        finished would be a bad trade.

        The pipeline runs as a background task on the FastAPI event
        loop. The :class:`EventBridge` already fans out every engine
        event to subscribed SSE clients, so the caller just needs to
        open the returned ``events_url`` to see the stream.
        """
        ws = _open_workspace(payload.path)

        # Zero-scope guard. The client-side Start button is disabled
        # when there's nothing to run, but a direct API call or a
        # stale confirm payload could still reach here.
        if not ws.list_profiles():
            raise HTTPException(
                status_code=400,
                detail="no competitors in this workspace",
            )
        sections = ws.schema.sections if ws.schema else []
        if not sections:
            raise HTTPException(
                status_code=400,
                detail="no sections selected in the research template",
            )

        # Defer the heavy imports until someone actually runs a pipeline.
        # Matches the TUI pipeline_runner pattern so the web app stays
        # snappy at startup.
        from dataclasses import replace

        from recon.pipeline import Pipeline, PipelineConfig, PipelineStage
        from recon.state import StateStore
        from recon.web.fake_llm import FakeLLMClient

        # Fake mode is the only supported mode today. A future branch
        # will honour use_fake_llm=False by routing through
        # recon.client_factory.create_llm_client with proper API-key
        # validation — but doing that from the web UI before the flow
        # is nailed down would spend real dollars on a button click.
        client = FakeLLMClient()

        store = StateStore(db_path=ws.root / ".recon" / "state.db")
        await store.initialize()

        config = PipelineConfig(
            start_from=PipelineStage.RESEARCH,
            stop_after=PipelineStage.DELIVER,
            verification_enabled=False,
        )
        if payload.workers:
            config = replace(config, max_research_workers=payload.workers)

        import asyncio as _asyncio

        cancel_event = _asyncio.Event()
        pause_event = _asyncio.Event()
        pause_event.set()  # set = running, cleared = paused

        pipeline = Pipeline(
            workspace=ws,
            state_store=store,
            llm_client=client,
            config=config,
            cancel_event=cancel_event,
            pause_event=pause_event,
        )

        try:
            run_id = await pipeline.plan()
        except Exception as exc:  # noqa: BLE001 -- surface failure to caller
            raise HTTPException(
                status_code=500,
                detail=f"could not plan run: {exc}",
            ) from exc

        async def _execute() -> None:
            try:
                await pipeline.execute(run_id)
            except Exception:
                # Errors flow to the UI via RunFailed events; we don't
                # want to crash the server loop just because one run
                # failed.
                import logging as _logging

                _logging.getLogger(__name__).exception(
                    "pipeline run %s crashed", run_id,
                )

        _asyncio.create_task(_execute())

        return StartRunResponse(
            run_id=run_id,
            events_url=f"/api/runs/{run_id}/events",
            use_fake_llm=True,
        )

    @app.get("/api/events")
    async def events() -> EventSourceResponse:
        """Server-Sent Events stream of every engine event.

        Use this from the browser via:

            const stream = new EventSource('/api/events');
            stream.addEventListener('CostRecorded', e => { ... });

        sse-starlette handles heartbeats automatically (15s default)
        so connections survive idle browsers and local proxies.
        """
        return EventSourceResponse(bridge.subscribe())

    @app.get("/api/runs", response_model=RunListResponse)
    async def list_runs(
        path: str = Query(..., description="Workspace directory path"),
    ) -> RunListResponse:
        """History of every run for a workspace, most recent first.

        Drives the Runs tab timeline. Each summary includes enough to
        render a one-line row — status, cost, task counts — without a
        second round-trip per run."""
        from recon.state import StateStore

        ws = _open_workspace(path)
        store = StateStore(db_path=ws.root / ".recon" / "state.db")
        await store.initialize()

        rows = await store.list_runs()
        summaries: list[RunSummary] = []
        for row in rows:
            run_id = row["run_id"]
            tasks = await store.list_tasks(run_id)
            completed = sum(1 for t in tasks if t["status"] == "researched")
            failed = sum(1 for t in tasks if t["status"] == "failed")
            cost = await store.get_run_total_cost(run_id)
            summaries.append(RunSummary(
                run_id=run_id,
                status=row.get("status", "unknown"),
                created_at=str(row.get("created_at", "")),
                updated_at=str(row.get("updated_at", "")),
                total_cost_usd=float(cost),
                task_count=len(tasks),
                completed_tasks=completed,
                failed_tasks=failed,
                model=row.get("model", "") or "",
            ))
        return RunListResponse(runs=summaries)

    @app.get("/api/runs/{run_id}", response_model=RunStateResponse)
    async def get_run_state(
        run_id: str,
        path: str = Query(..., description="Workspace directory path"),
    ) -> RunStateResponse:
        """Current snapshot of a single run — used for slide-over
        reattach when the user reloads mid-run. Pair with the SSE
        stream for live updates."""
        from recon.state import StateStore

        ws = _open_workspace(path)
        store = StateStore(db_path=ws.root / ".recon" / "state.db")
        await store.initialize()

        row = await store.get_run(run_id)
        if row is None:
            raise HTTPException(status_code=404, detail=f"run {run_id} not found")

        tasks = await store.list_tasks(run_id)
        completed = sum(1 for t in tasks if t["status"] == "researched")
        failed = sum(1 for t in tasks if t["status"] == "failed")
        running = sum(1 for t in tasks if t["status"] == "researching")
        cost = await store.get_run_total_cost(run_id)

        return RunStateResponse(
            run_id=run_id,
            status=row.get("status", "unknown"),
            created_at=str(row.get("created_at", "")),
            updated_at=str(row.get("updated_at", "")),
            total_cost_usd=float(cost),
            task_count=len(tasks),
            completed_tasks=completed,
            failed_tasks=failed,
            running_tasks=running,
            model=row.get("model", "") or "",
            events_url=f"/api/runs/{run_id}/events",
        )

    @app.get("/api/runs/{run_id}/events")
    async def run_events(run_id: str) -> EventSourceResponse:
        """SSE stream filtered to events for one run.

        Events without a ``run_id`` field (``SectionStarted`` and
        friends) are forwarded too — they fire from inside a run even
        though their payload does not carry the id.
        """
        async def _filtered():
            async for message in bridge.subscribe():
                # Cheap check: parse only when there's a chance of match.
                # The serialized payload includes the run_id field when
                # the event has one.
                if f'"run_id": "{run_id}"' in message["data"]:
                    yield message
                    continue
                if '"run_id"' not in message["data"]:
                    yield message

        return EventSourceResponse(_filtered())

    _register_root_route(app)

    return app


_CONFIG_MARKER = "<!--RECON_CONFIG-->"


def _render_index_html() -> str:
    """Return the SPA shell with server-side config injected.

    We swap the ``<!--RECON_CONFIG-->`` marker in index.html for a
    ``<script>`` that sets ``window.RECON_HOME``. The frontend reads
    this to display HOME-relative paths as ``~/...`` (see
    ``welcomeScreen.shortPath`` in app.js).

    Rendering happens per-request because ``$HOME`` can differ between
    the process and the user viewing the page. The file is small
    (<20KB) so reading it fresh has no meaningful cost.
    """
    raw = (_STATIC_DIR / "index.html").read_text()
    home = os.path.expanduser("~")
    # json.dumps produces a valid JS string literal (escapes quotes,
    # backslashes, control chars, and produces "null" for None). This
    # is safer than repr() or manual string splicing since the home
    # directory can contain characters with special meaning in JS.
    payload = (
        "<script>"
        f"window.RECON_HOME = {json.dumps(home)};"
        "</script>"
    )
    # Use a single-shot replace so accidental duplicate markers in
    # future edits don't silently double-inject.
    if _CONFIG_MARKER in raw:
        return raw.replace(_CONFIG_MARKER, payload, 1)
    return raw


def _register_root_route(app: FastAPI) -> None:
    """Attach the SPA shell route. Split out to keep create_app readable."""

    @app.get("/")
    async def root() -> HTMLResponse:
        """Serve the SPA shell with runtime config injected.

        We serve the rendered index.html directly rather than mounting
        StaticFiles at "/" so that hash-based client routes (e.g.
        ``/#/welcome``) and future deep links don't accidentally hit
        a static-file 404.
        """
        return HTMLResponse(_render_index_html())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _open_workspace(raw_path: str):
    """Resolve a workspace path or raise HTTPException(404).

    Centralizes the validate-then-open dance so every endpoint has the
    same error response. Importing Workspace here (not at module top)
    avoids paying the schema-loader cost on app startup for users who
    only ever hit /api/health.
    """
    from recon.workspace import Workspace

    try:
        path = Path(raw_path).expanduser()
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"invalid path: {exc}") from exc

    if not path.exists() or not path.is_dir():
        raise HTTPException(status_code=404, detail=f"workspace not found: {path}")
    if not (path / "recon.yaml").exists():
        raise HTTPException(status_code=404, detail=f"no recon.yaml in: {path}")

    try:
        return Workspace.open(path)
    except Exception as exc:
        # Schema parse error etc — surface as a 400 so the UI can show
        # a real message instead of a generic server error.
        raise HTTPException(status_code=400, detail=f"workspace open failed: {exc}") from exc


def _safe_cost_summary(workspace) -> dict[str, float]:
    """Return cost summary for a workspace, suppressing any state-store error.

    The dashboard model has its own resilient version; we duplicate
    the suppression here to keep the workspace endpoint independent
    of dashboard internals.
    """
    from recon.tui.models.dashboard import _read_cost_summary

    try:
        return _read_cost_summary(workspace)
    except Exception:
        return {"run_count": 0, "total_cost": 0.0, "last_run_cost": 0.0}


def _load_api_key_status(workspace_root: Path) -> dict[str, bool]:
    """Presence map for every recognized provider.

    Always returns the full provider set (with False for missing) so
    the UI can render the same shape every time.
    """
    try:
        from recon.api_keys import load_api_keys
    except ImportError:
        return {name: False for name in sorted(_RECOGNIZED_API_KEY_NAMES)}
    try:
        keys = load_api_keys(workspace_root)
    except Exception:
        keys = {}
    return {
        name: bool(keys.get(name))
        for name in sorted(_RECOGNIZED_API_KEY_NAMES)
    }


def _heuristic_company_name(description: str) -> str:
    """Pull a likely company name out of a freeform description.

    Heuristic: first run of capitalized words at the start of the
    description. Falls back to the first word if no capitalized run
    is found, and ultimately to "Unknown" so callers always get a
    non-empty string.

    Examples:
        "Bambu Lab makes ..."           -> "Bambu Lab"
        "Acme Corp makes widgets"       -> "Acme Corp"
        "we build x"                    -> "we"            (best effort)
        ""                              -> "Unknown"
    """
    if not description.strip():
        return "Unknown"
    tokens = description.split()
    leading: list[str] = []
    for token in tokens:
        # Strip surrounding punctuation when checking case.
        stripped = token.strip(",.;:()[]'\"")
        if stripped and stripped[0].isupper():
            leading.append(token.rstrip(",.;:()"))
        else:
            break
    if leading:
        return " ".join(leading)
    return tokens[0]


def _estimate_cost_by_stage(
    competitor_count: int,
    section_count: int,
) -> dict[str, float]:
    """Stage-by-stage USD estimates for the Confirm screen.

    Numbers are intentionally rough — the cost tracker records real
    spend during a run. This is just "how many dollars should the
    user steel themselves for before hitting Start?"
    """
    research = competitor_count * section_count * _COST_PER_SECTION_USD
    enrichment = (
        competitor_count * _ENRICHMENT_PASSES * _COST_PER_ENRICH_PROFILE_USD
    )
    themes = _DEFAULT_THEME_COUNT * _COST_PER_THEME_USD
    summaries = _DEFAULT_THEME_COUNT * _COST_PER_SUMMARY_USD + _COST_PER_SUMMARY_USD
    return {
        "research": round(research, 2),
        "enrichment": round(enrichment, 2),
        "themes": round(themes, 2),
        "summaries": round(summaries, 2),
    }


def _estimate_eta_seconds(
    competitor_count: int,
    section_count: int,
    workers: int = 5,
) -> int:
    """Rough wall-clock estimate. Research dominates; fixed overhead
    for enrichment + synthesis is added separately."""
    workers = max(1, workers)
    research_work = competitor_count * section_count * _SECONDS_PER_SECTION
    return int(
        (research_work / workers)
        + _ENRICHMENT_OVERHEAD_S
        + _SYNTHESIS_OVERHEAD_S,
    )


def _profile_to_model(
    profile_meta: dict,
    *,
    url: str | None = None,
    blurb: str | None = None,
) -> CompetitorModel:
    """Convert a ``Workspace.list_profiles`` entry to a response model."""
    return CompetitorModel(
        name=str(profile_meta.get("name", "Unknown")),
        slug=str(profile_meta.get("_slug", "")),
        type=str(profile_meta.get("type", "competitor")),
        status=str(profile_meta.get("research_status", "scaffold")),
        url=url or profile_meta.get("url"),
        blurb=blurb or profile_meta.get("blurb"),
    )


def _attach_candidate_metadata(
    profile_path: Path,
    url: str | None,
    blurb: str | None,
) -> None:
    """Add discovery-provided url/blurb to a profile's frontmatter."""
    import frontmatter

    post = frontmatter.load(str(profile_path))
    changed = False
    if url and not post.metadata.get("url"):
        post["url"] = url
        changed = True
    if blurb and not post.metadata.get("blurb"):
        post["blurb"] = blurb
        changed = True
    if changed:
        profile_path.write_text(frontmatter.dumps(post))


def _slugify_for_path(name: str) -> str:
    """Filesystem-safe slug suitable for a directory name."""
    out = []
    for ch in name.lower():
        if ch.isalnum():
            out.append(ch)
        elif ch in {" ", "-", "_"}:
            out.append("-")
    slug = "".join(out)
    while "--" in slug:
        slug = slug.replace("--", "-")
    slug = slug.strip("-")
    return slug or "workspace"


def _build_results_response(workspace_root: Path) -> ResultsResponse:
    """Enumerate exec summary + theme files on disk."""
    summary_path = workspace_root / "executive_summary.md"
    summary_preview = ""
    summary_path_str: str | None = None
    if summary_path.exists():
        summary_path_str = str(summary_path)
        summary_preview = _markdown_preview(summary_path)

    theme_files: list[ThemeFileModel] = []
    output_files: list[OutputFileModel] = []
    themes_dir = workspace_root / "themes"
    distilled_dir = themes_dir / "distilled"

    if themes_dir.exists():
        # themes/<slug>.md (skip the distilled subdirectory)
        for path in sorted(themes_dir.glob("*.md")):
            slug = path.stem
            distilled_path = distilled_dir / f"{slug}.md"
            theme_files.append(
                ThemeFileModel(
                    name=slug,
                    title=_extract_h1(path) or slug.replace("_", " ").title(),
                    path=str(path),
                    distilled_path=(
                        str(distilled_path) if distilled_path.exists() else None
                    ),
                ),
            )
            output_files.append(
                OutputFileModel(name=slug, path=str(path), kind="theme"),
            )

    if summary_path_str is not None:
        # Surface the summary at the top of the output list so the UI
        # can render it before per-theme entries.
        output_files.insert(
            0,
            OutputFileModel(
                name="executive_summary",
                path=summary_path_str,
                kind="exec_summary",
            ),
        )

    return ResultsResponse(
        workspace_path=str(workspace_root),
        executive_summary_path=summary_path_str,
        executive_summary_preview=summary_preview,
        theme_files=theme_files,
        output_files=output_files,
    )


_TRUNCATION_MARKER = "\n\n[...]"


def _markdown_preview(path: Path) -> str:
    """Return the first ~2KB of a markdown file with frontmatter stripped.

    The total returned length never exceeds ``_PREVIEW_MAX_CHARS`` so
    the JSON payload size is bounded — the truncation marker eats
    into the budget rather than extending past it.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return ""
    text = _FRONTMATTER_RE.sub("", text, count=1).strip()
    if len(text) <= _PREVIEW_MAX_CHARS:
        return text
    budget = _PREVIEW_MAX_CHARS - len(_TRUNCATION_MARKER)
    truncated = text[:budget].rstrip()
    return truncated + _TRUNCATION_MARKER


def _extract_h1(path: Path) -> str | None:
    """First H1 header in a markdown file, or None."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    match = _H1_RE.search(text)
    return match.group(1).strip() if match else None
