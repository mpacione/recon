# recon — Competitive Intelligence CLI

> Structured competitive landscape research, synthesis, and analysis powered by LLMs and local vector search.

## What This Is

`recon` is a CLI tool that automates the competitive intelligence workflow: research competitors via web search, structure findings into a consistent schema, index everything locally, then synthesize strategic themes across the full landscape. Outputs are markdown files organized for Obsidian (or any markdown-based knowledge base).

It was extracted from a production system that analyzed 288 competitors across 9 strategic themes for Atlassian's developer tools portfolio.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        recon CLI                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐    │
│  │   Collect     │  │   Index      │  │   Synthesize       │    │
│  │              │  │              │  │                    │    │
│  │  research    │  │  embed       │  │  synthesize        │    │
│  │  enrich      │  │  retrieve    │  │  distill           │    │
│  │  cleanup     │  │  tag         │  │  summarize         │    │
│  └──────┬───────┘  └──────┬───────┘  └────────┬───────────┘    │
│         │                 │                    │                │
│         ▼                 ▼                    ▼                │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    Workspace                             │   │
│  │                                                         │   │
│  │  workspace/                                             │   │
│  │  ├── recon.yaml           # Project config              │   │
│  │  ├── schema.md            # Competitor profile schema   │   │
│  │  ├── template.md          # Blank competitor template   │   │
│  │  ├── competitors/         # Individual profiles (.md)   │   │
│  │  ├── own-products/        # Your product profiles       │   │
│  │  ├── themes/              # Synthesized theme docs      │   │
│  │  │   └── _deep/           # Full multi-pass analysis    │   │
│  │  ├── .vectordb/           # ChromaDB (gitignored)       │   │
│  │  └── .retrieved/          # Retrieval cache (gitignored)│   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Core Concepts

### Workspace
A directory containing all competitive intelligence for a domain. Created with `recon init`. Contains config, schema, templates, competitor profiles, and synthesized outputs. Designed to be an Obsidian vault or live inside one.

### Profile
A markdown file with YAML frontmatter describing a single entity (competitor or own product). Follows the schema defined in `schema.md`. Profiles progress through research stages: `scaffold` → `p1-complete` → `p2-complete` → `p3-complete` → `verified`.

### Theme
A strategic lens for cross-cutting analysis (e.g., "Agentic Shift", "Platform Wars"). Defined in `recon.yaml` with semantic queries for retrieval. Themes are the unit of synthesis.

### Pipeline Stages
The system processes data in stages, each building on the last. Stages are idempotent — safe to re-run. Progress is tracked per-file via frontmatter `research_status` and per-batch via JSON logs.

## CLI Commands

### `recon init`

Interactive workspace setup. Creates directory structure, config file, and starter templates.

```bash
recon init [directory]

# Interactive prompts:
# - Company name (for "your company" context in prompts)
# - Products/offerings to compare against
# - Domain description ("developer tools", "project management", etc.)
# - Initial competitor list (optional, can add later)
# - Initial themes (optional, can configure later)
```

**Generates:**
- `recon.yaml` — project config (company, products, model settings, theme definitions)
- `schema.md` — competitor profile schema (customizable)
- `template.md` — blank competitor template
- `.gitignore` — excludes .vectordb/, .retrieved/, .env

### `recon add <name>`

Scaffold a new competitor profile from the template.

```bash
recon add "Cursor"
recon add "Cursor" --research    # Scaffold + immediately run P1 research
recon add --from-list competitors.txt  # Bulk scaffold from file
```

### `recon research <target>`

Run LLM-powered web research to populate a competitor profile. This is P1 — initial deep research.

```bash
recon research "Cursor"          # Research single competitor
recon research --all --status scaffold  # Research all scaffolds
recon research --workers 5       # Parallel research (careful with rate limits)
recon research --dry-run         # Show what would be researched
```

**How it works:**
1. Reads the profile template and schema
2. Constructs search queries from the competitor name + domain context
3. Executes web searches (7-10+ queries per competitor)
4. Calls LLM with search results + schema to generate structured profile
5. Writes completed profile, sets `research_status: p1-complete`

### `recon enrich <target>`

Progressive enrichment passes. Each pass adds a layer of data.

```bash
recon enrich "Cursor" --pass cleanup     # P2: Format cleanup + schema alignment
recon enrich "Cursor" --pass sentiment   # P3: Developer sentiment via web search
recon enrich "Cursor" --pass strategic   # P3.5: Strategic fields enrichment
recon enrich --all --pass cleanup --workers 10
recon enrich --all --pass sentiment --workers 5  # Fewer workers (web search)
```

**Passes:**

