# Interactive Competitor Presentation App

**Status:** Concept
**Owner:** Matt Pacione
**Contributors:** Caris, Harry (available next week), HD (demo accounts)
**Audience:** Emily (VP), Christian, LT stakeholders
**Format:** Web app (Confluence embed or standalone URL)
**Meeting:** 90 min total, 3 presenters (~30 min each)

---

## Emily's Actual Ask

From Emily's brief:

> "Competitor landscape by product (RovoDev, DX, Bitbucket). I plan to do a live walk-through of the competitors so will need instances set up... My plan is to share my screen and have tabs open and toggle to each competitor and facilitate the convo. Suggest creating a Connie page as that's likely easiest."

### What she needs

| Need | Implication |
|------|-------------|
| "Live walk-through of competitors" | She's driving, showing actual competitor products |
| "Instances set up" | HD setting up live demos/accounts |
| "Toggle to each competitor" | Browser tabs with real products |
| "Connie page as easiest" | Confluence as home base/reference |
| "Shared language / POV" | Alignment artifact, not analysis artifact |
| "Build muscle of talking about product" | Forcing function for LT, not a deliverable |
| "90 min total for all 3" | ~30 min per presenter, tight |

### Meeting goals

1. Walk away with shared language/POV on competitor landscape
2. Build the muscle of talking about product at LT level
3. Cover: what keeps us up at night, competitive advantages/disadvantages, features assessment
4. Surface SDLC/Agentic trends — "out of left field" competitors

---

## Core Concept

**Product-centric card explorer** with Atlassian products as the primary navigation axis.

This is NOT a graph visualization. It's a briefing companion for Emily's live demos.

### Key Interaction Model

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  COMPETITIVE LANDSCAPE                                            [Agentic ▼]  │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐                   │
│  │ Rovo    │ │ Jira    │ │Bitbucket│ │Compass  │ │Confluence                   │
│  │  Dev    │ │         │ │         │ │         │ │         │                   │
│  │  ●●●    │ │  ●●     │ │  ●●     │ │  ●      │ │  ●      │  ← threat dots    │
│  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘                   │
│       │           │           │           │           │                         │
│  ─────┴───────────┴───────────┴───────────┴───────────┴─────                   │
│                                                                                 │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐      ┌─────────────┐ │
│  │ 🔴 Cursor │ │ 🔴 Devin  │ │ 🔴 Linear │ │ 🟡 Codex  │      │             │ │
│  │           │ │           │ │           │ │           │      │  CURSOR     │ │
│  │ L3 Agent  │ │ L4 Agent  │ │ Task+Agent│ │ L4 Agent  │      │             │ │
│  │ $400M     │ │ $500M     │ │ $1.25B    │ │ OpenAI    │      │  Threatens: │ │
│  └───────────┘ └───────────┘ └───────────┘ └───────────┘      │  • Rovo Dev │ │
│                                                                │  • Jira     │ │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐      │             │ │
│  │ 🔴 GitHub │ │ 🟡 GitLab │ │ 🟡 Graphit│ │ 🟡 Notion │      │  Their edge:│ │
│  │           │ │           │ │           │ │           │      │  Codebase   │ │
│  │ Copilot++ │ │ Full SDLC │ │ Code Rev  │ │ Docs+AI   │      │  context    │ │
│  │ MSFT      │ │ $428M     │ │ $52M      │ │ $10B      │      │             │ │
│  └───────────┘ └───────────┘ └───────────┘ └───────────┘      │  [Demo ↗]   │ │
│                                                                │  [Profile ↗]│ │
│  [+12 more...]                                                 └─────────────┘ │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Interaction States

| Action | Result |
|--------|--------|
| Click Atlassian product chip | Filter competitor cards to those threatening that product |
| Click multiple products | Show union (competitors threatening ANY selected product) |
| Click competitor card | Open detail panel with talking points, demo link |
| Toggle "Agentic" filter | Show only L3+ autonomy competitors ("out of left field") |
| Hover competitor | Show which Atlassian products it threatens (visual connection) |

### The "Aha" Moment

Some competitors aren't single-product threats—they're platform threats.

- **Cursor** → Threatens: Rovo Dev (primary), Bitbucket (code review)
- **Linear** → Threatens: Jira (primary), Rovo Dev (agentic task breakdown)
- **GitHub** → Threatens: Bitbucket (primary), Rovo Dev (Copilot), Jira (Issues)

This cross-product threat visibility is the key insight the tool surfaces.

---

## Card Anatomy

### Competitor Card (collapsed)

```
┌───────────────────────────┐
│ [Logo]  Cursor       🔴   │
│ AI-native IDE with        │
│ codebase context          │
│                           │
│ L3 Agent  │  $400M raised │
│                           │
│ ○ Rovo Dev  ○ Bitbucket   │  ← which products it threatens
└───────────────────────────┘
```

### Detail Panel (expanded)

