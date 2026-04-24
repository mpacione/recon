"""recon web UI — FastAPI + Alpine.js + SSE.

Third UI alongside the CLI (``recon`` Click commands) and the TUI
(``recon tui``). Driven by the same engine via ``recon.events.EventBus``
and ``recon.pipeline.Pipeline``. See ``design/web-ui-spec.md`` for the
canonical reference.

Public entry points:

- :func:`recon.web.api.create_app` — build a FastAPI app instance
- :func:`recon.web.server.run_server` — launch uvicorn

Both are imported lazily by the ``recon serve`` Click command so that
unrelated CLI invocations don't pay the FastAPI import cost.
"""
