# Canonical Schema Reference

> **Single source of truth** for all competitor profile formatting.
> All prompts reference this file—do not duplicate these definitions elsewhere.
> Last updated: 2026-01-25

---

## Frontmatter Schema

### Competitor Profile

```yaml
---
type: competitor
name: "{Name}"
domain: [Code Generation | Code Review | CI/CD | Documentation | DX Platform | Task Breakdown | Security | Spec & Planning]
tier: [Established | Emerging | Experimental]
threat_level: [High | Medium | Low | Watch]
atlassian_overlap: [Bitbucket | Compass | Rovo Dev | Jira | Confluence]
last_updated: YYYY-MM-DD
research_status: [scaffold | p1-complete | p2-complete | p3-complete | verified | skipped]
skip_reason: "{optional: only required if research_status is 'skipped'}"

# Presentation fields (for interactive demo app)
demo_url: "{URL to product homepage or signup}"
demo_account: "{optional: e.g., 'See 1Password > Competitors' or 'HD setting up'}"
logo_url: "{optional: URL to logo image}"
tagline: "{One-liner for card display, 5-10 words}"
funding_display: "{e.g., '$400M Series C' or 'Bootstrapped'}"
autonomy_level: [L1 | L2 | L3 | L4 | L5]
out_of_left_field: [true | false]  # Emerging/agentic threats that should be on radar
presentation_priority: [1 | 2 | 3]  # 1 = must discuss, 2 = discuss if time, 3 = reference only

# Theme tags (populated by P4 synthesis pipeline)
themes: ["{Theme 1}", "{Theme 2}"]  # e.g., ["Agentic Shift", "Platform Wars"]

# P3.5 Strategic Enrichment Fields
# Platform & Ecosystem
marketplace_size: "{number or 'N/A'}"  # e.g., "500+ extensions", "N/A"
api_surface: [REST | GraphQL | SDK | Webhooks | MCP | CLI | None]  # List all that apply
partner_ecosystem: "{notable partnerships}"  # e.g., "GitHub, Vercel, AWS integrations"
lock_in_signals: "{portability assessment}"  # e.g., "Proprietary format, no export", "Open standards, easy migration"

# Trust & Governance
compliance_certs: [SOC2 | GDPR | HIPAA | FedRAMP | ISO27001 | None]  # List all that apply
audit_capabilities: "{logging, explainability features}"  # e.g., "Full decision audit trail", "None"
admin_controls: "{enterprise admin features}"  # e.g., "SSO, SCIM, RBAC, approval workflows"

# Workflow Embedding (UX Architecture)
interaction_model: [sidecar | inline | chat | ambient | autonomous | hybrid]
context_sources: [codebase | docs | tickets | git_history | runtime | web | none]  # List all that apply
trigger_pattern: [user-invoked | event-driven | continuous | scheduled | hybrid]

# Time to Value
onboarding_friction: [1 | 2 | 3 | 4 | 5]  # 1=frictionless self-serve, 5=complex enterprise setup
time_to_first_value: "{minutes | hours | days}"  # e.g., "5 minutes", "2-3 days"
free_tier_limits: "{what's free}"  # e.g., "2000 completions/mo", "14-day trial only", "Unlimited free tier"
self_serve: [true | false]  # Can you start without talking to sales?

# Engineering Evolution: Left-of-Code / Alignment Infrastructure
left_of_code_value: [planning | alignment | intent | specs | requirements | design_review | none]  # List all
right_of_code_value: [code_review | testing | deployment | monitoring | none]  # List all that apply
alignment_artifact_support: "{Does it generate/capture alignment artifacts?}"  # e.g., "Generates specs from convos"
conductor_model_fit: [builder | reviewer | hybrid | neither]  # Built for engineer-as-builder or engineer-as-reviewer?
decision_trace_capability: "{Can you trace specs → agent runs → human interventions → code?}"  # Full trace, partial, none
---
```

### Atlassian Product Profile

