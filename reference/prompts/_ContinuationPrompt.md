# ContinuationKit: Competitive Landscape Research

> **Purpose**: Prompts and schemas to resume research if rate-limited or context-compacted.
> **Last Updated**: 2026-01-24
> **Current State**: P1 Deep Research COMPLETE. Ready for note persistence + P2.

---

## How to Use This Kit

**Vault absolute path**: `/Users/mattpacione/MattPacione_Local/Competitors/CompetitiveLandscape-2025/`

### Option 1: Obsidian MCP Tools (preferred)

**Skill**: If `obsidian-context` skill is available, invoke it first — it has detailed guidance on Obsidian MCP tool usage, Dataview queries, and vault patterns.

**MCP tools available**:

| Tool | Purpose |
|------|---------|
| `mcp__obsidian-mcp-tools__get_vault_file` | Read a file |
| `mcp__obsidian-mcp-tools__create_vault_file` | Create or overwrite a file |
| `mcp__obsidian-mcp-tools__append_to_vault_file` | Append to existing file |
| `mcp__obsidian-mcp-tools__list_vault_files` | List directory contents |
| `mcp__obsidian-mcp-tools__search_vault_simple` | Keyword search |
| `mcp__obsidian-mcp-tools__search_vault_smart` | Semantic search (Smart Connections) |
| `mcp__obsidian-mcp-tools__search_vault` | Dataview queries (`queryType: "dataview"`) — TABLE only, LIST/TASK fail |

**Path format for MCP tools**: Use vault-relative paths starting from root (not filesystem paths).
- To read this file: `filename: "Competitors/CompetitiveLandscape-2025/_ContinuationKit.md"`
- To create a competitor note: `filename: "Competitors/CompetitiveLandscape-2025/Competitors/Cursor.md"`

### Option 2: Cowork

Select `MattPacione_Local` folder. Navigate to `Competitors/CompetitiveLandscape-2025/`.

### Option 3: Claude Code

```bash
cd /Users/mattpacione/MattPacione_Local/Competitors/CompetitiveLandscape-2025
```

### Option 4: Claude.ai chat (no file access)

Upload `_ContinuationKit.md`, `_SearchSpace.md`, and the relevant prompt from `_Prompts/`.

---

All paths in this document are **relative to the vault folder** (e.g., `Competitors/GitHub Copilot.md` means `Competitors/CompetitiveLandscape-2025/Competitors/GitHub Copilot.md` in MCP tool calls).

---

## Current Progress

| Pass | Status     | Description                                                               |
| ---- | ---------- | ------------------------------------------------------------------------- |
| P0   | ✅ Complete | Discovery - 296 competitors identified across 8 categories                |
| P1   | ✅ Complete | Deep research gathered for all categories (in context, not yet persisted) |
| P2   | ✅ Complete | Capabilities depth                                                        |
| P3   | 🔲 Pending | Sentiment & evidence                                                      |
| P4   | 🔲 Pending | Implications & synthesis                                                  |
| P5   | 🔲 Pending | Exec deliverable                                                          |

**Immediate Next Step**: Persist P1 research to individual competitor notes in `Competitors/` subfolder.

---

## Project Context (paste at conversation start)

```
PROJECT CONTEXT: Atlassian Competitive Landscape Research

Owner: Matt Pacione (Principal UX Designer)
Sponsor: Emily Henlein (VP)
Deliverable: 15-30 min exec briefing on competitive landscape

ATLASSIAN PRODUCTS IN SCOPE:
- Bitbucket → Code Review, CI/CD
- Compass → DX Platform
- Rovo Dev → Code Generation, Task Breakdown
- Jira → Spec & Planning, Task Breakdown
- Confluence → Documentation

SDLC CATEGORIES:
1. Spec & Planning
2. Task Breakdown
3. Code Generation
4. Code Review
5. CI/CD
6. Documentation
7. DX Platform
8. Security

VAULT STRUCTURE:
/Competitors/CompetitiveLandscape-2025/
├── _SearchSpace.md (296 competitors, complete)
├── _MOC.md (Map of Content)
├── _Glossary.md (exec terms)
├── _ContinuationKit.md (this file)
├── Competitors/ (individual profiles go here)
├── Signals/ (raw evidence)
└── Themes/ (synthesized patterns)

AUTONOMY SCALE (see _Schema.md for full definitions):
- L1: Suggestion/Tab — Copilot autocomplete, Tabnine basic
- L2: Bounded task — ChatGPT, Copilot chat, Copilot Edits
- L3: Multi-step with approval — Cursor Agent, Copilot Workspace
- L4: Goal-directed — Devin, Codex
- L5: Fully autonomous — Factory, hypothetical future agents
```

---

## Competitor Note Schema

**See `_Prompts/_Schema.md` for the complete canonical schema.**

