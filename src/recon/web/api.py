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
    CompetitorRow,
    DashboardResponse,
    HealthResponse,
    OutputFileModel,
    RecentProjectModel,
    RecentProjectsResponse,
    ResultsResponse,
    SectionStatusModel,
    ThemeFileModel,
    WorkspaceResponse,
)

_STATIC_DIR = Path(__file__).parent / "static"

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
    """Best-effort api-key presence check.

    Reads ``.env`` if the api-keys module exposes a loader; otherwise
    returns an empty dict. The web UI tolerates missing data here so
    Phase 1 doesn't depend on Phase 2's api_keys integration.
    """
    try:
        from recon.api_keys import load_api_keys
    except ImportError:
        return {}
    try:
        keys = load_api_keys(workspace_root)
        return {name: bool(value) for name, value in keys.items()}
    except Exception:
        return {}


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
