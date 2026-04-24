"""uvicorn launcher for the recon web UI.

Wrapped behind :func:`run_server` so the CLI command (``recon serve``)
has a single typed seam to mock in tests.
"""

from __future__ import annotations

import threading
import time
import urllib.request
import webbrowser

import uvicorn

from recon.logging import get_logger
from recon.web.api import create_app

_log = get_logger(__name__)

# Hosts that are local-only and don't require ``--unsafe-bind-all``.
_LOOPBACK_HOSTS: frozenset[str] = frozenset(
    {"127.0.0.1", "localhost", "::1", "0:0:0:0:0:0:0:1"},
)


def is_loopback_host(host: str) -> bool:
    """Return True if binding to ``host`` is safe by default.

    Anything outside the loopback set requires the explicit
    ``--unsafe-bind-all`` flag at the CLI layer.
    """
    return host.strip().lower() in _LOOPBACK_HOSTS


def _open_browser_when_ready(host: str, port: int) -> None:
    """Poll the health endpoint, then open the user's browser.

    Runs in a background thread so it doesn't block uvicorn's startup.
    Gives up silently after ~5s — uvicorn will print the URL anyway.
    """
    url = f"http://{host}:{port}"
    health_url = f"{url}/api/health"
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(health_url, timeout=0.5) as resp:  # noqa: S310
                if resp.status == 200:
                    webbrowser.open(url)
                    return
        except Exception:  # noqa: BLE001 - intentional swallow during boot poll
            time.sleep(0.1)
    _log.info("browser auto-open: server did not become healthy within 5s")


def run_server(
    *,
    host: str = "127.0.0.1",
    port: int = 8787,
    open_browser: bool = True,
    log_level: str = "info",
) -> None:
    """Block on uvicorn until shutdown.

    Args:
        host: Bind interface. Loopback by default; the CLI is responsible
            for refusing non-loopback values without ``--unsafe-bind-all``.
        port: Bind port.
        open_browser: When True, open the user's default browser to the
            shell after the server reports healthy.
        log_level: uvicorn log level (case-insensitive).
    """
    _log.info("starting recon web UI on %s:%s", host, port)
    if open_browser:
        threading.Thread(
            target=_open_browser_when_ready,
            args=(host, port),
            daemon=True,
        ).start()

    uvicorn.run(
        create_app(),
        host=host,
        port=port,
        log_level=log_level.lower(),
        # Single worker by design — the EventBridge holds in-process
        # subscriber state that doesn't survive a fork.
        workers=1,
    )
