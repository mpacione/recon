# Competitor Profile Template

> **PHILOSOPHY**: This template scaffolds structure, but RICHNESS comes from deep research and strategic analysis. Prioritize insight over checkbox completion.
>
> **CANONICAL REFERENCE**: See `_Schema.md` for all rating scales, status definitions, and formatting rules.

---

## Template (copy for each competitor)

```markdown
---
type: competitor
name: "{Name}"
domain: [Code Generation | Code Review | CI/CD | Documentation | DX Platform | Task Breakdown | Security | Spec & Planning]
tier: [Established | Emerging | Experimental]
threat_level: [High | Medium | Low | Watch]
atlassian_overlap: [Bitbucket | Compass | Rovo Dev | Jira | Confluence]
last_updated: YYYY-MM-DD
research_status: scaffold
---

# {Name}

## Overview

<!-- MINIMUM: 150 words (not 3-5 sentences) -->
<!-- Must include:
- What it actually does (specific features, not just category)
- Target user persona (with evidence: "popular with React developers" not "developers")  
- Market positioning and differentiation (vs who? why better?)
- Why this matters to Atlassian (specific threat or opportunity)
- Recent momentum (funding, launches, traction signals)
-->

<!-- EXAMPLE STRUCTURE:
{Name} is a [specific description] that [key differentiator]. Unlike [alternative approach], {Name} [unique mechanism/approach], enabling [concrete user outcome]. 

Founded in [year] by [relevant background], the company has raised $[amount] from [notable investors] and serves [specific traction metric: X users, Y companies, Z revenue]. Target users are [specific persona: "DevOps engineers at Series B startups"] rather than generic "developers."

Key threat to Atlassian: [specific product vulnerability this exposes]. [Competitor strength] positions them to [specific competitive outcome: displace, partner, acquire market share]. Notably, [tactical detail that reveals strategic opportunity or risk].
-->


## Capabilities

| Capability | Rating | Notes |
|------------|--------|-------|
| Core Function | ★★★★☆ | <!-- Min 10 words: specific features + evidence. Example: "Maintains persistent codebase understanding vs point-in-time analysis; architectural violation detection; multi-file refactor suggestions. Loses one star for lack of CI/CD integration." --> |
| AI/Agentic | ★★★☆☆ | <!-- What AI capabilities? What autonomy level? What limitations? --> |
| Integration | ★★★★☆ | <!-- Which integrations? Quality? Strategic coverage? --> |
| Enterprise Ready | ★★☆☆☆ | <!-- SSO? SOC2? What's missing? What's planned? --> |

<!-- Rating Scale:
★★★★★ = Best-in-class, market leader
★★★★☆ = Strong, competitive with leaders  
★★★☆☆ = Adequate, meets expectations
★★☆☆☆ = Limited, notable gaps
★☆☆☆☆ = Minimal, early stage
-->


## Agentic Capabilities

**Autonomy Level**: L[1-5] — [brief description]

<!-- 
L1: Tab autocomplete only
L2: Generate function/file on request
L3: Multi-step with approval
L4: Goal-directed autonomy  
L5: Fully autonomous
-->

| Capability | Status | Notes |
|------------|--------|-------|
| Code generation | ✅/⚠️/❌ | <!-- Specific feature names, not "supported". Include limitations. --> |
| Multi-file edits | ✅/⚠️/❌ | <!-- How many files? What constraints? --> |
| Tool use/MCP | ✅/⚠️/❌ | <!-- Which tools? MCP protocol support? --> |
| Self-correction | ✅/⚠️/❌ | <!-- How does it validate output? Iterates? --> |
| Autonomous execution | ✅/⚠️/❌ | <!-- Runs without approval? What safety rails? --> |

<!-- Status: ✅ = Full support, ⚠️ = Partial/Beta, ❌ = Not supported -->

### Strategic Agentic Analysis

<!-- REQUIRED: 1-2 paragraphs analyzing:
- How agentic capabilities position this competitively
- Implications for Atlassian (threat? opportunity?)
- Trajectory (getting more autonomous? plateauing?)

EXAMPLE:
"While {Name} rates as L2 autonomy, its [specific capability] positions it between [category A] and [category B]. The lack of [missing feature] is intentional—[strategic reason]. This creates [opportunity/threat for Atlassian]: [specific strategic implication]. However, [competitor's] [funding/roadmap/hiring] suggests they'll reach [next capability level] before Atlassian can [respond organically/build alternative]."
-->


## Integration Ecosystem

<!-- Use TABLE for structured integration inventory -->

| Integration Type | Status | Details |
|------------------|--------|---------|
| GitHub | ✅/⚠️/❌ | <!-- Native app? Webhook? Quality of integration? --> |
| GitLab | ✅/⚠️/❌ | <!-- --> |
| Bitbucket | ✅/⚠️/❌ | <!-- CRITICAL: Note if absent (opportunity for Atlassian) --> |
| VS Code | ✅/⚠️/❌ | <!-- Extension? Install count? --> |
| JetBrains | ✅/⚠️/❌ | <!-- Which IDEs? --> |
| MCP Protocol | ✅/⚠️/❌ | <!-- Tools? Resources? Version? --> |
| Self-Hosted | ✅/⚠️/❌ | <!-- Cloud-only is ❌ --> |
| API/SDK | ✅/⚠️/❌ | <!-- REST? GraphQL? SDK languages? --> |

<!-- Status values:
✅ Native = First-party integration
✅ Extension/Plugin = Official extension  
✅ Available = Feature exists
⚠️ Limited = Partial support
⚠️ Planned = Announced, not released
❌ = Not available
-->

### Strategic Integration Analysis

<!-- REQUIRED: 1-2 paragraphs analyzing:
- Why these integration choices? (GitHub-first strategy signals what?)
- What's missing and why? (No Bitbucket = opportunity? Or irrelevant market?)
- MCP positioning (platform play? tool play?)
- API quality and extensibility
- Atlassian implications (partnership? competitive moat?)

EXAMPLE:
"{Name}'s GitHub-first strategy reflects [market reality] and positions them [competitively against X]. The lack of native Bitbucket support creates [specific vulnerability/opportunity]: Atlassian teams wanting [capability] must either [migrate to GitHub] or [workaround]. This gap presents two options: (1) [partnership approach] or (2) [build approach]. Their announced MCP support suggests [strategic positioning: platform vs tool], which could make them [integration partner or competitive threat to Rovo]."
-->


## Enterprise Readiness

<!-- Use TABLE for compliance/security checklist items -->

| Feature | Status | Details |
|---------|--------|---------|
| SSO/SAML | ✅/⚠️/❌ | <!-- Which providers? Custom OIDC? --> |
| SCIM | ✅/⚠️/❌ | <!-- Auto-provisioning? --> |
| Audit Logs | ✅/⚠️/❌ | <!-- Retention period? Prompt logging? --> |
| Data Residency | ✅/⚠️/❌ | <!-- US/EU/APAC? Customer choice? --> |
| SOC 2 Type II | ✅/⚠️/❌ | <!-- Report available where? --> |
| HIPAA/GDPR | ✅/⚠️/❌ | <!-- BAA available? GDPR compliant? --> |

### Enterprise Strategy Analysis

<!-- OPTIONAL but RECOMMENDED: 100+ words analyzing:
- Enterprise sales motion (self-serve? sales-led?)
- Target enterprise segment (Fortune 500? Series B startups?)  
- Pricing structure implications (seat vs usage)
- Lock-in risk (proprietary formats? Vendor dependency?)
- Competitive enterprise positioning (who are they displacing?)

EXAMPLE:
"{Name}'s enterprise readiness is intentionally minimal—targeting [segment] that value [speed over compliance]. The lack of [features] eliminates [Fortune 500 buyers], creating temporary safe zone for Atlassian's enterprise positioning. However, this is likely strategic: building compliance is expensive upfront but unlocks higher ACVs later. If {Name} raises [next funding round], expect [compliance features] within 12 months, turning them from [startup tool] to [enterprise threat]. Atlassian's window to respond is [narrower/wider] than it appears."
-->


## Developer Love

**Sentiment**: 🟢 Positive | 🟡 Mixed | 🔴 Negative

<!--
🟢 = >70% positive mentions, enthusiastic language
🟡 = Split opinions, significant praise AND criticism
🔴 = Majority negative, trust issues, churn signals

See _Schema.md for complete rating definitions.
-->

### Quotes

<!-- MINIMUM: 3 quotes (not 2) -->
<!-- Include: attribution, date, engagement metrics -->
<!-- Mix sources: HN, Reddit, G2, Twitter, Discord -->
<!-- Show range: positive, critical, contextual -->

> "Exact quote from source that reveals genuine developer sentiment"
> — [Source/Author], [Date or context], [engagement: 450 upvotes / 89 likes]

> "Another quote showing different perspective"  
> — [Attribution]

> "Third quote revealing nuance or concern"
> — [Attribution]

### Traction Signals

| Metric | Value | Source |
|--------|-------|--------|
| GitHub Stars | X | GitHub, [date] |
| G2 Rating | X/5 (X reviews) | G2.com, [date] |
| Discord Members | X | Discord invite page |
| HN Mentions (2025) | X threads | HN search |
| Revenue (ARR) | $XM | [source], [date] |
| Users | XM+ developers | [source], [date] |

### Developer Sentiment Analysis

<!-- REQUIRED: 1-2 paragraphs analyzing:
- What developers ACTUALLY love (specific features, not "UX")
- Competitive migration patterns ("switched from X to Y")
- Community health (growing? plateauing? fragmenting?)
- Sentiment trajectory (improving/declining over time?)
- Atlassian implications (what can we learn? what threatens us?)

EXAMPLE:
"Developer sentiment centers on {Name}'s [specific quality]—a step-function improvement over [alternative]. The most common migration pattern is [X → Y], suggesting they're displacing [category] rather than [other category]. Community health is [strong/weak]: [specific metrics], but [limitation/risk]. Sentiment trajectory is [positive/negative/mixed] but shows early signs of [concern: pricing tension, feature gaps]. Key Atlassian insight: [strategic takeaway about what developers value and how it threatens/helps Atlassian]."
-->


## Demo & Trial

| Type | Available | Link/Notes |
|------|-----------|------------|
| Free tier | ✅/❌ | <!-- What's included? Limits? --> |
| Trial | ✅/❌ | <!-- Duration? Credit card required? --> |
| Demo video | ✅/❌ | <!-- Link? Quality? Length? --> |
| Sandbox | ✅/❌ | <!-- Interactive demo? --> |
| Live demo | ✅/❌ | <!-- Sales-led? Self-service? --> |


## Company & Pricing

- **Founded**: [Year] by [Founder background if relevant]
- **Funding**: $[X]M [Round] at $[Y]B valuation ([Lead investors], [Date])
- **Team size**: ~[X] employees ([Source], [Date])
- **Headquarters**: [Location] | [Remote-first/Hybrid]

**Pricing**:

| Plan | Price | Includes |
|------|-------|----------|
| Free | $0 | <!-- Limits: users, features, usage --> |
| Pro | $X/user/mo | <!-- Key features unlocked --> |
| Business | $X/user/mo | <!-- Team features --> |
| Enterprise | Custom | <!-- Enterprise features, minimum seats? --> |

<!-- OPTIONAL: Pricing analysis prose
If pricing structure reveals strategic positioning, add paragraph:
- Seat-based vs usage-based (implications?)
- Competitive pricing (vs GitHub/GitLab/Atlassian?)
- Pricing inflection points (where does it get expensive?)
- Lock-in mechanisms (annual commits? Volume discounts?)
-->


## Head-to-Head vs Atlassian

| Dimension | {Name} | Atlassian |
|-----------|--------|-----------|
| Core strength | ★★★★★ [brief: what specifically?] | ★★★☆☆ [brief: where we fall short?] |
| AI/Agentic | ★★★★☆ [brief: autonomy level] | ★★☆☆☆ [brief: current state] |
| Integration | ★★★★☆ [brief: ecosystem] | ★★★★★ [brief: Atlassian suite strength] |
| Pricing | ★★★☆☆ [brief: value prop] | ★★★★☆ [brief: bundling advantage] |

### Competitive Analysis

<!-- REQUIRED: Must include ALL of these -->

**Key Differentiator**: 
<!-- One sentence: competitor's unique advantage over Atlassian -->

**Atlassian Vulnerability**: 
<!-- Specific product gap or weakness this exposes. Which Atlassian product? Which use case? -->

**Competitive Response Options**:
- **Build**: [Internal development approach, timeline, cost]
- **Buy**: [Acquisition target? Estimated valuation? Integration challenges?]  
- **Partner**: [Integration/resale model? Revenue split? Strategic risks?]
- **Ignore**: [Why this isn't strategic? What would change that assessment?]

**Timeline**: 
<!-- When does this become urgent?
- NOW: Immediate threat, customers asking for this
- 6-12 months: Growing threat, window to respond
- 2+ years: Emerging threat, monitoring phase
-->

<!-- EXAMPLE:
**Key Differentiator**: {Name}'s persistent codebase understanding enables architectural-level review that Bitbucket's point-in-time PR checks cannot match.

**Atlassian Vulnerability**: Bitbucket has no intelligent code review capability beyond basic linting integrations. Enterprise teams wanting AI-assisted review must either adopt {Name} (fragmenting toolchain) or migrate to GitHub (where Copilot integration is tighter).

**Competitive Response Options**:
- Build: 2-3 eng quarters for codebase indexing + LLM review; leverage Bitbucket permissions model as moat
- Buy: Not recommended—$4M seed suggests $40M+ acquisition cost for <2 years runway  
- Partner: "Powered by" integration in Bitbucket Cloud, similar to Snyk model; 20% rev share
- Ignore: Only if we're exiting code review market entirely

**Timeline**: 6-12 months—{Name}'s growth suggests enterprise-ready by mid-2026, after which partnership leverage declines.
-->


## Strategic Notes

<!-- MINIMUM: 100 words -->

### Watch Signals
<!-- Specific events that would change threat assessment:
- Funding rounds (how much? from whom? signals enterprise push?)
- Product launches (which features? fills which gaps?)  
- Customer wins (which logos? which verticals?)
- Executive hires (CRO? Enterprise lead? signals what?)
- MCP/ecosystem announcements
-->

**Examples**:
- Series A raise >$15M signals enterprise expansion (expect SOC2, SCIM, EU residency)
- Bitbucket integration announcement flips from competitor to distribution partner
- GitHub acquisition rumors would consolidate category under Microsoft
- MCP protocol adoption positions as platform vs point solution

### Partnership Potential
<!-- Yes/No/Maybe with reasoning:
- Strategic fit (fills Atlassian gap? complements products?)
- Integration complexity (API quality? Architecture compatibility?)
- Revenue model compatibility (resale? rev share? bundling?)
- Competitive risk of partnering (legitimizes category? Creates dependency?)
-->

**Example**: **Yes, high value**. {Name} fills [Atlassian gap] without requiring [expensive build]. Integration complexity is [low/high] because [technical reason]. Revenue share model could work: [specific model]. Risk: [competitive risk of legitimizing category or creating dependency].

### Acquisition Consideration  
<!-- Yes/No/Maybe with analysis:
- Estimated valuation range (based on funding, revenue, comps)
- Strategic value to Atlassian (why buy vs build/partner?)
- Integration challenges (team size? Culture fit? Tech stack?)
- Alternative acquirers (who else wants this? What's their motive?)
- Timing (now? after Series A? never?)
-->

**Example**: **Maybe at Series A**. Current valuation likely $[range] based on [reasoning]. Strategic value is [high/medium/low] because [specific capability gain]. Key risk: [acqui-hire risk, integration complexity]. Alternative acquirers: [GitHub, GitLab, Snyk] because [their strategic motive]. Recommend: [explore partnership now, revisit acquisition if X happens].


---

## Sources

<!-- CRITICAL: Every factual claim needs a source -->
<!-- All sources must have access dates -->
<!-- Organize into 4 subsections -->

### Research Queries Used
<!-- Record searches for reproducibility -->
- "{name} features capabilities 2025" — Google — YYYY-MM-DD
- "site:news.ycombinator.com {name}" — HN Search — YYYY-MM-DD  
- "{name} vs [competitor] reddit" — Google — YYYY-MM-DD

### Primary Sources
<!-- Official docs, pricing pages, changelogs, company blog -->
- [Title](URL) — accessed YYYY-MM-DD, used for: [which sections]
- [Pricing Page](URL) — accessed YYYY-MM-DD, used for: Pricing section
- [Documentation](URL) — accessed YYYY-MM-DD, used for: Capabilities, Integration

### Community Sources  
<!-- HN threads, Reddit discussions, Twitter/X posts, Discord -->
- [HN: Thread Title](URL) — YYYY-MM-DD, used for: Developer Love quotes
- [Reddit: Discussion](URL) — YYYY-MM-DD, used for: Sentiment analysis
- [Twitter thread](URL) — YYYY-MM-DD, used for: Traction signals

### Third-Party Sources
<!-- G2, Capterra, analyst reports, news articles, funding announcements -->
- [TechCrunch: Article](URL) — YYYY-MM-DD, used for: Funding, Company overview
- [G2 Reviews](URL) — accessed YYYY-MM-DD, used for: Ratings, Sentiment
- [Analyst Report](URL) — YYYY-MM-DD, used for: Market positioning

<!-- If source is unavailable, note: ⚠️ paywalled or ⚠️ login required -->
```

