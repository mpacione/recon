# Operations

> Run planner, incremental runs, diff updates, cost estimation, install and dependencies.

## Run Planner

The run planner is the central interface for executing pipeline operations. It presents the user with clear options based on workspace state, computes what needs to happen, shows cost estimates, and waits for confirmation before spending money.

### Run Planner Screen (TUI)

```
+-- Run Planner -------------------------------------------+
|                                                           |
|  Workspace: 50 competitors, 8 sections, 5 themes         |
|                                                           |
|  What do you want to do?                                  |
|                                                           |
|  [1] Add new competitors                                  |
|      Add to the workspace and research from scratch       |
|                                                           |
|  [2] Update specific competitors                          |
|      Re-research selected profiles in full                |
|                                                           |
|  [3] Update all competitors                               |
|      Re-research every profile in full                    |
|                                                           |
|  [4] Diff update -- specific competitors                  |
|      Check what changed externally, update stale          |
|      sections for selected profiles                       |
|                                                           |
|  [5] Diff update -- all competitors                       |
|      Check what changed externally, update stale          |
|      sections across the full workspace                   |
|                                                           |
|  [6] Re-run failed / disputed                             |
|      Retry anything that errored or failed verification   |
|                                                           |
|  [7] Full pipeline                                        |
|      End-to-end: research -> verify -> enrich ->          |
|      synthesize                                           |
|                                                           |
+-----------------------------------------------------------+
|  [1-7] Select  [S] View status first  [Q] Back           |
+-----------------------------------------------------------+
```

### Headless Equivalents

```bash
# Add new competitors
recon add --from-list new_competitors.txt --research --headless

# Update specific
recon research "Cursor" "Linear" --force --headless

# Update all
recon research --all --force --headless

# Diff update specific
recon research "Cursor" "Linear" --diff --headless

# Diff update all
recon research --all --diff --headless

# Re-run failed
recon repair --headless

# Full pipeline
recon run --headless
```

### Operation Details

#### 1. Add New Competitors

Flow:
1. User provides names (manually, from file, or triggers another discovery round)
2. New profiles scaffolded from template
3. Research runs for new profiles only (all sections)
4. Verification runs for new profiles
5. Enrichment runs for new profiles
6. Re-index (incremental — only new files added to ChromaDB)
7. Prompt: "New competitors added. Themes may need re-synthesis. Re-synthesize? [Y/n]"

#### 2. Update Specific Competitors

Flow:
1. User selects competitors (searchable/filterable list in TUI, names as args in CLI)
2. All sections re-researched from scratch for selected competitors
3. Full verification pass on new research
4. Enrichment re-run
5. Re-index (incremental — updated files re-embedded)
6. Flag if themes may be affected

#### 3. Update All Competitors

Flow:
1. All profiles re-researched from scratch (all sections)
2. Full verification pass
3. Full enrichment
4. Full re-index
5. Theme re-synthesis recommended

Cost warning: "This will re-research all 50 competitors across 8 sections. Estimated cost: $X. Proceed?"

#### 4. Diff Update -- Specific Competitors

Flow:
1. User selects competitors
2. For each selected competitor, the diff agent checks each section:
   - Has the company's website/pricing page changed?
   - New funding round, acquisition, or major announcement?
   - New product launches or feature announcements?
   - Community sentiment shift?
3. Agent compares against current profile content
4. Flags sections that are likely outdated
5. Presents diff report: "Cursor: Pricing changed (new enterprise tier), Developer Love stale (3 months). 2/8 sections need update."
6. User confirms which sections to re-research
7. Only flagged sections are re-researched and re-verified

#### 5. Diff Update -- All Competitors

Same as #4 but across all competitors. The diff agent batches the staleness check efficiently — checks source recency thresholds from schema, compares `last_researched` timestamps in state DB, runs targeted searches for recent changes.

Presents a summary: "12 competitors have stale sections. 38 are up to date. Details: [expand]"

#### 6. Re-run Failed / Disputed

Flow:
1. Query state DB for tasks with status `failed` or `disputed`
2. Present list: "3 failed tasks, 2 disputed claims"
3. For failed: retry the exact operation (research/verification/enrichment)
4. For disputed: re-research the section from scratch with a fresh agent, then re-verify
5. Option to skip specific items: "Skip Earthly's Enterprise section? [Y/n]"

#### 7. Full Pipeline

Runs the complete pipeline end-to-end:
1. Research all sections for all pending/scaffold competitors
2. Verify all researched sections
3. Enrich (cleanup, sentiment, strategic) with verification after each
4. Index
5. Discover themes (pipeline gate — wait for user curation)
6. Retrieve per theme
7. Synthesize per theme (single or deep)
8. Tag competitors with themes
9. Distill theme documents
10. Meta-synthesis

Offers `--from` flag to start from a specific phase: `recon run --from index` skips research/enrichment and starts from indexing. Useful when profiles are already complete and you want to re-synthesize.

## Incremental Runs

### Principle

Every operation is incremental by default. The system checks what's already done and skips it. `--force` overrides to redo everything.

### How Incrementality Works Per Phase

**Research:** State DB tracks which sections are complete per competitor. `recon research --all` only researches sections that aren't already done. A section is "done" when it has `status: completed` in the tasks table.

**Verification:** Only runs for sections that have been researched but not yet verified. Re-verification only happens when the underlying section is re-researched.

**Enrichment:** Tracks which enrichment passes have run per competitor. `recon enrich --all --pass sentiment` only enriches competitors that haven't had the sentiment pass.

