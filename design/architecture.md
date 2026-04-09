# Architecture

> Three-layer system architecture, TUI design and aesthetic, CLI/headless mode, state management, error logging.

## System Architecture

Three layers with clear separation of concerns:

```
+---------------------------------------------------+
|  Interface Layer (thin)                            |
|  Translates user intent to engine calls.           |
|  Renders engine state back to the user.            |
|                                                    |
|  +-- TUI (Textual) -- interactive, monitoring      |
|  +-- CLI (headless) -- scriptable, agent-callable  |
+---------------------------------------------------+
|  Engine Layer (all logic)                          |
|                                                    |
|  +-- Pipeline Orchestrator -- state machine        |
|  +-- Worker Pool -- async, semaphore-controlled    |
|  +-- Verification Engine -- consensus protocol     |
|  +-- Cost Tracker -- token counting, estimates     |
|  +-- Prompt Composer -- schema-driven assembly     |
|  +-- Format Validator -- deterministic checks      |
+---------------------------------------------------+
|  Data Layer                                        |
|                                                    |
|  +-- Workspace -- profiles (.md), schema, config   |
|  +-- Vector Store -- ChromaDB (local)              |
|  +-- State Store -- SQLite (.recon/state.db)       |
|  +-- Evidence Store -- per-section sources/status  |
|  +-- Log Store -- .recon/logs/                     |
+---------------------------------------------------+
```

### Interface Layer

The interface layer is thin. It never contains business logic. It translates user intent into engine calls and renders engine state for display.

**TUI (default mode):** Full Textual application with screens, keybinds, live monitoring, interactive wizard. See TUI Design section below.

**CLI (headless mode):** Same engine, no TUI. Activated via `--headless` flag or automatic detection of non-interactive terminal. Returns JSON to stdout. For scripting and LLM agents calling recon programmatically.

```bash
# Headless examples
recon research --all --headless --output json
# Returns: {"status": "running", "run_id": "abc123", "progress": {...}}

recon status --headless --output json
# Returns: {"competitors": {"total": 50, "by_status": {...}}, ...}

recon discover --domain "CI/CD tools" --headless --output json
# Returns: {"candidates": [...], "round": 1}
```

Both interfaces call the same engine API. The Python API is internal-only for v1 — the CLI is the public contract. The API stabilizes naturally when a web UI is added later.

### Engine Layer

All business logic lives here. The engine is async-native (Python asyncio).

**Pipeline Orchestrator:** Manages the state machine for runs. Tracks run-level and per-competitor state. Handles pause/stop/restart/repair/redo operations. See State Management section below.

**Worker Pool:** Async semaphore-controlled concurrency. Dispatches work to LLM agents. Configurable worker count per operation type (more for format cleanup, fewer for web-search-heavy operations).

**Verification Engine:** Implements the multi-agent consensus protocol. Manages Agent A/B/C sequencing per the verification tier. Tracks verification status per source.

**Cost Tracker:** Counts tokens per API call. Maintains running totals per run. Provides estimates before execution based on schema complexity and competitor count. Stores actuals in state DB for refining future estimates.

**Prompt Composer:** Assembles prompts from composable fragments. Base system prompt + per-section fragment + example output. Reads schema metadata at composition time — no static prompt files to maintain.

**Format Validator:** Deterministic (non-LLM) validation of agent output. Checks format type, table structure, rating scales, word counts, emoji, required fields, source list. Triggers retry on failure.

### Data Layer

**Workspace:** The user-facing data. Markdown profiles with YAML frontmatter, schema definition, project config. Lives in the project directory, designed to be an Obsidian vault or part of one.

**Vector Store:** ChromaDB for local embedding storage and retrieval. Stored in `.vectordb/` within the workspace. No external server. Uses fastembed (ONNX runtime) for embeddings — fast, lightweight (~200MB vs ~2GB for PyTorch-based sentence-transformers).

**State Store:** SQLite database at `.recon/state.db`. See State Management section below.

**Evidence Store:** Per-section source attribution with verification status. Stored within the markdown profiles themselves (each section ends with its sources list) and indexed in the state DB for querying.

**Log Store:** Debug and error logs at `.recon/logs/`. See Error Logging section below.

## TUI Design

### Framework

Textual (Python). Built on Rich. Provides:
- Full widget system (tables, trees, tabs, progress bars, inputs, selectable lists)
- CSS-like styling
- Async-native (critical since the pipeline is all async)
- Works over SSH
- Keyboard-first navigation

### Visual Aesthetic