| Pass | What It Does | API Calls | Workers |
|------|-------------|-----------|---------|
| `cleanup` | Format alignment, schema compliance, quality scoring | 1 LLM call/file | 10 |
| `sentiment` | Web search for quotes, reviews, traction data | 1 LLM call + searches/file | 5 |
| `strategic` | Enriches strategic metadata fields | 1 LLM call/file | 10 |

### `recon index`

Build the local vector database from all competitor profiles.

```bash
recon index                  # Full re-index
recon index --incremental    # Only new/changed files (future)
```

**How it works:**
1. Reads all markdown profiles with frontmatter
2. Skips `scaffold` and `skipped` status files
3. Chunks by markdown section (~500 tokens, 50 overlap)
4. Embeds with local sentence-transformers model (all-MiniLM-L6-v2)
5. Stores in ChromaDB (local, persistent, no server)

Takes 5-10 min for ~300 files on CPU. Embedding model downloads on first run (~90MB).

### `recon retrieve`

Semantic retrieval of relevant competitor chunks per theme.

```bash
recon retrieve --theme agentic_shift    # Single theme
recon retrieve --theme all              # All themes
recon retrieve --list                   # List available themes
```

**How it works:**
1. Loads theme queries from `recon.yaml`
2. Embeds each query, searches ChromaDB (top-50 per query)
3. Aggregates results by competitor, ranks by aggregate relevance score
4. Outputs `.retrieved/{theme}.json` with ranked competitors and top chunks

### `recon synthesize`

Generate theme analysis documents from retrieved context.

```bash
recon synthesize --theme agentic_shift           # Single pass
recon synthesize --theme agentic_shift --deep    # 4-pass deep synthesis
recon synthesize --theme all --deep              # All themes, deep
recon synthesize --theme agentic_shift --dry-run # Show context size + cost estimate
```

**Single pass**: Pattern synthesis → theme document
**Deep mode (4 passes):**

| Pass | Role | Temperature | Purpose |
|------|------|-------------|---------|
| 1 | Strategist | 0.3 | Pattern synthesis from evidence |
| 2 | Devil's advocate | 0.4 | Challenge assumptions, find counterexamples |
| 3 | Gap analyst | 0.2 | Compare against your actual product capabilities |
| 4 | Executive integrator | 0.2 | Reconcile all passes into actionable brief |

### `recon distill`

Condense deep synthesis into executive-friendly 1-pagers.

```bash
recon distill --theme agentic_shift
recon distill --theme all
```

Produces tight, structured summaries with: threat landscape table, competitive positioning, key questions, demo links.

### `recon summarize`

Cross-theme meta-synthesis. Reads all theme documents, identifies cross-cutting patterns, produces unified executive summary.

```bash
recon summarize              # From standard themes
recon summarize --deep       # From deep synthesis files
recon summarize --dry-run    # Show cost estimate
```

### `recon tag`

Write theme tags back to competitor profile frontmatter based on retrieval results.

```bash
recon tag                    # Tag all competitors
recon tag --dry-run          # Preview changes
recon tag --threshold 0.5    # Stricter relevance threshold
recon tag --top-n 20         # Fewer competitors per theme
```

### `recon status`

Dashboard of workspace state.

```bash
recon status

# Output:
# Competitors: 288 total
#   scaffold: 0 | p1: 12 | p2: 45 | p3: 200 | verified: 31
# Themes: 9 defined, 9 synthesized, 9 distilled
# Index: 4,200 chunks from 276 files (last indexed: 2026-01-25)
# Last full run: 2026-01-25
```

### `recon run`

Execute the full pipeline end-to-end.

```bash
recon run                          # Full pipeline
recon run --from index             # Skip collection, start from indexing
recon run --from synthesize --deep # Re-synthesize only
recon run --dry-run                # Show plan + cost estimate
```

**Default pipeline order:**
1. `enrich --all --pass cleanup`
2. `enrich --all --pass sentiment`
3. `index`
4. `retrieve --theme all`
5. `synthesize --theme all --deep`
6. `tag`
7. `distill --theme all`
8. `summarize --deep`

## Configuration (`recon.yaml`)

