# Prompt: Single Competitor Deep Dive

> Use this prompt to research and create a RICH, strategically insightful competitor profile.
>
> **CANONICAL REFERENCE**: See `_Schema.md` for all rating scales, status definitions, and formatting rules.

---

## Quick Context

I'm building competitive intelligence for Atlassian's developer tools (Bitbucket, Compass, Rovo Dev, Jira, Confluence).

Create a competitor profile for: **[COMPETITOR NAME]**

Save it to: `Competitors/CompetitiveLandscape-2025/Competitors/[Name].md`

---

## Research Philosophy

**Goal**: Strategic insight, not checkbox completion.

**Quality bar**: 
- Overview: 150+ words (not 3-5 sentences)
- Every capability rating: 20+ words of justification
- Every section: Evidence-backed with sources
- Strategic analysis: Why this matters to Atlassian specifically

**Bad profile indicators**:
- Generic descriptions ("good tool for developers")
- Thin notes ("strong integration support")
- Missing strategic context (doesn't explain Atlassian threat/opportunity)
- <20 sources cited

**Good profile indicators**:
- Specific product details ("persistent codebase understanding vs point-in-time analysis")
- Evidence-backed ratings ("loses one star for lack of CI/CD integration per docs")
- Strategic narrative (explains competitive dynamics, migration patterns, Atlassian vulnerabilities)
- 25+ sources across primary/community/third-party

---

## Research Queries (Minimum 7, Expand as Needed)

### Required Searches:

1. **Product capabilities**:
   - `"{name} features capabilities 2026"`
   - `"{name} documentation getting started"`

2. **Pricing and business model**:
   - `"{name} pricing plans enterprise"`
   - `"{name} revenue ARR funding"`

3. **Competitive positioning**:
   - `"{name} vs Jira"` OR `"{name} vs Bitbucket"` OR `"{name} vs Confluence"` (pick relevant)
   - `"{name} vs [direct competitor]"` (e.g., "Cursor vs GitHub Copilot")

4. **Developer sentiment**:
   - `"site:news.ycombinator.com {name}"`
   - `"site:reddit.com/r/programming {name}"`
   - `"{name} review" OR "{name} worth it"`

5. **AI/Agentic capabilities** (for AI tools):
   - `"{name} AI features autonomous agent"`
   - `"{name} MCP model context protocol"`
   - `"{name} code generation multi-file"`

6. **Enterprise readiness**:
   - `"{name} enterprise features SSO SOC2"`
   - `"{name} security compliance GDPR"`

7. **Integration ecosystem**:
   - `"{name} integrations GitHub GitLab Bitbucket"`
   - `"{name} API SDK documentation"`

### Additional Searches (as needed):

8. **Community health**:
   - `"site:github.com {name} stars"`
   - `"{name} Discord community"`

9. **Funding and trajectory**:
   - `"{name} Series A/B funding TechCrunch"`
   - `"{name} acquisition rumors"`

10. **Migration patterns**:
    - `"switched from [competitor] to {name}"`
    - `"{name} migration guide"`

---

## Profile Structure (Copy This Template)

```yaml
---
type: competitor
name: "[Name]"
domain: [Code Generation | Code Review | CI/CD | Documentation | DX Platform | Task Breakdown | Security | Spec & Planning]
tier: [Established | Emerging | Experimental]
threat_level: [High | Medium | Low | Watch]
atlassian_overlap: [Bitbucket | Compass | Rovo Dev | Jira | Confluence]
last_updated: 2026-01-25
research_status: p2-complete
---

# [Name]

## Overview

<!-- MINIMUM: 150 words -->
<!-- Structure:
Paragraph 1: What it is, specific features, target users
Paragraph 2: Funding, traction, market position  
Paragraph 3: Why this matters to Atlassian (specific threat/opportunity)
-->

[Name] is a [specific description with key features]. Unlike [alternative approach], [Name] [unique mechanism], enabling [concrete user outcome]. [Additional specifics about how it works, key capabilities, differentiation].

Founded in [year] by [founder background if notable], the company has raised $[amount] from [investors] and [traction: X users, Y revenue, Z customers]. Target users are [specific persona evidence] rather than generic developers. [Market positioning: growing/stable, which segment, competitive dynamics].

Key threat to Atlassian: [specific product vulnerability]. [Competitor's strength] positions them to [specific competitive outcome]. Notably, [tactical detail that reveals strategic opportunity/risk—e.g., "lacks Bitbucket support, creating partnership window" or "tight GitHub integration makes them hard to displace"].


## Capabilities

| Capability | Rating | Notes |
|------------|--------|-------|
| Core Function | ★★★★☆ | [Minimum 20 words: Specific features + evidence + why this rating. Example: "Maintains persistent codebase understanding through AST indexing and vector embeddings; enables architectural-level review vs point-in-time linting. Multi-file refactor suggestions and custom rule engine. Loses one star for lack of CI/CD integration and limited monorepo support per documentation."] |
| AI/Agentic | ★★★☆☆ | [What AI capabilities specifically? What autonomy level? What are limitations? Evidence from docs/demos.] |
| Integration | ★★★★☆ | [Which platforms? Quality of integration? Strategic gaps—Bitbucket absence?] |
| Enterprise Ready | ★★☆☆☆ | [SSO? SOC2? What's missing? What's on roadmap? Why this matters.] |


## Agentic Capabilities

**Autonomy Level**: L[1-5] — [Description of what this means for this product]

<!-- 
L1: Tab autocomplete only (Copilot basic)
L2: Generate function/file on request (ChatGPT)
L3: Multi-step with approval (Cursor Agent)
L4: Goal-directed autonomy (Devin)
L5: Fully autonomous (Factory)
-->

| Capability | Status | Notes |
|------------|--------|-------|
| Code generation | ✅ | [Specific feature names, models used, quality indicators] |
| Multi-file edits | ⚠️ | [Limitations: how many files? What constraints? Beta vs GA?] |
| Tool use/MCP | ❌ | [Planned? Why not supported? Strategic implication?] |
| Self-correction | ✅ | [How does it validate? Iterates how many times? Error handling?] |
| Autonomous execution | ⚠️ | [What safety rails? Requires approval for what?] |

### Strategic Agentic Analysis

<!-- 1-2 paragraphs REQUIRED -->

[How do these agentic capabilities position this product competitively? Compare to alternatives. What's the trajectory—getting more autonomous or staying bounded? What does this mean for Atlassian—is this a threat model we need to match, or a strategic mistake we can avoid?]

[Example: "While [Name] rates as L2 autonomy, its persistent codebase understanding positions it strategically between traditional SAST tools and emerging L4 agents like Devin. The intentional limitation to review-only (no autonomous execution) reflects customer preference for augmentation over replacement. This creates opportunity for Atlassian: Bitbucket could integrate similar indexing without threatening developer agency. However, [Name]'s 6-month head start and $4M seed suggest they'll reach L3 multi-file autonomous refactoring before Atlassian can respond organically."]


## Integration Ecosystem

| Integration Type | Status | Details |
|------------------|--------|---------|
| GitHub | ✅ Native | [Quality: GitHub App? Webhook? Feature completeness? Install count?] |
| GitLab | ⚠️ Limited | [What works? What doesn't? Roadmap?] |
| Bitbucket | ❌ | [CRITICAL: If absent, explain why this matters for Atlassian] |
| VS Code | ✅ Extension | [Marketplace stats? Feature parity with other IDEs?] |
| JetBrains | ✅ Plugin | [Which IDEs? Quality? Update frequency?] |
| MCP Protocol | ⚠️ Planned | [Timeline? Tools vs Resources? Strategic positioning?] |
| Self-Hosted | ❌ | [Cloud-only strategy—why? Enterprise limitation?] |
| API/SDK | ✅ Available | [REST/GraphQL? Documentation quality? Rate limits? SDK languages?] |

### Strategic Integration Analysis

<!-- 1-2 paragraphs REQUIRED -->

[Why did they choose these integrations? GitHub-first strategy signals what about their market positioning? What's missing and why does it matter? If no Bitbucket support, is this a strategic opportunity for Atlassian to partner, or evidence that Bitbucket market share doesn't matter to emerging tools?]

[Example: "[Name]'s GitHub-first strategy (70% of seed-stage startups use GitHub per Stack Overflow survey) positions them against GitHub Copilot, not Bitbucket. The lack of Bitbucket support creates asymmetric vulnerability: Atlassian teams wanting AI code review must fragment toolchain or migrate. Two options: (1) Partner to build native Bitbucket support, gaining AI review without build cost, or (2) Use their absence as 12-month window to build competitive features. Their MCP announcement (Q2 2026) suggests platform positioning—could become Rovo competitor, not just tool."]


## Enterprise Readiness

| Feature | Status | Details |
|---------|--------|---------|
| SSO/SAML | ✅ | [Which providers? Okta, Entra ID, custom OIDC? Setup complexity?] |
| SCIM | ⚠️ | [Manual provisioning only? Roadmap for auto-provisioning?] |
| Audit Logs | ✅ | [Retention period? What's logged? Prompt/response logging for AI tools?] |
| Data Residency | ❌ | [US-only? EU/APAC planned? GDPR implications?] |
| SOC 2 Type II | ✅ | [Report availability? Date certified? Coverage?] |
| HIPAA/GDPR | ⚠️ | [BAA available? GDPR compliant in practice?] |

### Enterprise Strategy Analysis

<!-- 100+ words OPTIONAL but RECOMMENDED for strategic insight -->

[What segment are they targeting? Series B startups vs Fortune 500? Why does enterprise readiness look like this—intentionally minimal to move fast, or building compliance incrementally? What's the pricing implication—seat-based vs usage locks out different segments. When does this become enterprise-competitive with Atlassian?]

[Example: "[Name]'s enterprise readiness targets Series B-C companies valuing speed over compliance checkboxes. Lack of EU residency and SCIM eliminates Fortune 500, creating temporary Atlassian safe zone. But this is strategic: compliance features are expensive upfront, unlock 3x ACVs later. If Series A raise >$15M, expect SOC2, EU residency, SCIM within 6 months, shifting from startup tool to enterprise threat. Atlassian's response window: narrower than it appears."]


## Developer Love

**Sentiment**: 🟢 Positive | 🟡 Mixed | 🔴 Negative

<!-- Based on:
🟢 = >70% positive, enthusiastic language ("love", "game-changer")
🟡 = Split opinions, notable praise AND criticism  
🔴 = Majority negative, trust issues, churn signals
-->

### Quotes

<!-- MINIMUM 3 quotes, mix sources -->

> "Exact quote that reveals genuine developer sentiment and specific value"
> — [HN user / Reddit u/username / G2 reviewer], [Date], [engagement: 450 upvotes]

> "Quote showing different perspective—maybe critical or contextual"
> — [Source], [Date]

> "Quote revealing migration pattern or comparison to alternatives"
> — [Source], [Date]

### Traction Signals

| Metric | Value | Source |
|--------|-------|--------|
| GitHub Stars | 45,000 | GitHub, Jan 2026 |
| G2 Rating | 4.7/5 (234 reviews) | G2.com, Jan 2026 |
| Discord Members | 12,000+ | Discord invite page |
| HN Mentions (2025) | 47 threads | HN search, Jan 2026 |
| Revenue (ARR) | $8M | TechCrunch, Nov 2025 |
| Users/Customers | 50k devs / 200 companies | Company blog, Dec 2025 |

### Developer Sentiment Analysis

<!-- 1-2 paragraphs REQUIRED -->

[What do developers actually love? Be specific—not "UX" but "tab completion feels psychic because of X". What are common migration patterns—"switched from Copilot to Cursor" reveals competitive dynamic. How healthy is the community—growing, plateauing, fragmenting? What's the sentiment trajectory over time—any signs of pricing tension, feature gaps emerging?]

[Key Atlassian insight: What does this reveal about what developers value? How does it threaten or inform Atlassian strategy?]

[Example: "Developer sentiment centers on 'feels like it actually read my code'—a step-function improvement over generic linters. Most common migration: GitHub Actions + Semgrep → [Name], suggesting they're displacing static analysis, not human review. Community strong (12k Discord, daily activity) but concentrated in React/TypeScript—Python/Java support lags. Sentiment trajectory positive but early pricing tension emerging ('loved at 5 devs, can't justify at 50'). Atlassian insight: developers will pay premium for tools that 'understand' codebase, but pricing must scale sub-linearly or adoption stalls at team growth."]


## Demo & Trial

| Type | Available | Link/Notes |
|------|-----------|------------|
| Free tier | ✅ | [What's included? Limits? Generous or restrictive?] |
| Trial | ✅ | [Duration? Credit card required? Feature limitations?] |
| Demo video | ✅ | [Link? Quality? Length? Convincing?] |
| Sandbox | ✅ | [Interactive demo? Try before signup?] |
| Live demo | ⚠️ | [Sales-led only? Self-service available?] |


## Company & Pricing

- **Founded**: [Year] by [Founder background if notable—"Stanford CS PhD" or "ex-GitHub engineer"]
- **Funding**: $[X]M [Round] at $[Y]B valuation ([Lead investors], [Date])
- **Team size**: ~[X] employees ([Source], [Date])
- **Headquarters**: [Location] | [Remote-first/Hybrid/Office-based]

**Pricing**:

| Plan | Price | Includes |
|------|-------|----------|
| Free | $0 | [Limits: users, features, usage caps] |
| Pro | $X/user/mo | [Key features unlocked, integration access] |
| Business | $X/user/mo | [Team features, admin controls] |
| Enterprise | Custom | [SSO, SLA, support level, minimum seats?] |

<!-- OPTIONAL: If pricing reveals strategic insight, add paragraph analyzing:
- Seat vs usage-based implications
- Where it gets expensive (inflection points)
- Competitive pricing vs GitHub/Atlassian
- Lock-in mechanisms
-->


## Head-to-Head vs Atlassian

| Dimension | [Name] | Atlassian |
|-----------|--------|-----------|
| Core strength | ★★★★★ [specific capability] | ★★★☆☆ [where we lag] |
| AI/Agentic | ★★★★☆ L3 autonomous | ★★☆☆☆ L1 integrations only |
| Integration | ★★★★☆ GitHub-native | ★★★★★ Full Atlassian suite |
| Pricing | ★★★☆☆ $50/seat premium | ★★★★☆ Bundled advantage |

### Competitive Analysis

**Key Differentiator**: 
[One sentence: competitor's unique advantage that Atlassian doesn't match]

**Atlassian Vulnerability**: 
[Specific product gap this exposes. Which product? Which use case? What customer pain goes unaddressed?]

**Competitive Response Options**:

- **Build**: [How long? What investment? Technical complexity? Example: "2-3 eng quarters for codebase indexing + LLM review; leverage Bitbucket permissions as moat; estimated $2M eng cost"]

- **Buy**: [Acquisition target? Valuation estimate? Integration challenges? Example: "Not recommended—$4M seed suggests $40-60M acquisition cost for <2yr runway; team of 8 creates acqui-hire risk"]

- **Partner**: [Integration model? Revenue share? Strategic risk? Example: "'Powered by' integration in Bitbucket Cloud, similar to Snyk; 20% revenue share model; risk of legitimizing separate AI review category"]

- **Ignore**: [Why not strategic? What would change assessment? Example: "Only if exiting code review market; current trajectory suggests ignore = cede market to GitHub"]

**Timeline**: 
[When urgent? NOW / 6-12 months / 2+ years, with reasoning]

**Recommended Action**: [Build/Buy/Partner/Ignore with brief justification]


## Strategic Notes

<!-- MINIMUM 100 words -->

### Watch Signals

[Specific events that would escalate threat or change strategy:]

- Funding: Series A >$15M signals enterprise push (expect SOC2, EU residency, SCIM)
- Product: Bitbucket integration announcement (competitor → partner)
- Market: GitHub acquisition (consolidates category under Microsoft)
- Ecosystem: MCP adoption trajectory (platform play vs tool play)
- Customer: Fortune 500 logo wins (enterprise viability proof)
- Team: Enterprise sales hire (CRO, VP Enterprise) signals GTM shift

### Partnership Potential

[Yes/No/Maybe with detailed reasoning]

**Assessment**: [Yes/No/Maybe]

**Rationale**: 
- Strategic fit: [Does this fill Atlassian gap? Complement existing products?]
- Integration complexity: [API quality? Architecture compatibility? Engineering lift?]
- Revenue model: [Resale? Revenue share? Bundling? Specific numbers if possible]
- Competitive risk: [Does partnering legitimize category? Create dependency? Lock us into their roadmap?]

[Example: "**Yes, high value**. Fills Bitbucket AI review gap without $2M+ build cost. Integration complexity low (webhook architecture, documented APIs). Revenue share model: 20-30% of Bitbucket Premium customers might adopt at $20-30/seat incremental = $X ARR potential. Risk: legitimizes 'AI code review' as separate category, harder to bundle later. Recommendation: 6-month partnership pilot with option to acquire."]

### Acquisition Consideration

[Yes/No/Maybe with detailed analysis]

**Assessment**: [Yes/No/Maybe]

**Valuation estimate**: $[X-Y]M based on [funding round, revenue multiple, comparable exits]

**Strategic value**: 
- Capability acquisition: [What do we get that we can't build?]
- Talent acquisition: [Team quality? Key engineers? Retention risk?]
- Customer acquisition: [Do they bring customers/logos we want?]
- Competitive removal: [Does acquiring remove a threat? Or just slow them?]

**Integration challenges**:
- Technical: [Architecture compatibility? Code quality? Technical debt?]
- Cultural: [Team size? Startup vs enterprise culture fit?]
- Product: [Roadmap alignment? Sunsetting vs continuation?]

**Alternative acquirers**: 
[Who else wants this? GitHub, GitLab, Microsoft, Snyk? What's their motive? How does that change our calculus?]

**Recommendation**: 
[Acquire now / Wait for Series A / Partner instead / Pass, with reasoning and conditions]

[Example: "**Maybe at Series A**. Current valuation $30-50M ($4M seed @ 15% dilution). Strategic value high (instant AI code review, removes competitor, quality team). Integration risk medium (8-person team, acqui-hire concern, need 2-year retention). Alternative acquirers: GitHub (obvious fit), GitLab (AI gap), Snyk (expanding beyond security). Recommendation: Explore partnership now with acquisition option; revisit if Series A values <$100M or if GitHub makes move."]


---

## Sources

<!-- MINIMUM: 20+ sources across all categories -->
<!-- ALL sources must have access dates -->
<!-- Organize into 4 subsections -->

### Research Queries Used
<!-- Document searches for reproducibility -->
- "{name} features capabilities 2026" — Google — 2026-01-25
- "site:news.ycombinator.com {name}" — HN Search — 2026-01-25
- "{name} vs Bitbucket" — Google — 2026-01-25
- [Add all searches performed]

### Primary Sources
<!-- Official docs, company pages, pricing, changelogs -->
- [Company Website](URL) — accessed 2026-01-25, used for: Overview, Company info
- [Documentation](URL) — accessed 2026-01-25, used for: Capabilities, Integration
- [Pricing Page](URL) — accessed 2026-01-25, used for: Pricing section
- [API Documentation](URL) — accessed 2026-01-25, used for: Integration ecosystem
- [Changelog](URL) — accessed 2026-01-25, used for: Recent features, trajectory
- [Add more...]

### Community Sources
<!-- HN, Reddit, Twitter, Discord, developer discussions -->
- [HN: Show HN: {Name}](URL) — 2025-XX-XX, used for: Developer Love quotes, sentiment
- [Reddit: r/programming discussion](URL) — 2025-XX-XX, used for: Migration patterns
- [Twitter: Developer review thread](URL) — 2025-XX-XX, used for: Sentiment
- [Discord: Community stats](URL) — accessed 2026-01-25, used for: Traction signals
- [Add more...]

### Third-Party Sources
<!-- News, funding announcements, reviews, analyst reports -->
- [TechCrunch: Funding announcement](URL) — 2025-XX-XX, used for: Funding, Company
- [G2 Reviews](URL) — accessed 2026-01-25, used for: Ratings, Sentiment, Quotes
- [Capterra Reviews](URL) — accessed 2026-01-25, used for: Enterprise sentiment
- [Stack Overflow Survey](URL) — 2025-XX-XX, used for: Market data
- [Gartner/Forrester Report](URL) — 2025-XX-XX, used for: Competitive positioning
- [Add more...]

<!-- If source unavailable: ⚠️ paywalled, ⚠️ login required, ⚠️ removed -->
```

---

## Quality Checklist (Before Saving)

**Content completeness**:
- [ ] Overview ≥150 words with strategic Atlassian context
- [ ] All capability ratings have 20+ word notes with evidence
- [ ] Agentic section has table + strategic analysis paragraph(s)
- [ ] Integration section has table + strategic analysis paragraph(s)
- [ ] Developer Love has 3+ quotes + traction table + analysis paragraph(s)
- [ ] Head-to-Head has differentiator + vulnerability + response options + timeline
- [ ] Strategic Notes ≥100 words with watch signals + partnership + acquisition analysis
- [ ] Sources section has 20+ sources across all 4 subsections

**Formatting**:
- [ ] Capabilities table uses ★ ratings (NOT ✅)
- [ ] Agentic table uses ✅/⚠️/❌ (NOT ★)
- [ ] All sources have access dates
- [ ] No blank cells (use 🔍 if unknown)
- [ ] `research_status: p2-complete` in frontmatter
- [ ] `last_updated: 2026-01-25` in frontmatter

**Quality score**: [Rate 1-5 per dimension using rubric in _FormatStandards.md]
- Overview depth: /5
- Capability notes: /5
- Integration analysis: /5
- Developer sentiment: /5
- Head-to-head: /5
- Strategic notes: /5
- Sources: /5

**Minimum**: ≥21/35 (all dimensions ≥3)
**Target**: ≥30/35 (most dimensions = 5)

See `_Schema.md` for complete rubric details.

---

## After Creating Profile

1. Verify file saved to: `Competitors/CompetitiveLandscape-2025/Competitors/[Name].md`
2. Check if competitor is in `_SearchSpace.md` (add if missing)
3. Consider: Does this reveal a pattern across multiple competitors? (Document insight)
4. Identify: Are there 2-3 similar competitors worth researching next for comparison?
