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
    DiscoveryAuditResponse,
    DiscoverResponse,
    DiscoveredCandidate,
    HealthResponse,
    ModelOption,
    OutputFileModel,
    PlanSettingsResponse,
    PutTemplateRequest,
    RecentProjectModel,
    RecentProjectsResponse,
    ResultsResponse,
    RunListResponse,
    RunProvenanceModel,
    RunStateResponse,
    RunSummary,
    SaveApiKeyRequest,
    SectionStatusModel,
    StartRunRequest,
    StartRunResponse,
    TemplateResponse,
    TemplateSectionModel,
    ThemeFileModel,
    UpdatePlanSettingsRequest,
    WorkspaceResponse,
)

_STATIC_DIR = Path(__file__).parent / "static"

# Default parent for newly-created workspaces when the request doesn't
# pin one. We used to put workspaces in ~/recon which collides with
# the v1 recon source checkout on developer machines — that was a
# real bug report. Tests monkeypatch this to redirect into tmp_path.
_DEFAULT_WORKSPACES_PARENT = Path.home() / "recon-workspaces"

_DEFAULT_THEME_COUNT = 5
_ENRICHMENT_PASSES = 3
_DEFAULT_PLAN_SETTINGS: dict[str, object] = {
    "model_name": "sonnet",
    "workers": 5,
    "verification_mode": "standard",
}


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

# Provider names recognized by the api-keys endpoints. Mirrors
# recon.api_keys._KEY_MAP keys (the lowercase aliases).
_RECOGNIZED_API_KEY_NAMES: frozenset[str] = frozenset({"anthropic", "google_ai"})


# ---------------------------------------------------------------------------
# Per-run control handles
# ---------------------------------------------------------------------------
#
# Each in-flight run registers its cancel/pause asyncio.Events in the
# module-level dict below so the pause/resume/cancel HTTP endpoints can
# find them by run_id. The entry is removed in the run's `finally`
# block when it terminates.

from dataclasses import dataclass as _dataclass


@_dataclass
class RunControl:
    cancel_event: Any
    pause_event: Any


