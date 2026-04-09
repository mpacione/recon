# Prompt: P2 Capabilities Depth Research

> **CRITICAL**: Read `_Prompts/_FormatStandards.md` first for exact formatting rules.
> Copy this entire prompt into a new Claude session to continue.

---

## Context

I'm building a competitive landscape analysis for Atlassian's developer tools. P1 research is complete. Now I need to enrich each profile with deeper capability analysis.

**Vault location**: `/Users/mattpacione/MattPacione_Local/Competitors/CompetitiveLandscape-2025/`

Use Obsidian MCP tools with vault-relative paths.

---

## Your Task

1. Read `_Prompts/_FormatStandards.md` for exact formatting rules
2. Read `_ContinuationKit.md` for project context
3. List notes in `Competitors/CompetitiveLandscape-2025/Competitors/`
4. For each competitor with `research_status: p1-complete`, enrich with P2 content

---

## P2 Sections to Fill

### 1. Capabilities Table (REQUIRED FORMAT)

**Use ★ star ratings, NOT checkmarks:**

```markdown
## Capabilities

| Capability | Rating | Notes |
|------------|--------|-------|
| Core Function | ★★★★★ | [specific evidence with sources] |
| AI/Agentic | ★★★★☆ | [specific evidence] |
| Integration | ★★★☆☆ | [specific evidence] |
| Enterprise Ready | ★★☆☆☆ | [specific evidence] |
```

**Rating criteria:**
- ★★★★★ = Best-in-class, market leader
- ★★★★☆ = Strong, competitive with leaders
- ★★★☆☆ = Adequate, meets expectations
- ★★☆☆☆ = Limited, notable gaps
- ★☆☆☆☆ = Minimal, early stage

### 2. Integration Ecosystem (Table Format)

```markdown
## Integration Ecosystem

| Integration Type | Status | Details |
|------------------|--------|---------|
| GitHub | ✅ Native | Full PR integration, issue sync |
| GitLab | ⚠️ Limited | Basic via API only |
| VS Code | ✅ Extension | Official marketplace extension |
| JetBrains | ✅ Plugin | IntelliJ, PyCharm, WebStorm |
| MCP Protocol | ✅ Supported | Tools + Resources, announced Jan 2025 |
| Self-Hosted | ❌ | Cloud only |
| API/SDK | ✅ Available | REST, TypeScript SDK |
```

### 3. Enterprise Readiness (Table Format)

```markdown
## Enterprise Readiness

| Feature | Status | Details |
|---------|--------|---------|
| SSO/SAML | ✅ | Okta, Entra ID, custom OIDC |
| SCIM | ✅ | Auto user provisioning |
| Audit Logs | ⚠️ | 90-day retention; no prompt logging |
| Data Residency | ❌ | US only; EU planned Q2 2026 |
| SOC 2 Type II | ✅ | Report at trust.example.com |
| HIPAA | ⚠️ | BAA available on request |
```

### 4. AI Architecture (For AI tools)

```markdown
## AI Architecture

| Component | Details |
|-----------|---------|
| **Models** | GPT-4o, Claude 3.5 Sonnet (configurable) |
| **Context Window** | 128k tokens; full repo indexing |
| **Indexing** | AST-based chunking, vector embeddings |
| **Privacy** | Enterprise: no training on data; SOC2 |
| **Self-Correction** | Iterates on errors, validates output |
```

---

## Research Queries Per Competitor

```
"{name} integrations list 2025"
"{name} MCP model context protocol support"
"{name} enterprise features SSO SAML"
"{name} API documentation SDK"
"{name} SOC2 compliance security certifications"
"{name} data residency GDPR"
"{name} context window tokens codebase indexing"
```

---

## Priority Order

### Batch 1: Code Generation (highest threat)
1. GitHub Copilot
2. Cursor
3. Claude Code
4. Codex (OpenAI)

### Batch 2: Code Generation continued
5. Gemini Code Assist
6. Windsurf (Codeium)
7. Devin (Cognition)

### Batch 3: Task Breakdown & DX
8. Linear
9. Backstage

### Batch 4: Security
10. Wiz
11. Snyk

### Batch 5: Remaining high-priority
(Continue with Code Review, CI/CD, Documentation competitors)

---

## Quality Checklist (per competitor)

**Content:**
- [ ] Capabilities table filled with ★ ratings (all 4 rows)
- [ ] Integration Ecosystem table complete
- [ ] Enterprise Readiness table complete
- [ ] AI Architecture table (if AI tool)
- [ ] Sources updated with P2 queries and links
- [ ] `research_status` updated to `p2-complete`

**Formatting (from `_FormatStandards.md`):**
- [ ] Capabilities uses ★★★★★ stars (NOT ✅ checkmarks)
- [ ] Integration/Enterprise tables use ✅/⚠️/❌ status
- [ ] No blank cells — use `🔍 Needs research` if unknown
- [ ] Notes column has specific evidence, not generic text

---

## Session State (include at END)

```
## Session State
- Competitors completed: [list]
- Competitors remaining: [list]
- Files updated: [paths]
- Format issues fixed: [any corrections]
- Next: Continue with Batch X
```

---

## When P2 Complete

Update `_ContinuationKit.md` progress table.
Then run `03_SentimentEvidence.md` for P3.