```yaml
---
type: atlassian
name: "{Product Name}"
domain: [Code Generation | Code Review | CI/CD | Documentation | DX Platform | Task Breakdown]
product_url: "{URL to product page}"
logo_url: "{optional: URL to logo image}"
tagline: "{One-liner for card display, 5-10 words}"
autonomy_level: [L1 | L2 | L3 | L4 | L5]
last_updated: YYYY-MM-DD
research_status: [scaffold | p1-complete | p2-complete | p3-complete | verified]

# Competitive positioning
top_competitors: ["{Competitor 1}", "{Competitor 2}", "{Competitor 3}"]
primary_threat: "{Single biggest competitive threat}"
---
```

### Atlassian Overlap Mapping

| Category | Atlassian Products |
|----------|-------------------|
| Code Generation | `[Rovo Dev]` |
| Task Breakdown | `[Jira, Rovo Dev]` |
| Code Review | `[Bitbucket]` |
| CI/CD | `[Bitbucket]` |
| Documentation | `[Confluence]` |
| DX Platform | `[Compass]` |
| Security | `[Bitbucket]` (or `[]` if not core) |
| Spec & Planning | `[Jira, Confluence]` |

### Research Status Values

| Status | Meaning | When to Use |
|--------|---------|-------------|
| `scaffold` | Empty template | File created, no research done |
| `p1-complete` | Overview + Agentic level filled | P1 pass complete |
| `p2-complete` | All sections filled | P2 pass complete (target: score ≥25/35) |
| `p3-complete` | Sentiment enriched | P3 pass complete |
| `p3_5-complete` | Strategic fields added | P3.5 strategic enrichment complete |
| `verified` | Matt reviewed | Production ready |
| `skipped` | Intentionally not researched | Requires `skip_reason` in frontmatter |

**Skip reasons** (use when setting `research_status: skipped`):
- `defunct` — Company shut down or product discontinued
- `acquired` — Merged into another product (note which one)
- `irrelevant` — No longer competes with Atlassian products
- `duplicate` — Covered under another profile
- `insufficient-data` — Cannot find enough reliable sources

---

## Rating Scales

### Capability Ratings (★ stars)

Use in: **Capabilities table**, **Head-to-Head table**

| Rating | Meaning | Criteria |
|--------|---------|----------|
| ★★★★★ | Best-in-class | Market-defining, sets the standard |
| ★★★★☆ | Strong | Competitive with leaders |
| ★★★☆☆ | Adequate | Meets expectations |
| ★★☆☆☆ | Limited | Notable gaps |
| ★☆☆☆☆ | Minimal | Early stage or bare-bones |

**Calibration anchors**:
- GitHub Copilot = ★★★★☆ for AI/Agentic (market leader baseline)
- Linear = ★★★★★ for Developer Love (cult favorite)
- Jira = ★★★★★ for Enterprise Ready (market leader)

### Status Icons (✅/⚠️/❌)

Use in: **Agentic Capabilities table**, **Integration Ecosystem table**, **Enterprise Readiness table**, **Demo & Trial table**

| Icon | Meaning | When to Use |
|------|---------|-------------|
| ✅ | Fully supported | Production-ready, well-documented |
| ⚠️ | Partial/Limited | Beta, constraints, or gaps |
| ❌ | Not supported | Missing or explicitly unavailable |
| 🔍 | Needs research | Unknown—do not leave cells blank |

### Sentiment Indicators

Use in: **Developer Love section**

| Indicator | Meaning | Criteria |
|-----------|---------|----------|
| 🟢 Positive | >70% positive | Enthusiastic language ("love", "game-changer") |
| 🟡 Mixed | Split opinions | Notable praise AND criticism |
| 🔴 Negative | Majority negative | Trust issues, churn signals, complaints |

---

## Autonomy Level Scale (L1–L5)

Use in: **Agentic Capabilities section**

