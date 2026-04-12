# Pipeline Design

> The full revised pipeline from workspace setup through executive delivery.

## Overview

The pipeline has 6 phases. Each phase builds on the last. All phases are idempotent — safe to re-run without data loss. Progress is tracked per-competitor, per-section in a SQLite state database.

```
Phase 1: Setup       — discover competitors, design schema, generate prompts
Phase 2: Research    — section-by-section research with independent agents
Phase 3: Verify      — multi-agent consensus verification
Phase 4: Enrich      — sentiment, strategic metadata, cleanup
Phase 5: Synthesize  — index, discover themes, retrieve, synthesize, distill
Phase 6: Deliver     — meta-synthesis, executive summary
```

Phases 2-3 repeat as a unit: every information-gathering step (research, sentiment, strategic enrichment) is followed by verification. Enrichment in Phase 4 also triggers verification for any new factual claims introduced.

## Phase 1: Setup

Setup is interactive. The pipeline does not spend money until the user explicitly confirms.

### 1a. Domain Discovery (`recon discover`)

An agent searches for competitors in the user's space using an iterative approach with user checkpoints.

**How it works:**
1. User provides a domain description ("CI/CD tools") and optionally 3-5 known competitors as seeds
2. Agent searches: market maps, analyst reports, "alternatives to X" lists, product directories (G2, ProductHunt, StackShare), funding databases (Crunchbase)
3. Agent presents a batch of 10-15 candidates to the user

