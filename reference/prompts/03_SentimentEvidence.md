# Prompt: P3 Sentiment & Presentation Enrichment

> **Manual use**: Copy this prompt into a new Claude session.
> **Orchestrator use**: This file is read by `_BatchCleanup/p3_orchestrator.py` for parallel processing.

---

## Context

I'm building a competitive landscape analysis for Atlassian's developer tools. P1 (profiles) and P2 (capabilities) are complete. Now I need:
1. Real developer sentiment and traction evidence
2. Presentation-ready frontmatter for an interactive demo app
3. Talking Points section for executive presentation

**See `_Schema.md`** for canonical field definitions.

---

## Your Task

For each competitor file:

1. **Research sentiment** using web search (HN, Reddit, G2, Twitter)
2. **Enrich Developer Love section** with real quotes and traction data
3. **Add presentation frontmatter** (demo_url, tagline, autonomy_level, etc.)
4. **Add Talking Points section** for exec presentation
5. **Update `research_status`** from `p2-complete` to `p3-complete`
6. **Append new sources** to the Sources section

---

## Research Sources

### Hacker News
```
site:news.ycombinator.com "{competitor name}"
site:news.ycombinator.com "Show HN" "{competitor name}"
```
Look for: launch threads, discussion threads, complaints, praise

### Reddit
```
site:reddit.com/r/programming "{competitor name}"
site:reddit.com/r/ExperiencedDevs "{competitor name}"
site:reddit.com/r/webdev "{competitor name}"
site:reddit.com "{competitor name}" review
```

### Twitter/X
```
"{competitor name}" developer experience
"{competitor name}" worth it
"{competitor name}" switched from
```

### Review Sites
```
site:g2.com "{competitor name}"
site:capterra.com "{competitor name}"
site:trustradius.com "{competitor name}"
```

### GitHub (for open source tools)
- Star count and trajectory
- Issue activity
- Contributor count
- Recent release cadence

### Community Signals
- Discord/Slack member counts
- YouTube tutorial views
- Conference talk mentions
- Newsletter mentions (TLDR, Bytes, etc.)

---

## What to Add/Update

### 1. Presentation Frontmatter (NEW)

Add these fields to the YAML frontmatter:

```yaml
# Presentation fields
demo_url: "https://cursor.com"  # Product homepage or signup
demo_account: "See 1Password > Competitors"  # Optional
logo_url: "https://..."  # Optional, for card display
tagline: "AI-native IDE with codebase context"  # 5-10 words
funding_display: "$400M Series C"  # Human-readable
autonomy_level: L3  # Extract from Agentic Capabilities section
out_of_left_field: false  # true = emerging agentic threat
presentation_priority: 1  # 1=must discuss, 2=if time, 3=reference only
```

**Priority assignment logic:**
- `1` = High threat + well-known + directly competes
- `2` = Medium threat OR high but niche
- `3` = Low/Watch OR context only

### 2. Developer Love Section

Enhance with real data:

```markdown
## Developer Love

**Sentiment**: 🟢 Positive | 🟡 Mixed | 🔴 Negative

**Strengths mentioned**:
- Speed/performance (frequently cited)
- AI quality
- UX polish

**Concerns mentioned**:
- Pricing at scale
- Vendor lock-in
- Privacy concerns

### Quotes

> "Cursor is legitimately the first AI tool that's changed how I code. The tab completion is almost psychic."
> — HN user, Dec 2024 (450 upvotes)

> "Switched from Copilot to Cursor and haven't looked back. The multi-file editing is game-changing."
> — r/programming, Jan 2025

> "My only concern is what happens if they get acquired or shut down."
> — r/ExperiencedDevs, Jan 2025

### Traction Signals

| Metric | Value | Source |
|--------|-------|--------|
| GitHub Stars | 45,000 | GitHub, Jan 2026 |
| G2 Rating | 4.7/5 (234 reviews) | G2.com, Jan 2026 |
| Discord Members | 89,000 | Discord |
| Funding | $400M Series C | TechCrunch, Oct 2025 |

### Notable Customers
- Shopify (engineering blog mention)
- Stripe (job posting reference)
- Vercel (public endorsement)

### Competitive Migration Patterns
- "Switched from Copilot" — common theme
- "Used to use Tabnine" — mentioned occasionally
```

### 3. Talking Points Section (NEW)

Add after Strategic Notes:

```markdown
## Talking Points

### What keeps us up at night
- [Punchy, specific concern—not generic "AI is changing things"]
- [Second concern if applicable]

### Their competitive advantage
- [What they do better than Atlassian—be specific]

### Our competitive advantage
- [Where Atlassian wins—suite integration, enterprise trust, etc.]

### Discussion prompt
- [Question for LT: "Should we...?", "How do we respond to...?"]
```

---

## What to Capture

**Positive signals**:
- Enthusiastic endorsements
- Migration stories (from what?)
- Productivity claims (with specifics)
- Enterprise adoption mentions

**Negative signals**:
- Reliability complaints
- Pricing frustration
- Missing features
- Support quality issues

**Neutral but useful**:
- Comparison discussions
- Use case limitations
- Integration challenges

---

## Priority Order

Process in this order (highest impact first):

**Tier 1** (must have rich sentiment):
1. Cursor
2. Linear
3. GitHub Copilot
4. GitHub (platform)
5. Devin

**Tier 2** (important):
6. Claude Code
7. Codex
8. Backstage
9. Wiz
10. Snyk
11. Notion
12. GitLab

**Tier 3**: All others

---

## What NOT to Do

- Do NOT fabricate quotes—only use real quotes found in research
- Do NOT remove existing content—only enrich
- Do NOT change threat_level or domain
- Do NOT use generic talking points—be specific to this competitor
- Do NOT skip research—each file needs real sentiment data

---

## Orchestrator Output Format

When run via `p3_orchestrator.py`, return:

```xml
<corrected_file>
[Full enriched file content]
</corrected_file>

<report>
{
  "file": "path/to/file.md",
  "status": "enriched" | "already_complete" | "insufficient_data" | "error",
  "sentiment_found": "🟢 Positive" | "🟡 Mixed" | "🔴 Negative",
  "quotes_added": 3,
  "traction_signals_added": ["GitHub Stars", "G2 Rating", "Funding"],
  "talking_points_added": true,
  "presentation_fields_added": ["demo_url", "tagline", "autonomy_level"],
  "sources_added": ["https://... — used for: Developer Love"],
  "error_message": null
}
</report>
```

---

## When Done

1. Update `research_status: p3-complete` in frontmatter
2. Append new sources to `## Sources` section
3. Update `_ContinuationKit.md` progress table
4. Create summary: "Top 3 most-loved" and "Top 3 rising threats by sentiment"
