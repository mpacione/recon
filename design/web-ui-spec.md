# recon Web UI — Design Specification

**Status:** Phase 1 (scaffold) in progress. Branch: `v2`. Started 2026-04-13.

This document is the canonical reference for the third recon UI: a local web UI
that mirrors the TUI's functionality, shares the same engine, and ports the
cyberspace.online aesthetic to the browser.

The web UI sits **alongside** the existing CLI and TUI — it does not replace
them. All three drive the same engine via the same `EventBus` and `Pipeline`
entry points.

---

## 1. Why a web UI

The TUI works inside a terminal cell grid. That constraint is good for many
things and bad for a few:

- **Wider tables.** The discovery candidates table truncates name/url/blurb
  aggressively at 80 columns. A 1280px browser viewport doesn't.
- **Side-by-side evidence.** Theme curation can show theme + evidence chunks
  in two columns; the TUI has to pick one or scroll between.
- **Clickable file links.** Results-screen markdown can link to themes and
  output files directly.
- **Shareable screencasts.** Recording a browser tab is easier than recording
  a tmux pane and produces friendlier artifacts.

The web UI does not try to replace the keyboard-driven flow — keybinds are
mirrored 1:1 (`n` new, `o` open, `1-9` recents, `q` quit, etc.).

---

## 2. Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│  Browser (127.0.0.1:8787)                                            │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │  index.html + Alpine.js + theme.css                          │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐      │    │
│  │  │ Welcome  │  │ Describe │  │ Discover │  │ ... 6 more │    │    │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘      │    │
│  └────────────┬──────────────────────┬──────────────────────────┘    │
│               │ fetch (REST/JSON)    │ EventSource (SSE)             │
└───────────────┼──────────────────────┼───────────────────────────────┘
                │                      │
┌───────────────▼──────────────────────▼───────────────────────────────┐
│  FastAPI app (uvicorn, single worker)                                │
│  ┌──────────────────────────┐  ┌──────────────────────────────────┐  │
│  │ src/recon/web/api.py     │  │ src/recon/web/events_bridge.py   │  │
│  │  - REST routes           │  │  - subscribes to EventBus        │  │
│  │  - Pydantic schemas      │  │  - fans events to SSE clients    │  │
│  └────────────┬─────────────┘  └────────────────┬─────────────────┘  │
│               │                                  │                   │
└───────────────┼──────────────────────────────────┼───────────────────┘
                │                                  │
┌───────────────▼──────────────────────────────────▼───────────────────┐
│  Engine (UNCHANGED)                                                  │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐         │
│  │ Workspace  │ │  Pipeline  │ │ EventBus   │ │ StateStore │  ...    │
│  └────────────┘ └────────────┘ └────────────┘ └────────────┘         │
└──────────────────────────────────────────────────────────────────────┘
```

### Decisions (locked, do not re-debate)

| Concern | Choice | Why |
|---|---|---|
| Backend | FastAPI + uvicorn | Already in Python ecosystem; first-class async |
| Event streaming | SSE via `sse-starlette` | Read-only fits perfectly; no WS handshake quirks |
| Frontend reactivity | Alpine.js (CDN) | No npm; stays in Python devloop |
| HTTP from frontend | `fetch()` + native `EventSource` | Built-in; no axios needed |
| Bundler | None | If we hit a wall, add HTMX. Only React/Svelte if forced |
| Auth | None | Localhost only, refuse 0.0.0.0 without explicit flag |
| CORS | Off | Same-origin only |
| Persistence | Existing on-disk state | Web UI is a view; `recon.yaml` + SQLite + markdown unchanged |

### Engine integration boundary

The web layer touches the engine via these public surfaces only:

- `recon.events.get_bus()` — subscribe to events
- `recon.workspace.Workspace` — open/init workspaces
- `recon.pipeline.Pipeline` — orchestrate runs
- `recon.state.StateStore` — query run history and costs
- `recon.discovery.DiscoveryAgent` + `DiscoveryState` — discovery rounds
- `recon.themes.ThemeDiscovery` + `DiscoveredTheme` — theme data model
- `recon.tui.screens.welcome.RecentProjectsManager` — recents (we'll lift this out of `tui/` in Phase 2; see §9)
- `recon.tui.models.dashboard.build_dashboard_data` — same dashboard data builder the TUI uses

**No engine modifications in Phase 1.** If we need something the engine doesn't
expose, we add a method (not refactor existing ones) and flag the change for
review.

---

## 3. Flow

The web UI mirrors the TUI flow exactly:

```
[1] Welcome  →  [2] Describe  →  [3] Discover  →  [4] Template  →
[5] Confirm  →  [6] Run  →  [7] Results
                                  ↑
                          [Theme Curation gate
                          fires between SYNTHESIZE
                          and DELIVER stages]