**Each candidate shows:**
- Company name + URL (so user can verify it's real)
- 2-line blurb (what they do, scale, funding if notable)
- Provenance ("Found via: G2 category leader, 3x alternatives lists")
- Suggested tier (Established / Emerging / Experimental) based on signals like funding, employee count, analyst coverage

**User interaction:**
- Candidates are pre-checked by default (user unchecks unwanted ones)
- User can toggle individual entries, accept all, reject all
- User can add competitors manually
- User can request "search more" for broader coverage

**Refinement loop:**
- After each round, agent analyzes accepted/rejected patterns
- Agent suggests a search direction: "I noticed gaps in self-hosted options — want me to search there?"
- Repeats until user says "done"
- Agent pre-filters obvious junk (dead companies, unrelated products) but errs on inclusion

### 1b. Schema Wizard (`recon init`)

Guided conversational wizard in 3 phases. Must work as TUI interaction AND as LLM-callable flow.

**Phase 1 — Identity:**
- Company name
- Products/offerings to compare against
- Domain description
- What decisions this research will inform (build/buy/partner, investment, positioning, market entry, executive briefing)
- Toggle: "Want to research your own products through the same lens?" — if yes, own products become profiles with `type: own_product` in frontmatter, researched from an external perspective using public sources only

**Phase 2 — Sections:**
- System recommends sections based on the decision types selected
- User can accept defaults, add sections, remove sections, customize per-section
- For each section: sub-dimensions, rating scales, evidence types, search guidance
- Source preferences per section: primary sources, secondary sources, sources to avoid, recency threshold

**Phase 3 — Source Preferences:**
- For each selected section, the wizard asks about preferred sources
- Provides sensible defaults based on section type (e.g., pricing -> official pricing pages; sentiment -> HN/Reddit/G2)
- User adjusts as needed

**Note:** Themes are NOT defined during setup. They emerge from data during Phase 5 (see Theme Discovery below).

### 1c. Schema Review and Confirm

Full schema presented for review before anything is committed to disk.

**The review screen shows:**
- Domain, company, products
- All sections with descriptions and format types
- Source preferences per section
- Verification tier (Standard / Verified / Deep Verified)
- Estimated cost for the discovered competitor count

**User options:**
- Edit sections
- Edit source preferences
- View full YAML (power users can inspect exact config)
- Confirm and create workspace
- Cancel

**On confirm, the system generates:**
- `recon.yaml` — project config
- `schema.md` — competitor profile schema
- `template.md` — blank competitor template
- Directory structure (competitors/, own-products/, themes/, .recon/)
- `.gitignore` — excludes .recon/, .vectordb/, .retrieved/, .env
- Worker prompt templates (auto-generated from schema)

Nothing runs. Nothing costs money. User inspects, tweaks files if desired, then kicks off research.

### 1d. Worker Prompt Generation (automatic)

Each section in the schema carries enough metadata to auto-generate effective worker prompts:

```yaml
sections:
  regulatory_compliance:
    title: "Regulatory Compliance"
    description: "Certifications, data residency, audit capabilities"
    evidence_types:
      - certification_claims
      - public_audit_reports
      - compliance_page_urls
    search_guidance: "Look for trust/security pages, compliance documentation, press releases about certifications"
    rating_scale: "status"
    preferred_sources:
      primary: ["official trust/security pages", "compliance documentation"]
      secondary: ["analyst reports", "G2 reviews"]
      avoid: ["vendor press releases without verification"]
    source_recency: "12 months"
```

The research agent for this section receives: section definition, evidence types to look for, search guidance, rating scale reference, source preferences, and a concrete example of correctly-formatted output.

When the user modifies the schema (adds/removes/changes sections), worker prompts automatically adapt. No hand-authored prompt maintenance.

## Phase 2: Research

### Section-by-Section Research

Research is batched by section across all competitors, not by competitor across all sections.

**Why section-by-section:**
1. **Consistency** — the agent develops calibration across the cohort. Ratings are relative to the full competitive landscape, not drifting as the agent sees more data.
2. **Format enforcement** — producing 50 of the same table format consecutively is more consistent than switching between formats.
3. **Parallelism** — 10 workers all doing the same section simultaneously, same prompt, no context switching.
4. **Resume** — "Pricing done for 48/50, 2 failed" is cleaner state than scattered partial dossiers.

**How it works:**
1. For each section defined in the schema:
   a. Compose the worker prompt from schema metadata (section definition + evidence types + search guidance + source preferences + rating scale + example)
   b. Dispatch workers (semaphore-controlled concurrency) across all competitors
   c. Each worker: searches for information using preferred sources, fills the section, lists sources at the bottom of the section with URLs and dates
   d. Post-write validation (deterministic, not LLM) checks format compliance
   e. If validation fails: re-prompt with specific failure, retry (max 3 attempts)
2. Move to next section
3. After all sections complete: profile has `research_status: researched`

**LLM interaction model:**
- Data-heavy sections (capabilities tables, ratings, key-value fields): structured output via tool use, engine renders to markdown
- Prose-heavy sections (overview, strategic analysis): markdown output with validation
- Schema defines which mode each section uses
- Composable prompts: base system prompt (global rules, rating scales, no-emoji) + per-section fragment (format spec, examples, search guidance)

**Per-section source attribution:**
Each section ends with its own sources list:
```markdown
### Sources — Capabilities
- [Cursor Features Page](https://cursor.com/features) — Official documentation
- [Cursor vs Copilot comparison](https://blog.example.com/...) — Third-party review, 2026-03
```

## Phase 3: Verify

Verification runs after every information-gathering step (Phase 2 research, Phase 4 enrichment). See [Research and Verification](research-and-verification.md) for full protocol.

**Summary:** Agent B receives Agent A's claims and sources. Two-step: first checks existing sources (does URL exist, does it support the claim), then independently searches for corroboration. Each source gets a verification status.

## Phase 4: Enrich

Enrichment passes add layers of data to existing profiles. Each pass introduces new factual claims, which trigger verification.

### 4a. Cleanup
- Format alignment across all profiles
- Schema compliance check
- Quality scoring against rubric
- Unified async orchestrator (not 3 copy-pasted scripts like the legacy system)

### 4b. Sentiment Enrichment
- Developer quotes from community sources (HN, Reddit, G2, Stack Overflow)
- Traction signals (GitHub stars, funding, growth metrics)
- Talking points section
- **Followed by verification of new claims**

### 4c. Strategic Enrichment
- Deep metadata fields: platform/ecosystem, trust/governance, workflow embedding, time-to-value
- Fields defined in schema, not hardcoded
- **Followed by verification of new claims**

## Phase 5: Synthesize

### 5a. Index (`recon index`)
- Read all markdown profiles with frontmatter
- Skip profiles with `research_status: scaffold` or `skipped`
- Chunk by markdown section (~500 tokens, 50 token overlap)
- Embed with local model (fastembed, all-MiniLM-L6-v2, ONNX runtime)
- Store in ChromaDB (local, persistent, no server)
- Preserve full metadata: filepath, section, sources, competitor name, chunk index
- Incremental by default: track file hashes in state DB, only re-embed changed/new files

### 5b. Theme Discovery
- Run clustering (k-means or similar) on all embeddings
- Surface emergent themes with evidence strength indicators
- Present to user for curation (pipeline pauses here — this is a gate)

**Theme curation screen shows:**
- Discovered themes ranked by evidence strength (strong/moderate/weak)
- Competitor count per theme
- User toggles themes on/off, edits names
- **"Investigate a topic"** — user suggests a pattern, system runs directed retrieval against the index, confirms or denies signal strength. If confirmed, joins the list. If weak signal, reports back and user decides.
- User confirms final theme set before synthesis proceeds

### 5c. Retrieve (`recon retrieve`)
- Multi-query retrieval per theme (queries auto-generated from theme descriptions)
- Embed each query, search ChromaDB (top-50 per query)
- Aggregate results by competitor, rank by aggregate relevance score
- **Preserve filepath in output** (fix from legacy which dropped it)
- **Preserve query-to-chunk linkage** (fix from legacy which lost it after aggregation)
- Output `.retrieved/{theme}.json` with ranked competitors, top chunks, source metadata

### 5d. Synthesize (`recon synthesize`)

**Single pass:** Pattern synthesis from top-30 competitors (3 chunks each) into theme document.

**Deep mode (4 passes with extended thinking):**

| Pass | Role | Temperature | Purpose |
|---|---|---|---|
| 1 | Strategist | 0.3 | Pattern synthesis from evidence — 50 competitors, 4 chunks each |
| 2 | Devil's advocate | 0.4 | Challenge assumptions, find counterexamples, identify contradictions |
| 3 | Gap analyst | 0.2 | Compare against own-product profiles (if enabled), identify capability gaps |
| 4 | Executive integrator | 0.2 | Reconcile all passes into actionable brief with kill criteria |

**Provenance in synthesis:**
- Synthesis context includes source URLs from profiles (carried through from retrieval chunks)
- Theme documents cite back to competitor profiles: `[CompetitorName](competitors/CompetitorName.md)`
- Evidence tables include competitor name + signal + source reference
- Deep synthesis passes carry forward the evidence table, not just prose

### 5e. Tag (`recon tag`)
- Write theme tags to competitor profile frontmatter based on retrieval relevance
- Threshold-based assignment (min score, top-N per theme)
- Configurable parameters

## Phase 6: Deliver

### 6a. Distill (`recon distill`)
- Compress deep synthesis documents into tight executive 1-pagers
- Structured extraction: threat landscape table, competitive positioning, key questions, demo links
- **Required before meta-synthesis** — distilled docs are what fit into context for the cross-theme summary

### 6b. Meta-Synthesis (`recon summarize`)
- Read all distilled theme documents
- Identify cross-cutting patterns, compounding threats, strategic opportunities
- Produce unified executive summary
- Single-pass or deep mode available

## Pipeline State Machine

### Run-level states

```
idle --> planning --> running --> paused --> running --> completed
                       |                      |
                       v                      v
                     failed              stopping --> stopped
```

- **idle** — no active run
- **planning** — computing what needs to run (diff analysis, cost estimate)
- **running** — workers active, processing
- **paused** — no new work dispatched, in-flight workers finish
- **stopping** — cancel signal sent, waiting for in-flight to complete
- **stopped** — all work halted, state saved
- **failed** — unrecoverable error
- **completed** — all planned work finished

### Per-competitor states

```
pending --> researching --> verifying --> enriching --> verified --> indexed
                |               |             |
                v               v             v
             failed          disputed       failed
```

### Operations

| Operation | What it does |
|---|---|
| **Pause** | Stop dispatching new work, let in-flight workers finish |
| **Stop** | Cancel in-flight work, save full state |
| **Restart** | Resume from saved state, pick up where stopped |
| **Repair** | Re-run only failed and disputed items |
| **Redo** | Re-run a specific competitor or section from scratch |
| **Restore** | Roll back to a previous run's state (requires snapshots) |

## Phase Dependencies

```
Phase 1 (Setup)
  |
  v
Phase 2 (Research) <--> Phase 3 (Verify)    [verify after each section batch]
  |
  v
Phase 4 (Enrich) <--> Phase 3 (Verify)      [verify after each enrichment pass]
  |
  v
Phase 5a (Index)
  |
  v
Phase 5b (Theme Discovery)  <-- USER GATE (curation required)
  |
  v
Phase 5c (Retrieve)
  |
  v
Phase 5d (Synthesize)
  |
  v
Phase 5e (Tag)
  |
  v
Phase 6a (Distill)
  |
  v
Phase 6b (Meta-Synthesis)
```