```yaml
---
type: competitor
name: "{{Name}}"
domain: [Code Generation | Code Review | CI/CD | Documentation | DX Platform | Task Breakdown | Security | Spec & Planning]
tier: [Established | Emerging | Experimental]
threat_level: [High | Medium | Low | Watch]
atlassian_overlap: [Bitbucket | Compass | Rovo Dev | Jira | Confluence]
last_updated: {{date}}
research_status: [scaffold | p1-complete | p2-complete | p3-complete | verified | skipped]
---
```

### Note Template (Markdown body)

```markdown
# {{Name}}

## Overview
> One paragraph: what it is, who it's for, why it matters.

## Capabilities
| Capability | Rating | Notes |
|------------|--------|-------|
| Core Function | ★★★★☆ | |
| AI/Agentic | ★★★☆☆ | |
| Integration | ★★★★☆ | |
| Enterprise Ready | ★★☆☆☆ | |

## Agentic Capabilities
**Autonomy Level**: L3 (Multi-step/plan approval)

| Capability | Status | Notes |
|------------|--------|-------|
| Code generation | ✅ | |
| Multi-file edits | ✅ | |
| Tool use/MCP | ✅ | |
| Self-correction | ⚠️ | Partial |
| Autonomous execution | ❌ | |

## Developer Love
> Evidence of adoption, sentiment, community traction.

**Quotes**:
- "Quote from HN/Reddit/Twitter" — Source
- "Another quote" — Source

**Signals**:
- GitHub stars: X
- Discord/Slack members: X
- Notable adopters: Company A, Company B

## Demo & Trial
| Type | Available | Link |
|------|-----------|------|
| Free tier | ✅ | |
| Trial | ✅ | 14 days |
| Demo video | ✅ | |
| Sandbox | ❌ | |

## Company & Pricing
- **Founded**: Year
- **Funding**: $XM Series X (Investor A, Investor B)
- **Team size**: ~X
- **Pricing**: Free / $X per seat / Enterprise

## Head-to-Head vs Atlassian
| Dimension | {{Name}} | Atlassian |
|-----------|----------|-----------|
| Core strength | | |
| AI/Agentic | | |
| Integration | | |
| Pricing | | |

**Key Differentiator**: One sentence.
**Atlassian Vulnerability**: One sentence.
```

---

## Research Prompts by Phase

### P1: Persist Research to Notes

```
TASK: Create competitor profile notes from P1 research.

Read _SearchSpace.md to get the competitor list.
For each HIGH-THREAT competitor in these categories, create a note at:
/Competitors/CompetitiveLandscape-2025/Competitors/{Name}.md

Use the schema in _ContinuationKit.md.

PRIORITY ORDER:
1. Code Generation (high-threat): GitHub Copilot, Cursor, Claude Code, Codex, Gemini Code Assist, Windsurf, Devin, Lovable
2. Task Breakdown (high-threat): Linear, Codex, Copilot Coding Agent
3. DX Platform (high-threat): Backstage, Linear, MCP Protocol
4. Security (high-threat): Wiz, Snyk, GitHub Advanced Security
5. Code Review: GitHub, GitLab, Graphite, CodeRabbit
6. CI/CD: GitHub Actions, GitLab CI
7. Documentation: Notion, Mintlify

Research each by searching for:
- "{name} features capabilities 2025"
- "{name} vs {atlassian product}"
- "{name} developer reviews hacker news"
- "{name} pricing enterprise"
```

### P2: Capabilities Depth

```
TASK: Enrich competitor profiles with capability depth.

For each competitor note in /Competitors/CompetitiveLandscape-2025/Competitors/:

1. Search for detailed feature lists and capabilities
2. Find integration documentation (especially MCP support)
3. Look for enterprise features (SSO, audit logs, compliance)
4. Document API/extensibility options

Update the Capabilities table with specific evidence.
Add a new section "## Integration Ecosystem" listing:
- Native integrations
- MCP support (yes/no/planned)
- API quality (REST/GraphQL/SDK)
- Marketplace/plugin ecosystem
```

### P3: Sentiment & Evidence

```
TASK: Gather sentiment and traction evidence.

For each competitor profile:

1. Search Hacker News: "site:news.ycombinator.com {name}"
2. Search Reddit: "site:reddit.com {name} review"
3. Search Twitter/X: "{name} developer experience"
4. Check G2/Capterra ratings
5. Find case studies or notable customers

Update "Developer Love" section with:
- Direct quotes (attributed)
- Quantitative signals (stars, ratings, community size)
- Notable enterprise customers
- Any negative sentiment or concerns
```

### P4: Implications & Synthesis

