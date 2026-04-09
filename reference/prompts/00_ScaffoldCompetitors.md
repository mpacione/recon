# Prompt: Scaffold All Competitor Files

> Run this FIRST before any research passes. Creates empty template files for all competitors.

---

## IMPORTANT: File Access

**Vault location**: `/Users/mattpacione/MattPacione_Local/Competitors/CompetitiveLandscape-2025/`

Use Obsidian MCP tools with vault-relative paths:
```
mcp__obsidian-mcp-tools__create_vault_file(
  filename: "Competitors/CompetitiveLandscape-2025/Competitors/{Name}.md",
  content: "..."
)
```

---

## Your Task

1. **Read `_SearchSpace.md`** to get the full competitor list
2. **Read `_Prompts/_CompetitorTemplate.md`** to get the template
3. **Create scaffold files** for all HIGH and MEDIUM threat competitors

---

## Scaffold Template

For each competitor, create a file using this exact structure:

```markdown
---
type: competitor
name: "{Name}"
domain: {from _SearchSpace.md}
tier: {Established|Emerging|Experimental}
threat_level: {High|Medium}
atlassian_overlap: [{relevant products}]
last_updated: 2026-01-24
research_status: scaffold
---

# {Name}

## Overview
<!-- P1: 3-5 sentences - what it is, who it's for, why it matters -->


## Capabilities

| Capability | Rating | Notes |
|------------|--------|-------|
| Core Function | | |
| AI/Agentic | | |
| Integration | | |
| Enterprise Ready | | |

## Agentic Capabilities

**Autonomy Level**:

| Capability | Status | Notes |
|------------|--------|-------|
| Code generation | | |
| Multi-file edits | | |
| Tool use/MCP | | |
| Self-correction | | |
| Autonomous execution | | |

## Developer Love

**Sentiment**:

### Quotes

### Traction Signals

## Demo & Trial

| Type | Available | Link/Notes |
|------|-----------|------------|
| Free tier | | |
| Trial | | |
| Demo video | | |
| Sandbox | | |

## Company & Pricing

- **Founded**:
- **Funding**:
- **Team size**:
- **Pricing**:

## Head-to-Head vs Atlassian

| Dimension | {Name} | Atlassian |
|-----------|--------|-----------|
| Core strength | | |
| AI/Agentic | | |
| Integration | | |
| Pricing | | |

**Key Differentiator**:

**Atlassian Vulnerability**:

## Integration Ecosystem

## Strategic Notes

---

## Sources

### Research Queries Used

### Primary Sources

### Community Sources

### Third-Party Sources

```

---

## Priority List (scaffold these)

**Read `_SearchSpace.md` for the current priority list by category.**

The priority list is maintained in `_SearchSpace.md` to avoid duplication drift. Pull HIGH and MEDIUM threat competitors from there.

### Scaffolding Order

1. All **High** threat competitors across all categories
2. All **Medium** threat competitors across all categories
3. Skip **Low** and **Watch** tier competitors unless explicitly requested

---

## Filling in Frontmatter

Pull this data from `_SearchSpace.md`:

| Field | Source |
|-------|--------|
| `name` | Competitor name |
| `domain` | Category from _SearchSpace |
| `tier` | Established/Emerging/Experimental from _SearchSpace |
| `threat_level` | High/Medium from _SearchSpace |
| `atlassian_overlap` | Infer from category (Code Gen → Rovo Dev, Task → Jira, etc.) |

**Atlassian overlap mapping**:
- Code Generation → `[Rovo Dev]`
- Task Breakdown → `[Jira, Rovo Dev]`
- Code Review → `[Bitbucket]`
- CI/CD → `[Bitbucket]`
- Documentation → `[Confluence]`
- DX Platform → `[Compass]`
- Security → `[Bitbucket]` (or none if not core)
- Spec & Planning → `[Jira, Confluence]`

---

## Output

Create all scaffold files. Then report:

```
## Scaffold Complete
- Files created: [count]
- High threat: [list]
- Medium threat: [list]
- Skipped (low/watch): [count]

Files are ready for P1 research pass.
```

---

## After Scaffolding

Run `_Prompts/01_PersistP1Research.md` to fill in P1 content (Overview, Agentic level).

The scaffold approach means:
- All files exist immediately (visible in Obsidian)
- Agents fill sections progressively
- `research_status` frontmatter tracks progress
- Sources section captures all links
