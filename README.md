# recon

Competitive intelligence CLI and TUI. Structured research, multi-agent verification, local vector search, LLM-powered synthesis.

**Status:** Engine complete (202 tests), TUI foundation in place. Discovery wizard and live run monitor coming next.

## What it does

1. **Discover** -- iterative competitor discovery with LLM agents and user checkpoints
2. **Research** -- section-by-section LLM research across all competitors, driven by a YAML schema
3. **Verify** -- multi-agent consensus verification (standard / verified / deep) with per-source status tracking
4. **Enrich** -- three progressive passes: format cleanup, developer sentiment, strategic analysis
5. **Index** -- chunk profiles by section, embed locally with fastembed, store in ChromaDB
6. **Discover themes** -- K-means clustering on embeddings surfaces themes from the data (not user-defined)
7. **Synthesize** -- single-pass or deep 4-pass analysis (strategist, devil's advocate, gap analyst, executive integrator)
8. **Deliver** -- distill to executive 1-pagers, cross-theme meta-synthesis

## Quick start

```bash
pip install -e ".[dev]"

# Initialize a workspace
recon init my-landscape --domain "Developer Tools" --company "Acme Corp" --products "Acme IDE"
cd my-landscape

# Add competitors
recon add "GitHub Copilot"
recon add "Cursor"
recon add "Acme IDE" --own-product

# Check workspace status
recon status

# See what research would do (dry run)
recon research --all --dry-run

# Index profiles into the local vector DB
recon index

# Semantic search across all profiles
recon retrieve --query "AI code generation"

# Launch the interactive TUI
recon tui

# See full pipeline plan
recon run --dry-run
```

## Architecture

Three-layer design with clear separation of concerns:

```
Interface Layer        Engine Layer              Data Layer
+-----------------+    +---------------------+   +------------------+
| CLI (Click)     | -> | Pipeline Orchestrator|   | Workspace (.md)  |
| TUI (Textual)   |    | Research Orchestrator|   | ChromaDB vectors |
|   warm amber    |    | Verification Engine |   | SQLite state     |
|   retro theme   |    | Enrichment Pipeline |   | Evidence store   |
+-----------------+    | Synthesis Engine    |   +------------------+
                       | Cost Tracker        |
                       | Prompt Composer     |
                       | Format Validator    |
                       | Worker Pool (async) |
                       | Theme Discovery     |
                       +---------------------+
```

**Schema drives everything.** The `recon.yaml` schema defines sections, allowed formats, rating scales, source preferences, and verification tiers. Worker prompts are auto-generated from schema metadata at composition time.

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
| `workers.py` | Semaphore-controlled async worker pool |
| `research.py` | Section-by-section research orchestrator |
| `verification.py` | Multi-agent consensus (standard/verified/deep) |
| `enrichment.py` | Cleanup, sentiment, and strategic enrichment passes |
| `index.py` | Markdown chunking + ChromaDB vector index + semantic retrieval |
| `themes.py` | K-means clustering theme discovery |
| `synthesis.py` | Single-pass + deep 4-pass synthesis engine |
| `deliver.py` | Distillation + cross-theme meta-synthesis |
| `pipeline.py` | Full pipeline orchestrator with state tracking |
| `tui/` | Textual app with warm amber retro terminal aesthetic |

## Design

Full design documentation lives in `design/`:

- `pipeline.md` -- 6-phase pipeline (setup, research, verify, enrich, synthesize, deliver)
- `architecture.md` -- three-layer system architecture, TUI design, state management
- `research-and-verification.md` -- research model, verification protocol, format constraints
- `setup-and-discovery.md` -- wizard, discovery, theme discovery, own-product research
- `operations.md` -- run planner, incremental runs, cost estimation
- `README.md` -- design principles overview

## Development

```bash
# Create venv and install
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=recon --cov-report=term-missing

# Lint
ruff check src/ tests/
```

TDD is non-negotiable. Every line of production code responds to a failing test.

## Prior art

Extracted from a production system that analyzed 288 competitors across 9 strategic themes for Atlassian's developer tools portfolio. The original system's 12 brittleness points are documented in `design/` and systematically addressed in the redesign.