| Level | Name | Description | Examples |
|-------|------|-------------|----------|
| L1 | Suggestion | Tab autocomplete only; inline completions | Tabnine basic, Copilot suggestions |
| L2 | Bounded task | Generates function/file on explicit request | ChatGPT, Copilot chat, Copilot Edits |
| L3 | Multi-step with approval | Plans multi-step changes, shows plan, waits for approval | Cursor Agent, Copilot Workspace |
| L4 | Goal-directed | Given a goal, works toward it with minimal intervention | Devin, Codex |
| L5 | Fully autonomous | Can be assigned tasks and completes them without oversight | Factory, hypothetical future agents |

**Key distinctions**:
- L1→L2: Passive suggestions vs. active generation
- L2→L3: Single output vs. multi-step planning with human checkpoint
- L3→L4: Approval gates vs. autonomous execution toward goal
- L4→L5: Minimal oversight vs. zero oversight

---

## Threat Level Criteria

| Level | Definition | Typical Indicators |
|-------|------------|-------------------|
| High | Direct competitor, strong traction | >$50M funding, >100k users, enterprise customers |
| Medium | Partial overlap OR emerging traction | $10-50M funding, growing mindshare, indirect threat |
| Low | Minimal overlap, niche use case | <$10M funding, narrow focus, not scaling |
| Watch | Not a threat today but trajectory matters | New entrant, strategic investor, potential pivot |

---

## Source Documentation Format

**Every competitor file must include this section at the bottom.**

```markdown
## Sources

### Research Queries Used
<!-- Document searches for reproducibility -->
- "{name} features capabilities 2026" — Google — YYYY-MM-DD
- "site:news.ycombinator.com {name}" — HN Search — YYYY-MM-DD

### Primary Sources
<!-- Official docs, pricing pages, changelogs, company blog -->
- [Title](URL) — accessed YYYY-MM-DD, used for: [sections]

### Community Sources
<!-- HN, Reddit, Twitter/X, Discord -->
- [HN: Thread Title](URL) — YYYY-MM-DD, used for: [sections]

### Third-Party Sources
<!-- G2, Capterra, news articles, analyst reports -->
- [TechCrunch: Article](URL) — YYYY-MM-DD, used for: [sections]
```

**Rules**:
1. No factual claim without a source
2. All sources must have access/publication date
3. Note which section(s) each source supports
4. If unavailable: `⚠️ paywalled` or `⚠️ login required`
5. If conflicting sources: Add `⚠️ Disputed: [brief explanation]` inline

---

## Quality Rubric

**Score each dimension 1–5 before marking `p2-complete`:**

| Dimension | 1-2 (Thin) | 3-4 (Adequate) | 5 (Rich) |
|-----------|------------|----------------|----------|
| Overview depth | <100 words, generic | 100-150 words, specific | 150+ words, strategic insight |
| Capability notes | <5 words, vague | 10-20 words, specific | 20+ words, evidence + implications |
| Integration analysis | Table only | Table + 50 words | Table + 100+ words strategic prose |
| Developer sentiment | 1 quote, no analysis | 2-3 quotes, basic analysis | 3+ quotes, migration patterns, trajectory |
| Head-to-head | Table only | Table + differentiator | Table + vulnerability + response options + timeline |
| Strategic notes | <50 words | 50-100 words | 100+ words with watch signals, partnership, acquisition |
| Sources | <10 sources | 10-20 sources | 20+ sources, all dated |

**Scoring**:
- **Minimum acceptable**: 21/35 (all dimensions ≥3)
- **Target quality**: 30/35 (most dimensions = 5)
- **If <21**: Enrich thin sections before marking complete

---

## Formatting Rules Summary

| Section | Format | Symbol Set |
|---------|--------|------------|
| Capabilities | Table with ratings | ★ stars |
| Agentic Capabilities | Table with status | ✅/⚠️/❌ |
| Integration Ecosystem | Table with status | ✅/⚠️/❌ |
| Enterprise Readiness | Table with status | ✅/⚠️/❌ |
| Demo & Trial | Table with status | ✅/⚠️/❌ |
| Developer Love sentiment | Inline prefix | 🟢/🟡/🔴 |
| Head-to-Head | Table with ratings | ★ stars |
| Unknown values | Placeholder | 🔍 Needs research |

**Never leave cells blank.** Use `🔍 Needs research` if information is unknown.

