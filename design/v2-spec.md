# recon v2 — Design Specification

## Overview

recon is a competitive intelligence research tool. It discovers competitors in a given space, researches each one across multiple dimensions, identifies strategic themes, and produces executive summaries — all powered by AI with web search.

v2 is a UX redesign. The engine (pipeline, LLM client, workers, state store) is largely unchanged. The TUI flow is rebuilt around **progressive disclosure** — each step feeds the next, and the user never makes decisions about things they haven't seen yet.

### Design principles

1. **No upfront configuration.** The user describes their space, the system does the rest.
2. **Show your work.** Every AI action surfaces what it's doing — search terms, sources found, sections being written.
3. **Progressive disclosure.** Each screen reveals the next step based on what was just accomplished.
4. **The user steers, not configures.** Toggle, remove, add via prompt — not forms and checkboxes.
5. **Real-time feedback.** Cost, progress, and activity stream as they happen, not in batches.

---

## Flow

```
[1] Welcome  →  [2] Describe  →  [3] Discover  →  [4] (search rounds)
                                                          ↓
[9] Results  ←  [8] Themes  ←  [7] Run  ←  [6] Confirm  ←  [5] Template
```

The user moves left-to-right. Each screen produces output the next screen consumes.

---

## Screen 1: Welcome

**Purpose:** Explain what recon does. Start new or resume existing.

```
recon

Competitive intelligence research, automated.

recon discovers your competitors, researches them across multiple
dimensions, identifies strategic themes, and produces executive
summaries — all powered by AI with web search.

How it works:
  1. You describe your company or space
  2. recon finds competitors via web search
  3. You review and refine the competitor list
  4. recon researches each one in depth
  5. You get themed analysis + executive summary

── RECENT PROJECTS ──
  1  Bambu Lab · additive manufacturing    ~/recon/bambu
  2  Acme Corp · CI/CD tools               ~/recon/acme

n new project · 1-9 resume project · q quit
```

**Inputs:** None (selection only)
**Outputs:** Path to workspace (new or existing)
**Keybinds:** `n` new, `1-9` recent, `q` quit

**Resume behavior:** When picking a recent project, the system opens the dashboard which shows where the user left off and what actions are available.

---

## Screen 2: Describe Your Space

**Purpose:** Single freeform input to describe the company/space. Persistent API keys.

```
recon │ new project

── DESCRIBE YOUR SPACE ──

Describe your company, product, or the competitive space you want
to research. A sentence or two is enough — we'll figure out the rest.

┌──────────────────────────────────────────────────────────────┐
│ Bambu Lab makes consumer and prosumer 3D printers (FDM and   │
│ resin) competing in desktop additive manufacturing           │
└──────────────────────────────────────────────────────────────┘

── API KEYS ── stored in .env (persists across sessions)

  Anthropic   sk-ant-···················341f  ✓  saved
  Google AI   ·······························     not set

enter continue · a edit API keys · esc back
```

**Inputs:** Freeform text description, API keys (optional edit)
**Outputs:** Parsed company_name, domain, products (via LLM or heuristics), workspace created on disk
**Keybinds:** `enter` continue, `a` edit API keys, `esc` back

**API key storage:** Keys are written to `.env` in the workspace root and `~/.recon/.env` as global fallback. The screen reads from both on load. Once saved, they persist — the user never re-enters them.

**Parsing:** The freeform description is parsed to extract:
- `company_name` — the primary entity
- `products` — specific products mentioned
- `domain` — the competitive space label

This can be done via a small LLM call or keyword extraction. The parsed values populate the schema YAML but are not shown to the user (they see their raw description, the system uses the structured fields internally).

---

## Screen 3 + 4: Competitor Discovery

**Purpose:** Find competitors via web search. Full screen (not a modal). The user watches candidates stream in, toggles acceptance, refines search terms, adds manually.