```

Theme curation is a **gate** within the run, not a sibling screen. When the
pipeline reaches the THEMES stage, the engine emits `ThemesDiscovered` and the
web UI renders the curation modal over the Run screen. The user picks themes;
on submit, we POST `/api/runs/{run_id}/themes/select` and the pipeline resumes.

(Phase 1 caveat: we'll do option-A — auto-accept all themes and require an
explicit second run for selective synthesis — and upgrade to true mid-run
gating in Phase 2 once we wire the curation callback through SSE.)

Dashboard is a sidecar screen accessible from any project, not part of the
linear flow.

---

## 4. Route table

### REST (JSON)

| Method | Path | Returns | Phase |
|---|---|---|---|
| GET | `/` | `index.html` | 1 |
| GET | `/static/{path}` | static assets | 1 |
| GET | `/api/health` | `{ok: true, version}` | 1 |
| GET | `/api/recents` | `RecentProjectsResponse` | 2 |
| GET | `/api/workspace?path=...` | `WorkspaceResponse` | 2 |
| POST | `/api/workspaces` | `WorkspaceResponse` (creates new) | 2 |
| GET | `/api/discovery?path=...` | `DiscoveryResponse` (current state) | 3 |
| POST | `/api/discovery/search` | `DiscoveryResponse` (run another round) | 3 |
| PATCH | `/api/discovery/candidates/{idx}` | `DiscoveryCandidate` (toggle accept) | 3 |
| DELETE | `/api/discovery/candidates/{idx}` | `204` (remove entirely) | 3 |
| POST | `/api/discovery/candidates` | `DiscoveryCandidate` (manual add) | 3 |
| GET | `/api/template?path=...` | `TemplateResponse` (section pool + selected) | 4 |
| PATCH | `/api/template/sections/{key}` | `SectionToggle` | 4 |
| POST | `/api/template/sections` | `Section` (custom section via prompt) | 4 |
| GET | `/api/confirm?path=...` | `ConfirmResponse` (cost breakdown, model, workers) | 5 |
| POST | `/api/runs` | `{run_id}` (launches pipeline) | 6 |
| GET | `/api/runs/{run_id}` | `RunStatusResponse` | 6 |
| POST | `/api/runs/{run_id}/cancel` | `204` | 6 |
| POST | `/api/runs/{run_id}/pause` | `204` | 6 |
| POST | `/api/runs/{run_id}/resume` | `204` | 6 |
| POST | `/api/runs/{run_id}/themes/select` | `204` (curation gate) | 6/Phase2 |
| GET | `/api/results?path=...` | `ResultsResponse` (exec summary + theme files) | 7 |
| GET | `/api/dashboard?path=...` | `DashboardResponse` | 7 |
| GET | `/api/files/{path:path}` | raw markdown content (read-only, scoped to workspace) | 7 |

### SSE

| Path | Description |
|---|---|
| `GET /api/events` | All engine events as `event_to_dict()`-serialized JSON, one per line, type set in SSE `event:` field |
| `GET /api/runs/{run_id}/events` | Filtered to events with matching `run_id` field |

Both streams use heartbeats (1 every 15s) and reconnect via the standard
EventSource auto-retry.

### Refusal behavior

- `recon serve --host 0.0.0.0` — refuses with explicit error unless
  `--unsafe-bind-all` is passed.
- `/api/files/{path}` — refuses any path that escapes the workspace root
  (resolves relative, then checks `Path.is_relative_to(workspace.root)`).

---

## 5. Pydantic schemas (sketch)

All API responses are Pydantic models. Lifted into `src/recon/web/schemas.py`.
This is a sketch; finalize per phase as needed.

```python
class HealthResponse(BaseModel):
    ok: bool
    version: str

