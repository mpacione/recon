# Research and Verification

> Section-by-section research agents, multi-agent consensus verification protocol, format constraints, and source preferences.

## Research Model

### Section-by-Section Batching

Research is batched by section across all competitors, not by competitor across all sections. The system completes one section for all competitors before moving to the next.

**Example flow for 50 competitors, 8 sections:**
```
Round 1:  Fill "Overview" for all 50 competitors      --> Verify all 50
Round 2:  Fill "Capabilities" for all 50 competitors   --> Verify all 50
Round 3:  Fill "Pricing" for all 50 competitors        --> Verify all 50
...
Round 8:  Fill "Strategic Notes" for all 50 competitors --> Verify all 50
```

**Why this order:**

1. **Consistency** — The research agent develops calibration across the cohort. After seeing 50 pricing pages, it knows what "enterprise pricing" looks like in this space. Ratings are relative to the landscape, not drifting as the agent gains context. Competitor #1 and #50 are rated on the same basis.

2. **Verification benefits** — The verification agent reviewing 50 Pricing sections consecutively can spot outliers: "Every other competitor has a free tier, this one claims they don't — worth double-checking."

3. **Format enforcement** — Producing 50 of the same table format consecutively yields more consistent output than switching between different section formats.

4. **Parallelism** — 10 workers all doing the Pricing section simultaneously, all with the same prompt and constraints. No context switching between section types.

5. **Clean resume** — "Pricing done for 48/50, 2 failed" is cleaner state than "Competitor A has 6/8 sections, Competitor B has 3/8, Competitor C has 7/8."

**Tradeoff:** No single competitor dossier is "complete" until all section rounds have run. The dashboard shows both views: section-level completion and competitor-level completion.

### Worker Agent Architecture

Each section-round dispatches workers through a semaphore-controlled async pool.

**Per-worker flow:**
1. Receive: competitor name, section definition (from schema), worker prompt (auto-generated)
2. Search for information using the section's preferred sources
3. Fill the section according to the format spec
4. List sources at the bottom of the section with URLs and dates
5. Return the completed section

**Worker prompt composition (composable, not monolithic):**
- Base system prompt: global rules, no-emoji policy, rating scale definitions
- Section fragment: format spec, allowed format types, evidence types, search guidance, source preferences, recency threshold
- Example: a concrete correctly-formatted output for this section type
- Context: competitor name, domain description, company context from recon.yaml

Only the relevant section's constraints are in the worker's context. No bloated mega-prompts.

### LLM Interaction Model (Hybrid)

The schema defines which output mode each section uses:

**Structured output (tool use)** for data-heavy sections:
- Capabilities tables (columns, ratings, evidence)
- Status tables (feature checklists)
- Key-value metadata fields
- The engine receives structured JSON and renders it to markdown
- Guarantees format compliance, eliminates parsing

**Markdown output with validation** for prose-heavy sections:
- Overview narratives
- Strategic analysis
- Talking points
- The LLM writes markdown directly, guided by examples and constraints
- Post-write parser validates format, catches drift, triggers retry on failure
- Allows more natural writing

**Extended thinking** is used only for synthesis passes (Phase 5) where reasoning quality matters and cost is already high. Research and enrichment phases skip it — volume matters more than depth.

## Verification Protocol

### Multi-Agent Consensus Model

Every information-gathering step is followed by verification. This applies to:
- Initial research (Phase 2)
- Sentiment enrichment (Phase 4b)
- Strategic enrichment (Phase 4c)

### Three Verification Tiers

The user selects a tier during setup. Shown with cost estimate.

| Tier | Agents | Cost Multiplier | Use Case |
|---|---|---|---|
| Standard | Agent A only (no verification) | 1x | Draft, exploration, low-stakes |
| Verified | Agent A + Agent B consensus | ~2x | Working analysis, internal use |
| Deep Verified | Agent A + Agent B + Agent C | ~3x | Final deliverable, executive presentation |

### Verified Tier Protocol (Agent A + Agent B)

**Step 1: Agent A researches the section** (as described above).

**Step 2: Agent B receives Agent A's output** — the claims and cited sources for the section.

**Step 3: Agent B performs two-step verification:**

**3a. Source checking:**
- For each cited source: does this URL resolve? Does the content at this URL actually support the claim Agent A made?
- This catches hallucinated URLs and misattributed claims
- Lightweight — mostly HTTP checks and targeted content reading

