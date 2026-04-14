"""FastAPI app for the recon web UI.

Phase 1: serves the SPA shell + a minimal health endpoint. Subsequent
phases add the read-only state API, discovery, template, run, and
results endpoints (see ``design/web-ui-spec.md`` §4 for the full route
table).
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

_STATIC_DIR = Path(__file__).parent / "static"


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
    app = FastAPI(
        title="recon",
        description="Local web UI for the recon competitive intelligence CLI.",
        version=_package_version(),
        # Disable the default docs UIs — this is a private, local-only
        # surface and the route table lives in design/web-ui-spec.md.
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    app.mount(
        "/static",
        StaticFiles(directory=str(_STATIC_DIR)),
        name="static",
    )

    @app.get("/api/health")
    async def health() -> dict[str, object]:
        """Liveness check. Used by the CLI to confirm the server booted."""
        return {"ok": True, "version": _package_version()}

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

    return app