---

---

## Atlassian Product Sections

Atlassian product profiles use a modified structure:

**Include:**
- Overview (current state, positioning)
- Capabilities (same format as competitors)
- Agentic Capabilities (same format)
- Integration Ecosystem (same format)
- Enterprise Readiness (same format)
- Developer Love (internal + external sentiment)
- Head-to-Head vs Top 3 Competitors
- Talking Points (for presentation)
- Roadmap Positioning (NEW - Atlassian only)

**Exclude:**
- Company & Pricing (we are Atlassian)
- Partnership Potential (N/A)
- Acquisition Consideration (N/A)
- Funding/Traction metrics (N/A)

### Roadmap Positioning Section (Atlassian only)

```markdown
## Roadmap Positioning

### Current State
- [Where the product is today—be honest about gaps]

### Announced/Planned
- [Public roadmap items, recent announcements]

### Gap Analysis vs {Top Competitor}
| Capability | {Competitor} | {Atlassian Product} | Gap |
|------------|--------------|---------------------|-----|
| {Capability 1} | ★★★★★ | ★★★☆☆ | 2 stars |
| {Capability 2} | ★★★★☆ | ★★★★☆ | Parity |

### Investment Required
- [What would it take to close the gap? Eng quarters? Acquisitions?]
```

---

## Talking Points Section (for P3+)

Add this section to competitor profiles for presentation use:

```markdown
## Talking Points

### What keeps us up at night
- [1-2 punchy bullets—specific, quotable concerns]

### Their competitive advantage
- [Specific capability or position Atlassian can't easily match]

### Our competitive advantage
- [Where Atlassian wins against this competitor]

### Discussion prompt
- [Question for LT to consider—drives conversation]
```

---

## P3.5 Strategic Enrichment Fields

These fields are added during P3.5 enrichment to support strategic theme synthesis.

### Platform & Ecosystem Fields

| Field | Purpose | Values |
|-------|---------|--------|
| `marketplace_size` | Extension/plugin ecosystem scale | Number + "extensions" or "N/A" |
| `api_surface` | Integration capabilities | List: REST, GraphQL, SDK, Webhooks, MCP, CLI |
| `partner_ecosystem` | Notable integrations | Free text describing partnerships |
| `lock_in_signals` | Switching cost indicators | Assessment of data portability, export options |

### Trust & Governance Fields

| Field | Purpose | Values |
|-------|---------|--------|
| `compliance_certs` | Security certifications | List: SOC2, GDPR, HIPAA, FedRAMP, ISO27001 |
| `audit_capabilities` | Transparency features | Description of logging, explainability |
| `admin_controls` | Enterprise management | SSO, SCIM, RBAC, approval workflows, etc. |

### Workflow Embedding Fields (UX Architecture)

| Field | Purpose | Values |
|-------|---------|--------|
| `interaction_model` | Where/how AI appears | sidecar, inline, chat, ambient, autonomous, hybrid |
| `context_sources` | What AI can access | List: codebase, docs, tickets, git_history, runtime, web |
| `trigger_pattern` | How AI is invoked | user-invoked, event-driven, continuous, scheduled, hybrid |

**Interaction Model Definitions:**
- `sidecar` — Separate panel/window alongside main work (e.g., Copilot Chat)
- `inline` — Appears in the flow of work, inline completions (e.g., Copilot suggestions)
- `chat` — Dedicated chat interface as primary interaction
- `ambient` — Always-on, proactive suggestions without explicit invocation
- `autonomous` — Works independently toward goals with minimal interaction
- `hybrid` — Combines multiple models

### Time to Value Fields

| Field | Purpose | Values |
|-------|---------|--------|
| `onboarding_friction` | Setup complexity (1-5) | 1=frictionless, 5=complex enterprise |
| `time_to_first_value` | When user gets value | minutes, hours, or days |
| `free_tier_limits` | What's available free | Description of free tier constraints |
| `self_serve` | PLG vs sales-led | true/false |