```yaml
# Project identity
project:
  name: "Competitive Landscape 2026"
  company: "Acme Corp"
  products:
    - name: "Acme CI"
      domain: "CI/CD"
      description: "Cloud CI/CD platform"
    - name: "Acme Review"
      domain: "Code Review"
      description: "Pull request and code review tool"
  domain_description: "Developer tools and DevOps platforms"

# Directory layout
paths:
  competitors: "competitors"
  own_products: "own-products"
  themes: "themes"
  vectordb: ".vectordb"

# Model configuration
models:
  research: "claude-sonnet-4-20250514"     # For P1-P3 research passes
  synthesis: "claude-opus-4-20250514"      # For theme synthesis
  distill: "claude-opus-4-20250514"        # For distillation
  temperature:
    research: 0.3
    synthesis: 0.3
    contrarian: 0.4     # Pass 2 devil's advocate
    gap_analysis: 0.2   # Pass 3
    integration: 0.2    # Pass 4
  max_tokens:
    research: 8192
    synthesis: 8192
    distill: 2000
    summary: 6000

# Embedding configuration
embedding:
  model: "all-MiniLM-L6-v2"
  chunk_size: 500
  chunk_overlap: 50

# Retrieval settings
retrieval:
  top_k: 50
  queries_per_theme: 4

# Orchestration
orchestration:
  default_workers: 10
  sentiment_workers: 5    # Fewer for web search passes
  batch_log_dir: ".logs"

# Theme definitions
themes:
  agentic_shift:
    title: "The Agentic Shift"
    output_file: "_AgenticShift.md"
    queries:
      - "autonomous agents executing tasks without human approval"
      - "plan-and-execute workflows where AI proposes and human approves"
      - "L4 L5 autonomy level fully autonomous agents"
      - "risks and limitations of autonomous AI"
      - "human oversight patterns in AI-assisted workflows"

  platform_wars:
    title: "Platform Wars: Who Owns the Orchestration Layer"
    output_file: "_PlatformWars.md"
    queries:
      - "platform strategy ecosystem lock-in"
      - "orchestration layer workflow ownership"
      - "extension marketplace plugin ecosystem moat"
      - "multi-tool interoperability vs walled garden"
  # ... more themes

# Schema configuration (which fields to include in frontmatter)
schema:
  # Core fields (always present)
  core:
    - name
    - domain
    - tier           # Established | Emerging | Experimental
    - threat_level   # High | Medium | Low | Watch
    - overlap        # Which of your products this competes with
    - last_updated
    - research_status

  # Extended fields (added during enrichment passes)
  extended:
    platform:
      - marketplace_size
      - api_surface
      - partner_ecosystem
      - lock_in_signals
    trust:
      - compliance_certs
      - audit_capabilities
      - admin_controls
    workflow:
      - interaction_model
      - context_sources
      - trigger_pattern
    time_to_value:
      - onboarding_friction
      - time_to_first_value
      - free_tier_limits
      - self_serve
```

## Profile Schema

The profile schema is the contract between collection and synthesis. It defines:

1. **Frontmatter fields** — structured metadata for filtering and retrieval
2. **Section structure** — markdown sections with quality requirements
3. **Rating scales** — consistent scoring (★ stars for capabilities, ✅/⚠️/❌ for status)
4. **Quality rubric** — 7-dimension scoring, minimum thresholds

The schema is stored as `schema.md` in the workspace and referenced by all prompts. Users customize it during `recon init` or edit directly.

**Key sections in a competitor profile:**
- Overview (150+ words, strategic context)
- Capabilities (table with star ratings + evidence notes)
- Agentic Capabilities (status table + strategic analysis prose)
- Integration Ecosystem (status table + strategic analysis prose)
- Enterprise Readiness (status table + analysis)
- Developer Love (sentiment, quotes, traction metrics, analysis)
- Head-to-Head comparison (table + response options: build/buy/partner/ignore)
- Strategic Notes (watch signals, partnership potential, acquisition consideration)
- Sources (4 subsections: queries used, primary, community, third-party)

## Implementation Plan

### Phase 1: Core CLI + Workspace (MVP)

**Goal:** `recon init`, `recon add`, `recon status`, workspace structure

```
recon/
├── pyproject.toml
├── src/
│   └── recon/
│       ├── __init__.py
│       ├── cli.py              # Click/Typer CLI entrypoint
│       ├── config.py           # Load/validate recon.yaml
│       ├── workspace.py        # Init, paths, validation
│       ├── profile.py          # Read/write/validate profiles
│       └── defaults/           # Default templates
│           ├── recon.yaml      # Starter config
│           ├── schema.md       # Default schema
│           └── template.md     # Default competitor template
├── tests/
└── README.md
```

**Tech stack:**
- Python 3.11+
- Click or Typer for CLI
- python-frontmatter for markdown parsing
- pyyaml for config
- Rich for terminal output

### Phase 2: Research + Enrichment

**Goal:** `recon research`, `recon enrich`

```
src/recon/
├── research.py         # P1 research orchestration
├── enrich.py           # P2/P3/P3.5 enrichment passes
├── orchestrator.py     # Async batch processing engine
├── prompts/
│   ├── research.py     # Research prompt builder
│   ├── cleanup.py      # P2 cleanup prompt
│   ├── sentiment.py    # P3 sentiment prompt
│   └── strategic.py    # P3.5 strategic prompt
└── llm.py              # Anthropic API client wrapper
```

**Dependencies added:** anthropic, asyncio