```
┌─────────────────────────────────────────┐
│ CURSOR                             🔴   │
│ AI-native IDE with codebase context     │
├─────────────────────────────────────────┤
│ Threatens: Rovo Dev, Bitbucket          │
│ Autonomy: L3 (supervised agent)         │
│ Funding: $400M Series B (2024)          │
├─────────────────────────────────────────┤
│ WHAT KEEPS US UP AT NIGHT               │
│ • "Tab completion feels psychic" - HN   │
│ • 50% adoption at [Customer] in 3mo     │
├─────────────────────────────────────────┤
│ THEIR EDGE                              │
│ • Persistent codebase understanding     │
│ • L3 autonomy with human-in-loop        │
├─────────────────────────────────────────┤
│ OUR EDGE                                │
│ • Enterprise trust and compliance       │
│ • Full Atlassian suite integration      │
├─────────────────────────────────────────┤
│ DISCUSSION PROMPT                       │
│ Should Rovo Dev aim for Cursor-level    │
│ context, or differentiate on enterprise │
│ workflow integration?                   │
├─────────────────────────────────────────┤
│ [Open Demo ↗]  [Full Profile ↗]         │
└─────────────────────────────────────────┘
```

---

## Data Model

### Frontmatter (already in `_Schema.md`)

```yaml
# Presentation fields
demo_url: "https://cursor.com"
demo_account: "See 1Password > Competitors"  # HD to populate
logo_url: ""
tagline: "AI-native IDE with codebase context"
funding_display: "$400M Series B"
autonomy_level: L3
out_of_left_field: false
presentation_priority: 1  # 1=must show, 2=if time, 3=reference only
```

### Talking Points Section (in competitor .md)

```markdown
## Talking Points

### What keeps us up at night
- [1-2 bullets, punchy, quotable]

### Their competitive advantage
- [Specific, not generic]

### Our competitive advantage
- [Why Atlassian wins here]

### Discussion prompt
- [Question Emily can pose to LT]
```

### Cross-Product Mapping

Uses existing `atlassian_overlap` field:

```yaml
atlassian_overlap: [Rovo Dev, Jira, Bitbucket]
```

---

## Filtering & Views

### Filters

| Filter | Values |
|--------|--------|
| Atlassian product | Rovo Dev, Jira, Bitbucket, Compass, Confluence |
| Strategic theme | Agentic Shift, MCP Ecosystem, Developer Love, Consolidation Patterns, Pricing Pressure |
| Threat level | 🔴 High, 🟡 Medium, 🟢 Low |
| Autonomy level | L1-L5 (or "Agentic only" = L3+) |
| Out of left field | Toggle |
| Presentation priority | 1 / 2 / 3 |

### Sort Options

- Threat level (default)
- Presentation priority
- Alphabetical
- Funding amount

### Special Views

1. **Emily's Shortlist** — `presentation_priority: 1` only (~5-10 per product)
2. **Agentic Trends** — L3+ autonomy, any threat level
3. **Platform Threats** — Competitors with 2+ `atlassian_overlap` entries
4. **By Theme** — Filter to competitors tagged with a specific strategic theme

---

## Technical Approach

### Recommended Stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Build Tool | **Replit Agent** | Fast iteration, hosted deploys, no local setup |
| Framework | React + Tailwind | Fast filtering, easy styling |
| Data | Static JSON | Parse markdown at build time |
| Hosting | Replit (built-in) | Instant deploys, shareable URL |
| Confluence | iframe embed | Native feel for Atlassian users |

### Data Pipeline

```
294 markdown files
       ↓
  Python parser (frontmatter + Talking Points extraction)
       ↓
  competitors.json (upload to Replit project)
       ↓
  React app (static import)
```

### Components

1. `ProductChips` — Atlassian product selector (top row)
2. `ThemeChips` — Strategic theme filter (second row, purple/indigo styling)
3. `CompetitorGrid` — Filterable card grid
4. `CompetitorCard` — Collapsed card view
5. `DetailPanel` — Expanded talking points + demo link
6. `FilterBar` — Threat level, autonomy, search
7. `PresentationMode` — Larger cards, hidden filters, optimized for screen share
8. `ThemesPage` — Strategic theme summaries with linked competitors (optional)

---

## Replit Agent Build Guide

### Prompting Best Practices

1. **Plan first** — Think through structure before prompting
2. **Be specific** — Detailed prompts = fewer mistakes
3. **Build incrementally** — One feature at a time, checkpoint after each
4. **Attach references** — Upload `competitors.json` and wireframe screenshots
5. **Iterate** — Reprompt if results aren't right

### Build Sequence

Use these prompts in order, checkpointing after each successful step.

#### Step 0: Upload Data First

Before prompting, upload `competitors.json` to the Replit project root. See `_Prompts/ReplitPrompts/00_DataExport.md` for the export script.

#### Step 1-5: Sequential Prompts

See `_Prompts/ReplitPrompts/` folder for the full prompt sequence:

| File | Purpose |
|------|---------|
| `00_DataExport.md` | Python script to generate competitors.json |
| `01_BaseApp.md` | Initial app scaffold with card grid |
| `02_DetailPanel.md` | Add click-to-expand detail panel |
| `03_Filtering.md` | Add product chips and threat filters |
| `04_PresentationMode.md` | Add presentation mode toggle |
| `05_Polish.md` | Visual refinements for exec presentation |