class RecentProjectModel(BaseModel):
    path: str
    name: str
    last_opened: str
    status: Literal["new", "in_progress", "complete", "abandoned"] = "in_progress"

class RecentProjectsResponse(BaseModel):
    projects: list[RecentProjectModel]

class WorkspaceResponse(BaseModel):
    path: str
    domain: str
    company_name: str
    products: list[str]
    competitor_count: int
    section_count: int
    total_cost: float
    api_keys: dict[str, bool]   # {"anthropic": True, "google": False}

class DiscoveryCandidateModel(BaseModel):
    index: int
    name: str
    url: str
    blurb: str
    provenance: str
    suggested_tier: str
    accepted: bool

class DiscoveryResponse(BaseModel):
    domain: str
    round_count: int
    accepted: int
    candidates: list[DiscoveryCandidateModel]
    in_progress: bool

class SectionModel(BaseModel):
    key: str
    title: str
    description: str
    selected: bool

class TemplateResponse(BaseModel):
    sections: list[SectionModel]
    custom_examples: list[str]

class ConfirmResponse(BaseModel):
    competitor_count: int
    section_keys: list[str]
    section_names: list[str]
    cost_by_stage: dict[str, float]   # {"research": 18.0, "enrichment": 3.6, ...}
    cost_by_model: dict[str, float]
    eta_seconds: int
    model_options: list[ModelOption]
    default_model: str
    default_workers: int

class RunLaunchRequest(BaseModel):
    workspace_path: str
    model: str = "claude-sonnet-4-20250514"
    workers: int = 5
    deep_synthesis: bool = False
    targets: list[str] | None = None

class RunStatusResponse(BaseModel):
    run_id: str
    state: Literal["idle","running","paused","completed","failed","cancelled"]
    stage: str
    progress: ProgressSnapshot
    cost_usd: float
    started_at: str | None
    completed_at: str | None

class ResultsResponse(BaseModel):
    workspace_path: str
    executive_summary_path: str | None
    executive_summary_preview: str
    theme_files: list[ThemeFile]
    output_files: list[OutputFile]
    total_cost: float
    duration_seconds: float

class DashboardResponse(BaseModel):
    """Mirrors recon.tui.models.dashboard.DashboardData."""
    domain: str
    company_name: str
    total_competitors: int
    status_counts: dict[str, int]
    competitor_rows: list[CompetitorRow]
    section_statuses: list[SectionStatus]
    theme_count: int
    themes_selected: int
    total_cost: float
    last_run_cost: float
    run_count: int
```

---

## 6. Frontend layout

```
src/recon/web/static/
├── index.html              # SPA shell, loads Alpine + screens
├── theme.css               # Ported tokens from src/recon/tui/theme.py
├── app.js                  # Top-level Alpine x-data, router, EventSource
├── icons.js                # Inline SVG/text symbols (no emoji)
└── screens/
    ├── welcome.js          # Recents + new project
    ├── describe.js         # Freeform text + API keys
    ├── discovery.js        # Candidate table + toggles
    ├── template.js         # Section checklist
    ├── confirm.js          # Cost + model + workers
    ├── run.js              # Stage monitor + workers + activity feed
    ├── theme_curation.js   # Modal over Run when ThemesDiscovered fires
    ├── results.js          # Exec summary preview + file list
    └── dashboard.js        # Resume view for existing projects
