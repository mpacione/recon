"""FastAPI app for the recon web UI.

Phase 1: serves the SPA shell + a minimal health endpoint. Subsequent
phases add the read-only state API, discovery, template, run, and
results endpoints (see ``design/web-ui-spec.md`` §4 for the full route
table).
"""

from __future__ import annotations

import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse

from recon.web.events_bridge import EventBridge
from recon.web.schemas import (
    CompetitorListResponse,
    CompetitorModel,
    CompetitorRow,
    CreateCompetitorRequest,
    CreateWorkspaceRequest,
    DashboardResponse,
    HealthResponse,
    OutputFileModel,
    RecentProjectModel,
    RecentProjectsResponse,
    ResultsResponse,
    SaveApiKeyRequest,
    SectionStatusModel,
    ThemeFileModel,
    WorkspaceResponse,
)

_STATIC_DIR = Path(__file__).parent / "static"

# Default parent for newly-created workspaces when the request doesn't
# pin one. Tests monkeypatch this to redirect into tmp_path.
_DEFAULT_WORKSPACES_PARENT = Path.home() / "recon"

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
                    path=p.path, name=p.name, last_opened=p.last_opened,
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

    @app.post("/api/workspaces", response_model=WorkspaceResponse, status_code=201)
    async def create_workspace(payload: CreateWorkspaceRequest) -> WorkspaceResponse:
        """Create a workspace from a freeform description.

        Description parsing in Phase 5 is heuristic-only (offline) so
        the flow works without an API key. LLM-backed parsing arrives
        with the discovery agent in a later phase.
        """
        from recon.workspace import Workspace

        company_name = payload.company_name or _heuristic_company_name(payload.description)
        domain = payload.domain or payload.description
        slug = _slugify_for_path(company_name)

        if payload.path:
            target = Path(payload.path).expanduser()
        else:
            target = _DEFAULT_WORKSPACES_PARENT / slug

        if (target / "recon.yaml").exists():
            raise HTTPException(
                status_code=409,
                detail=f"workspace already exists at {target}",
            )

        ws = Workspace.init(
            root=target,
            domain=domain,
            company_name=company_name,
            products=payload.products,
        )

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
        try:
            profile_path = ws.create_profile(
                payload.name, own_product=payload.own_product,
            )
        except FileExistsError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

        if payload.url or payload.blurb:
            _attach_candidate_metadata(profile_path, payload.url, payload.blurb)

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


def _register_root_route(app: FastAPI) -> None:
    """Attach the SPA shell route. Split out to keep create_app readable."""

    @app.get("/")
    async def root() -> FileResponse:
        """Serve the SPA shell.

        We serve the static index.html directly rather than mounting
        StaticFiles at "/" so that hash-based client routes (e.g.
        ``/#/welcome``) and future deep links don't accidentally hit
        a static-file 404.
        """
        return FileResponse(
            _STATIC_DIR / "index.html",
            media_type="text/html",
        )


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