**3b. Independent corroboration:**
- For each confirmed claim: search independently for the same fact from different sources
- For each unconfirmed claim (URL doesn't resolve or doesn't support the claim): do full independent research as if no source existed
- Look for additional evidence beyond what Agent A found

**Step 4: Each source gets a verification status:**

| Status | Meaning | Display |
|---|---|---|
| Confirmed | Agent B independently found the same fact from a different source | Y (confirmed) |
| Corroborated | Same source confirmed + additional supporting evidence found | Y (corroborated) |
| Unverified | Agent B could not independently confirm the claim | ~ (unverified) |
| Disputed | Agent B found contradicting evidence | N (disputed) |

### Deep Verified Tier Protocol (Agent A + Agent B + Agent C)

Adds Agent C after the A+B consensus:

**Where A and B agree:** Agent C searches for additional corroboration or counter-evidence. Strengthens the confidence signal.

**Where A and B disagree:** Agent C acts as tie-breaker. Performs independent research, evaluates both positions, assigns a verdict.

**Where gaps exist:** Agent C looks for information that both A and B missed. Fills holes in coverage.

### Per-Section Source Attribution

Every section in every profile ends with a sources list that includes verification status:

```markdown
### Sources -- Capabilities
- [Cursor Features Page](https://cursor.com/features) -- Y Confirmed (independently verified via G2 feature comparison)
- [GitHub stars: 42k](https://github.com/getcursor/cursor) -- Y Confirmed (corroborated, checked 2026-04-08)
- [Series B: $60M](https://techcrunch.com/...) -- ~ Unverified (article found but amount stated as $65M in another source)
- "Fastest AI code editor" claim -- N Disputed (no independent source supports this ranking)
```

### Verification After Enrichment

When sentiment enrichment adds new quotes and traction data, or strategic enrichment adds metadata fields, those new claims go through the same verification protocol. Only the new/changed content is verified — previously verified content is not re-checked unless the user explicitly requests it.

## Format Constraints

### The Problem

The legacy system had inconsistent output across profiles: different table formats, mixed rating systems (stars vs numbers vs text), some profiles used emoji while others didn't, bullet lists where tables were expected, inconsistent column names. This undermines credibility — the whole point is uniform, comparable data across competitors.

### Solution: Constrained Freedom

Each section defines a set of **allowed format options**. The agent picks the best representation for the data within those options. Nothing outside the allowed set.

### Allowed Format Types

| Type | Description | When to use |
|---|---|---|
| `table` | Standard rows and columns | Structured comparisons |
| `rated_table` | Table with a rating column using a defined scale | Capability scoring |
| `status_table` | Table with status indicators (Y/~/N/?) | Feature checklists |
| `comparison_table` | Side-by-side comparison | Head-to-head sections |
| `key_value` | Label: value pairs, one per line | Metadata, quick facts |
| `prose` | Free text with min/max word count | Narratives, analysis |
| `bullet_list` | Bulleted items with optional sub-bullets | Lists, quotes |
| `numbered_list` | Ordered items | Rankings, steps |

### Per-Section Format Configuration

Each section in the schema defines which formats are allowed and which is preferred:

```yaml
sections:
  capabilities:
    allowed_formats: ["rated_table", "prose"]
    preferred_format: "rated_table"
    format_spec:
      rated_table:
        columns: ["Capability", "Rating", "Evidence"]
        rating_scale: "stars_5"
        min_rows: 6
        evidence_min_words: 20
      prose:
        heading: "Strategic Analysis"
        min_words: 100
        max_words: 300

  developer_love:
    allowed_formats: ["key_value", "bullet_list", "prose"]
    preferred_format: "key_value"
    format_spec:
      key_value:
        fields: ["Overall Sentiment", "GitHub Stars", "Community Size"]
      bullet_list:
        label: "Notable Quotes"
        min_items: 3
        quote_format: "> \"quote\" -- source, date"
      prose:
        heading: "Analysis"
        min_words: 80
        max_words: 200
```

### Global Rating Scales

Defined once in the schema, referenced everywhere by name. Every section that uses ratings references a named scale — never defines its own.

