# Format Standards for Competitor Profiles

> **PHILOSOPHY**: Prioritize **information richness and strategic insight** over rigid formatting. Tables should supplement narrative analysis, not replace it.
>
> **CANONICAL REFERENCE**: See `_Schema.md` for authoritative rating scales, status icons, and frontmatter schema. This document provides examples and quality criteria.

---

## Core Principle: Richness Over Uniformity

**The goal is consistently rich competitive intelligence, not visual uniformity.**

Good profiles demonstrate:
- **Evidence density**: Every claim backed by sources
- **Strategic depth**: Why this matters to Atlassian specifically  
- **Narrative synthesis**: Connecting dots across sections
- **Minimum word counts**: Substantive analysis, not bullet points

Poor profiles show:
- Checkbox compliance without insight
- Generic descriptions that could apply to any competitor
- Tables filled but lacking context
- Thin research dressed up in formatting

---

## Section-by-Section Requirements

### 1. Overview Section

**Minimum**: 150 words (not "3-5 sentences")

**Must include**:
- What the product actually does (specific features, not categories)
- Target user persona (with evidence)
- Market positioning and differentiation
- Why this matters to Atlassian (competitive threat or opportunity)
- Recent momentum (funding, launches, traction)

**Example of THIN overview** ❌:
> "Greptile is an AI code review tool. It helps developers review code faster. It integrates with GitHub. Founded in 2023 with seed funding."

**Example of RICH overview** ✅:
> "Greptile is a codebase-aware AI that provides context-rich code reviews by indexing entire repositories and understanding architectural patterns. Unlike point-in-time tools like GitHub Copilot, Greptile maintains a persistent understanding of your codebase, enabling it to catch architectural violations, suggest refactors across multiple files, and provide PR reviews that account for project-specific conventions. Founded in 2023 by Stanford grads, raised $4M seed from Khosla Ventures. Key threat to Atlassian: fills the gap between Bitbucket's basic PR experience and enterprise teams' need for intelligent code review—a capability Atlassian currently lacks. Notably, Greptile has no native Bitbucket support, creating both competitive vulnerability and partnership opportunity."

---

### 2. Capabilities Table

**Format**:
```markdown
| Capability | Rating | Notes |
|------------|--------|-------|
| Core Function | ★★★★☆ | [specific evidence with sources] |
| AI/Agentic | ★★★☆☆ | [specific evidence] |
| Integration | ★★★★☆ | [specific evidence] |
| Enterprise Ready | ★★☆☆☆ | [specific evidence] |
```

**Rating Scale**:
- ★★★★★ = Best-in-class, market-defining
- ★★★★☆ = Strong, competitive with leaders
- ★★★★☆ = Adequate, meets expectations
- ★★☆☆☆ = Limited, notable gaps
- ★☆☆☆☆ = Minimal, early stage

**Notes Column Requirements**:
- Minimum 10 words per note (avoid "Good integration support")
- Include specific feature names or evidence
- Cite sources inline where relevant
- Explain the rating choice

**Example of THIN notes** ❌:
```
| Core Function | ★★★★☆ | Good code review features |
```

**Example of RICH notes** ✅:
```
| Core Function | ★★★★☆ | Maintains persistent codebase understanding vs point-in-time analysis; architectural violation detection; multi-file refactor suggestions; custom rule engine. Loses one star for lack of CI/CD integration and no support for monorepo architectures. |
```

---

### 3. Agentic Capabilities

**Autonomy Level Definitions** (be precise):
- **L1**: Tab autocomplete only (e.g., Tabnine basic, Copilot suggestions)
- **L2**: Generate function/file on explicit request (e.g., ChatGPT, Copilot chat)
- **L3**: Multi-step plans with human approval before execution (e.g., Cursor Agent)
- **L4**: Goal-directed with minimal intervention; executes autonomously (e.g., Devin)
- **L5**: Fully autonomous; can be assigned tasks and completes without oversight (e.g., Factory)

