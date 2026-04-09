# Setup and Discovery

> Wizard flow, schema design, competitor discovery, theme discovery, and own-product research.

## Competitor Discovery

### Approach: Iterative with User Checkpoints

Discovery is an interactive loop. The agent finds candidates in batches, presents them, and the user curates. The agent refines its search based on what the user accepts and rejects.

### Discovery Flow

```
User provides domain description + optional seed competitors
  |
  v
Agent searches (market maps, analyst reports, alternatives lists, directories, funding DBs)
  |
  v
Present batch of 10-15 candidates
  |
  v
User reviews: toggle, accept all, reject all, add manually, search more
  |
  v
Agent analyzes accepted/rejected patterns, suggests next search direction
  |
  v
Repeat until user says "done"
```

### Candidate Presentation

Each discovered competitor is presented with:

```
[x] GitHub Actions        github.com/features/actions
    Built-in CI/CD for GitHub repos. Free tier for
    public repos. Dominant in open source.
    Found via: G2 category leader, 3x "alternatives" lists
    Suggested tier: Established
```

**Fields:**
- **Name** — company or product name
- **URL** — primary website (so user can verify it's real and relevant)
- **Blurb** — 2-line description: what they do, scale, notable signals (funding, market position)
- **Provenance** — where the agent found this candidate ("Found via: ..."). This starts the provenance chain from step zero. Examples: "G2 category leader", "mentioned in Forrester Wave 2026", "top result for 'alternatives to Jenkins'", "YC S24 batch"
- **Suggested tier** — Established / Emerging / Experimental, based on signals like funding amount, employee count, domain age, analyst report coverage, GitHub activity

### Agent Behavior

- Candidates are pre-checked by default (user unchecks unwanted ones)
- Agent pre-filters obvious junk: dead companies, unrelated products, duplicates, products that clearly fall outside the domain
- Agent errs on the side of inclusion — easier for the user to remove than to know what's missing
- After each round, agent analyzes the accept/reject pattern:
  - "User rejected all build-only tools, focusing on full CI/CD platforms"
  - "User accepted all enterprise tools, may want more coverage there"
- Agent suggests a next search direction: "I noticed gaps in self-hosted and open-source options — want me to search there?"
- Loop continues until user selects "Done"

### Search Sources

The discovery agent searches across:
- **Product directories:** G2, ProductHunt, StackShare, AlternativeTo
- **Analyst reports:** Gartner, Forrester, IDC (via search — not direct access)
- **Funding databases:** Crunchbase, PitchBook mentions (via search)
- **Community:** "alternatives to X" discussions on HN, Reddit
- **Market maps:** published landscape diagrams, industry overviews
- **Seed expansion:** if user provides known competitors, search "X vs Y", "alternatives to X", "companies like X"

### Deduplication

Agent tracks all candidates across rounds to avoid re-presenting rejected ones. Handles aliases (e.g., "GitHub Actions" vs "GitHub CI" vs "GitHub Workflows") by matching on URL domain.

## Schema Wizard

### Overview

`recon init` runs a guided conversational wizard that produces the complete workspace configuration. The wizard has 3 phases plus a review step. It must work both as an interactive TUI and as an LLM-callable flow (agent answers the prompts programmatically).

### Wizard Phase 1: Identity

Questions asked:
1. **Company name** — "What company or organization is this research for?"
2. **Products** — "What products or offerings do you want to compare against competitors?" (list with name, domain, description per product)
3. **Domain description** — "How would you describe the competitive space?" (free text, e.g., "developer tools and DevOps platforms")
4. **Decision context** — "What decisions will this research inform?" (multi-select from options, can add custom):
   - Build vs buy vs partner
   - Investment / acquisition evaluation
   - Product positioning and differentiation
   - Market entry strategy
   - Executive threat briefing
   - General competitive awareness
5. **Own-product research toggle** — "Want to research your own products through the same lens? This gives you an honest external view — public sources, real criticisms, same scoring as competitors." [Y/N]

### Wizard Phase 2: Sections

Based on the decision context selected in Phase 1, the system recommends sections:

**Recommendation logic:**
- Build/buy/partner -> Capabilities, Pricing, Integration Ecosystem, Head-to-Head
- Investment evaluation -> Overview, Capabilities, Pricing, Enterprise Readiness, Strategic Notes
- Product positioning -> Capabilities, Developer Love, Head-to-Head, Pricing
- Market entry -> Overview, Capabilities, Pricing, Developer Love, Time to Value
- Executive briefing -> Overview, Capabilities, Enterprise Readiness, Head-to-Head, Strategic Notes
- General awareness -> all default sections

**For each recommended section, the system shows:**
- Section name and description
- Whether it's recommended (pre-checked) or optional
- Why it's recommended based on the user's decision context

**User can:**
- Accept the recommended set
- Toggle individual sections on/off
- Add custom sections (provides name, description, sub-dimensions)
- Customize any section (change sub-dimensions, rating scales, evidence types)

### Wizard Phase 3: Source Preferences

For each selected section, the wizard presents default source preferences and lets the user adjust.

**Per-section source configuration:**

```yaml
pricing:
  preferred_sources:
    primary: ["official pricing pages", "documentation"]
    secondary: ["G2 reviews", "TrustRadius", "analyst reports"]
    avoid: ["reddit speculation", "outdated blog posts"]
  source_recency: "6 months"

developer_love:
  preferred_sources:
    primary: ["Hacker News", "Reddit r/programming", "dev.to"]
    secondary: ["Twitter/X", "Stack Overflow", "Discord communities"]
    avoid: ["sponsored content", "vendor press releases"]
  source_recency: "12 months"
```

**The wizard explains the defaults:**
- "For Pricing, I recommend official pricing pages as primary sources. These change frequently, so I'll only use sources from the last 6 months."
- "For Developer Sentiment, community sources like HN and Reddit give authentic opinions. I'll avoid sponsored content."

**User can adjust:**
- Add/remove sources from primary, secondary, avoid lists
- Change recency threshold per section
- Accept all defaults at once for speed

### Schema Review and Confirm

After the wizard completes, the full configuration is presented for review.

**Review screen displays:**

```
Domain: Developer Tools
Company: Acme Corp
Products: Acme CI, Acme Review, Acme Deploy
Own-product research: Yes

Sections (8):
  1. Overview          -- 150+ words, strategic context
  2. Capabilities      -- star ratings, 6 sub-dimensions
  3. Pricing           -- tiers, free plan, enterprise
  4. Integration       -- status table + ecosystem analysis
  5. Enterprise Ready  -- compliance, SSO, audit
  6. Developer Love    -- sentiment, quotes, traction
  7. Head-to-Head      -- vs your products, response options
  8. Strategic Notes   -- watch signals, partnership, M&A

Verification: Verified (2-agent consensus)
Competitors: 47 discovered
Estimated cost: $140-180

[e] Edit sections   [p] Edit source preferences
[v] View full YAML  [c] Confirm & create workspace
[q] Cancel
```

**"View full YAML"** shows the exact `recon.yaml` and `schema.md` that will be generated. Power users can inspect every field before committing.

**On confirm, the system creates:**
- `recon.yaml` — full project configuration
- `schema.md` — competitor profile schema with section definitions, format specs, rating scales
- `template.md` — blank competitor template derived from schema
- `competitors/` — directory with scaffolded profiles for all discovered competitors
- `own-products/` — directory with profiles for own products (if enabled)
- `themes/` — empty, populated after theme discovery
- `.recon/state.db` — SQLite state database (empty)
- `.recon/logs/` — log directory
- `.gitignore` — excludes `.recon/`, `.vectordb/`, `.retrieved/`, `.env`
- Worker prompt templates — auto-generated from schema section metadata

## Theme Discovery

### Approach: Data-Driven, Post-Research

Themes are NOT defined during setup. They emerge from the research data after indexing.

### When It Happens

After Phase 5a (Index), the pipeline runs theme discovery as Phase 5b. This is a **pipeline gate** — execution pauses and waits for user curation before proceeding to retrieval and synthesis.

### How It Works

1. Run clustering (k-means or similar) on all embeddings in ChromaDB
2. Analyze clusters for coherent themes: what do these competitors have in common?
3. Rank themes by evidence strength (how many competitors, how dense the cluster)
4. Present discovered themes to user

### Theme Curation Screen

```
Discovered 7 themes from 50 competitor profiles:

[x] 1. Platform Consolidation  (38 competitors, strong)
[x] 2. Agentic Shift           (31 competitors, strong)
[x] 3. Developer Experience    (45 competitors, strong)
[x] 4. Pricing Race            (29 competitors, moderate)
[ ] 5. Enterprise Lock-in      (18 competitors, moderate)
[x] 6. Open Source Moats       (22 competitors, moderate)
[ ] 7. Vertical Specialization (12 competitors, weak)

[Space] Toggle  [E] Edit name  [V] View evidence
[+] Investigate a topic  [D] Done -- synthesize selected
```

**User can:**
- Toggle themes on/off
- Edit theme names (the clustering gives working names, user refines)
- View evidence for a theme (which competitors, what signals)
- Investigate a topic (see below)
- Confirm final theme set

### Investigate a Topic

When the user thinks there should be a theme the clustering didn't surface:

1. User enters a topic phrase (e.g., "regulatory risk")
2. System runs directed retrieval queries against the index
3. System reports back:
   - If strong signal: "Found significant evidence. 12 competitors have regulatory-related content. Here are the key signals: [summary]. Add as a theme?"
   - If weak signal: "I searched for this but found very little. Only 2 brief mentions across 50 competitors. Add anyway or skip?"
4. If user adds it, it joins the theme list with the same structure as discovered themes

### Theme Output

After curation, the confirmed themes are written to `recon.yaml`:

```yaml
themes:
  platform_consolidation:
    title: "Platform Consolidation"
    discovered: true
    evidence_strength: strong
    competitor_count: 38
    # queries are auto-generated from the cluster analysis
    queries:
      - "platform expansion feature bundling strategies"
      - "all-in-one developer platforms versus best-of-breed"
      - "enterprise bundling platform lock-in"
      - "acquisition targets developer tools space"
```

## Own-Product Research

### Approach: Same Pipeline, Different Framing

Own products are researched through the same pipeline as competitors. They are not treated specially in terms of sections, format, or verification.

### What's Different

1. **Frontmatter flag:** `type: own_product` in the profile
2. **Research prompt framing:** The research agent gets an additional instruction: "Research this product from an external perspective only. Use public sources — documentation, reviews, community discussions, analyst reports. Do not assume insider knowledge. Be honest about weaknesses and gaps. Rate capabilities the same way you would rate a competitor."
3. **Synthesis awareness:** Deep synthesis Pass 3 (gap analyst) knows which profiles are own products and uses them for comparative analysis
4. **Dashboard separation:** Own products shown in a separate section from competitors, but with the same status tracking

### Why This Matters

The value of own-product research is seeing your products scored on the same scale as everyone else. If the Capabilities section uses star ratings, your product gets star ratings too. If Developer Love tracks sentiment, your product gets real external sentiment too. No special treatment, no inflated ratings. That's the credibility.

### Toggle During Setup

The wizard asks during the Identity phase: "Want to research your own products through the same lens?" with a clear explanation of what this means. If the user says yes, own products are included in the competitor discovery output and go through the full pipeline. If no, the `own-products/` directory is still created (for future use) but empty.