**Onboarding Friction Scale:**
- `1` — Click, install, working in <5 minutes. No account required or instant signup.
- `2` — Quick signup, minimal config. Working in <30 minutes.
- `3` — Moderate setup. Need to configure integrations, ~1-2 hours.
- `4` — Significant setup. Team onboarding, permissions, integrations. Half-day to full day.
- `5` — Enterprise deployment. Requires sales call, IT involvement, days to weeks.

### Engineering Evolution Fields (Left-of-Code / Alignment Infrastructure)

These fields map competitors to the emerging model of how engineering is changing.

| Field | Purpose | Values |
|-------|---------|--------|
| `left_of_code_value` | Where tool adds value before coding | List: planning, alignment, intent, specs, requirements, design_review |
| `right_of_code_value` | Where tool adds value after coding | List: code_review, testing, deployment, monitoring |
| `alignment_artifact_support` | Does it capture alignment artifacts? | Description of spec/decision capture capabilities |
| `conductor_model_fit` | Built for what engineer role? | builder, reviewer, hybrid, neither |
| `decision_trace_capability` | Can you trace specs → code? | Full trace, partial, none |

**Core Thesis:** "Coding is no longer the bottleneck. Alignment is."

**Left-of-Code** increases in value:
- Planning, design review, spec'ing, requirements, cross-functional negotiation

**Right-of-Code** shifts from diff review to intent review:
- What problem is solved and why now
- Architecture + key decisions
- Observable playback

**Conductor Model Fit:**
- `builder` — Tool assumes engineer writes code (traditional)
- `reviewer` — Tool assumes engineer reviews AI-generated code (emerging model)
- `hybrid` — Supports both modes
- `neither` — Not a coding tool (e.g., pure documentation)

**Decision Trace Capability** (key concern):
> "We're not capturing: specs → breakdown → agent runs → human interventions → code. Without this, we lose context, auditability, and onboarding velocity."

- `Full trace` — Complete lineage from requirement to shipped code
- `Partial` — Captures some steps but gaps exist
- `None` — No traceability features

---

## Theme Tags

The `themes` field is populated automatically by the P4 synthesis pipeline based on semantic retrieval.

**Standard themes** (from `config.yaml`):
- `Agentic Shift` — L1→L5 autonomy transition patterns
- `Platform Wars` — Who owns the orchestration layer, ecosystem lock-in
- `Trust & Governance` — Enterprise compliance, audit, admin controls
- `Workflow Embedding` — Where AI lives in the developer workflow (UX architecture)
- `Time to Value` — Onboarding friction, first 5 minutes, PLG patterns
- `Developer Love` — UX patterns developers gravitate toward
- `Consolidation Patterns` — Platform bundling and expansion
- `Alignment Infrastructure` — System of record: specs → agent runs → code
- `Conductor Model` — Tools built for engineer-as-reviewer vs engineer-as-builder

**Emergent themes** may be discovered via clustering (see `00_discover.py`).

A competitor is tagged with a theme if it surfaces in the top-30 results for that theme's retrieval queries.

---

## Change Log

| Date | Change |
|------|--------|
| 2026-01-25 | Added engineering evolution fields (left_of_code, conductor_model, alignment_artifact, decision_trace) |
| 2026-01-25 | Added Alignment Infrastructure and Conductor Model themes |
| 2026-01-25 | Added P3.5 strategic enrichment fields (platform, trust, workflow, time-to-value) |
| 2026-01-25 | Expanded theme list (added Platform Wars, Trust & Governance, Workflow Embedding, Time to Value) |
| 2026-01-25 | Added themes[] field for P4 synthesis tagging |
| 2026-01-25 | Added Atlassian product profile schema (type: atlassian) |
| 2026-01-25 | Added Roadmap Positioning section for Atlassian products |
| 2026-01-25 | Added presentation frontmatter fields (demo_url, tagline, autonomy_level, out_of_left_field, presentation_priority) |
| 2026-01-25 | Added Talking Points section template |
| 2026-01-25 | Created as single source of truth; consolidated from _FormatStandards, _ModelGuidance, _CompetitorTemplate |
