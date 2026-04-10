```
░▒▓███████▓▒░░▒▓████████▓▒░▒▓██████▓▒░ ░▒▓██████▓▒░░▒▓███████▓▒░  
░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░     ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░ 
░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░     ░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░ 
░▒▓███████▓▒░░▒▓██████▓▒░░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░ 
░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░     ░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░ 
░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░     ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░ 
░▒▓█▓▒░░▒▓█▓▒░▒▓████████▓▒░▒▓██████▓▒░ ░▒▓██████▓▒░░▒▓█▓▒░░▒▓█▓▒░
```

A CLI and TUI for competitive intelligence research. Recon orchestrates LLM agents to discover competitors, research them section-by-section against a structured schema, and synthesize the results into thematic analyses and executive summaries -- all stored locally as Obsidian-compatible markdown.

> **Status: v0.1 (alpha).** Both the CLI and the TUI can now run the full pipeline end-to-end against the live Anthropic API. See [`design/wiring-audit.md`](design/wiring-audit.md) for the wiring audit and [`CHANGELOG.md`](CHANGELOG.md) for what's fixed since the initial alpha.

## Status

| Component | State | Notes |
|---|---|---|
| Engine layer (pipeline, research, verification, enrichment, index, themes, synthesis, deliver, discovery, tag) | **Stable** | 400+ unit tests, 25 integration tests, lint clean |
| `recon init` / `add` / `status` | **Stable** | Headless init produces full 8-section default schema |
| `recon discover` | **Stable** | Uses `web_search_20250305` tool for live competitor discovery |
| `recon research [target | --all]` | **Stable** | Target argument now honored; single-profile filtering case-insensitive |
| `recon enrich [target | --all]` | **Stable** | Target argument honored; unknown names error clearly |
| `recon index` / `retrieve` | **Stable** | Local fastembed + ChromaDB, incremental via SHA-256 hashes |
| `recon tag` | **Stable** | K-means clustering with LLM-generated strategic theme labels |
| `recon synthesize` / `distill` / `summarize` | **Stable** | Single-pass + deep 4-pass synthesis, distillation, meta-synthesis |
| `recon run` (full pipeline) | **Stable** | End-to-end: research → verify → enrich → index → themes → synthesize → deliver. Writes `themes/<slug>.md`, `themes/distilled/<slug>.md`, and `executive_summary.md`. |
| TUI: welcome / wizard / dashboard / discovery / browser | **Working** | Screens render, navigate, accept input, write profiles |
| TUI: run button → planner → pipeline execution | **Working** | Planner-to-pipeline wiring landed; `FULL_PIPELINE`, `UPDATE_ALL`, `UPDATE_SPECIFIC` operations call the real engine via `tui/pipeline_runner.py` |
| TUI: competitor selector (update specific) | **Working** | Pushed from planner when the chosen op needs targets |
| TUI: diff update / rerun failed operations | **WIP** | Planner options exist but the engine logic is not yet implemented; selecting these notifies the user |
| Real-API E2E tests | **Available** | Opt-in via `ANTHROPIC_API_KEY`, tests in `tests/test_e2e_real.py` |
| Fake-LLM CLI E2E tests | **Stable** | `tests/test_cli_e2e_fake_llm.py` covers `research`, `enrich`, and `run` via `CliRunner` |

## Dependencies and setup