**Table Format**:
```markdown
| Capability | Status | Notes |
|------------|--------|-------|
| Code generation | ✅ | [specific evidence] |
| Multi-file edits | ⚠️ | [specific limitation] |
| Tool use/MCP | ❌ | [why not supported] |
| Self-correction | ✅ | [how it works] |
| Autonomous execution | ⚠️ | [specific constraint] |
```

**Status Icons**:
- `✅` = Fully supported, production-ready
- `⚠️` = Partial/beta/limited (explain in Notes)
- `❌` = Not supported

**CRITICAL**: Notes column must include:
- Specific feature names (not "supported" or "available")
- Version/date if recently added
- Limitations or constraints
- Comparison to competitors where relevant

**Narrative Supplement** (REQUIRED):

After the table, add 1-2 paragraphs analyzing:
- How agentic capabilities position this competitively
- Strategic implications for Atlassian
- Trajectory (getting more/less autonomous)

**Example**:
> While Greptile rates as L2 autonomy (generates reviews on explicit PR events), its persistent codebase understanding positions it strategically between traditional SAST tools and emerging L4 agents like Devin. The lack of autonomous execution is intentional—teams want review augmentation, not replacement. This creates a window for Atlassian: Bitbucket could integrate similar codebase indexing without threatening developer agency. However, Greptile's 6-month head start and venture backing ($4M seed) suggest they'll reach multi-file autonomous refactoring (L3) before Atlassian can catch up organically.

---

### 4. Integration Ecosystem

**Flexible Format**: Use tables for structured data, prose for strategic analysis.

**Table Format** (use when cataloging integrations):
```markdown
| Integration Type | Status | Details |
|------------------|--------|---------|
| GitHub | ✅ Native | GitHub App, full PR integration, comment threads |
| GitLab | ⚠️ Limited | Basic webhook support, no MR comments |
| Bitbucket | ❌ | No support (strategic gap for Atlassian) |
| VS Code | ✅ Extension | Marketplace extension, 50k installs |
| MCP Protocol | ⚠️ Planned | Announced for Q2 2026 |
```

**Narrative Format** (use for strategic analysis):

After or instead of table, add prose covering:
- **Strategic integration choices** (why GitHub-first? Why no Bitbucket?)
- **MCP positioning** (if this becomes the standard, who wins?)
- **API quality** (documented? Stable? Rate limits?)
- **Extensibility** (can users build custom integrations?)
- **Atlassian implications** (partnership opportunity? Competitive moat?)

**Example of RICH integration analysis**:
> Greptile's GitHub-first strategy reflects both market pragmatism (70%+ of their target market uses GitHub) and strategic positioning against Bitbucket. The lack of native Bitbucket support creates a vulnerability: Atlassian teams wanting AI code review must either migrate to GitHub or cobble together webhook-based solutions. This gap presents two options for Atlassian: (1) partner with Greptile to build native Bitbucket support, gaining AI code review capabilities without build costs, or (2) use Greptile's absence as a window to build competitive features before they expand SCM coverage. Their announced MCP support (Q2 2026) suggests they're positioning for a multi-tool ecosystem play, which could make them either a strong integration partner or a platform competitor to Rovo.

---

### 5. Enterprise Readiness

**When to use table format**:
Use tables for compliance/security checklist items (SSO, SOC2, etc.):

```markdown
| Feature | Status | Details |
|---------|--------|---------|
| SSO/SAML | ✅ | Okta, Entra ID, custom OIDC |
| SCIM | ⚠️ | Manual provisioning only; SCIM planned Q3 2026 |
| Audit Logs | ✅ | 1-year retention; includes prompt history |
| Data Residency | ❌ | US only; no EU/APAC options |
| SOC 2 Type II | ✅ | Report available at trust.greptile.com |
```