#### Rollback Strategy

If a prompt breaks something:
1. Click "Rollback" to restore previous checkpoint
2. Simplify the prompt (ask for less)
3. Try again

### Common Issues & Fixes

| Issue | Fix |
|-------|-----|
| "Can't read JSON" | Check file path, ensure valid JSON syntax |
| Styling looks off | Ask: "Make the cards look more polished with shadows and hover states" |
| Filter not working | Provide specific field names: "Filter by `atlassian_overlap` array" |
| Detail panel broken | Simplify: "Show a basic sidebar when a card is clicked" |

---

## MVP Scope

### Phase 1: Meeting-Ready (target: 1 week before meeting)

- [ ] Product chip navigation (Rovo Dev, Jira, Bitbucket, Compass, Confluence)
- [ ] Competitor card grid with threat indicators
- [ ] Detail panel with Talking Points
- [ ] Demo URL links (new tab)
- [ ] Filter by threat level
- [ ] Emily's Shortlist view (`presentation_priority: 1`)

### Phase 2: Enhanced Navigation

- [ ] Multi-product selection (show union)
- [ ] Agentic-only toggle (L3+)
- [ ] Out of left field filter
- [ ] Search (fuzzy match on name/tagline)
- [ ] Presentation mode toggle

### Phase 3: Post-Meeting

- [ ] Comparison drawer (2-3 competitors side-by-side)
- [ ] Embedded demo iframe (if useful)
- [ ] Export to Confluence table
- [ ] Annotation layer (Emily's notes)
- [ ] Themes page with strategic synthesis

---

## Themes Integration

### Theme Data Flow

```
P4 Pipeline (00_discover → 02_retrieve → 03_synthesize → 04_tag_themes)
       ↓
Competitor .md files updated with themes: [] frontmatter
       ↓
export_competitors.py extracts themes into JSON
       ↓
App filters by theme OR displays theme pages
```

### Theme Filtering (MVP)

Add `themes` array to competitor data model. Allow filtering competitors by which strategic theme they're tagged with.

Example: Selecting "Agentic Shift" shows only competitors relevant to the L1→L5 autonomy transition (Cursor, Devin, Codex, etc.)

### Themes Page (Phase 3)

Optional dedicated page showing strategic synthesis:

```
┌─────────────────────────────────────────────────────────────────────────┐
│  STRATEGIC THEMES                                                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ 🔮 AGENTIC SHIFT                                    28 competitors│  │
│  │                                                                   │  │
│  │ Key insight: Autonomous agents executing Jira issues directly    │  │
│  │ threaten Jira's UI relevance within 18 months.                  │  │
│  │                                                                   │  │
│  │ Top signals: Devin, Codex, Factory, Claude Code                  │  │
│  │                                                                   │  │
│  │ [View Competitors →]  [Full Analysis →]                          │  │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ 🔌 MCP ECOSYSTEM                                    15 competitors│  │
│  │                                                                   │  │
│  │ Key insight: Universal MCP adoption means Atlassian must provide │  │
│  │ MCP servers or become invisible to AI agents.                    │  │
│  │ ...                                                               │  │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Data Source for Themes Page

Load theme synthesis from `Themes/*.md` files (generated by P4 pipeline) OR include theme summaries in the JSON export:

```json
{
  "themes": [
    {
      "id": "agentic_shift",
      "title": "Agentic Shift",
      "key_insight": "Autonomous agents...",
      "competitor_count": 28,
      "top_competitors": ["Devin", "Codex", "Claude Code"],
      "threat_level": "High"
    }
  ],
  "competitors": [...]
}
```

---

## Open Questions

### For Emily

1. Does she want the app on screen during demos, or just Confluence as side reference?
2. Which ~5-10 competitors per product area are must-haves?
3. Is John Kinmonth's input already captured, or net-new research needed?

### For HD

1. Which competitors need demo accounts set up?
2. Where will credentials live (1Password vault)?

### For Caris/Harry

1. Available cycles next week?
2. React experience for component buildout?

### Technical

1. Hosting: Vercel (standalone URL) or Confluence-only?
2. Auth: Does it need Atlassian SSO, or is URL-sharing sufficient?
3. Update frequency: Manual JSON export, or automated pipeline?

---

## Stakeholder Map

| Person | Role | Input Needed |
|--------|------|--------------|
| Emily | VP, presenter | Validate concept, shortlist competitors |
| Christian | Co-presenter | Business rhythms context |
| Matt | Owner, design | UX, schema, prompts |
| Caris | Contributor | Build support (next week) |
| Harry | Contributor | Build support (next week) |
| HD | Demo accounts | Competitor credentials |
| John Kinmonth | SME | Competitor intelligence |

---

## Next Steps

1. ~~Validate card-based model~~ (Emily's brief confirms this fits her flow)
2. Update schema with Talking Points section template
3. Run P3 enrichment to populate presentation fields
4. Run `00_DataExport.md` script to generate `competitors.json`
5. Open Replit Agent, upload JSON, run prompts from `ReplitPrompts/` folder
6. Share deployed URL with Emily for feedback
7. Get shortlist from Emily for `presentation_priority: 1` tagging