**Reference:** cyberspace.online (Dark theme)

The visual style is warm retro terminal — professional warez aesthetic. Serious tool that looks good.

**Color palette:**

| Role | Value | Description |
|---|---|---|
| Background | `#000000` | Pure black |
| Foreground | `#efe5c0` | Warm parchment/amber — dominant text color |
| Dim text | `#a89984` | Muted brownish-gray for secondary/meta text |
| Border | `#3a3a3a` | Very dark gray, subtle 1px lines |
| Accent | `#e0a044` | Warm amber-orange for highlights |
| Error | TBD | For error states, kept warm not harsh red |
| Success | TBD | For completed states, kept warm not bright green |

**Typography:**
- Monospace everything — JetBrains Mono or system monospace
- Hierarchy through text weight and dimming, not size or color variety

**UI patterns:**
- Keyboard shortcuts displayed inline using bracket notation: `[S] Save  [R] Run  [ESC] Back  [Q] Quit`
- 1px borders as the only visual separator — no shadows, no gradients
- Status bar fixed at bottom showing available commands for current screen
- ANSI/ASCII art for branding, progress indicators, and visual interest
- Retro-style progress bars (block characters, percentage, ETA)
- Warez-style loaders for long operations
- No emoji anywhere in the interface

### TUI Screens

#### 1. Wizard Screen (`recon init`)

Multi-step form implementing the setup wizard:
- Identity phase: text inputs, multi-select
- Sections phase: toggleable list with descriptions
- Source preferences phase: per-section configuration
- Review phase: full schema display with edit/confirm/cancel
- Competitor discovery: iterative batch presentation with toggle/search/done

Each step has a progress indicator showing wizard position (Step 2/5).

#### 2. Dashboard Screen (home / `recon status`)

Workspace status at a glance:

```
+-- recon // Acme Corp -- Developer Tools ----------------+
|                                                          |
|  Competitors    47 total                                 |
|    scaffolded    0  |  researched   12  |  verified  35  |
|    enriching     0  |  failed        0  |  disputed   0  |
|                                                          |
|  Own Products    3 total                                 |
|    verified      3                                       |
|                                                          |
|  Sections        8 defined                               |
|    Overview .... complete                                 |
|    Capabilities  complete                                 |
|    Pricing ..... 45/47                                    |
|    ...                                                    |
|                                                          |
|  Themes          7 discovered, 5 selected                |
|    synthesized   5  |  distilled  5  |  summarized  1   |
|                                                          |
|  Index           4200 chunks from 47 files               |
|    last indexed  2026-04-08 14:30                        |
|                                                          |
|  Cost            $142.30 spent across 3 runs             |
|    last run      $48.20 (verified tier)                  |
|                                                          |
+----------------------------------------------------------+
|  [R] Run  [S] Status detail  [B] Browse  [Q] Quit       |
+----------------------------------------------------------+
```

#### 3. Run Monitor Screen (active pipeline)

Shows real-time pipeline execution with high granularity:

```
+-- Run #4 // Research -- Capabilities section -----------+
|                                                          |
|  Phase: Research (2/6)  Section: Capabilities (3/8)      |
|  Progress: [==========>          ] 24/47  51%            |
|  Workers: 10 active  |  ETA: ~12 min  |  Cost: $18.40   |
|                                                          |
|  Worker Status:                                          |
|    W01  Cursor ........... searching capabilities        |
|    W02  Linear ........... writing section               |
|    W03  GitHub Actions ... validating format             |
|    W04  CircleCI ......... Y complete                    |
|    W05  GitLab ........... searching capabilities        |
|    W06  Jenkins .......... Y complete                    |
|    W07  Buildkite ........ retrying (format error #1)    |
|    W08  Drone ............ Y complete                    |
|    W09  Semaphore ........ searching capabilities        |
|    W10  Earthly .......... Y complete                    |
|                                                          |
|  Recent:                                                 |
|    14:32:01  CircleCI -- Capabilities -- Y verified      |
|    14:31:58  Jenkins -- Capabilities -- Y verified       |
|    14:31:45  Drone -- Capabilities -- ~ 1 claim unverif  |
|    14:31:30  Earthly -- Capabilities -- Y verified       |
|                                                          |
|  Errors (0) | Warnings (1):                              |
|    Buildkite: table missing Evidence column, retry 1/3   |
|                                                          |
+----------------------------------------------------------+
|  [P] Pause  [S] Stop  [K] Skip  [R] Retry failed        |
+----------------------------------------------------------+
```