```
recon │ Bambu Lab · additive manufacturing │ discovering...

── COMPETITOR DISCOVERY ──

── SEARCH ── round 2 of 3
████████████████████████████░░░░░░░░░░░░  searching...
"consumer resin 3D printer companies 2026"

── CANDIDATES ── 14 found · 12 accepted
┌────────────────────────────────────────────────────────────┐
│  ✓  Prusa Research        prusa3d.com       FDM printers   │
│  ✓  Creality              creality.com      Budget FDM     │
│  ✓  Formlabs              formlabs.com      Resin / SLA    │
│  ✓  AnkerMake             ankermake.com     Consumer FDM   │
│  ·  Stratasys             stratasys.com     Industrial     │
│  ✓  Elegoo                elegoo.com        Resin + FDM    │
│  ✓  Artillery             artillery3d.com   Budget FDM     │
│  ✓  Phrozen               phrozen3d.com     Resin          │
│  ✓  Anycubic              anycubic.com      FDM + resin    │
│  ✓  Raise3D               raise3d.com       Prosumer FDM   │
│  ✓  QIDI Technology       qidi3d.com        Enclosed FDM   │
│  ✓  Snapmaker             snapmaker.com     Multi-tool     │
│  ·  3D Systems            3dsystems.com     Industrial     │
│  ✓  FlashForge            flashforge.com    Desktop FDM    │
└────────────────────────────────────────────────────────────┘

── SEARCH ACTIVITY ──
14:31:22  Searching "desktop 3D printer manufacturers 2026"
14:31:28  Found: Prusa Research — Czech FDM pioneer, open-source
14:31:28  Found: Creality — Shenzhen, high-volume budget FDM
14:31:35  Searching "consumer resin 3D printer companies"
14:31:40  Found: Formlabs — Boston, SLA/resin specialist

↑↓ navigate · space toggle · del remove · s search more ·
t edit search terms · n add manually · enter done
```

**Inputs:** Candidate toggles, search term edits, manual additions
**Outputs:** List of accepted competitors (profiles created on disk)
**Keybinds:** `space` toggle, `del` remove, `s` search more, `t` edit terms, `n` add manually, `enter` done, `esc` back

**Search progress** is separated above the candidates table: progress bar, current search term, round counter.

**Search terms** are visible and editable (`t`). The user can see what queries the system is using and refine them ("also search for industrial SLS printers"). Next `s` round uses updated terms.

**Candidates stream in** as they're found. Each shows: name, URL (truncated), and a short descriptor explaining why it was suggested.

**`del` removes** entirely (not just rejects). For "I don't want to see Stratasys at all" vs `space` which keeps it in the list but deselected.

---

## Screen 5: Research Template

**Purpose:** The system proposes research sections based on the space. The user toggles and optionally adds custom sections via prompt.

```
recon │ Bambu Lab · 12 competitors │ research template

── RESEARCH TEMPLATE ──

We designed these sections based on your space. Each competitor
will be researched across the sections you select.

 [x] Overview              Company background, positioning, key facts
 [x] Product Lineup        Models, specs, price points, target segments
 [x] Technology & IP       Core tech, patents, print quality metrics
 [x] Pricing & Business    Revenue model, pricing tiers, market position
 [x] Distribution          Sales channels, availability, partnerships
 [ ] Software Ecosystem    Slicer software, firmware, cloud features
 [ ] Community & Reviews   User community, sentiment, review scores

── ADD YOUR OWN ──
Describe a section you'd like added and we'll create it.
e.g. "Compare open-source vs proprietary firmware approaches"
e.g. "Materials compatibility — which filaments each printer supports"

┌──────────────────────────────────────────────────────────────┐
│                                                              │
└──────────────────────────────────────────────────────────────┘

space toggle · enter proceed · type below to add a section
```

**Inputs:** Section toggles, optional custom section prompt
**Outputs:** Final schema (section list) written to recon.yaml
**Keybinds:** `space` toggle, `enter` proceed, type in prompt field to add

### Section generation approach

**Phase (a): Predefined superset with intelligent selection.**

The system selects from ~15 predefined sections. Each has a prompt template, format spec, and verification tier already defined. The LLM's job is to pick which subset is relevant for this industry and propose an ordering.

Available section pool:

| Section Key | Title | When Relevant |
|-------------|-------|---------------|
| `overview` | Overview | Always |
| `product_lineup` | Product Lineup | Product companies |
| `technology_ip` | Technology & IP | Tech / hardware |
| `pricing_business` | Pricing & Business Model | Always |
| `distribution_gtm` | Distribution & GTM | Physical products, SaaS |
| `developer_experience` | Developer Experience | Dev tools, APIs |
| `enterprise_features` | Enterprise Features | B2B |
| `community_ecosystem` | Community & Ecosystem | Open-source, platforms |
| `customer_segments` | Customer Segments | B2B and B2C |
| `regulatory_compliance` | Regulatory & Compliance | Healthcare, fintech |
| `partnerships` | Partnerships & Integrations | Platform/API businesses |
| `team_leadership` | Team & Leadership | Startups, VC-backed |
| `funding_financials` | Funding & Financials | Public cos, startups |
| `head_to_head` | Head-to-Head Comparison | Always (references own company) |
| `market_position` | Market Position & Trends | Always |

The LLM receives: the user's description, the list of discovered competitors, and the full section pool. It returns which sections to select and why.

**Phase (c): Custom sections via prompt.**

When the user types a custom section description (e.g., "Compare open-source vs proprietary firmware approaches"), the system makes one LLM call to generate:
1. A section key (e.g., `firmware_strategy`)
2. A section title (e.g., "Open Source vs Proprietary Firmware")
3. A section description (e.g., "Analysis of firmware openness strategy...")
4. A structured research prompt with:
   - What to look for (specific angles)
   - Output format (prose, table, comparison)
   - Sourcing guidance (where to find this info)
   - Word count range

The generated prompt is stored in the schema alongside the predefined ones.

**Phase (b): Fully dynamic generation (future).**

Replace the predefined pool entirely. The LLM generates ALL sections from scratch based on the user's description and competitor list. Every prompt template is custom-generated. This gives maximum flexibility but requires strong prompt engineering for the meta-prompt (the prompt that generates prompts).

---

## Screen 6: Cost Confirmation

**Purpose:** Show estimated cost breakdown. Let user choose model and worker count. Explicit "are you sure" gate before spending money.

```
recon │ Bambu Lab · 12 competitors · 5 sections

── READY TO RESEARCH ──

This will research 12 competitors across 5 sections each.

  Research:     60 section calls          ~$18.00
  Enrichment:   12 profiles × 3 passes    ~$3.60
  Themes:        5 themes                  ~$1.50
  Summaries:     5 themes + 1 executive    ~$1.80
                                    ──────────────
  Estimated total:                    ~$24.90

── MODEL ──

 ● Sonnet 4   $3 / $15 per M tokens    ~$24.90    recommended
 ○ Opus 4     $15 / $75 per M tokens   ~$124.50   deeper analysis
 ○ Haiku 4    $0.80 / $4 per M tokens   ~$6.50   faster, less depth

Workers: [5]  ← → to adjust

enter start research · esc go back
```

**Inputs:** Model selection (radio), worker count (arrows)
**Outputs:** PipelineConfig with model, workers, sections, targets
**Keybinds:** `↑↓` select model, `←→` adjust workers, `enter` start, `esc` back

**Cost estimates** recalculate live when model changes. The math is transparent: section count × competitor count × per-call estimate.

---

## Screen 7: Research Run

**Purpose:** Live execution monitor. Side column for competitor progress, worker cards for detailed per-worker activity. Streaming cost.

### Layout

```
recon │ Bambu Lab │ $4.82 │ researching 22/350 sections  6%

── RESEARCH ── 3:42  $4.82  Workers: 5
██████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  22/350  6%

COMPETITORS         PROGRESS      WORKERS
┌──────────────────────────────┐  ┌─ W1 ── Creality · pricing ── $0.38 ─────────┐
│ ✓ Prusa Research    5/5 100% │  │ Searching "Creality pricing tiers 2026"     │
│ >> Creality          3/5  60% │  │ Found 3 sources: creality.com, reddit       │
│ >> Formlabs          3/5  60% │  │ Composing section from 3 sources...         │
│ >> AnkerMake         2/5  40% │  └─────────────────────────────────────────────┘
│ >> Elegoo            2/5  40% │  ┌─ W2 ── Formlabs · pricing ── $0.41 ────────┐
│ ·  Artillery         0/5   0% │  │ Searching "Formlabs dental pricing plans"  │
│ ·  Phrozen           0/5   0% │  │ Found 4 sources: formlabs.com, all3dp      │
│ ·  Anycubic          0/5   0% │  │ Writing pricing breakdown...                │
│ ·  Raise3D           0/5   0% │  └─────────────────────────────────────────────┘
│ ·  QIDI              0/5   0% │  ┌─ W3 ── AnkerMake · tech ── $0.32 ──────────┐
│ ·  Snapmaker         0/5   0% │  │ Analyzing patent filings and docs           │
│ ·  FlashForge        0/5   0% │  └─────────────────────────────────────────────┘
│ ·  Sindoh            0/5   0% │  ┌─ W4 ── Elegoo · overview ── $0.29 ─────────┐
│ ·  Tiertime          0/5   0% │  │ Searching "Elegoo company background"       │
│    ...+86 more       ↓       │  └─────────────────────────────────────────────┘
└──────────────────────────────┘  ┌─ W5 ── idle ────────────────────────────────┐
                                  │ waiting for next task...                     │
                                  └─────────────────────────────────────────────┘

p pause · s stop · w ±workers · ↑↓ scroll · q quit
```