```
TASK: Synthesize strategic implications.

1. Create /Competitors/CompetitiveLandscape-2025/Themes/ notes for:
   - _AgenticShift.md (L1→L5 transition, issue tracker disruption)
   - _MCPEcosystem.md (protocol wars, integration standards)
   - _DeveloperLoveTrends.md (what's winning hearts)
   - _ConsolidationPatterns.md (platform plays, acquisitions)
   - _PricingPressure.md (free tiers, usage-based, enterprise)

2. For each theme, synthesize across competitors:
   - Key pattern
   - Evidence (link to competitor notes)
   - Atlassian implication
   - Recommended response

3. Update _SearchSpace.md with "Cross-Cutting Trends" section.
```

### P5: Exec Deliverable

```
TASK: Create executive briefing document.

Create /Competitors/CompetitiveLandscape-2025/_ExecBrief.md with:

## Executive Summary (1 page)
- Market is shifting from tools to agents
- 3 existential threats
- 3 strategic opportunities
- Recommended actions

## Landscape Overview (2-3 pages)
- Category-by-category summary
- Threat heatmap (visual)
- Key players to watch

## Deep Dives (1 page each)
- Top 5 threats with full profiles
- Head-to-head comparisons

## Strategic Implications
- What this means for each Atlassian product
- Where to invest vs. partner vs. watch

## Appendix
- Full competitor list (link to _SearchSpace.md)
- Methodology
- Glossary (link to _Glossary.md)
```

---

## Quick Search Queries

### By Category
```
Code Generation: "AI code assistant 2025" OR "copilot alternative" OR "AI coding tool"
Code Review: "AI code review" OR "PR automation" OR "code quality AI"
CI/CD: "AI CI/CD" OR "intelligent deployment" OR "DevOps automation AI"
Documentation: "AI documentation" OR "docs as code" OR "developer docs platform"
DX Platform: "developer experience platform" OR "internal developer portal" OR "platform engineering"
Task Breakdown: "AI project management" OR "issue breakdown AI" OR "Linear vs Jira"
Security: "AI security scanning" OR "DevSecOps AI" OR "code security platform"
```

### By Source
```
VC Maps: "{firm} developer tools market map 2025"
HN: "site:news.ycombinator.com Show HN {category}"
Reddit: "site:reddit.com/r/programming {tool} review"
G2: "site:g2.com {category} software"
Product Hunt: "site:producthunt.com {category} AI"
GitHub: "site:github.com awesome-{category}"
```

### By Competitor Type
```
Big Tech: "{Google|Microsoft|Amazon|Apple|Meta} developer tools AI 2025"
Startups: "YC {category} startup 2024 2025"
Enterprise: "Gartner {category} magic quadrant 2025"
International: "{category} tool China|India|Israel startup"
```

---

## Key Competitors Quick Reference

### Must-Profile (Existential Threats)
| Name | Category | Why |
|------|----------|-----|
| GitHub Copilot | Code Gen | Market leader, Copilot Coding Agent |
| Cursor | Code Gen | Fastest growing, developer love |
| Claude Code | Code Gen | L4 autonomy, MCP native |
| Codex | Code Gen + Task | Autonomous agent, Jira threat |
| Linear | Task + DX | "Jira 2.0", 2x speed claim |
| Backstage | DX Platform | Compass competitor, huge adoption |
| MCP Protocol | DX Platform | Universal standard, Atlassian must support |

### High Priority
| Name | Category | Why |
|------|----------|-----|
| Devin | Code Gen | First AI engineer, L4-L5 |
| Windsurf | Code Gen | Agentic-first IDE |
| Wiz | Security | Cloud security leader |
| Snyk | Security | Developer-first security |
| Notion | Docs | Confluence competitor |
| Mintlify | Docs | AI-native docs |

---

## Resumption Checklist

When resuming after rate limit:

1. [ ] Read this file (`_ContinuationKit.md`)
2. [ ] Read `_SearchSpace.md` for competitor list
3. [ ] Check `/Competitors/` folder for existing notes
4. [ ] Identify what's already done vs. pending
5. [ ] Continue from current phase prompt above
6. [ ] Update "Current Progress" table when phase completes

---

## Notes for Future Sessions

- **MCP Protocol is critical**: Anthropic created it, OpenAI/Google/Microsoft adopted it. Universal agent-tool standard. Atlassian MUST support this.
- **Agentic shift is existential**: Codex and Copilot Coding Agent can execute Jira issues autonomously. If agents read issues directly, Jira UI becomes optional.
- **Linear is the "Jira killer"**: Strong developer love, 2x speed claims, modern UX. Direct threat.
- **Big Tech plays**: Google (Gemini Code Assist, IDX), Microsoft (Copilot ecosystem), Amazon (CodeWhisperer, Q). All investing heavily.
- **International markets**: China (Gitee, Alibaba Cloud), India (Postman, Hasura), Israel (Qodo, Lightrun) have strong players.