**Features:**
- Per-worker status showing competitor name, current operation, progress
- Live cost accumulator (running total for this run)
- Estimated time remaining
- Recent activity feed (scrolling log of completed items with status)
- Error/warning feed with actionable details
- Retro ASCII progress bars with block characters
- Controls: pause, stop, skip competitor, retry failed

#### 4. Competitor Browser Screen

Browse and search profiles with verification status:

```
+-- Competitors (47) ----- Filter: [all] Sort: [name] ---+
|                                                          |
|  Name              Tier          Status     Verified     |
|  ----              ----          ------     --------     |
|> Cursor            Established   verified   47/48 Y      |
|  Linear            Established   verified   48/48 Y      |
|  GitHub Actions    Established   verified   45/48 Y      |
|  CircleCI          Established   enriching  40/48 Y      |
|  Buildkite         Emerging      verified   46/48 Y      |
|  Earthly           Experimental  researched 32/48 ~      |
|  ...                                                     |
|                                                          |
+-- Cursor -- Detail ----- Verification: 98% --------+    |
|                                                      |    |
|  Overview .......... Y verified (4/4 sources)        |    |
|  Capabilities ...... Y verified (6/6 sources)        |    |
|  Pricing ........... Y verified (3/3 sources)        |    |
|  Integration ....... ~ 1 unverified claim            |    |
|  Enterprise ........ Y verified (5/5 sources)        |    |
|  Developer Love .... Y verified (8/8 sources)        |    |
|  Head-to-Head ...... Y verified (4/4 sources)        |    |
|  Strategic Notes ... Y verified (3/3 sources)        |    |
|                                                      |    |
|  [Enter] View section  [O] Open file  [R] Re-run    |    |
+------------------------------------------------------+    |
|                                                          |
+----------------------------------------------------------+
|  [/] Search  [F] Filter  [S] Sort  [ESC] Back           |
+----------------------------------------------------------+
```

**Features:**
- Searchable, filterable competitor list (by tier, threat level, status, theme, staleness)
- Detail panel showing per-section verification status
- Drill into individual sections to see sources with verification status
- Quick actions: open file, re-run research, view in full

### Theme Curation Screen

Shown during Phase 5b when themes are discovered. The pipeline pauses here.

```
+-- Theme Discovery -- 50 profiles analyzed ---------------+
|                                                           |
|  Discovered 7 themes:                                     |
|                                                           |
|  [x] 1. Platform Consolidation  (38 competitors, strong)  |
|  [x] 2. Agentic Shift           (31 competitors, strong)  |
|  [x] 3. Developer Experience    (45 competitors, strong)   |
|  [x] 4. Pricing Race            (29 competitors, moderate) |
|  [ ] 5. Enterprise Lock-in      (18 competitors, moderate) |
|  [x] 6. Open Source Moats       (22 competitors, moderate) |
|  [ ] 7. Vertical Specialization (12 competitors, weak)     |
|                                                           |
+-----------------------------------------------------------+
|  [Space] Toggle  [E] Edit name  [V] View evidence         |
|  [+] Investigate a topic  [D] Done -- synthesize selected  |
+-----------------------------------------------------------+
```

## State Management

### SQLite Database (`.recon/state.db`)

Single database file replaces the legacy system's scattered JSON logs (`processed.json`, `p3_processed.json`, etc.).

**Why SQLite:**
- Local, single-file, no server
- Survives crashes (WAL mode)
- Queryable for dashboard displays
- Transactional (state updates are atomic)
- Fast enough for this workload

### Schema

**runs table:**
```sql
CREATE TABLE runs (
    id TEXT PRIMARY KEY,
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    status TEXT NOT NULL,  -- idle, planning, running, paused, stopping, stopped, failed, completed
    config_snapshot TEXT,  -- JSON snapshot of recon.yaml at run start
    verification_tier TEXT,  -- standard, verified, deep_verified
    total_cost_usd REAL DEFAULT 0,
    total_input_tokens INTEGER DEFAULT 0,
    total_output_tokens INTEGER DEFAULT 0
);
```

**tasks table:**
```sql
CREATE TABLE tasks (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(id),
    competitor TEXT NOT NULL,
    phase TEXT NOT NULL,      -- research, verify, enrich_cleanup, enrich_sentiment, enrich_strategic, index, synthesize
    section TEXT,             -- nullable (not all phases are per-section)
    status TEXT NOT NULL,     -- pending, running, completed, failed, disputed, skipped
    worker_id TEXT,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    cost_usd REAL DEFAULT 0,
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0
);
```