```

### Routing

Hash-based router (`#/welcome`, `#/describe`, `#/discover/{path}`, `#/run/{run_id}`,
etc.). No history API gymnastics needed — refresh works because state is on
disk and re-fetched on screen mount.

### Ported theme tokens

CSS custom properties live in `:root`. Values lifted directly from
`src/recon/tui/theme.py` so any tweak to the TUI palette propagates by editing
both files (see §9 — we'll consider extracting a shared tokens file later).

```css
:root {
  --recon-bg:           #000000;  /* theme.py: background */
  --recon-fg:           #efe5c0;  /* theme.py: foreground */
  --recon-dim:          #a89984;  /* theme.py: dim */
  --recon-border:       #3a3a3a;  /* theme.py: border */
  --recon-amber:        #e0a044;  /* theme.py: accent */
  --recon-error:        #cc241d;  /* theme.py: error */
  --recon-success:      #98971a;  /* theme.py: success */
  --recon-warn:         #d79921;  /* theme.py: warning */
  --recon-surface:      #1a1a1a;  /* theme.py: surface */
  --recon-panel:        #0d0d0d;  /* theme.py: panel */
  --recon-font: "JetBrains Mono", "IBM Plex Mono", "Menlo", monospace;
}
```

### Visual patterns to replicate (from TUI)

| Pattern | Implementation |
|---|---|
| `── HEADING ──` | `.section-divider` with pseudo-element box-drawing characters |
| `[x]` / `[ ]` checkboxes | Plain text rendered amber/dim |
| `●` / `○` radios | Plain text |
| `Step 3/6 · …` breadcrumb | `<nav class="flow-progress">` in the header |
| Bottom keybind bar | `<footer class="keybinds">` docked, 1 line |
| Rounded thin borders | `border: 1px solid var(--recon-border); border-radius: 2px;` |
| No emoji | Lint rule in tests + pre-commit |

---

## 7. SSE strategy

### Server side (`events_bridge.py`)

```python
class EventBridge:
    """Subscribes to EventBus once, fans out to async SSE subscribers."""
    def __init__(self) -> None:
        self._queues: list[asyncio.Queue[Event]] = []
        get_bus().subscribe(self._on_event)

    def _on_event(self, event: Event) -> None:
        # Synchronous EventBus subscriber → enqueue to each async client
        for q in list(self._queues):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass  # drop on backpressure (best-effort)

    async def subscribe(self) -> AsyncIterator[dict]:
        q: asyncio.Queue[Event] = asyncio.Queue(maxsize=1024)
        self._queues.append(q)
        try:
            while True:
                event = await q.get()
                yield {"event": type(event).__name__, "data": json.dumps(event_to_dict(event))}
        finally:
            self._queues.remove(q)
```

The bridge is a singleton, instantiated at app startup. It subscribes to the
`EventBus` once; every SSE client gets its own queue. The TUI is unaffected
because EventBus subscribers don't conflict.

### Client side

```javascript
const stream = new EventSource('/api/events');
stream.addEventListener('CostRecorded', e => {
  const data = JSON.parse(e.data);
  Alpine.store('run').addCost(data.cost_usd);
});
```

One global EventSource per session; each Alpine component listens for the
event types it cares about. Heartbeats every 15s keep the connection alive
behind any local proxies.

---

## 8. CLI integration

```
$ recon serve --help
Usage: recon serve [OPTIONS]

  Launch the recon web UI on http://127.0.0.1:8787 by default.

Options:
  --port INTEGER          Bind port (default 8787)
  --host TEXT             Bind host (default 127.0.0.1)
  --workspace PATH        Pre-open this workspace on launch
  --unsafe-bind-all       Required to bind 0.0.0.0 (not recommended)
  --no-open               Don't auto-open the browser
  --log-level TEXT        Override log level for the web server
```

Default behavior:
1. Start uvicorn on `127.0.0.1:8787`
2. Open `http://127.0.0.1:8787` in the default browser (unless `--no-open`)
3. Log structured info to `~/.recon/logs/recon.log` (same logger as TUI/CLI)
4. Ctrl-C: graceful shutdown — drain SSE queues, close StateStore, exit

---

## 9. Open questions / future work

These are flagged for later phases, not Phase 1 blockers:

1. **`RecentProjectsManager` lives in `src/recon/tui/screens/welcome.py`.**
   The web UI needs the same logic. Phase 2 will lift it into
   `src/recon/recents.py` so both UIs depend on the engine layer, not on each
   other. Until then, the web layer imports from `tui/` (a one-way dependency
   that's acceptable but ugly).

2. **Theme tokens duplicated** between `tui/theme.py` and `web/static/theme.css`.
   Acceptable for v1. Consider extracting `recon/branding.py` with hex
   constants both layers read from.

3. **Theme curation gate.** Phase 1 ships option-A (auto-accept all themes,
   re-run with `start_from=SYNTHESIZE` for selective sync). Phase 6 upgrades
   to a true mid-run gate via the existing `theme_curation_callback` and a
   Future-resolved-by-HTTP-POST pattern.

4. **Multi-tab safety.** Two browser tabs opened against the same workspace
   could race on discovery toggles. Out of scope for v1 (single-user,
   single-tab assumption). Add an "edited elsewhere" warning if it bites in
   testing.

5. **Authenticated remote use.** Out of scope. If you ever want to run this
   on a server, put it behind Tailscale or `ssh -L`.

---

## 10. Test strategy

| Layer | Tool | Lives in |
|---|---|---|
| API routes | `pytest` + `httpx.AsyncClient` (FastAPI's `TestClient` for sync where simpler) | `tests/web/test_api.py` |
| EventBridge | `pytest-asyncio` + fake EventBus emitter | `tests/web/test_events_bridge.py` |
| `recon serve` CLI | `click.testing.CliRunner` | `tests/web/test_cli_serve.py` |
| Pydantic schemas | `pytest` (round-trip + boundary cases) | `tests/web/test_schemas.py` |
| Frontend (E2E) | `pytest-playwright` (added Phase 5) | `tests/web/e2e/` |

TDD per CLAUDE.md: every route ships test-first. Schema-first via Pydantic.
No production code without a failing test demanding it.

The existing `tests/conftest.py` fixtures already cover the cross-cutting
concerns we need (event bus reset, recent.json isolation), so web tests
inherit them automatically.

---

## 11. Build sequence

Mirrors the prompt's 11-step plan:

1. **Scaffold** (Phase 1, this commit) — `recon/web/` skeleton, deps, smoke test
2. **EventBridge** (Phase 2) — fan-out tested against fake bus
3. **Read-only API** (Phase 3) — `/api/health`, `/api/recents`, `/api/workspace`, `/api/results`
4. **Static shell** (Phase 4) — `index.html` + `theme.css` + empty Alpine app
5. **Welcome + Describe** (Phase 5) — first interactive screens
6. **Discovery** (Phase 6) — search + candidate table
7. **Template + Confirm** (Phase 7)
8. **Run screen** (Phase 8) — the big one, multiple sub-commits
9. **Results + Curation + Dashboard** (Phase 9)
10. **Polish** (Phase 10) — keybinds, breadcrumb, responsive layout
11. **Visual verification** (Phase 11) — Chrome screenshots vs TUI SVGs

Each phase: green test suite before commit, conventional commit messages,
push to `origin/v2` after the phase closes.

---

## 12. Done criteria (lifted from the prompt)

- `recon serve` launches on `127.0.0.1:8787` and opens in browser
- Full Welcome → Describe → Discovery → Template → Confirm → Run → Results
  flow works end-to-end on a real workspace
- Live pipeline events stream to the Run screen with < 500ms latency
- Styling is visually indistinguishable from the TUI for shared elements
  (dividers, checkboxes, amber accents)
- All existing tests still pass (832 as of branch head 2975ead)
- New test suite covers every route and every major frontend interaction
- This document stays current as decisions evolve
