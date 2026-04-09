# Batch Cleanup Orchestrator

Parallel processing system for cleaning up competitor profile formatting.

## Setup

```bash
# Install dependencies
pip install anthropic aiofiles

# Set API key
export ANTHROPIC_API_KEY="your-key-here"

# Navigate to the vault root
cd ~/MattPacione_Local
```

## Usage

### Test with a single file first

```bash
python Competitors/CompetitiveLandscape-2025/_Prompts/_BatchCleanup/orchestrator.py \
    --file "Linear.md" \
    --dry-run
```

### Run on single file (real)

```bash
python Competitors/CompetitiveLandscape-2025/_Prompts/_BatchCleanup/orchestrator.py \
    --file "Linear.md"
```

### Run on all files (dry run)

```bash
python Competitors/CompetitiveLandscape-2025/_Prompts/_BatchCleanup/orchestrator.py \
    --workers 10 \
    --dry-run
```

### Run on all files (real)

```bash
python Competitors/CompetitiveLandscape-2025/_Prompts/_BatchCleanup/orchestrator.py \
    --workers 10
```

### Resume after interruption

The script tracks processed files in `processed.json`. Just re-run:

```bash
python orchestrator.py --workers 10
```

### Reset and start fresh

```bash
python orchestrator.py --workers 10 --reset
```

## How It Works

1. **Orchestrator** lists all `.md` files in `Competitors/`
2. Checks `processed.json` to skip already-done files
3. Spawns up to N concurrent Sonnet API calls
4. Each worker:
   - Reads the file
   - Gets formatting rules from `_Schema.md`
   - Fixes issues (content preserved, only formatting changes)
   - Writes corrected file back
   - Returns JSON report
5. Results logged to `processed.json`

## Files

- `orchestrator.py` - Main script
- `worker_prompt.md` - Prompt template for each file
- `processed.json` - Tracks completion (auto-created)
- `results.json` - Detailed results (auto-created)

## Tuning

- **Workers**: 10 is safe. Can go up to 20 if you have rate limit headroom.
- **Model**: Uses `claude-sonnet-4-20250514`. Change `MODEL` constant if needed.

## Cost Estimate

~294 files × ~4K tokens input × ~2K tokens output = ~1.7M tokens total
At Sonnet pricing (~$3/M input, $15/M output): ~$30-50 total

## Troubleshooting

**Rate limited?** Reduce `--workers` to 5.

**File not updating?** Check `processed.json` - if it's marked processed, use `--reset` or manually remove entry.

**Parsing errors?** The worker prompt expects specific XML tags in response. Check Claude's raw output.

---

# P3 Sentiment & Presentation Enrichment

After P2 cleanup, run P3 to enrich profiles with real sentiment data and presentation fields.

## What P3 Does

1. **Searches** HN, Reddit, G2 for real developer sentiment
2. **Adds quotes** with attribution and engagement metrics
3. **Adds traction signals** (GitHub stars, funding, ratings)
4. **Adds presentation frontmatter** (demo_url, tagline, autonomy_level, etc.)
5. **Adds Talking Points section** for exec presentation

## Usage

```bash
# Test on single file
python Competitors/CompetitiveLandscape-2025/_Prompts/_BatchCleanup/p3_orchestrator.py \
    --file "Cursor.md"

# Run priority competitors first (Cursor, Linear, GitHub, Devin, etc.)
python Competitors/CompetitiveLandscape-2025/_Prompts/_BatchCleanup/p3_orchestrator.py \
    --workers 5 \
    --priority

# Run all p2-complete files
python Competitors/CompetitiveLandscape-2025/_Prompts/_BatchCleanup/p3_orchestrator.py \
    --workers 5
```

## Key Differences from P2

| Aspect | P2 Cleanup | P3 Enrichment |
|--------|------------|---------------|
| Workers | 10 | 5 (search is slower) |
| Timeout | 2 min | 2 min |
| Max tokens | 8K | 16K (larger output) |
| Web search | No | Yes |
| Log file | processed.json | p3_processed.json |

## New Schema Fields Added

```yaml
# Presentation fields (in frontmatter)
demo_url: "https://cursor.com"
tagline: "AI-native IDE with codebase context"
funding_display: "$400M Series C"
autonomy_level: L3
out_of_left_field: false
presentation_priority: 1
```

## New Section Added

```markdown
## Talking Points

### What keeps us up at night
### Their competitive advantage
### Our competitive advantage
### Discussion prompt
```

## Cost Estimate

~294 files × ~8K tokens input × ~4K tokens output = ~3.5M tokens
At Sonnet pricing: ~$60-80 total

---

# Atlassian Product Research

Research Atlassian products from an **external perspective**—how the market sees us, not internal metrics.

## Philosophy

Treat Atlassian products the same way we research competitors:
- Use public sources only (G2, HN, Reddit, product docs)
- Include real criticisms and complaints
- Be honest about gaps vs competitors
- No insider knowledge or marketing claims

## Usage

```bash
# Test single product
python Competitors/CompetitiveLandscape-2025/_Prompts/_BatchCleanup/atlassian_orchestrator.py \
    --file "Jira.md"

# Run all 5 products
python Competitors/CompetitiveLandscape-2025/_Prompts/_BatchCleanup/atlassian_orchestrator.py \
    --workers 3
```

## What It Does

1. Reads scaffold files in `Atlassian/` folder
2. Loads competitor profiles for comparison context
3. Searches for external sentiment (G2, HN, Reddit)
4. Fills in capabilities, developer love, head-to-head, gap analysis
5. Writes honest "what keeps us up at night" talking points

## Key Differences from Competitor Research

| Aspect | Competitors | Atlassian Products |
|--------|-------------|-------------------|
| Folder | `Competitors/` | `Atlassian/` |
| Template | `_CompetitorTemplate.md` | `_AtlassianProductTemplate.md` |
| Workers | 5-10 | 3 (deeper research) |
| Sections | Partnership, Acquisition | Roadmap, Gap Analysis |
| Perspective | External threat | External self-assessment |

## Products Included

- Rovo Dev (vs Cursor, Copilot, Devin)
- Jira (vs Linear, GitHub Issues, Asana)
- Bitbucket (vs GitHub, GitLab, Graphite)
- Compass (vs Backstage, Port, Cortex)
- Confluence (vs Notion, Mintlify, GitBook)

## Cost Estimate

5 files × ~12K tokens input × ~6K tokens output = ~90K tokens
At Sonnet pricing: ~$2-3 total
