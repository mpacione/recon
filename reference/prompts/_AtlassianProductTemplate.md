# Atlassian Product Profile Template

> **PURPOSE**: Self-assessment profiles for Atlassian products to enable apples-to-apples comparison with competitors in the interactive presentation app.
>
> **CANONICAL REFERENCE**: See `_Schema.md` for all rating scales and formatting rules.

---

## Template

```markdown
---
type: atlassian
name: "{Product Name}"
domain: [Code Generation | Code Review | CI/CD | Documentation | DX Platform | Task Breakdown]
product_url: "https://www.atlassian.com/software/{product}"
logo_url: ""
tagline: "{5-10 word description}"
autonomy_level: L[1-5]
last_updated: YYYY-MM-DD
research_status: scaffold

# Competitive positioning
top_competitors: ["{Competitor 1}", "{Competitor 2}", "{Competitor 3}"]
primary_threat: "{Single biggest competitive threat}"
---

# {Product Name}

## Overview

<!-- 150+ words covering:
- What this product does today
- Target users and use cases
- Market position (leader, challenger, etc.)
- Key differentiators vs competitors
- Honest assessment of current gaps
-->


## Capabilities

| Capability | Rating | Notes |
|------------|--------|-------|
| Core Function | ★★★★☆ | [Specific features, strengths, gaps] |
| AI/Agentic | ★★☆☆☆ | [Current AI capabilities, autonomy level] |
| Integration | ★★★★★ | [Atlassian ecosystem advantage] |
| Enterprise Ready | ★★★★★ | [Compliance, scale, support] |


## Agentic Capabilities

**Autonomy Level**: L[1-5] — [Description]

| Capability | Status | Notes |
|------------|--------|-------|
| Code generation | ✅/⚠️/❌ | [Current state] |
| Multi-file edits | ✅/⚠️/❌ | [Current state] |
| Tool use/MCP | ✅/⚠️/❌ | [Current state] |
| Self-correction | ✅/⚠️/❌ | [Current state] |
| Autonomous execution | ✅/⚠️/❌ | [Current state] |

### Strategic Agentic Analysis

<!-- How do our agentic capabilities compare to competitors?
Where are we ahead? Where are we behind?
What's our trajectory? -->


## Integration Ecosystem

| Integration Type | Status | Details |
|------------------|--------|---------|
| GitHub | ✅/⚠️/❌ | [Quality of integration] |
| GitLab | ✅/⚠️/❌ | |
| VS Code | ✅/⚠️/❌ | |
| JetBrains | ✅/⚠️/❌ | |
| MCP Protocol | ✅/⚠️/❌ | |
| Atlassian Suite | ✅ Native | [Jira, Confluence, Bitbucket integration] |
| API/SDK | ✅/⚠️/❌ | |

### Strategic Integration Analysis

<!-- Where is Atlassian suite integration a genuine advantage?
Where do we lag on third-party integrations?
How does this affect competitive positioning? -->


## Enterprise Readiness

| Feature | Status | Details |
|---------|--------|---------|
| SSO/SAML | ✅ | [Atlassian Access] |
| SCIM | ✅ | |
| Audit Logs | ✅ | |
| Data Residency | ✅ | [Regions available] |
| SOC 2 Type II | ✅ | |
| HIPAA/GDPR | ✅ | |
| FedRAMP | ⚠️ | [Status] |


## Developer Love

**Sentiment**: 🟢 Positive | 🟡 Mixed | 🔴 Negative

<!-- Be honest—what do developers actually think of this product?
Check HN, Reddit, Twitter for real sentiment.
Don't just use internal metrics. -->

**Strengths mentioned**:
- [What developers like]

**Concerns mentioned**:
- [Common complaints—be honest]

### Quotes

> "Quote from external source showing real developer sentiment"
> — Source, Date

### Traction Signals

| Metric | Value | Source |
|--------|-------|--------|
| Active Users | X | Internal data |
| NPS | X | Internal data |
| G2 Rating | X/5 | G2.com |
| Market Share | X% | [Analyst report] |


## Head-to-Head vs Top Competitors

### vs {Competitor 1}

| Dimension | {Product} | {Competitor 1} |
|-----------|-----------|----------------|
| Core strength | ★★★★☆ [brief] | ★★★★★ [brief] |
| AI/Agentic | ★★☆☆☆ [brief] | ★★★★☆ [brief] |
| Integration | ★★★★★ [brief] | ★★★★☆ [brief] |
| Enterprise | ★★★★★ [brief] | ★★★☆☆ [brief] |

**Where we win**: [Specific advantages]
**Where we lose**: [Specific gaps]

### vs {Competitor 2}

[Same format]

### vs {Competitor 3}

[Same format]


## Roadmap Positioning

### Current State
- [Honest assessment of where the product is today]
- [Key recent releases]

### Announced/Planned
- [Public roadmap items]
- [Recent announcements]

### Gap Analysis vs {Primary Threat}

| Capability | {Competitor} | {Product} | Gap |
|------------|--------------|-----------|-----|
| [Key capability 1] | ★★★★★ | ★★★☆☆ | 2 stars |
| [Key capability 2] | ★★★★☆ | ★★★★☆ | Parity |
| [Key capability 3] | ★★★★☆ | ★★☆☆☆ | 2 stars |

### Investment Required to Close Gap
- [Eng quarters, acquisitions, partnerships needed]
- [What's realistic vs aspirational]


## Talking Points

### What keeps us up at night
- [Specific concern about this product's competitive position]

### Our competitive advantage
- [What we do better than competitors—be specific]

### Our vulnerability
- [Where competitors are winning—be honest]

### Discussion prompt
- [Question for LT to consider]


---

## Sources

### Internal Sources
- [Product roadmap, internal metrics, strategy docs]

### External Sources
- [G2 reviews, HN discussions, analyst reports]
```

---

## Products to Create

| Product | Domain | Top Competitors | Primary Threat |
|---------|--------|-----------------|----------------|
| Rovo Dev | Code Generation | Cursor, GitHub Copilot, Devin | Cursor |
| Jira | Task Breakdown | Linear, GitHub Issues, Asana | Linear |
| Bitbucket | Code Review, CI/CD | GitHub, GitLab, Graphite | GitHub |
| Compass | DX Platform | Backstage, Port, Cortex | Backstage |
| Confluence | Documentation | Notion, Mintlify, GitBook | Notion |

---

## Guidance for Honest Self-Assessment

**Don't**:
- Inflate ratings to make us look good
- Use only internal metrics for Developer Love
- Ignore real criticisms from HN/Reddit
- Pretend gaps don't exist

**Do**:
- Rate capabilities honestly vs market
- Include real external developer sentiment
- Acknowledge where competitors win
- Be specific about gaps and investment required

The value of these profiles is **honest comparison**. Leadership needs to understand where we actually stand, not a marketing view.
