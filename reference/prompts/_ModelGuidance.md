# Model Selection & Prompt Robustness Guide

## Which Model for Which Task

| Task                          | Recommended | Acceptable            | Not Recommended |
| ----------------------------- | ----------- | --------------------- | --------------- |
| 00: Single competitor profile | Sonnet      | Haiku (one at a time) | —               |
| 01: Persist P1 research       | Sonnet      | Haiku (one at a time) | —               |
| 02: Capabilities depth        | Sonnet      | Haiku (one at a time) | —               |
| 03: Sentiment evidence        | Sonnet      | Haiku (one at a time) | —               |
| 04: Implications synthesis    | **Opus**    | Sonnet                | Haiku           |
| 05: Exec deliverable          | **Opus**    | Sonnet                | Haiku           |

## If Using Haiku

Add these constraints to any prompt:

### 1. Smaller Batches
Instead of "do all high-threat competitors," specify:
```
Process these 3 competitors in this session:
1. GitHub Copilot
2. Cursor
3. Claude Code

Stop after these 3 and report progress.
```

### 2. Explicit Rating Criteria
Haiku benefits from explicit rubrics. Add:

```
RATING RUBRICS (see _Schema.md for canonical definitions):

Capability Ratings (★):
- ★★★★★: Best-in-class, market-defining
- ★★★★☆: Strong, competitive with leaders
- ★★★☆☆: Adequate, meets expectations
- ★★☆☆☆: Limited, notable gaps
- ★☆☆☆☆: Minimal, early stage

Autonomy Levels:
- L1: Tab autocomplete only (Tabnine basic, Copilot suggestions)
- L2: Generates function/file on explicit request (ChatGPT, Copilot chat)
- L3: Multi-step with plan approval (Cursor Agent, Copilot Workspace)
- L4: Goal-directed with minimal intervention (Devin, Codex)
- L5: Fully autonomous (Factory, hypothetical)

Threat Levels:
- High: Direct competitor, >$50M funding, >100k users
- Medium: Partial overlap OR emerging traction, $10-50M funding
- Low: Minimal overlap, niche, <$10M funding
- Watch: Not a threat today but trajectory matters

Sentiment:
- 🟢 Positive: >70% positive, enthusiastic ("love", "game-changer")
- 🟡 Mixed: Split opinions, notable praise AND criticism
- 🔴 Negative: Majority negative, trust issues, churn signals
```

### 3. Explicit Output Checkpoints
Add verification steps:
```
After completing each competitor profile:
1. Verify all sections are filled (Overview, Capabilities, Agentic, Developer Love, Demo, Pricing, Head-to-Head)
2. Verify ratings are applied (not left blank or TBD)
3. Verify at least 2 quotes in Developer Love section
4. Verify Head-to-Head table has content in all cells
5. If any section is incomplete, search again before moving to next competitor
```

### 4. Fallback Instructions
```
If you cannot find information for a field:
- Mark it as "🔍 Not found - needs manual research"
- Do NOT leave blank or make up information
- Do NOT skip the competitor - complete what you can
```

### 5. Session State Tracking
```
At the END of your response, always include:

## Session State
- Competitors completed this session: [list]
- Competitors remaining: [list]
- Files created: [list with paths]
- Blockers/issues: [any problems encountered]
- Recommended next prompt: [which prompt file to use next]
```

## If Using Sonnet

Sonnet should handle the prompts as written. Optional additions for better results:

### Encourage Depth
```
For each competitor, aim for:
- Overview: 3-5 sentences minimum
- At least 3 capability ratings with notes
- At least 2 developer quotes with sources
- Specific, non-generic Head-to-Head comparisons
```

### Encourage Critical Thinking
```
Don't just report features - analyze:
- Why is this a threat to Atlassian specifically?
- What would make a developer choose this over Jira/Bitbucket/Confluence?
- What's the trajectory - growing threat or plateauing?
```

## If Using Opus

Opus can handle more ambiguity and larger scope. You can:
- Combine multiple prompts into one session
- Ask for strategic insights beyond the template
- Request novel frameworks or perspectives
- Give broader scope (e.g., "all code generation competitors" vs batching)

### Opus-Specific Additions
```
Beyond filling the template, provide:
- Non-obvious insights (what's everyone missing?)
- Contrarian takes (where is conventional wisdom wrong?)
- Second-order effects (if X wins, what else changes?)
- Atlassian-specific strategic options (build vs buy vs partner)
```

## Common Failure Modes to Watch For

### All Models
- **Recency bias**: Older but relevant competitors get less detail
- **Hype bias**: Well-marketed tools get inflated ratings
- **Search failure**: If a search returns nothing useful, model may hallucinate

### Haiku Specifically
- **Shallow profiles**: Just surface-level info, no depth
- **Missing fields**: Skips sections it finds hard
- **Generic comparisons**: "Both are good tools" instead of specific trade-offs
- **Lost context**: Forgets project context mid-task

### Sonnet Specifically
- **Over-qualification**: Too many caveats, hedging
- **Balanced to a fault**: Reluctant to call clear threats/winners

## Recovery Prompts

If a session produces poor output:

### For Incomplete Profiles
```
The profile for [Competitor] is incomplete. Please:
1. Read the existing profile at /Competitors/CompetitiveLandscape-2025/Competitors/[Name].md
2. Identify missing or "🔍 Not found" sections
3. Run targeted searches to fill gaps
4. Update the file with findings
```

### For Low-Quality Ratings
```
Review the profile for [Competitor]. The ratings seem [generic/inflated/unclear].

Recalibrate using these anchors:
- GitHub Copilot = ★★★★☆ for AI/Agentic (market leader baseline)
- Linear = ★★★★★ for Developer Love (cult favorite)
- Jira = ★★★★★ for Enterprise Ready (market leader)

Adjust ratings with specific reasoning for each.
```

### For Missing Strategic Insight
```
The profile for [Competitor] lacks strategic depth. Add:
1. Specific Atlassian vulnerability (which product, which use case)
2. Timeline of threat (immediate / 6-12 months / 2+ years)
3. Recommended Atlassian response (ignore / monitor / respond / acquire)
```