**Index:** Tracks file hashes in the state DB (`file_hashes` table). On `recon index`:
- Compare current file hash to stored hash
- New files: embed and add to ChromaDB
- Changed files: re-embed and update in ChromaDB
- Deleted files: remove from ChromaDB
- Unchanged files: skip

No full rebuild unless `--force`.

**Retrieve:** Re-runs if the index has changed since last retrieval (tracked via index timestamp). Otherwise serves cached results from `.retrieved/`.

**Synthesize:** Re-runs if retrieval results have changed. Otherwise serves existing theme documents. `--force` to re-synthesize even with unchanged input.

### Diff Updates

Diff updates are smarter than simple "has this been done" checks. They detect whether external reality has changed since the last research.

**Per-section staleness detection:**
- Each section has a `source_recency` threshold in the schema (e.g., "6 months" for pricing)
- State DB tracks `last_researched` timestamp per section per competitor
- If `now - last_researched > source_recency`, the section is flagged as stale
- The diff agent can also actively check for changes: new pricing pages, funding announcements, product launches

**Diff report structure:**
```json
{
  "competitor": "Cursor",
  "stale_sections": [
    {
      "section": "Pricing",
      "last_researched": "2026-01-15",
      "recency_threshold": "6 months",
      "reason": "Exceeds recency threshold",
      "signals": ["New enterprise tier announced 2026-03-20"]
    }
  ],
  "current_sections": ["Overview", "Capabilities", "..."]
}
```

## Cost Estimation

### Estimation Method

Schema-derived calculation with model-specific multipliers. No historical data needed for first run — refines with actuals over time.

### Calculation

```
base_cost_per_section = estimated_tokens(section_type) * model_price_per_token

research_cost = num_competitors * num_sections * base_cost_per_section
verification_cost = research_cost * verification_multiplier
enrichment_cost = num_competitors * num_enrichment_passes * base_cost_per_section
synthesis_cost = num_themes * synthesis_cost_per_theme * depth_multiplier

total_estimate = research_cost + verification_cost + enrichment_cost + synthesis_cost
```

**Verification multipliers:**

| Tier | Multiplier |
|---|---|
| Standard (no verification) | 1.0x |
| Verified (A + B) | ~2.0x |
| Deep Verified (A + B + C) | ~3.0x |

**Token estimates per section type:**

| Format | Estimated Input Tokens | Estimated Output Tokens |
|---|---|---|
| `rated_table` | 2000-3000 | 500-1000 |
| `status_table` | 1500-2500 | 400-800 |
| `prose` (150+ words) | 2000-3000 | 300-600 |
| `key_value` | 1000-2000 | 200-400 |
| `bullet_list` | 1500-2500 | 300-500 |

These are initial estimates. After the first run, the system uses actual token counts from the `cost_history` table to refine future estimates.

### Presentation

Costs are always shown as ranges, honest about uncertainty:

```
Estimated cost:
  Research:     $60 - $90   (50 competitors x 8 sections x Sonnet)
  Verification: $60 - $90   (verified tier, ~2x research)
  Enrichment:   $30 - $50   (sentiment + strategic passes)
  Synthesis:    $25 - $40   (5 themes, single pass, Opus)
  ---
  Total:        $175 - $270

  Deep synthesis adds: $45 - $72 (4-pass Opus per theme)
```

After runs complete, the state DB stores actual costs. Future estimates blend schema-derived estimates with historical actuals, weighting toward actuals as more data accumulates.

### Cost Display During Execution

The run monitor shows a live cost accumulator:

```
Cost: $48.20 / ~$175-270 estimated  |  This section: $0.12
```

Updated after every API call completes.

### Dry Run

Every command supports `--dry-run` which shows the plan and cost estimate without executing:

```bash
recon research --all --dry-run
# Output:
# Plan: Research 50 competitors across 8 sections
# Verification: Verified tier (2-agent consensus)
# Model: claude-sonnet-4-20250514
# Workers: 10
# Estimated cost: $120-180
# Estimated time: ~45 minutes
# Would you like to proceed? This is a dry run, no changes will be made.
```

## Install and Dependencies

### Single Command Install

```bash
pip install recon-cli
```

This pulls all dependencies. The user provides their Anthropic API key during `recon init`.

### Dependencies

**Core (always installed):**
- Python 3.11+
- click (CLI framework)
- textual (TUI framework, includes Rich)
- pyyaml (config parsing)
- python-frontmatter (markdown with YAML frontmatter)
- anthropic (Claude API client)
- fastembed (ONNX-based embeddings, ~200MB — replaces sentence-transformers/PyTorch at ~2GB)
- chromadb (local vector database)
- aiosqlite (async SQLite)

**No heavy ML dependencies.** fastembed uses ONNX runtime which is much lighter than PyTorch. The all-MiniLM-L6-v2 model downloads on first `recon index` (~90MB).

**Dev dependencies (not installed by users):**
- pytest + pytest-asyncio
- ruff (linter)
- hatchling (build)

### First Run Experience

```bash
pip install recon-cli     # Install
cd my-project
recon init                # Wizard starts, asks for API key, guides setup
```

The API key is stored in `.env` in the workspace (gitignored) or in an environment variable `ANTHROPIC_API_KEY`.

On first `recon index`, the embedding model downloads automatically (~90MB). Progress shown: "Downloading embedding model (90MB)... [========>  ] 80%"

### Version Management

The package follows semver. The CLI shows version on `recon --version`. The state DB schema is versioned — migrations run automatically when upgrading.