---

## Research Status Values

Update `research_status` in frontmatter as work progresses:

| Status | Meaning | Quality Bar |
|--------|---------|-------------|
| `scaffold` | Empty template, no research | N/A |
| `p1-complete` | Overview (150+ words), Agentic level assigned | Minimum viable |
| `p2-complete` | All sections filled with rich analysis | Target quality (score ≥25/35 on rubric) |
| `verified` | Matt reviewed and approved | Production ready |

---

## Quality Rubric (Before Marking P2-Complete)

Score each dimension 1-5:

| Dimension | Score | Criteria |
|-----------|-------|----------|
| Overview depth | /5 | 1-2: <100 words; 3-4: 100-150 words; 5: 150+ words with strategic insight |
| Capability notes | /5 | 1-2: <5 words; 3-4: 10-20 words; 5: 20+ words with evidence + implications |
| Integration analysis | /5 | 1-2: Table only; 3-4: Table + 50 words; 5: Table + 100+ words strategic prose |
| Developer sentiment | /5 | 1-2: 1 quote; 3-4: 2-3 quotes + basic analysis; 5: 3+ quotes + migration patterns + trajectory |
| Head-to-head | /5 | 1-2: Table only; 3-4: Table + differentiator; 5: Table + vulnerability + response + timeline |
| Strategic notes | /5 | 1-2: <50 words; 3-4: 50-100 words; 5: 100+ words with watch signals + partnership + acquisition |
| Sources | /5 | 1-2: <10 sources; 3-4: 10-20 sources; 5: 20+ sources, all dated, 4 subsections |

**Minimum acceptable: 25/35** (all dimensions ≥3)  
**Target quality: 30/35** (most dimensions = 5)

**If score <25**: Do additional research to enrich thin sections before marking complete.