### Left column: Competitor progress (30% width)

Scrollable list. One line per competitor: status icon + name + section fraction + percentage.

Status icons:
- `✓` — all sections complete
- `>>` — has at least one section in progress
- `·` — queued (no work started)
- `!!` — has failed sections
- `~>` — retrying

The list auto-scrolls to keep active items visible. `↑↓` scrolls manually. Completed items rise to the top.

### Right column: Worker cards (70% width)

One card per worker (up to worker count). Each card header shows: worker number, current competitor + section, model, cost accrued by this worker.

Card body shows 2-3 lines of recent activity for that worker:
- Search queries being executed
- Sources found
- Current writing state

**Activity source:** Route log lines to the correct worker card by competitor+section key. The engine already logs per-task activity — we filter and display per-worker.

Idle workers show "waiting for next task..." and collapse to a single line.

### Stage transitions

When research completes and enrichment starts, the layout adapts:

```
── ENRICHING ── 18:42  $20.14  cleanup pass  4/12 profiles

COMPETITORS          PROGRESS      WORKERS
┌──────────────────────────────┐  ┌─ W1 ── Creality · cleanup ── $0.08 ────────┐
│ ✓ Prusa Research    3/3 100% │  │ Normalizing formatting, cleaning markup     │
│ >> Creality          1/3  33% │  └─────────────────────────────────────────────┘
│ >> Formlabs          1/3  33% │  ┌─ W2 ── Formlabs · cleanup ── $0.08 ───────┐
│ ·  AnkerMake         0/3   0% │  │ Fixing citation links, normalizing refs     │
│ ·  Elegoo            0/3   0% │  └─────────────────────────────────────────────┘
│    ...                       │
└──────────────────────────────┘
```

The left column switches from "N/5 sections" to "N/3 enrichment passes". Same visual pattern, different denominator. The worker cards adapt to show enrichment-specific activity.

For synthesis/deliver:

```
── SYNTHESIZING ── 30:32  $23.37  3/5 themes

THEMES               PROGRESS      WORKERS
┌──────────────────────────────┐  ┌─ W1 ── Closed Workflow Eco... ── $0.42 ────┐
│ ✓ Closed Workflows   done    │  │ Writing cross-competitor analysis...        │
│ >> Proprietary Lock   writing │  └─────────────────────────────────────────────┘
│ >> Regulatory Comp    writing │  ┌─ W2 ── Proprietary Lock-in ── $0.38 ──────┐
│ ·  Price Compression  queued  │  │ Retrieving chunks from 4 competitors       │
│ ·  DTC Distribution   queued  │  └─────────────────────────────────────────────┘
└──────────────────────────────┘
```

The left column becomes a theme list. The worker cards show synthesis activity.

### Streaming cost

Cost is recorded per-task (per-section during research, per-profile during enrichment, per-theme during synthesis). The `CostRecorded` event fires after each task, not after each stage. This means:
- Cost in the header, global progress bar, and worker cards ticks up in real time
- No more "$0.00 for 17 minutes then $19.82 all at once"

### Worker count adjustment

`w` opens a small inline control:

```
Workers: [5]  ← 3  4  [5]  6  7  8 →
```