### Phase 3: Index + Retrieve

**Goal:** `recon index`, `recon retrieve`, `recon tag`

```
src/recon/
├── index.py            # ChromaDB indexing
├── retrieve.py         # Semantic retrieval per theme
├── tag.py              # Write theme tags to frontmatter
└── chunker.py          # Markdown section chunking
```

**Dependencies added:** chromadb, sentence-transformers, tqdm

### Phase 4: Synthesis

**Goal:** `recon synthesize`, `recon distill`, `recon summarize`, `recon run`

```
src/recon/
├── synthesize.py       # Single + deep multi-pass synthesis
├── distill.py          # Deep → executive 1-pager
├── summarize.py        # Cross-theme meta-synthesis
├── pipeline.py         # Full pipeline orchestration
└── prompts/
    ├── synthesis.py    # Theme synthesis prompts (4 passes)
    ├── distill.py      # Distillation prompt
    └── summary.py      # Meta-synthesis prompt
```

### Phase 5: Polish

- `recon run` end-to-end pipeline
- Cost estimation (`--dry-run` on all commands)
- Progress tracking (Rich progress bars)
- Incremental indexing
- Export formats (HTML battlecard, PPTX via python-pptx)

## Key Design Decisions

### Domain-agnostic prompts
All prompts are parameterized by `recon.yaml` config. Instead of "Atlassian" hardcoded, prompts inject `{company}`, `{products}`, `{domain}`. The system prompt for synthesis reads the user's `schema.md` and product profiles dynamically.

### Schema as contract
The `schema.md` file is the single source of truth. All prompts reference it. Users can customize it to add domain-specific fields (e.g., `compliance_certs` matters for enterprise tools, not for consumer apps).

### Progressive enrichment
Profiles aren't built in one shot. Each pass adds a layer, with progress tracked in frontmatter. This means you can re-run any pass without losing prior work, and cost scales with what you actually need.

### Local-first vector search
ChromaDB + sentence-transformers runs entirely locally. No vector DB service, no API key for embeddings. The only API calls are to Claude for research and synthesis.

### Async batch processing
The orchestrator pattern (semaphore-controlled async) is battle-tested from the original system. Processed files are tracked in JSON logs, so interrupted runs resume where they left off.

## Cost Model

| Operation | Model | Cost per unit | Typical run |
|-----------|-------|--------------|-------------|
| Research (P1) | Sonnet | ~$0.10-0.20/competitor | $30-60 for 300 competitors |
| Cleanup (P2) | Sonnet | ~$0.05-0.10/competitor | $15-30 for 300 |
| Sentiment (P3) | Sonnet | ~$0.10-0.20/competitor | $30-60 for 300 |
| Indexing | Local | Free | Free |
| Retrieval | Local | Free | Free |
| Synthesis (single) | Sonnet | ~$0.15-0.30/theme | $2-3 for 9 themes |
| Synthesis (deep) | Opus | ~$5-8/theme | $45-72 for 9 themes |
| Distillation | Opus | ~$1-2/theme | $9-18 for 9 themes |
| Meta-synthesis | Opus | ~$8-12 | $8-12 |
| **Full pipeline (Sonnet)** | | | **~$80-150** |
| **Full pipeline (Opus deep)** | | | **~$150-250** |

## Prior Art / Source Files

This spec was derived from these source files in the original Atlassian competitive landscape project:

| Source File | Maps To |
|-------------|---------|
| `_Prompts/README.md` | Overall pipeline documentation |
| `_Prompts/_Schema.md` | `schema.md` default template |
| `_Prompts/_CompetitorTemplate.md` | `template.md` default template |
| `_Prompts/_FormatStandards.md` | Quality rubric, format rules |
| `_Prompts/00_SingleCompetitorProfile.md` | `recon research` prompt |
| `_Prompts/_BatchCleanup/p2_orchestrator.py` | `recon enrich --pass cleanup` |
| `_Prompts/_BatchCleanup/p3_orchestrator.py` | `recon enrich --pass sentiment` |
| `_Prompts/_BatchCleanup/worker_prompt.md` | Cleanup worker prompt |
| `_Prompts/p4_pipeline/config.yaml` | `recon.yaml` theme definitions |
| `_Prompts/p4_pipeline/01_index.py` | `recon index` |
| `_Prompts/p4_pipeline/02_retrieve.py` | `recon retrieve` |
| `_Prompts/p4_pipeline/03_synthesize_deep.py` | `recon synthesize --deep` |
| `_Prompts/p4_pipeline/04_tag_themes.py` | `recon tag` |
| `_Prompts/p4_pipeline/05_meta_synthesis.py` | `recon summarize` |
| `_Prompts/p4_pipeline/06_distill.py` | `recon distill` |
