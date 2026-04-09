# Prompt: P1 Research Pass

> **Prerequisite**: Run `00_ScaffoldCompetitors.md` first to create empty files.
> **CRITICAL**: Read `_Prompts/_FormatStandards.md` first for exact formatting rules.
> Copy this entire prompt into a new Claude session to continue.

---

## Context

I'm building a competitive landscape analysis for Atlassian's developer tools. Scaffold files exist for all competitors in `Competitors/CompetitiveLandscape-2025/Competitors/`. Now I need to fill in P1 content.

**Vault location**: `/Users/mattpacione/MattPacione_Local/Competitors/CompetitiveLandscape-2025/`

**My Atlassian products**: Bitbucket, Compass, Rovo Dev, Jira, Confluence

---

## File Access

Use Obsidian MCP tools with vault-relative paths:
```
mcp__obsidian-mcp-tools__get_vault_file(filename: "Competitors/CompetitiveLandscape-2025/Competitors/Cursor.md")
mcp__obsidian-mcp-tools__create_vault_file(filename: "...", content: "...")
```

---

## Your Task

1. **List scaffold files**: `mcp__obsidian-mcp-tools__list_vault_files(directory: "Competitors/CompetitiveLandscape-2025/Competitors")`

2. **For each competitor with `research_status: scaffold`**:
   - Read the existing scaffold
   - Research the competitor (see queries below)
   - Fill in P1 sections: **Overview**, **Agentic Capabilities**, **Autonomy Level**
   - Add sources to the **Sources** section
   - Update `research_status: p1-complete` and `last_updated`

3. **Work in batches** — if rate limited, report progress

---

## P1 Sections to Fill

### Overview
3-5 sentences covering:
- What it is (product category, core function)
- Who it's for (target user, company size)
- Why it matters to Atlassian (competitive threat angle)

### Agentic Capabilities
- Assign **Autonomy Level** (L1-L5)
- Fill the capabilities table with ✅/⚠️/❌ status

### Sources
**CRITICAL**: Document every source used. Format:

```markdown
## Sources

### Research Queries Used
- "Cursor AI features 2025" — Google — 2026-01-24
- "site:news.ycombinator.com Cursor" — HN — 2026-01-24

### Primary Sources
- [Cursor Docs](https://docs.cursor.com) — accessed 2026-01-24, used for: Overview, Agentic Capabilities
```

---

## Research Queries Per Competitor

Run these searches and document them in Sources:
1. `"{name} features capabilities 2025"` — for Overview
2. `"{name} AI agent autonomous"` — for Agentic Capabilities
3. `"{name} MCP model context protocol"` — for tool integration
4. `"site:{official-site} docs"` — for official capabilities

---

## Priority Order

### Batch 1: Code Generation
1. GitHub Copilot
2. Cursor
3. Claude Code
4. Codex (OpenAI)

### Batch 2: Code Generation continued
5. Gemini Code Assist
6. Windsurf (Codeium)
7. Devin (Cognition)
8. Lovable

### Batch 3: Task Breakdown & DX
9. Linear
10. Backstage
11. MCP Protocol

### Batch 4: Security
12. Wiz
13. Snyk
14. GitHub Advanced Security

### Batch 5: Code Review & CI/CD
15. GitHub
16. GitLab
17. Graphite
18. CodeRabbit

### Batch 6: Documentation
19. Notion
20. Mintlify
21. GitBook

---

## Rating Rubrics

**Autonomy Levels**:
- L1: ONLY autocomplete/tab suggestions (Copilot basic, Tabnine)
- L2: Can generate a function or file when explicitly asked (Copilot chat)
- L3: Can plan multi-step changes, shows plan, waits for approval (Cursor Agent)
- L4: Given a goal, works toward it with minimal intervention (Devin, Codex)
- L5: Fully autonomous, assigned tasks, completes them without oversight (Factory)

**Agentic Capability Status**:
- ✅ = Fully supported
- ⚠️ = Partial/beta/limited
- ❌ = Not supported

---

## Quality Checklist (per competitor)

**Content:**
- [ ] Overview is 3-5 sentences, specific to this competitor
- [ ] Autonomy Level assigned with justification (L1-L5 with parenthetical)
- [ ] Agentic table has status for all 5 capabilities
- [ ] At least 2 sources documented
- [ ] `research_status` updated to `p1-complete`
- [ ] `last_updated` set to today's date

**Formatting (see `_FormatStandards.md`):**
- [ ] Agentic Capabilities table uses ✅/⚠️/❌ (NOT stars)
- [ ] Capabilities table uses ★ stars (NOT checkmarks) — fill in P2
- [ ] No blank cells — use `🔍 Needs research` if unknown
- [ ] Sources have access dates and "used for" annotations

---

## Session State (include at END of response)

```
## Session State
- Competitors completed: [list]
- Competitors remaining: [list]
- Files updated: [paths]
- Sources added: [count]
- Blockers: [any issues]
- Next: Continue with Batch X
```

---

## When P1 Complete

Update `_ContinuationKit.md` progress table.
Then run `02_CapabilitiesDepth.md` for P2.