**verification_results table:**
```sql
CREATE TABLE verification_results (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES tasks(id),
    competitor TEXT NOT NULL,
    section TEXT NOT NULL,
    source_url TEXT,
    claim_text TEXT NOT NULL,
    agent TEXT NOT NULL,        -- agent_a, agent_b, agent_c
    status TEXT NOT NULL,       -- confirmed, corroborated, unverified, disputed
    evidence_summary TEXT,      -- what the verification agent found
    verified_at TIMESTAMP NOT NULL
);
```

**file_hashes table (for incremental indexing):**
```sql
CREATE TABLE file_hashes (
    filepath TEXT PRIMARY KEY,
    hash TEXT NOT NULL,
    last_indexed_at TIMESTAMP NOT NULL
);
```

**cost_history table (for refining estimates):**
```sql
CREATE TABLE cost_history (
    id TEXT PRIMARY KEY,
    section_type TEXT NOT NULL,
    phase TEXT NOT NULL,
    model TEXT NOT NULL,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    cost_usd REAL NOT NULL,
    recorded_at TIMESTAMP NOT NULL
);
```

### Pipeline State Machine

**Run-level states:**
```
idle --> planning --> running --> paused --> running --> completed
                       |                      |
                       v                      v
                     failed              stopping --> stopped
```

**Per-competitor states:**
```
pending --> researching --> verifying --> enriching --> verified --> indexed
                |               |             |
                v               v             v
             failed          disputed       failed
```

**State transitions:**
- `idle -> planning`: User starts a run. Engine analyzes what needs to happen (diff, cost estimate).
- `planning -> running`: User confirms the plan. Workers dispatched.
- `running -> paused`: User pauses. No new work dispatched. In-flight workers finish.
- `paused -> running`: User resumes. Workers dispatched for remaining work.
- `running -> stopping`: User stops. Cancel signal sent to workers.
- `stopping -> stopped`: All in-flight work completed or cancelled. State saved.
- `stopped -> planning`: User restarts. Engine re-analyzes from saved state.
- `running -> completed`: All planned work finished successfully.
- `running -> failed`: Unrecoverable error (e.g., API key invalid, rate limited permanently).

### Per-Section Timestamps

The state DB tracks timestamps per section per competitor (via the tasks table). This enables:
- Diff updates: "Pricing section for Cursor was last researched 3 months ago"
- Staleness detection: "42 competitors have Developer Sentiment older than the recency threshold"
- Granular re-runs: "Re-research only the Pricing section for these 5 competitors"

## Error Logging and Debug

### LLM-Assisted Diagnostics

Pipeline runs are expensive. When something fails at competitor #200, you need intelligent diagnostics, not just a stack trace.

**When an error occurs:**
1. Full error context captured: stack trace, input data (prompt sent), API response (or lack thereof), competitor/section/phase context
2. An LLM analyzes the error and suggests a fix/retry strategy
3. Diagnosis surfaced in the TUI error feed with actionable suggestion
4. Full debug log written to `.recon/logs/{run_id}/{timestamp}_error.json`

**Error categories and handling:**

| Category | Example | Auto-handling |
|---|---|---|
| Rate limit | 429 from Anthropic API | Exponential backoff, auto-retry |
| Format validation | Table missing column | Re-prompt with specific failure, max 3 retries |
| API error | 500, timeout | Retry with backoff, max 3 retries |
| Auth error | 401, invalid key | Halt run, surface to user immediately |
| Content filter | Model refuses to generate | Log, skip competitor, surface to user |
| Parse error | Can't extract structured output | Re-prompt with clearer instructions, retry |

**LLM diagnosis triggers** when auto-handling fails (max retries exceeded) or for unexpected errors. The diagnostic LLM receives the error context and returns:
- What likely went wrong (plain language)
- Suggested fix (if actionable)
- Whether to retry, skip, or halt

**Log structure:**
```
.recon/
  logs/
    run_abc123/
      run.log              -- full run log (timestamps, phase transitions, costs)
      errors/
        001_cursor_capabilities_format.json  -- individual error with context
        002_linear_pricing_timeout.json
      diagnostics/
        001_cursor_capabilities.md  -- LLM diagnosis for the error above
```

### Debug Mode

`--debug` flag (or `[D]` toggle in TUI) enables verbose logging:
- Every API call logged with full prompt and response
- Token counts per call
- Timing information
- State transitions
- Written to `.recon/logs/{run_id}/debug.log`

This is expensive in disk space but invaluable for debugging prompt issues or understanding why a particular competitor's output looks wrong.
