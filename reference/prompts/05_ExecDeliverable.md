# Prompt: P5 Executive Deliverable

> **Recommended model**: Opus strongly preferred. Sonnet acceptable. Haiku not recommended.
> Copy this entire prompt into a new Claude session to continue.

---

## Context

I'm building a competitive landscape analysis for Atlassian's developer tools. All research phases (P1-P4) are complete. Now I need to create the executive briefing.

**Audience**: Atlassian leadership team
**Format**: 15-30 minute presentation briefing
**Goal**: Shared language/POV on competitive landscape, inform product decisions

## Your Task

1. Read all files in `/Competitors/CompetitiveLandscape-2025/`:
   - `_SearchSpace.md` (full landscape)
   - `_ContinuationKit.md` (context)
   - `Themes/` (synthesis docs)
   - `Competitors/` (top profiles)

2. Create `_ExecBrief.md` - the executive briefing document

## Document Structure

```markdown
---
type: deliverable
title: "Competitive Landscape Briefing"
audience: Atlassian Leadership
duration: 15-30 minutes
created: 2026-01-24
owner: Matt Pacione
sponsor: Emily Henlein
---

# Competitive Landscape Briefing
## Developer Tools Market, Q1 2026

---

## Executive Summary

### The Big Picture
> 2-3 sentences: What's the single most important thing leadership needs to understand?

### Three Existential Threats
1. **{Threat 1}**: One sentence
2. **{Threat 2}**: One sentence
3. **{Threat 3}**: One sentence

### Three Strategic Opportunities
1. **{Opportunity 1}**: One sentence
2. **{Opportunity 2}**: One sentence
3. **{Opportunity 3}**: One sentence

### Recommended Actions
| Timeframe | Action | Owner |
|-----------|--------|-------|
| Immediate (0-3mo) | ... | ... |
| Near-term (3-12mo) | ... | ... |
| Strategic (12+mo) | ... | ... |

---

## Landscape Overview

### Market Shifts
> 2-3 paragraphs on the major shifts happening in developer tools

### Category Summary

| Category | Top Threat | Threat Level | Atlassian Position |
|----------|------------|--------------|-------------------|
| Code Generation | Cursor, Copilot | 🔴 High | Rovo Dev emerging |
| Task Breakdown | Linear, Codex | 🔴 High | Jira dominant but threatened |
| Code Review | GitHub, CodeRabbit | 🟡 Medium | Bitbucket stable |
| CI/CD | GitHub Actions | 🟡 Medium | Bitbucket Pipelines |
| Documentation | Notion, Mintlify | 🟡 Medium | Confluence needs refresh |
| DX Platform | Backstage | 🟡 Medium | Compass competitive |
| Security | Wiz, Snyk | 🟢 Low | Not core, partner |

### Threat Heatmap

```
                    Low Impact ←→ High Impact
High Urgency    |  [Pricing    ]  [Agentic Shift]
                |  [Pressure   ]  [MCP Protocol ]
                |
Low Urgency     |  [Platform   ]  [Dev Love    ]
                |  [Consolidate]  [Trends      ]
```

---

## Top 5 Threats: Deep Dives

### 1. {Competitor Name}
**Why it matters**: One paragraph
**Key stats**: Funding, traction, growth
**Atlassian vulnerability**: Specific
**Recommended response**: Specific

### 2. {Competitor Name}
...

### 3. {Competitor Name}
...

### 4. {Competitor Name}
...

### 5. {Competitor Name}
...

---

## Strategic Implications by Product

### Jira
- **Threat**: ...
- **Opportunity**: ...
- **Recommendation**: ...

### Confluence
- **Threat**: ...
- **Opportunity**: ...
- **Recommendation**: ...

### Bitbucket
- **Threat**: ...
- **Opportunity**: ...
- **Recommendation**: ...

### Compass
- **Threat**: ...
- **Opportunity**: ...
- **Recommendation**: ...

### Rovo Dev
- **Threat**: ...
- **Opportunity**: ...
- **Recommendation**: ...

---

## Key Trends Shaping the Market

### 1. The Agentic Shift
> Summary from theme doc. Link to [[_AgenticShift]]

### 2. MCP Protocol Emergence
> Summary from theme doc. Link to [[_MCPEcosystem]]

### 3. Developer Experience Expectations
> Summary from theme doc. Link to [[_DeveloperLoveTrends]]

---

## Appendix

### Methodology
- Sources: VC market maps, HN, Reddit, G2, product research
- Date range: 2024-2025 data
- Scope: 296 competitors across 8 categories

### Full Competitor List
See [[_SearchSpace]]

### Glossary
See [[_Glossary]]

### Detailed Competitor Profiles
See `/Competitors/` folder

---

## Discussion Questions

1. How aggressively should we pursue MCP integration?
2. Is Rovo Dev positioned to compete with L3+ agents?
3. Should we view Linear as acquisition target or competitor?
4. What's our response to free AI coding assistants?
5. How do we maintain developer love as tools get AI-native?
```

## Writing Guidelines

**For execs who know nothing about this space**:
- No jargon without explanation
- Lead with "so what"
- Be specific about threats (not vague "AI is changing things")
- Quantify where possible (market size, growth rates, adoption)
- Make recommendations actionable

**Tone**:
- Confident but not alarmist
- Evidence-based
- Focused on implications, not just descriptions

**Length**:
- Aim for 2000-3000 words
- Scannable with headers and tables
- Detailed enough to stand alone

## Also Create

### `_ExecBrief-OnePager.md`

A single-page summary version:

```markdown
# Competitive Landscape: One-Pager

## The Big Shift
One paragraph.

## Top 3 Threats | Top 3 Opportunities
Table format.

## By Product: Key Actions
Bullet list.

## Next Steps
1. ...
2. ...
3. ...
```

## Exec Brief Quality Checklist

Before finishing, verify:

- [ ] **No unexplained jargon**: Every technical term has context (MCP, L3 autonomy, etc.)
- [ ] **Specific threats**: Named competitors with concrete vulnerabilities, not "AI disruption"
- [ ] **Quantified where possible**: Funding, growth rates, market share, timelines
- [ ] **Actionable recommendations**: Specific enough that someone could act on them
- [ ] **Balanced**: Opportunities alongside threats (not doom-and-gloom)
- [ ] **Stands alone**: An exec could read this without the underlying research and understand the landscape

## Common Failure Modes to Avoid

- **Vague threats**: "AI is changing everything" → Be specific about what, when, how
- **Missing "so what"**: Don't just describe competitors, explain why leadership should care
- **No timeline**: When does this matter? Next quarter? Next year? 3 years?
- **Unactionable**: "Monitor the space" → Instead: "Assign 1 PM to evaluate MCP integration by Q2"
- **Over-long**: Execs won't read 5000 words. Ruthlessly prioritize.

## When Done

- Update `_ContinuationKit.md` to show P5 complete
- Verify all wikilinks resolve
- Note any sections that need Matt's input/validation