**Requires Python 3.11+** and an [Anthropic API key](https://console.anthropic.com/) for LLM-powered features.

```bash
# Clone and install
git clone <repo-url> && cd recon
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Set your API key
export ANTHROPIC_API_KEY=sk-ant-...

# Verify
pytest tests/ -q
recon --version
```

### Core dependencies

| Package | Purpose |
|---------|---------|
| [click](https://click.palletsprojects.com/) | CLI framework |
| [textual](https://textual.textualize.io/) | Terminal UI (warm amber retro aesthetic) |
| [anthropic](https://docs.anthropic.com/en/api) | Claude API client (async) |
| [chromadb](https://docs.trychroma.com/) | Local vector database for semantic search |
| [fastembed](https://qdrant.github.io/fastembed/) | Local embedding model (no API calls for indexing) |
| [pydantic](https://docs.pydantic.dev/) v2 | Schema validation |
| [aiosqlite](https://aiosqlite.omnilib.dev/) | Async SQLite for run/task state |
| [python-frontmatter](https://python-frontmatter.readthedocs.io/) | YAML frontmatter in markdown profiles |

### Dev dependencies

pytest, pytest-asyncio, pytest-cov, ruff

## How it works

Recon is schema-driven. A `recon.yaml` file defines every aspect of the research: sections, allowed output formats, rating scales, source preferences, and verification tiers. Worker prompts are auto-generated from this schema at composition time -- there are no hardcoded prompts.

The pipeline has 8 phases:

```mermaid
graph LR
    A[Discover] --> B[Research]
    B --> C[Verify]
    C --> D[Enrich]
    D --> E[Index]
    E --> F[Themes]
    F --> G[Synthesize]
    G --> H[Deliver]

    style A fill:#fff7e6,stroke:#c88a2e,color:#333
    style B fill:#fff7e6,stroke:#c88a2e,color:#333
    style C fill:#fff7e6,stroke:#c88a2e,color:#333
    style D fill:#fff7e6,stroke:#c88a2e,color:#333
    style E fill:#fff7e6,stroke:#c88a2e,color:#333
    style F fill:#fff7e6,stroke:#c88a2e,color:#333
    style G fill:#fff7e6,stroke:#c88a2e,color:#333
    style H fill:#fff7e6,stroke:#c88a2e,color:#333
```

**1. Discover** -- An LLM agent searches for competitors in batches. Users review candidates, toggle accept/reject, and the agent refines its search based on the pattern. Deduplication by URL domain across rounds.

**2. Research** -- Section-by-section batching across all competitors (not competitor-by-competitor). Each section is researched for every competitor before moving to the next, which produces more consistent and comparable output.

**3. Verify** -- Multi-agent consensus at three tiers: standard (single pass), verified (2-agent agreement), and deep (3-agent + reconciliation). Verification tier is set per-section in the schema.

**4. Enrich** -- Three progressive passes over the raw research: format cleanup (fix structure, sources, tables), developer sentiment (community perception, NPS signals), and strategic analysis (moats, risks, trajectory).

**5. Index** -- Profiles are chunked by section, embedded locally with fastembed, and stored in ChromaDB. Incremental indexing via SHA-256 file hashes in SQLite skips unchanged files on re-runs.

**6. Discover themes** -- K-means clustering on the embeddings surfaces themes from the data (not user-defined). Themes are ranked by evidence strength. Users curate: toggle, rename, investigate topics the clustering missed.

**7. Synthesize** -- Single-pass or deep 4-pass mode. Deep synthesis runs four agents in sequence: strategist, devil's advocate, gap analyst, and executive integrator. Each pass builds on the previous.

**8. Deliver** -- Distills each theme into an executive 1-pager, then runs cross-theme meta-synthesis to produce the final executive summary.

### Architecture

Three layers with strict separation:

```mermaid
graph LR
    subgraph Interface["Interface Layer"]
        CLI["CLI (Click)"]
        TUI["TUI (Textual)"]
    end

    subgraph Engine["Engine Layer"]
        Discovery["Discovery"]
        Research["Research + Verification"]
        Enrichment["Enrichment"]
        Index["Index + Themes"]
        Synthesis["Synthesis + Delivery"]
        Pipeline["Pipeline Orchestrator"]
    end

    subgraph Data["Data Layer"]
        Workspace["Workspace (.md)"]
        Vectors["ChromaDB"]
        State["SQLite"]
    end

    CLI --> Engine
    TUI --> Engine
    Engine --> Workspace
    Engine --> Vectors
    Engine --> State

    style Interface fill:#fff7e6,stroke:#c88a2e,color:#333
    style Engine fill:#fff7e6,stroke:#c88a2e,color:#333
    style Data fill:#fff7e6,stroke:#c88a2e,color:#333
```

All LLM calls go through a single async client wrapper with token counting. The worker pool uses semaphore-controlled concurrency. The pipeline orchestrator tracks state in SQLite so runs can resume from any phase.

## What it does

### CLI commands

```bash
# Workspace setup
recon init <dir> --domain "Developer Tools" --company "Acme" --products "Acme CI"
recon add "Cursor"                    # add a competitor
recon add "Acme CI" --own-product     # research your own product through the same lens
recon status                          # workspace dashboard

# Discovery
recon discover --rounds 3 --seed "VS Code" --seed "Cursor"
recon discover --auto-accept          # non-interactive mode

# Research and enrichment
recon research --all --dry-run        # preview research plan
recon research --all --workers 10     # run with 10 parallel workers
recon enrich --all --pass cleanup     # format cleanup pass
recon enrich --all --pass sentiment   # developer sentiment pass
recon enrich --all --pass strategic   # strategic analysis pass

# Indexing and search
recon index                           # incremental by default
recon index --full                    # re-index everything
recon retrieve --query "pricing model" --n-results 20

# Theme discovery and tagging
recon tag --n-themes 7                # discover themes and tag profiles
recon tag --dry-run --threshold 0.4   # preview tag assignments

# Synthesis and delivery
recon synthesize --theme "Platform Consolidation"
recon synthesize --theme "Developer Experience" --deep
recon distill --theme all
recon summarize                       # cross-theme executive summary

# Full pipeline
recon run --dry-run                   # show plan + cost estimate
recon run                             # execute everything
recon run --from research --deep      # resume from a stage, deep synthesis

# TUI (partial -- see Status section)
recon tui                             # launch the interactive UI
```

### Verified end-to-end flow

The full CLI pipeline has been exercised against the live Anthropic API
using DuckDuckGo as a test scenario. Every stage produced real artifacts:

```bash
# 1. Create workspace with 8-section default schema
recon init ~/recon/my-project --headless \
  --domain "privacy-focused search engines" \
  --company "DuckDuckGo" \
  --products "DuckDuckGo Search"

# 2. Discover competitors via live web search
cd ~/recon/my-project
recon discover --rounds 1 --batch-size 10 --seed "DuckDuckGo" --auto-accept
# → 12-15 candidates with real URLs, tiers, and provenance

# 3. Research each section of each competitor via live web search
recon research --all --workers 3
# → profiles filled with multi-paragraph sections and cited sources

# 4. Index into local ChromaDB
recon index
# → chunks by section, local fastembed embeddings, no API cost

# 5. Retrieve semantically
recon retrieve --query "decentralized peer to peer search engine" --n-results 5

# 6. Discover themes (k-means) and label via LLM
recon tag --n-themes 3
# → strategic labels like "Privacy-First Search Infrastructure"

# 7. Synthesize, distill, meta-summarize
recon synthesize --theme "Privacy-First Search Infrastructure"
recon distill --theme "Privacy-First Search Infrastructure"
recon summarize
# → themes/*.md, themes/distilled/*.md, executive_summary.md
```

**Cost profile** (measured on the 3-competitor × 8-section verification run):

| Stage | Input tokens | Output tokens | Approx cost |
|---|---:|---:|---:|
| discover (1 round, web search) | ~225K | ~2K | ~$0.70 |
| research (24 calls, web search) | 1.88M | 40K | ~$6 |
| index + retrieve + tag labeling | ~3K | ~50 | <$0.01 |
| synthesize (single pass) | 21K | 1.4K | ~$0.10 |
| distill + summarize | ~1K | ~1.5K | ~$0.03 |
| **Total** | **~2.1M** | **~45K** | **~$7** |

Research cost dominates because `web_search_20250305` inflates input
tokens 100× over training-data-only calls. That's the right tradeoff
for competitive intelligence -- results cite live sources dated today
instead of hallucinating from model training data.

### Profiles are plain markdown

Every competitor is a markdown file with YAML frontmatter, compatible with Obsidian and any markdown editor:

```markdown
---
name: Cursor
type: competitor
research_status: verified
domain: Developer Tools
themes:
  - AI-First Development
  - Developer Experience
---

## Overview

AI-native code editor built on VS Code...

## Capabilities

| Dimension | Rating | Evidence |
|-----------|--------|----------|
| ...       | ...    | ...      |
```

## Modules

| Module | Purpose |
|--------|---------|
| `schema.py` | Pydantic v2 schema parser -- the backbone |
| `workspace.py` | Workspace init, profile CRUD, Obsidian-compatible markdown |
| `state.py` | Async SQLite state store (runs, tasks, file hashes, costs) |
| `prompts.py` | Composable prompt assembly from schema metadata |
| `validation.py` | Deterministic format checks (emoji, sources, tables, word counts) |
| `cost.py` | Token estimation, model pricing, verification tier multipliers |
| `llm.py` | Async Anthropic client wrapper with usage tracking |
| `client_factory.py` | API key validation and client creation |
| `workers.py` | Semaphore-controlled async worker pool |
| `research.py` | Section-by-section research orchestrator |
| `verification.py` | Multi-agent consensus (standard/verified/deep) |
| `enrichment.py` | Cleanup, sentiment, and strategic enrichment passes |
| `index.py` | Markdown chunking + ChromaDB vector index + semantic retrieval |
| `incremental.py` | SHA-256 hash-based incremental indexing |
| `themes.py` | K-means clustering theme discovery (custom, no sklearn) |
| `tag.py` | Theme tagging via retrieval relevance aggregation |
| `synthesis.py` | Single-pass + deep 4-pass synthesis engine |
| `deliver.py` | Distillation + cross-theme meta-synthesis |
| `discovery.py` | Iterative competitor discovery with LLM agent |
| `pipeline.py` | Full pipeline orchestrator with state tracking |
| `logging.py` | Central file-based logging with live flush (`~/.recon/logs/recon.log`) |
| `tui/app.py` | Textual app with `MODES` (dashboard + run), global state |
| `tui/theme.py` | Warm amber retro terminal theme |
| `tui/widgets.py` | Status panel, competitor table, progress bar, curation/monitor panels |
| `tui/models/dashboard.py` | `DashboardData` + `build_dashboard_data` |
| `tui/models/curation.py` | Theme curation data model |
| `tui/models/monitor.py` | Run monitor data model |
| `tui/screens/welcome.py` | New/open/recent workspace picker + `RecentProjectsManager` |
| `tui/screens/wizard.py` | 4-phase schema wizard as a pushable `ModalScreen` |
| `tui/screens/dashboard.py` | Workspace dashboard + button-first action bar |
| `tui/screens/discovery.py` | Discovery candidate accumulation with live search |
| `tui/screens/planner.py` | 7-option run planner with clickable operation buttons |
| `tui/screens/run.py` | Live pipeline monitor (reactive state, not currently wired) |
| `tui/screens/curation.py` | Theme curation pipeline gate (`push_screen_wait`) |
| `tui/screens/browser.py` | Competitor browser with detail pane |
| `tui/screens/selector.py` | Competitor multi-select modal |

## Development

```bash
# Run tests (534 passing, 4 skipped real-API tests, ~35s)
pytest tests/ -q

# Run with coverage
pytest tests/ --cov=recon --cov-report=term-missing

# Lint
ruff check src/ tests/

# Real-API E2E tests (opt-in, costs pennies)
ANTHROPIC_API_KEY=sk-ant-... pytest tests/test_e2e_real.py -v
```

TDD is non-negotiable. Every line of production code responds to a failing test.

### Logging

The CLI writes structured logs to `~/.recon/logs/recon.log` on every
invocation:

```bash
recon --log-level DEBUG tui            # or any subcommand
tail -f ~/.recon/logs/recon.log
```

Every CLI entry point, LLM call, and pipeline stage logs start/finish
events with token counts. Use `--log-level DEBUG` to capture full
response text (truncated at 2000 chars) for diagnosing parser issues.

## Design docs

Full design documentation lives in [`design/`](design/):

| Document | Covers |
|----------|--------|
| [`design/README.md`](design/README.md) | Design principles (schema-driven, verification-first, local-first) |
| [`design/pipeline.md`](design/pipeline.md) | 8-phase pipeline, state machine, phase dependencies |
| [`design/architecture.md`](design/architecture.md) | Three-layer architecture, TUI design, SQLite state schema |
| [`design/research-and-verification.md`](design/research-and-verification.md) | Section-by-section batching, multi-agent consensus protocol, format constraints |
| [`design/setup-and-discovery.md`](design/setup-and-discovery.md) | Discovery flow, schema wizard, theme discovery, own-product research |
| [`design/operations.md`](design/operations.md) | Run planner, incremental runs, diff updates, cost estimation |

## License

MIT