**When to use prose format**:
Use narrative for strategic enterprise analysis:
- **Enterprise sales motion** (self-serve vs sales-led?)
- **Pricing structure implications** (seat-based vs usage-based)
- **Lock-in risk** (proprietary formats? Vendor dependency?)
- **Competitive enterprise positioning** (who are they displacing in enterprises?)

**Example of RICH enterprise analysis**:
> Greptile's enterprise readiness is intentionally minimal—they're targeting high-growth startups (Series A-B) that value speed over compliance checkboxes. The lack of EU data residency and SCIM auto-provisioning eliminates Fortune 500 buyers, which creates a temporary safe zone for Atlassian's enterprise-first positioning. However, this is likely strategic: building compliance features is expensive upfront but unlocks higher ACVs later. If Greptile raises a Series A ($15M+), expect SOC 2, EU residency, and SCIM within 12 months, turning them from startup tool to enterprise threat. Atlassian's window to respond is narrower than it appears.

---

### 6. Developer Love Section

**Sentiment Assessment**:
```markdown
**Sentiment**: 🟢 Positive
```

Use ONLY:
- `🟢 Positive` = >70% positive mentions, enthusiastic language
- `🟡 Mixed` = Split opinions, significant praise AND criticism
- `🔴 Negative` = Majority negative, trust issues, churn signals

**Quotes Requirements**:
- Minimum 3 quotes (not 2)
- Include attribution, date, and engagement metrics where possible
- Mix sources (HN, Reddit, G2, Twitter, Discord)
- Show range (positive, critical, contextual)

**Format**:
```markdown
### Quotes

> "Exact quote from source that reveals genuine developer sentiment"
> — [Source/Author], [Date or context], [engagement: 450 upvotes / 89 likes]

> "Another quote showing different perspective"
> — [Attribution]
```

**Traction Signals**:

Use **table format** for metrics:
```markdown
| Metric | Value | Source |
|--------|-------|--------|
| GitHub Stars | 45,000 | GitHub, Jan 2026 |
| G2 Rating | 4.7/5 (234 reviews) | G2.com, Jan 2026 |
| Discord Members | 12,000+ | Discord invite page |
| HN Mentions (2025) | 47 threads | HN search |
| Revenue (ARR) | $8M | TechCrunch, Nov 2025 |
```

**Narrative Supplement** (REQUIRED after quotes/metrics):

1-2 paragraphs analyzing:
- **What developers actually love** (be specific about features)
- **Competitive migration patterns** ("switched from X")
- **Community health** (growing/plateauing/fragmenting?)
- **Sentiment trajectory** (improving/declining over time?)
- **Atlassian implications** (what can we learn? What threatens us?)

**Example**:
> Developer sentiment centers on Greptile's "feels like it actually read my code" quality—a step-function improvement over generic linters. The most common migration pattern is "GitHub Actions + Semgrep → Greptile," suggesting they're displacing static analysis rather than human review. Community health is strong (12k Discord, active daily discussion) but concentrated in React/TypeScript ecosystem—Python and Java support lags, creating language-specific vulnerabilities. Sentiment trajectory is positive but shows early signs of pricing tension as teams scale ("loved it at 5 devs, can't justify at 50"). Key Atlassian insight: developers will pay premium for tools that "understand" their codebase, but pricing must scale sub-linearly with team size or adoption stalls.

---

### 7. Head-to-Head vs Atlassian

**Table Format**:
```markdown
| Dimension | {Competitor} | Atlassian |
|-----------|--------------|-----------|
| Core strength | ★★★★★ AI code review | ★★★☆☆ Basic PR UX |
| AI/Agentic | ★★★★☆ L2 autonomous | ★★☆☆☆ L1 copilot integrations |
| Integration | ★★★★☆ GitHub-native | ★★★★★ Full Atlassian suite |
| Pricing | ★★★☆☆ $50/seat/mo | ★★★★☆ Bundled with Bitbucket |
```

**Narrative Analysis** (REQUIRED after table):

