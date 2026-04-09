# Prompt: Format Cleanup Pass

> **Purpose**: Standardize existing competitor profiles to match `_FormatStandards.md`.
> Run this after P1/P2 to fix inconsistencies before P3.

---

## Context

Some competitor profiles were created before format standards were finalized. This pass fixes inconsistencies to ensure all profiles are uniform for downstream analysis.

**Vault location**: `/Users/mattpacione/MattPacione_Local/Competitors/CompetitiveLandscape-2025/`

Use Obsidian MCP tools with vault-relative paths.

---

## Your Task

1. **Read `_Prompts/_FormatStandards.md`** — memorize the exact formats
2. **List all profiles**: `mcp__obsidian-mcp-tools__list_vault_files(directory: "Competitors/CompetitiveLandscape-2025/Competitors")`
3. **For each profile**, check and fix format issues
4. **Report** what was fixed

---

## Format Issues to Fix

### Issue 1: Capabilities Table Using Checkmarks Instead of Stars

**Wrong:**
```markdown
| Capability | Rating | Notes |
|------------|--------|-------|
| Core Function | ✅ | Issue tracking with speed |
| AI/Agentic | ⚠️ | Agent support released 2025 |
```

**Correct:**
```markdown
| Capability | Rating | Notes |
|------------|--------|-------|
| Core Function | ★★★★★ | Issue tracking with exceptional speed (<50ms); clean UX |
| AI/Agentic | ★★★☆☆ | Agent support released 2025; L2 autonomy; limited scope |
```

**Conversion guide:**
- `✅` → `★★★★★` or `★★★★☆` (evaluate based on Notes)
- `⚠️` → `★★★☆☆` or `★★☆☆☆` (partial = adequate or limited)
- `❌` → `★☆☆☆☆` (minimal)

### Issue 2: Missing Star Ratings (Blank or Generic)

**Wrong:**
```markdown
| Core Function | | Good issue tracking |
| AI/Agentic | Strong | Has AI features |
```

**Correct:**
```markdown
| Core Function | ★★★★☆ | Issue tracking with clean UX; lacks advanced views |
| AI/Agentic | ★★★★☆ | L3 autonomy with Cursor integration; triage automation |
```

### Issue 3: Agentic Capabilities Using Stars Instead of Status

**Wrong:**
```markdown
| Capability | Status | Notes |
|------------|--------|-------|
| Code generation | ★★★★☆ | Via Cursor integration |
```

**Correct:**
```markdown
| Capability | Status | Notes |
|------------|--------|-------|
| Code generation | ⚠️ | Via Cursor integration; not native |
```

### Issue 4: Integration Ecosystem as Bullets Instead of Table

**Wrong:**
```markdown
## Integration Ecosystem

**Developer Tools**:
- GitHub (bidirectional PR/issue sync)
- GitLab (similar to GitHub)
- Cursor IDE (agents fix issues)

**Communication**:
- Slack (create issues, notifications)
```

**Correct:**
```markdown
## Integration Ecosystem

| Integration Type | Status | Details |
|------------------|--------|---------|
| GitHub | ✅ Native | Bidirectional PR/issue sync, auto-status on merge |
| GitLab | ✅ Native | Similar to GitHub integration |
| Cursor IDE | ✅ Native | Agents fix issues from tickets |
| Slack | ✅ Native | Create issues via @Linear, thread sync, notifications |
| MCP Protocol | 🔍 Needs research | |
| Self-Hosted | ❌ | Cloud only |
| API/SDK | ✅ Available | REST + GraphQL APIs |
```

### Issue 5: Missing Sentiment Emoji

**Wrong:**
```markdown
**Sentiment**: Extremely Positive
```

**Correct:**
```markdown
**Sentiment**: 🟢 Positive
```

### Issue 6: Traction Signals as Bullets Instead of Table

**Wrong:**
```markdown
### Traction Signals

- **$1.25B valuation** (June 2025 Series C)
- **$100M revenue** (June 2025)
- **178 employees** (2025)
```

**Correct:**
```markdown
### Traction Signals

| Metric | Value | Source |
|--------|-------|--------|
| Valuation | $1.25B | TechCrunch, Jun 2025 |
| Revenue | $100M ARR | Getlatka, Jun 2025 |
| Employees | 178 | Company data, 2025 |
```

### Issue 7: Head-to-Head Using Text Instead of Stars

**Wrong:**
```markdown
| Dimension | Linear | Atlassian (Jira) |
|-----------|--------|-----------|
| Core strength | Speed, developer UX | Customization, enterprise |
| AI/Agentic | L2 agents; triage | Rovo AI search |
```

**Correct:**
```markdown
| Dimension | Linear | Atlassian (Jira) |
|-----------|--------|-----------|
| Core strength | ★★★★★ Speed (<50ms), developer UX | ★★★★☆ Customization, enterprise reporting |
| AI/Agentic | ★★★☆☆ L2 agents; triage, Cursor integration | ★★★☆☆ Rovo AI search; limited autonomy |
```

### Issue 8: Blank Cells

**Wrong:**
```markdown
| Data Residency | | |
```

**Correct:**
```markdown
| Data Residency | 🔍 | Needs research |
```

---

## Profiles Likely Needing Fixes

Based on earlier review, these profiles use old formats:

| Profile | Issues |
|---------|--------|
| Linear.md | Capabilities uses ✅; Integration as bullets; Traction as bullets |
| Snyk.md | Capabilities uses ✅; Integration as bullets |
| (Check all others for consistency) |

---

## Process Per Profile

1. **Read the profile**
2. **Check each section against `_FormatStandards.md`**
3. **If issues found:**
   - Fix the formatting
   - Preserve all existing content/data
   - Don't change research findings, just presentation
4. **Update the file**
5. **Add to fix log**

---

## Rating Conversion Guide

When converting ✅/⚠️/❌ to stars in Capabilities table:

| Old | New | Logic |
|-----|-----|-------|
| ✅ with "strong/excellent/best" in notes | ★★★★★ | Best-in-class |
| ✅ with basic notes | ★★★★☆ | Strong |
| ⚠️ with "good/adequate" notes | ★★★☆☆ | Adequate |
| ⚠️ with "limited/early" notes | ★★☆☆☆ | Limited |
| ❌ or minimal mention | ★☆☆☆☆ | Minimal |

**Read the Notes column** to determine appropriate star rating. Don't just mechanically convert.

---

## Session State (include at END)

```
## Session State
- Profiles reviewed: [count]
- Profiles fixed: [list]
- Issues fixed: [count by type]
- Profiles already compliant: [list]
- Next: Run P3 (03_SentimentEvidence.md)
```

---

## Fix Log Template

For each profile, document:

```markdown
### [Competitor Name].md

**Issues found:**
- [ ] Capabilities table: ✅ → ★ conversion
- [ ] Agentic table: format OK / fixed
- [ ] Integration: bullets → table
- [ ] Enterprise: bullets → table
- [ ] Sentiment: added emoji
- [ ] Traction: bullets → table
- [ ] Head-to-Head: text → stars
- [ ] Blank cells: filled with 🔍

**Changes made:**
- Converted Capabilities ratings from checkmarks to stars
- Reformatted Integration Ecosystem as table
- Added 🟢 to Sentiment
- etc.
```