Arrow keys adjust. Takes effect for the next task dispatch (doesn't kill running workers).

---

## Screen 8: Theme Review

**Purpose:** Present discovered themes with descriptions. User toggles which to synthesize. Can request more themes via prompt.

```
recon │ Bambu Lab │ $21.40 │ themes

── THEMES DISCOVERED ── 5 themes from 12 competitors

 [x] 1. Closed Workflow Ecosystems                    8 sources  strong
        Proprietary slicer + firmware lock-in vs open-source stacks

 [x] 2. Prosumer Price Compression                    6 sources  strong
        Sub-$300 FDM collapsing margins across the segment

 [x] 3. Resin vs FDM Convergence                     5 sources  moderate
        Multi-technology platforms emerging (Elegoo, Anker)

 [ ] 4. Industrial Downmarket Push                    3 sources  weak
        Stratasys/3D Systems moving into prosumer

 [x] 5. Direct-to-Consumer Distribution               4 sources  moderate
        Bypassing resellers, DTC + Amazon strategies

── SEARCH FOR MORE ──
Ask recon to look for additional patterns or connections.
e.g. "Are there patterns around print speed claims and marketing?"
e.g. "Look for sustainability and environmental positioning"

┌──────────────────────────────────────────────────────────────┐
│                                                              │
└──────────────────────────────────────────────────────────────┘

space toggle · enter synthesize selected · type to search for more
```

**Inputs:** Theme toggles, optional prompt for more themes
**Outputs:** Selected themes → synthesis stage runs → deliver stage runs
**Keybinds:** `space` toggle, `enter` synthesize, type to search

Each theme shows a 1-line description so the user can judge relevance.

---

## Screen 9: Results

**Purpose:** Post-run summary. Preview the executive summary inline. Show output file paths with keybinds to open.

```
recon │ Bambu Lab │ $24.85 │ complete

── RESEARCH COMPLETE ── 35:12  $24.85

12 competitors researched · 5 sections each · 4 themes synthesized

── EXECUTIVE SUMMARY (preview) ──
The desktop additive manufacturing space is experiencing three
convergent pressures: prosumer price compression below $300,
proprietary ecosystem lock-in via slicer software, and the
emergence of multi-technology platforms. Bambu Lab's position...
[truncated — press v to view full]

── OUTPUT FILES ──
 1. Executive Summary        ~/recon/bambu/executive_summary.md
 2. Closed Workflow Eco...   ~/recon/bambu/themes/closed_workflow.md
 3. Price Compression        ~/recon/bambu/themes/price_compression.md
 4. Resin vs FDM             ~/recon/bambu/themes/resin_vs_fdm.md
 5. DTC Distribution         ~/recon/bambu/themes/dtc_distribution.md

v view summary · o open folder · b back to dashboard · q quit
```

**Inputs:** None (view only)
**Outputs:** None (terminal state)
**Keybinds:** `v` view full summary (opens in pager or $EDITOR), `o` open output directory (Finder/file manager), `b` back to dashboard, `q` quit

---

## Engine changes required

### Streaming cost (RC-1 fix)

Thread `run_id` + `cost_tracker` into orchestrators so cost is recorded per-task:

| Stage | Current | New |
|-------|---------|-----|
| Research | Batch after `research_all()` | Per-section in `_research_one()` |
| Enrich | Batch after `enrich_all()` | Per-profile in `_enrich_one()` |
| Synthesize | Per-theme (already correct) | No change |
| Deliver | Per-theme (already correct) | No change |

### New events for non-research stages

| Event | Published by | Fields |
|-------|-------------|--------|
| `EnrichmentStarted` | `enrichment.py` | competitor_name, pass_name |
| `EnrichmentCompleted` | `enrichment.py` | competitor_name, pass_name |
| `SynthesisStarted` | `pipeline.py` | theme_label |
| `SynthesisCompleted` | `pipeline.py` | theme_label |
| `DeliveryStarted` | `pipeline.py` | theme_label |
| `DeliveryCompleted` | `pipeline.py` | theme_label |

### Dynamic schema generation

New module: `src/recon/schema_designer.py`

```python
async def design_sections(
    description: str,
    competitors: list[str],
    section_pool: list[SectionTemplate],
    llm_client: LLMClient,
) -> list[SectionTemplate]:
    """Select relevant sections from the pool for this space."""

async def create_custom_section(
    description: str,
    llm_client: LLMClient,
) -> SectionTemplate:
    """Generate a complete section (key, title, description, prompt) from user input."""
```

### API key management

New module: `src/recon/api_keys.py`

```python
def load_api_keys(workspace_root: Path) -> dict[str, str]:
    """Load API keys from workspace .env and global ~/.recon/.env."""

def save_api_key(key_name: str, key_value: str, workspace_root: Path) -> None:
    """Write API key to workspace .env file."""

def validate_api_key(key_name: str, key_value: str) -> bool:
    """Check if an API key is valid (lightweight API ping)."""
```

### Description parsing

New module or function in `src/recon/wizard.py`:

```python
async def parse_description(
    description: str,
    llm_client: LLMClient | None = None,
) -> dict:
    """Parse freeform description into structured schema fields.
    Returns: {company_name, products, domain, decision_context}
    Falls back to keyword extraction if no LLM client available."""
```

---

## Files to create/modify

### New files
- `src/recon/schema_designer.py` — Dynamic section selection + custom section generation
- `src/recon/api_keys.py` — API key load/save/validate
- `src/recon/tui/screens/describe.py` — Screen 2 (replace wizard)
- `src/recon/tui/screens/template.py` — Screen 5 (schema design)
- `src/recon/tui/screens/confirm.py` — Screen 6 (cost confirmation)
- `src/recon/tui/screens/results.py` — Screen 9 (results preview)

### Modified files
- `src/recon/tui/screens/welcome.py` — Simplified (remove "open" path, add explanation)
- `src/recon/tui/screens/discovery.py` — Promoted from modal to full screen, search terms visible
- `src/recon/tui/screens/run.py` — Side column + worker cards layout
- `src/recon/tui/run_monitor.py` — Stage-aware rendering (research/enrich/synthesize)
- `src/recon/tui/screens/curation.py` — Becomes Screen 8 (themes review)
- `src/recon/tui/pipeline_runner.py` — Streaming cost, model selection passthrough
- `src/recon/tui/app.py` — New screen modes, revised flow
- `src/recon/research.py` — Per-section cost recording
- `src/recon/enrichment.py` — New events + per-profile cost
- `src/recon/pipeline.py` — New events in synthesize/deliver, model passthrough
- `src/recon/events.py` — 6 new event types
- `src/recon/cost.py` — Multi-model pricing support

### Archived files
- `src/recon/tui/wizard.py` — Replaced by Screen 2 (describe)
- `src/recon/tui/screens/planner.py` — Replaced by Screen 6 (confirm)
- `src/recon/tui/screens/selector.py` — Integrated into discovery + run flow

### Archived design docs (moved to `design/archive/`)
- `design/architecture.md`
- `design/operations.md`
- `design/pipeline.md`
- `design/research-and-verification.md`
- `design/setup-and-discovery.md`
- `design/system-improvement-plan-2026-04-10.md`
- `design/systemic-fixes-proposal-2026-04-11.md`
- `design/tui-audit-2026-04-10.md`
- `design/wiring-audit.md`
- `design/session-handoff-2026-04-12.md`

---

## Build sequence

### Phase 1: Engine foundations
1. Streaming cost — thread cost_tracker into research/enrichment orchestrators
2. New events — EnrichmentStarted/Completed, SynthesisStarted/Completed, DeliveryStarted/Completed
3. API key management — load/save/validate module
4. Multi-model pricing — CostTracker supports model selection

### Phase 2: New screens (left-to-right)
5. Screen 2 — Describe (single field + API keys, replaces wizard)
6. Screen 3/4 — Discovery redesign (full screen, search terms, streaming)
7. Screen 5 — Research template (section selection + custom prompts)
8. Screen 6 — Cost confirmation (model choice, worker count)

### Phase 3: Run screen redesign
9. Side column + worker cards layout
10. Stage-aware rendering (research → enrich → synthesize → deliver)
11. Remove legacy statics (Phase/Progress/Cost redundancy)

### Phase 4: Post-run
12. Screen 8 — Theme review (descriptions, prompt for more)
13. Screen 9 — Results (exec summary preview, file links, open keybinds)

### Phase 5: Dynamic schema
14. Schema designer — LLM selects from section pool
15. Custom section generation — prompt → section template
16. Wire into Screen 5