Must include:
- **Key Differentiator**: One sentence on competitor's unique advantage
- **Atlassian Vulnerability**: Specific product gap or weakness this exposes
- **Competitive Response Options**: 
  - Build (internal development)
  - Buy (acquisition target?)
  - Partner (integration/resale)
  - Ignore (not strategic)
- **Timeline**: When does this become urgent? (Now / 6-12mo / 2+ years)

**Example**:
> **Key Differentiator**: Greptile's persistent codebase understanding enables architectural-level review that Bitbucket's point-in-time PR checks cannot match.
>
> **Atlassian Vulnerability**: Bitbucket has no intelligent code review capability beyond basic linting integrations. Enterprise teams wanting AI-assisted review must either adopt Greptile (fragmenting toolchain) or migrate to GitHub (where Copilot integration is tighter). This positions Bitbucket as "legacy SCM" rather than "AI-native DevOps platform."
>
> **Recommended Response**: **Partner or Build** (not Buy—$4M seed suggests $40M+ acquisition cost for <2 years of runway). Partnership option: integrate Greptile as "Powered by" feature in Bitbucket Cloud, similar to Snyk integration model. Build option: invest 2-3 eng quarters in codebase indexing + LLM review; leverage existing Bitbucket permissions model as moat. Timeline: **6-12 months**—Greptile's growth suggests they'll be enterprise-ready by mid-2026, after which partnership leverage declines.

---

### 8. Strategic Notes Section

**Minimum**: 100 words of strategic analysis

**Must include**:
- **Watch Signals**: Specific events that would change threat assessment
  - Funding rounds (how much? from whom?)
  - Product launches (which features?)
  - Customer wins (which logos?)
  - Executive hires (CRO? Enterprise lead?)
  
- **Partnership Potential**: Yes/No with reasoning
  - Strategic fit
  - Integration complexity
  - Revenue model compatibility
  - Competitive risk of partnering

- **Acquisition Consideration**: Yes/No/Maybe with analysis
  - Estimated valuation range
  - Strategic value to Atlassian
  - Integration challenges
  - Alternative acquirers (who else wants this?)

**Example**:
> **Watch Signals**: 
> (1) Series A raise >$15M signals enterprise expansion—expect SOC2, SCIM, EU residency within 6 months
> (2) Bitbucket integration announcement—flips from competitor to distribution partner
> (3) GitHub acquisition rumors—would consolidate AI code review under Microsoft, forcing Atlassian's hand
> (4) MCP protocol adoption—if this becomes standard, Greptile positions as platform vs point solution
>
> **Partnership Potential**: **Yes, high value**. Greptile fills Bitbucket's AI review gap without requiring Atlassian to build ML infrastructure. Integration complexity is low (webhook-based architecture). Revenue share model could work (20% of Bitbucket Premium customers might adopt AI review at $20-30/seat incremental). Risk: legitimizes "AI code review" as separate category, making it harder for Atlassian to bundle later.
>
> **Acquisition Consideration**: **Maybe at Series A**. Current valuation likely $30-50M ($4M seed at ~15% dilution). Strategic value high (instant AI code review capability, talent acquisition, removes competitor). Key risk: team of 8 means culture integration challenges, and acqui-hire risk (founders leave after 1-year vesting). Alternative acquirers: GitHub (obvious), GitLab (catching up on AI), Snyk (expanding beyond security scanning). Recommend: explore partnership now, revisit acquisition if Series A values company <$100M.

---

### 9. Sources Section

**Four Required Subsections**:

```markdown
## Sources

### Research Queries Used
- "Greptile AI code review features" — Google — 2026-01-25
- "site:news.ycombinator.com Greptile" — HN Search — 2026-01-25
- "Greptile vs CodeRabbit reddit" — Google — 2026-01-25

### Primary Sources  
- [Greptile Docs](https://docs.greptile.com) — accessed 2026-01-25, used for: Capabilities, Integration
- [Greptile Pricing](https://greptile.com/pricing) — accessed 2026-01-25, used for: Pricing section
- [Khosla Ventures: Seed Announcement](https://www.khoslaventures.com/greptile) — 2023-08-15, used for: Funding

### Community Sources
- [HN: Show HN: Greptile](https://news.ycombinator.com/item?id=37280718) — 2023-08-20, used for: Developer Love quotes
- [Reddit: Greptile vs CodeRabbit comparison](https://reddit.com/r/programming/comments/18x9k3l/) — 2024-12-10, used for: Sentiment

### Third-Party Sources
- [TechCrunch: Greptile raises $4M](https://techcrunch.com/2023/08/15/greptile-seed) — 2023-08-15, used for: Company overview
- [G2 Reviews](https://g2.com/products/greptile/reviews) — accessed 2026-01-25, used for: Traction Signals
```

**Requirements**:
- Every factual claim must have a source
- Include access date (web content changes)
- Note which section(s) each source supports
- If source is paywalled/unavailable, note: `⚠️ paywalled` or `⚠️ login required`

---

## Common Mistakes to Avoid

| ❌ Wrong | ✅ Correct |
|----------|-----------|
| Overview is 3 sentences | Overview is 150+ words with strategic context |
| "Good integration support" | "Native GitHub App with PR comment threads, 50k installs" |
| Table with no narrative follow-up | Table + 1-2 paragraphs strategic analysis |
| Generic head-to-head | Specific Atlassian vulnerabilities and response options |
| "Partnership possible" | "Partnership: YES—here's the revenue model and risks" |
| Sources without dates | All sources have access dates |
| Thin strategic notes | 100+ word strategic analysis with watch signals |

---

## Quality Rubric

**Before marking a profile complete, score it:**

| Dimension | 1-2 (Thin) | 3-4 (Adequate) | 5 (Rich) |
|-----------|------------|----------------|----------|
| **Overview depth** | <100 words, generic | 100-150 words, specific | 150+ words, strategic insight |
| **Capability notes** | <5 words, vague | 10-20 words, specific | 20+ words, evidence + implications |
| **Integration analysis** | Table only | Table + 50 words | Table + 100+ words strategic prose |
| **Developer sentiment** | 1 quote, no analysis | 2-3 quotes, basic analysis | 3+ quotes, migration patterns, trajectory analysis |
| **Head-to-head** | Table only | Table + differentiator | Table + vulnerability + response options + timeline |
| **Strategic notes** | <50 words | 50-100 words | 100+ words with watch signals, partnership analysis |
| **Sources** | <10 sources | 10-20 sources | 20+ sources, all dated |

**Minimum acceptable score: 21/35 (all dimensions ≥3)**

**Target score: 30/35 (most dimensions = 5)**

> **Note**: See `_Schema.md` for the canonical rating definitions and rubric.

---

## Validation Checklist

Before marking `research_status: p2-complete`:

- [ ] Overview ≥150 words with strategic context
- [ ] Capabilities table: all notes ≥10 words with evidence
- [ ] Agentic section: table + narrative analysis
- [ ] Integration: table + strategic prose
- [ ] Enterprise: table OR rich prose (100+ words)
- [ ] Developer Love: 3+ quotes + traction table + narrative
- [ ] Head-to-Head: table + differentiator + vulnerability + response
- [ ] Strategic Notes: ≥100 words with watch signals + partnership + acquisition
- [ ] Sources: ≥20 sources, all with dates, organized in 4 subsections
- [ ] Quality rubric score: ≥25/35

---

## Format Flexibility

**When to use tables**: Structured data that benefits from side-by-side comparison
- Capabilities ratings
- Integration checklist  
- Enterprise compliance features
- Traction metrics
- Pricing tiers

**When to use prose**: Strategic analysis, synthesis, implications
- Overview section (always prose)
- Agentic capabilities follow-up
- Integration ecosystem strategy
- Enterprise positioning
- Developer Love narrative
- Head-to-head analysis
- Strategic notes (always prose)

**Best practice**: Use BOTH—table for scanability, prose for insight.