```yaml
rating_scales:
  stars_5:
    description: "5-point capability rating"
    render: ["_____", "*____", "**___", "***__", "****_", "*****"]
    # Actual rendering uses star characters, shown here simplified
    values: [0, 1, 2, 3, 4, 5]
    never_use:
      - emoji stars or sparkles
      - "X out of 5" text
      - numeric scores without stars
      - letter grades

  status:
    description: "Feature availability status"
    render:
      available: "Y"
      partial: "~"
      unavailable: "N"
      unknown: "?"
    never_use:
      - emoji checkmarks or crosses
      - colored circles
      - "Yes" / "No" text
      - thumbs up/down

  threat:
    description: "Competitive threat level"
    values: ["Critical", "High", "Medium", "Low", "Watch"]
    never_use:
      - emoji indicators
      - color names ("red", "green")
      - abbreviated forms ("H", "M", "L")
```

### No Emoji — Global Rule

Emoji are prohibited in all output. This is enforced at three levels:

1. **System prompt:** "Never use emoji characters in any output. Use the exact notation specified in the rating scale definitions."
2. **Rating scale `never_use` lists:** Catch common LLM substitutions per scale
3. **Post-write validation:** Deterministic regex check for any Unicode emoji codepoints. If found, reject and retry with specific failure message.

### Post-Write Validation

After every section is written, a deterministic (non-LLM) parser checks:

1. **Format type:** Is it one of the allowed formats for this section?
2. **Table structure:** Correct column count, correct column names, correct order?
3. **Rating scale:** Are all ratings using the exact defined scale notation?
4. **Word counts:** Does prose meet min/max requirements?
5. **Emoji check:** Regex scan for any Unicode emoji codepoints
6. **Required fields:** Are all required key-value fields present?
7. **Source list:** Does the section end with a sources list?

**On validation failure:**
- Section is rejected
- Agent is re-prompted with the specific failure: "Table is missing the 'Evidence' column. Expected columns: Capability, Rating, Evidence."
- Max 3 retries per section before flagging as failed

### Example-Driven Prompting

Every section's worker prompt includes a concrete correctly-formatted example output. The LLM pattern-matches against the example rather than interpreting abstract rules.

```
### Example output for Capabilities section:

| Capability | Rating | Evidence |
|---|---|---|
| Code completion | ***** | Context-aware completions across 20+ languages with multi-file understanding |
| Code review | ***__ | Basic PR suggestions, limited to single-file scope, no security analysis |
| Debugging | ****_ | Interactive debugger with AI-assisted breakpoint suggestions |

### Strategic Analysis

Cursor has invested heavily in code completion, achieving best-in-class
performance through their custom model fine-tuning pipeline. Their code
review capabilities remain underdeveloped compared to dedicated review
tools, representing a gap they may address as they expand from individual
developer to team workflows.
```

## Source Preferences

### Per-Section Configuration

Each section defines where agents should look for information:

```yaml
preferred_sources:
  primary:
    - "official pricing pages"
    - "product documentation"
  secondary:
    - "G2 reviews"
    - "analyst reports"
  avoid:
    - "reddit speculation"
    - "outdated blog posts > 12 months"
source_recency: "6 months"
```

### How Sources Feed Into Agents

**Research agent (Agent A):**
- Searches primary sources first
- Falls back to secondary sources if primary is insufficient
- Never cites avoided sources
- Checks source date against recency threshold

**Verification agent (Agent B):**
- When checking Agent A's sources: verifies they're from the preferred list or at least not in the avoid list
- When searching independently: uses the same source preferences but may discover sources Agent A missed
- Flags if Agent A cited an avoided source type

### Default Source Preferences by Section Type

The wizard provides sensible defaults that the user can adjust:

| Section Type | Primary | Secondary | Avoid |
|---|---|---|---|
| Overview | Official website, About page, Wikipedia | Crunchbase, LinkedIn, press releases | User-generated wikis |
| Capabilities | Official docs, feature pages, API docs | G2 feature comparisons, technical reviews | Marketing landing pages without specifics |
| Pricing | Official pricing page, documentation | G2 pricing info, TrustRadius | Reddit speculation, outdated blog posts |
| Enterprise | Trust/security pages, compliance docs | Analyst reports, enterprise review sites | Vendor press releases without verification |
| Developer Sentiment | Hacker News, Reddit, dev.to, Stack Overflow | Twitter/X, Discord, GitHub Discussions | Sponsored content, vendor press releases |
| Integration | Official integration directory, API docs | Partner announcements, technical blogs | Marketing claims without API evidence |
| Strategic | Analyst reports, funding announcements, earnings | Industry news, executive interviews | Social media speculation |