_run_controls: dict[str, RunControl] = {}

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

    @app.delete("/api/recents")
    async def delete_recent(path: str = Query(..., description="Project path to forget")) -> dict[str, bool]:
        """Remove a project from the recents list (doesn't touch disk)."""
        from recon.tui.screens.welcome import (
            _DEFAULT_RECENT_PATH,
            RecentProjectsManager,
        )

        manager = RecentProjectsManager(_DEFAULT_RECENT_PATH)
        projects = manager.load()
        before = len(projects)
        projects = [p for p in projects if p.path != path]
        if len(projects) == before:
            raise HTTPException(status_code=404, detail=f"no recent with path {path!r}")
        manager.save(projects)
        return {"ok": True}

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

    @app.patch("/api/workspace")
    async def patch_workspace(payload: dict[str, str]) -> dict[str, str]:
        """Update workspace metadata (currently only the research brief).

        Writes through to ``recon.yaml``'s top-level ``domain`` field
        since that's the on-disk home of the user-authored description.
        Future fields can join this endpoint rather than growing a new
        one per field.
        """
        path = payload.get("path", "")
        if not path:
            raise HTTPException(status_code=400, detail="path required")
        ws = _open_workspace(path)
        schema_path = ws.root / "recon.yaml"
        if not schema_path.exists():
            raise HTTPException(status_code=404, detail=f"no recon.yaml in: {ws.root}")

        raw = yaml.safe_load(schema_path.read_text()) or {}
        changed: dict[str, str] = {}
        if "brief" in payload:
            # Cap at a reasonable size to avoid writing a novel.
            new_brief = str(payload["brief"])[:4000]
            raw["domain"] = new_brief
            changed["brief"] = new_brief

        if not changed:
            return {"ok": "true", "changed": ""}

        schema_path.write_text(
            yaml.dump(raw, default_flow_style=False, sort_keys=False),
        )
        return {"ok": "true", **changed}

    @app.get("/api/plan-settings", response_model=PlanSettingsResponse)
    async def get_plan_settings(
        path: str = Query(..., description="Workspace directory path"),
    ) -> PlanSettingsResponse:
        ws = _open_workspace(path)
        return PlanSettingsResponse(**_load_plan_settings_for_workspace(ws.root))

    @app.patch("/api/plan-settings", response_model=PlanSettingsResponse)
    async def patch_plan_settings(
        payload: UpdatePlanSettingsRequest,
    ) -> PlanSettingsResponse:
        from recon.cost import get_model_pricing

        ws = _open_workspace(payload.path)
        current = _load_plan_settings_for_workspace(ws.root)
        if payload.model_name is not None:
            model_name = str(payload.model_name).strip() or "sonnet"
            try:
                get_model_pricing(model_name)
            except Exception as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            current["model_name"] = model_name
        if payload.workers is not None:
            current["workers"] = max(1, min(16, int(payload.workers)))
        if payload.verification_mode is not None:
            mode = str(payload.verification_mode).strip().lower() or "standard"
            if mode not in {"standard", "verified", "deep"}:
                raise HTTPException(
                    status_code=400,
                    detail=f"unknown verification mode: {mode}",
                )
            current["verification_mode"] = mode

        _save_plan_settings_for_workspace(ws.root, current)
        return PlanSettingsResponse(**current)

    @app.get("/api/files")
    async def get_file_content(
        path: str = Query(..., description="Workspace directory path"),
        target: str = Query(..., description="Absolute path to the file under the workspace"),
    ) -> dict[str, str]:
        """Read a text file from within the workspace.

        Read-only, constrained to files under the workspace root, and
        refuses symlinks that escape the root via ``.resolve()`` +
        ``relative_to()``. Caps body at 200KB so a pathological target
        doesn't blow up the browser.
        """
        ws = _open_workspace(path)
        resolved = Path(target).resolve()
        try:
            resolved.relative_to(ws.root.resolve())
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="target outside workspace") from exc
        if not resolved.exists() or not resolved.is_file():
            raise HTTPException(status_code=404, detail=f"{resolved} not a file")

        # Guard against enormous files — 200KB is generous for markdown
        # and refuses binary blobs that happen to be misnamed.
        max_bytes = 200 * 1024
        size = resolved.stat().st_size
        if size > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"file {resolved} is {size} bytes, max {max_bytes}",
            )
        try:
            content = resolved.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise HTTPException(status_code=415, detail="file is not utf-8 text") from exc
        return {"content": content, "path": str(resolved), "bytes": str(size)}

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

                try:
                    client = create_llm_client(api_key=anthropic_key)
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

    @app.get("/api/discovery-audit", response_model=DiscoveryAuditResponse)
    async def get_discovery_audit(
        path: str = Query(..., description="Workspace directory path"),
    ) -> DiscoveryAuditResponse:
        ws = _open_workspace(path)
        return _load_discovery_audit(ws.root)

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
        """Return the editable section pool with per-section selected flag."""
        ws = _open_workspace(path)
        sections = [
            TemplateSectionModel(**section)
            for section in _load_schema_pool_for_workspace(ws.root)
        ]
        return TemplateResponse(sections=sections)

    @app.put("/api/template", response_model=TemplateResponse)
    async def put_template(payload: PutTemplateRequest) -> TemplateResponse:
        """Persist the editable section pool and selected section subset."""
        ws = _open_workspace(payload.path)
        if payload.sections:
            sections = [_normalize_template_section(section.model_dump()) for section in payload.sections]
        else:
            pool = _load_schema_pool_for_workspace(ws.root)
            pool_by_key = {str(section["key"]): dict(section) for section in pool}
            unknown = [key for key in payload.section_keys if key not in pool_by_key]
            if unknown:
                raise HTTPException(
                    status_code=400,
                    detail=f"unknown section keys: {sorted(unknown)}",
                )
            selected = set(payload.section_keys)
            sections = [
                {**section, "selected": section["key"] in selected}
                for section in pool
            ]

        _save_schema_pool_for_workspace(ws.root, sections)
        return await get_template(str(ws.root))  # type: ignore[return-value]

    @app.get("/api/confirm", response_model=ConfirmResponse)
    async def get_confirm(path: str = Query(..., description="Workspace directory path")) -> ConfirmResponse:
        """Cost breakdown, model options, and ETA for the Confirm screen."""
        from recon.cost import (
            SectionCostSpec,
            estimate_run_breakdown,
            estimate_run_duration_minutes,
            get_model_pricing,
            list_available_models,
        )

        ws = _open_workspace(path)
        profiles = ws.list_profiles()
        competitor_count = len(profiles)
        estimate_competitor_count = competitor_count if competitor_count > 0 else 10

        sections = ws.schema.sections if ws.schema else []
        section_keys = [s.key for s in sections]
        section_names = [s.title for s in sections]
        section_count = len(sections)
        plan_settings = _load_plan_settings_for_workspace(ws.root)
        model_name = str(plan_settings.get("model_name", "sonnet"))
        workers = int(plan_settings.get("workers", 5))
        verification_mode = str(plan_settings.get("verification_mode", "standard"))
        pricing = get_model_pricing(model_name)
        section_specs = [
            SectionCostSpec(
                format_type=section.preferred_format,
                verification_tier=section.verification_tier.value,
            )
            for section in sections
        ]
        projected = estimate_run_breakdown(
            pricing=pricing,
            competitor_count=estimate_competitor_count,
            sections=section_specs,
            section_count=section_count,
            verification_mode=verification_mode,
            theme_count=_DEFAULT_THEME_COUNT,
            enrichment_passes=_ENRICHMENT_PASSES,
        )
        per_company = estimate_run_breakdown(
            pricing=pricing,
            competitor_count=1,
            sections=section_specs,
            section_count=section_count,
            verification_mode=verification_mode,
            theme_count=_DEFAULT_THEME_COUNT,
            enrichment_passes=_ENRICHMENT_PASSES,
        )
        standard_per_company = estimate_run_breakdown(
            pricing=pricing,
            competitor_count=1,
            sections=section_specs,
            section_count=section_count,
            verification_mode="standard",
            theme_count=_DEFAULT_THEME_COUNT,
            enrichment_passes=_ENRICHMENT_PASSES,
        )
        verification_uplift = max(
            0.0,
            per_company.variable_per_company - standard_per_company.variable_per_company,
        )
        eta_minutes = estimate_run_duration_minutes(
            section_count=section_count,
            competitor_count=estimate_competitor_count,
            worker_count=workers,
            verification_mode=verification_mode,
            enrichment_passes=_ENRICHMENT_PASSES,
        )
        cost_summary = _safe_cost_summary(ws)

        cost_by_stage = {
            "research": round(projected.research_total, 2),
            "enrichment": round(projected.enrichment_total, 2),
            "themes": round(projected.fixed_themes, 2),
            "summaries": round(projected.fixed_summary, 2),
        }
        estimated_total = round(sum(cost_by_stage.values()), 2)
        eta_seconds = int(eta_minutes * 60)

        model_options: list[ModelOption] = []
        for entry in list_available_models():
            option_pricing = get_model_pricing(str(entry["name"]))
            option_breakdown = estimate_run_breakdown(
                pricing=option_pricing,
                competitor_count=estimate_competitor_count,
                sections=section_specs,
                section_count=section_count,
                verification_mode=verification_mode,
                theme_count=_DEFAULT_THEME_COUNT,
                enrichment_passes=_ENRICHMENT_PASSES,
            )
            model_options.append(
                ModelOption(
                    name=str(entry["name"]),
                    id=entry["id"],
                    label=entry["label"],
                    input_price_per_million=entry["input_price_per_million"],
                    output_price_per_million=entry["output_price_per_million"],
                    description=entry["description"],
                    estimated_total=round(option_breakdown.total_run_cost, 2),
                    recommended=bool(entry["recommended"]),
                ),
            )

        return ConfirmResponse(
            competitor_count=competitor_count,
            estimate_competitor_count=estimate_competitor_count,
            section_keys=section_keys,
            section_names=section_names,
            cost_by_stage=cost_by_stage,
            estimated_total=estimated_total,
            eta_seconds=eta_seconds,
            model_options=model_options,
            default_model=model_name,
            default_workers=workers,
            default_verification_mode=verification_mode,
            research_per_company=round(per_company.research_per_company, 2),
            enrichment_per_company=round(per_company.enrichment_per_company, 2),
            total_cost_per_company=round(projected.blended_per_company, 2),
            verification_uplift_per_company=round(verification_uplift, 2),
            fixed_themes=round(projected.fixed_themes, 2),
            fixed_summary=round(projected.fixed_summary, 2),
            fixed_total=round(projected.fixed_total, 2),
            blended_per_company=round(projected.blended_per_company, 2),
            current_tracked_spend=round(cost_summary["total_cost"], 2),
            run_count=int(cost_summary["run_count"]),
        )

    @app.post("/api/api-keys")
    async def save_api_key_endpoint(payload: SaveApiKeyRequest) -> dict[str, bool]:
        """Save a provider key.

        With a ``path`` the key is written to both the workspace ``.env``
        and the global ``~/.recon/.env``. With an empty path we skip
        the workspace write — this is the flow used by the Settings
        overlay which can open without an active project.

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

        from recon.api_keys import _DEFAULT_GLOBAL_DIR, _write_key_to_env, _REVERSE_KEY_MAP, save_api_key

        if payload.path:
            ws = _open_workspace(payload.path)
            save_api_key(payload.name, payload.value, ws.root)
            return _load_api_key_status(ws.root)

        # Global-only path: write to ~/.recon/.env and return the
        # global-status view.
        env_var = _REVERSE_KEY_MAP.get(payload.name)
        if env_var is None:
            raise HTTPException(
                status_code=400,
                detail=f"unknown api key name: {payload.name!r}",
            )
        _DEFAULT_GLOBAL_DIR.mkdir(parents=True, exist_ok=True)
        _write_key_to_env(env_var, payload.value, _DEFAULT_GLOBAL_DIR / ".env")
        return _load_global_api_key_status()

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

        plan_settings = _load_plan_settings_for_workspace(ws.root)
        workers = int(payload.workers or plan_settings.get("workers", 5))
        verification_mode = str(
            payload.verification_mode or plan_settings.get("verification_mode", "standard")
        ).strip().lower()
        config = PipelineConfig(
            start_from=PipelineStage.RESEARCH,
            stop_after=PipelineStage.DELIVER,
            verification_enabled=verification_mode != "standard",
            verification_tier=(
                verification_mode if verification_mode in {"verified", "deep"} else "verified"
            ),
        )
        config = replace(config, max_research_workers=max(1, workers))

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

        # Register controls so pause/resume/cancel endpoints can look up
        # the events by run_id. Entry is cleared when the run finishes.
        _run_controls[run_id] = RunControl(
            cancel_event=cancel_event,
            pause_event=pause_event,
        )

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
            finally:
                _run_controls.pop(run_id, None)

        _asyncio.create_task(_execute())

        return StartRunResponse(
            run_id=run_id,
            events_url=f"/api/runs/{run_id}/events",
            use_fake_llm=True,
        )

    @app.post("/api/runs/{run_id}/pause")
    async def pause_run(run_id: str) -> dict[str, bool]:
        """Pause an in-flight run. No-op once terminal."""
        from recon.events import RunPaused, publish

        ctrl = _run_controls.get(run_id)
        if ctrl is None:
            raise HTTPException(status_code=404, detail=f"run {run_id} not active")
        ctrl.pause_event.clear()  # cleared = paused per convention above
        publish(RunPaused(run_id=run_id))
        return {"paused": True}

    @app.post("/api/runs/{run_id}/resume")
    async def resume_run(run_id: str) -> dict[str, bool]:
        """Resume a paused run."""
        from recon.events import RunResumed, publish

        ctrl = _run_controls.get(run_id)
        if ctrl is None:
            raise HTTPException(status_code=404, detail=f"run {run_id} not active")
        ctrl.pause_event.set()
        publish(RunResumed(run_id=run_id))
        return {"paused": False}

    @app.post("/api/runs/{run_id}/cancel")
    async def cancel_run(run_id: str) -> dict[str, bool]:
        """Cancel an in-flight run (workers abort at next check)."""
        from recon.events import RunCancelled, publish

        ctrl = _run_controls.get(run_id)
        if ctrl is None:
            raise HTTPException(status_code=404, detail=f"run {run_id} not active")
        ctrl.cancel_event.set()
        # Workers may also need pause_event set to unblock before they
        # notice cancel_event; set it defensively.
        ctrl.pause_event.set()
        publish(RunCancelled(run_id=run_id))
        return {"cancelled": True}

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


def _load_global_api_key_status() -> dict[str, bool]:
    """Presence map for the global ~/.recon/.env keys only.

    Mirrors :func:`_load_api_key_status` for the workspace-less Settings
    overlay flow. Falls through to all-False on any error so the UI
    renders a stable shape.
    """
    try:
        from recon.api_keys import _DEFAULT_GLOBAL_DIR, _parse_env_file, _KEY_MAP
    except ImportError:
        return {name: False for name in sorted(_RECOGNIZED_API_KEY_NAMES)}
    try:
        env = _parse_env_file(_DEFAULT_GLOBAL_DIR / ".env")
    except Exception:
        env = {}
    # _KEY_MAP is env-var → logical name (e.g. ANTHROPIC_API_KEY → anthropic).
    present: dict[str, bool] = {name: False for name in sorted(_RECOGNIZED_API_KEY_NAMES)}
    for env_var, value in env.items():
        logical = _KEY_MAP.get(env_var)
        if logical and logical in present:
            present[logical] = bool(value)
    return present


def _workspace_state_path(workspace_root: Path, *parts: str) -> Path:
    path = workspace_root / ".recon"
    for part in parts:
        path = path / part
    return path


def _load_plan_settings_for_workspace(workspace_root: Path) -> dict[str, object]:
    from recon.cost import get_model_pricing

    path = _workspace_state_path(workspace_root, "plan.yaml")
    settings = dict(_DEFAULT_PLAN_SETTINGS)
    if not path.exists():
        return settings
    try:
        data = yaml.safe_load(path.read_text()) or {}
        if not isinstance(data, dict):
            return settings
        settings["model_name"] = str(data.get("model_name", settings["model_name"]))
        settings["workers"] = max(1, min(16, int(data.get("workers", settings["workers"]))))
        verification = str(data.get("verification_mode", settings["verification_mode"])).strip().lower()
        settings["verification_mode"] = verification if verification in {"standard", "verified", "deep"} else "standard"
        try:
            get_model_pricing(str(settings["model_name"]))
        except Exception:
            settings["model_name"] = "sonnet"
    except Exception:
        return dict(_DEFAULT_PLAN_SETTINGS)
    return settings


def _save_plan_settings_for_workspace(
    workspace_root: Path,
    settings: dict[str, object],
) -> None:
    path = _workspace_state_path(workspace_root, "plan.yaml")
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = {
        "model_name": str(settings.get("model_name", "sonnet")),
        "workers": max(1, min(16, int(settings.get("workers", 5)))),
        "verification_mode": str(settings.get("verification_mode", "standard")).strip().lower() or "standard",
    }
    path.write_text(yaml.safe_dump(normalized, sort_keys=False))


def _normalize_template_section(raw: dict[str, Any]) -> dict[str, Any]:
    key = str(raw.get("key", "")).strip().lower()
    title = str(raw.get("title", "")).strip()
    description = str(raw.get("description", "")).strip()
    if not title:
        raise HTTPException(status_code=400, detail="section title required")
    if not description:
        raise HTTPException(status_code=400, detail="section description required")
    if not key:
        key = _slugify_for_path(title).replace("-", "_")
    allowed_formats_raw = raw.get("allowed_formats", ["prose"])
    if isinstance(allowed_formats_raw, list):
        allowed_formats = [
            str(item).strip()
            for item in allowed_formats_raw
            if str(item).strip()
        ] or ["prose"]
    else:
        allowed_formats = ["prose"]
    preferred_format = str(raw.get("preferred_format", allowed_formats[0] if allowed_formats else "prose")).strip() or "prose"
    if preferred_format not in allowed_formats:
        allowed_formats = [preferred_format, *[fmt for fmt in allowed_formats if fmt != preferred_format]]
    normalized = {
        "key": key,
        "title": title,
        "description": description,
        "selected": bool(raw.get("selected", False)),
        "when_relevant": str(raw.get("when_relevant", "")).strip(),
        "allowed_formats": allowed_formats,
        "preferred_format": preferred_format,
    }
    return normalized


def _load_schema_pool_for_workspace(workspace_root: Path) -> list[dict[str, Any]]:
    from recon.section_library import merge_with_selected
    from recon.workspace import Workspace

    ws = Workspace.open(workspace_root)
    state_path = _workspace_state_path(workspace_root, "schema_sections.yaml")
    if state_path.exists():
        try:
            data = yaml.safe_load(state_path.read_text()) or []
            if isinstance(data, list):
                seen: set[str] = set()
                sections: list[dict[str, Any]] = []
                for entry in data:
                    if not isinstance(entry, dict):
                        continue
                    section = _normalize_template_section(entry)
                    if section["key"] in seen:
                        continue
                    seen.add(section["key"])
                    sections.append(section)
                if sections:
                    return sections
        except HTTPException:
            raise
        except Exception:
            pass

    selected = []
    if ws.schema is not None:
        selected = [
            {
                "key": section.key,
                "title": section.title,
                "description": section.description or "",
                "allowed_formats": list(section.allowed_formats),
                "preferred_format": section.preferred_format,
                "when_relevant": getattr(section, "when_relevant", ""),
                "selected": True,
            }
            for section in ws.schema.sections
        ]
    return [
        _normalize_template_section(section)
        for section in merge_with_selected(selected)
    ]


def _save_schema_pool_for_workspace(
    workspace_root: Path,
    sections: list[dict[str, Any]],
) -> None:
    from recon.workspace import Workspace

    ws = Workspace.open(workspace_root)
    schema_path = ws.root / "recon.yaml"
    if not schema_path.exists():
        raise HTTPException(status_code=404, detail=f"no recon.yaml in: {ws.root}")

    normalized_sections: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in sections:
        section = _normalize_template_section(raw)
        if section["key"] in seen:
            raise HTTPException(status_code=400, detail=f"duplicate section key: {section['key']}")
        seen.add(section["key"])
        normalized_sections.append(section)

    pool_path = _workspace_state_path(workspace_root, "schema_sections.yaml")
    pool_path.parent.mkdir(parents=True, exist_ok=True)
    pool_path.write_text(yaml.safe_dump(normalized_sections, sort_keys=False))

    raw_schema = yaml.safe_load(schema_path.read_text()) or {}
    raw_schema["sections"] = [
        {
            "key": section["key"],
            "title": section["title"],
            "description": section["description"],
            "allowed_formats": list(section.get("allowed_formats", ["prose"])),
            "preferred_format": section.get("preferred_format", "prose"),
            **({"when_relevant": section["when_relevant"]} if section.get("when_relevant") else {}),
        }
        for section in normalized_sections
        if section.get("selected")
    ]
    schema_path.write_text(yaml.safe_dump(raw_schema, sort_keys=False))


def _load_discovery_audit(workspace_root: Path) -> DiscoveryAuditResponse:
    path = _workspace_state_path(workspace_root, "discovery", "searches.jsonl")
    if not path.exists():
        return DiscoveryAuditResponse()
    search_count = 0
    last_record: dict[str, Any] = {}
    try:
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                search_count += 1
                try:
                    last_record = json.loads(line)
                except Exception:
                    continue
    except Exception:
        return DiscoveryAuditResponse()
    return DiscoveryAuditResponse(
        search_count=search_count,
        last_searched_at=str(last_record.get("timestamp", "")),
        last_candidate_count=len(last_record.get("candidates", []) or []),
        last_provider=str(last_record.get("provider", "")),
    )


def _latest_run_provenance(workspace_root: Path) -> RunProvenanceModel | None:
    runs_root = _workspace_state_path(workspace_root, "runs")
    if not runs_root.exists():
        return None
    run_dirs = [path for path in runs_root.iterdir() if path.is_dir()]
    if not run_dirs:
        return None
    latest = max(
        run_dirs,
        key=lambda path: (path / "run.yaml").stat().st_mtime if (path / "run.yaml").exists() else path.stat().st_mtime,
    )
    manifest_path = latest / "run.yaml"
    manifest: dict[str, Any] = {}
    if manifest_path.exists():
        try:
            manifest = yaml.safe_load(manifest_path.read_text()) or {}
        except Exception:
            manifest = {}
    llm_calls_path = latest / "llm_calls.jsonl"
    sources_path = latest / "sources.jsonl"
    return RunProvenanceModel(
        run_id=latest.name,
        status=str(manifest.get("status", "")),
        llm_call_count=_jsonl_line_count(llm_calls_path),
        source_entry_count=_jsonl_line_count(sources_path),
        manifest_path=str(manifest_path) if manifest_path.exists() else "",
        llm_calls_path=str(llm_calls_path) if llm_calls_path.exists() else "",
        sources_path=str(sources_path) if sources_path.exists() else "",
    )


def _jsonl_line_count(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        with path.open(encoding="utf-8") as handle:
            return sum(1 for line in handle if line.strip())
    except Exception:
        return 0


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
    """Enumerate dossiers, exec summary, and theme files on disk."""
    summary_path = workspace_root / "executive_summary.md"
    summary_preview = ""
    summary_path_str: str | None = None
    if summary_path.exists():
        summary_path_str = str(summary_path)
        summary_preview = _markdown_preview(summary_path)

    theme_files: list[ThemeFileModel] = []
    output_files: list[OutputFileModel] = []
    competitors_dir = workspace_root / "competitors"
    themes_dir = workspace_root / "themes"
    distilled_dir = themes_dir / "distilled"

    if competitors_dir.exists():
        for path in sorted(competitors_dir.glob("*.md")):
            output_files.append(
                OutputFileModel(name=path.stem, path=str(path), kind="dossier"),
            )

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

    from recon.workspace import Workspace

    cost_summary = _safe_cost_summary(Workspace.open(workspace_root))

    return ResultsResponse(
        workspace_path=str(workspace_root),
        executive_summary_path=summary_path_str,
        executive_summary_preview=summary_preview,
        theme_files=theme_files,
        output_files=output_files,
        total_cost=cost_summary["total_cost"],
        provenance=_latest_run_provenance(workspace_root),
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
