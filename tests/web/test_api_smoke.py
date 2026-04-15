"""Smoke tests for the web UI HTTP layer.

Phase 1: only the static shell + /api/health exist. Later phases add
the rest of the API surface.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from recon.web.api import create_app


@pytest.fixture()
def client() -> TestClient:
    """Return a TestClient bound to a fresh app instance.

    Each test gets its own app so route registration side-effects
    (e.g., the EventBridge subscribing to the event bus) don't bleed
    across tests. The autouse ``_reset_event_bus`` fixture in the
    root conftest also catches anything that slips through.
    """
    return TestClient(create_app())


class TestRoot:
    def test_root_returns_200_and_html(self, client: TestClient) -> None:
        response = client.get("/")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/html")

    def test_root_serves_index_html_with_recon_marker(self, client: TestClient) -> None:
        response = client.get("/")
        # The shell must declare itself a recon page so we can detect
        # accidental fallback to a stock FastAPI redirect or 404 page.
        assert "recon" in response.text.lower()

    def test_root_includes_theme_css_link(self, client: TestClient) -> None:
        response = client.get("/")
        assert "theme.css" in response.text

    def test_root_injects_recon_home_config(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # The SPA's welcome screen uses window.RECON_HOME to shorten
        # paths like /Users/alice/work to ~/work. The root route must
        # swap the <!--RECON_CONFIG--> marker for a script that sets
        # it — otherwise the frontend shows absolute paths.
        monkeypatch.setenv("HOME", "/Users/alice")
        response = client.get("/")
        body = response.text
        assert "<!--RECON_CONFIG-->" not in body
        assert 'window.RECON_HOME = "/Users/alice"' in body

    def test_root_escapes_home_for_safe_injection(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # A HOME containing a double-quote or backslash must not break
        # the injected <script>. json.dumps produces a valid JS literal.
        monkeypatch.setenv("HOME", 'C:\\Users\\"bob"')
        response = client.get("/")
        body = response.text
        # Literal backslash + escaped quote inside the JS string.
        assert 'window.RECON_HOME = "C:\\\\Users\\\\\\"bob\\""' in body

    def test_root_does_not_use_emojis(self, client: TestClient) -> None:
        # House style: no emoji anywhere. Catches pasted-from-design
        # leakage where someone slips a U+1F* glyph into the HTML.
        response = client.get("/")
        for char in response.text:
            code = ord(char)
            # Emoji ranges (broad): Misc Symbols, Dingbats, Emoticons,
            # Misc Symbols & Pictographs, Transport, Supplemental, etc.
            if 0x1F000 <= code <= 0x1FAFF or 0x2600 <= code <= 0x27BF:
                pytest.fail(f"emoji U+{code:04X} found in index.html")


class TestStaticAssets:
    def test_theme_css_served(self, client: TestClient) -> None:
        response = client.get("/static/theme.css")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/css")

    def test_theme_css_uses_ported_tokens(self, client: TestClient) -> None:
        response = client.get("/static/theme.css")
        body = response.text
        # Spot-check ported tokens from src/recon/tui/theme.py
        assert "#000000" in body  # background
        assert "#efe5c0" in body  # foreground
        assert "#e0a044" in body  # amber accent
        assert "--recon-amber" in body  # CSS custom property naming

    def test_app_js_served(self, client: TestClient) -> None:
        response = client.get("/static/app.js")
        assert response.status_code == 200
        # text/javascript or application/javascript both acceptable
        assert "javascript" in response.headers["content-type"]

    def test_unknown_static_path_returns_404(self, client: TestClient) -> None:
        response = client.get("/static/does-not-exist.css")
        assert response.status_code == 404


class TestHealth:
    def test_health_returns_ok(self, client: TestClient) -> None:
        response = client.get("/api/health")
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert "version" in body

    def test_health_version_matches_package(self, client: TestClient) -> None:
        from importlib.metadata import version

        response = client.get("/api/health")
        assert response.json()["version"] == version("recon-cli")


class TestPathTraversalDefense:
    """Static file mount must not let callers escape /static/."""

    def test_dotdot_in_static_path_does_not_leak(self, client: TestClient) -> None:
        # FastAPI's StaticFiles already blocks this, but we lock it
        # in here so a future regression (e.g., switching to a custom
        # route) gets caught.
        response = client.get("/static/../api/health")
        # Either 404 (blocked path) or 200 (normalized + served as
        # health) is acceptable; what we DO NOT want is a 200 that
        # serves a file from outside the static dir.
        assert response.status_code in {200, 404}
        if response.status_code == 200:
            assert response.headers.get("content-type", "").startswith(
                ("application/json", "text/html"),
            )
