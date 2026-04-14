"""FastAPI app for the recon web UI.

Phase 1: serves the SPA shell + a minimal health endpoint. Subsequent
phases add the read-only state API, discovery, template, run, and
results endpoints (see ``design/web-ui-spec.md`` §4 for the full route
table).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse

from recon.web.events_bridge import EventBridge

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

    @app.get("/api/health")
    async def health() -> dict[str, object]:
        """Liveness check. Used by the CLI to confirm the server booted."""
        return {"ok": True, "version": _package_version()}

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
