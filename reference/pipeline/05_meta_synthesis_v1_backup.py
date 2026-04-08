#!/usr/bin/env python3
"""
P4 Pipeline - Cross-Theme Meta-Synthesis

After individual theme synthesis, this script:
1. Reads all theme documents
2. Identifies cross-cutting patterns, contradictions, and compounding threats
3. Creates a unified strategic brief

Usage:
    python _Prompts/p4_pipeline/05_meta_synthesis.py
    python _Prompts/p4_pipeline/05_meta_synthesis.py --deep  # Use deep synthesis files

Cost estimate: ~$8-12 with Opus (single pass but large context)
"""

import argparse
import yaml
from pathlib import Path
from datetime import datetime

import anthropic

# Load config
SCRIPT_DIR = Path(__file__).parent.resolve()
BASE_DIR = SCRIPT_DIR.parent.parent

with open(SCRIPT_DIR / "config.yaml") as f:
    CONFIG = yaml.safe_load(f)

THEMES_DIR = BASE_DIR / CONFIG["paths"]["themes_dir"]


def get_meta_system():
    """Generate the executive summary system prompt with current date awareness."""
    from datetime import datetime
    today = datetime.now()
    current_month = today.strftime("%B %Y")
    current_year = today.year

    return f"""You are preparing a competitive strategy executive summary for Atlassian's developer tools leadership.

You've been given synthesis documents for multiple strategic themes. These aren't separate problems—they're different angles on a single transformation. Your job is to name that transformation, show how themes connect, and identify the core strategic choice.

## CRITICAL: BREVITY

This is an EXECUTIVE SUMMARY. Keep it tight:
- Total output should be ~800-1000 words max
- No filler, no hedging, no "it's important to note"
- Tables over prose where possible
- One sentence per idea

## CRITICAL CONSTRAINTS

### Date Awareness
- Today's date is {current_month}
- Any dates before {current_month} have ALREADY PASSED
- Use relative timeframes ("within 6 months", "by end of {current_year}")

### Acquisition Language
- NEVER recommend "acquire X for $Y"
- Frame as CAPABILITY GAPS (e.g., "L3+ autonomous code review gap")
- Use "worth evaluating if exploring inorganic paths" if needed
- Focus on WHAT capability is needed, not WHO to buy

### No Made-Up Statistics
- NEVER invent confidence percentages (e.g., "90% confidence")
- NEVER invent revenue figures unless directly cited in the theme documents
- Stick to qualitative assessments ("critical", "high risk", "within 12 months")

## Output Format

# [Title]: Atlassian's [Timeframe] Window

Use a memorable, specific title. Good: "The Great Inversion: Atlassian's 18-Month Window". Bad: "The AI Development Revolution: Atlassian's Inflection Point" (too generic).

## The Shift
One paragraph (3-4 sentences) naming and describing the fundamental transformation. Give it a **memorable name in bold** (like "The Great Inversion" or "The Orchestration Imperative"). This name should be quotable in exec conversations.

Then, a few bullets on **what's driving this**—the key dynamics beneath the themes. No fixed count. Just the important ones. Format:

- Development is inverting from human-driven to AI-driven
- The battle isn't for best AI—it's for who orchestrates all the AIs
- Market is bifurcating: fast/simple vs. governed/complex
- Context ownership becomes the moat
- Per-seat pricing breaks when agents do the work

^^ Adapt based on what you find, but keep it concrete and punchy. No jargon.

## Themes at Play

MINIMUM 2 sentences per theme (preferably 2-3) explaining what it means and why it matters. Do NOT use single-sentence descriptions. End with "Key Examples:" and list 3-4 competitors WITH LINKS (for live demos).

IMPORTANT: Use the EXACT theme names from the source documents. Do not rename them (e.g., don't change "Time to Value" to "Time to Value Crisis").

- **The Agentic Shift**: [2-3 sentences explaining the theme and its implications]. Key Examples: [Linear](https://linear.app), [ClickUp](https://clickup.com), [Devin](https://devin.ai)
- **Platform Wars**: [2-3 sentences]. Key Examples: [GitHub](https://github.com), [Cursor](https://cursor.com), ...
- etc.

Pull competitor URLs from the theme files where available.

## Threat Landscape

| Product(s) | Competitors | Threat Type | Why It's Dangerous |
|------------|-------------|-------------|-------------------|
| Bitbucket | GitHub, CodeRabbit, GitLab, Graphite | Platform bundling, AI-native disruption | [2-3 sentences explaining the threat in detail] |
| Jira | Linear, ClickUp, GitHub Projects, Notion | Speed disruption, Context capture | [2-3 sentences] |
| Confluence | Mintlify, Notion, README.ai, Swimm | ... | [2-3 sentences] |
| Rovo Dev | Cursor, GitHub Copilot, Cline, Windsurf | ... | [2-3 sentences] |
| Compass | Backstage, Port, Cortex, OpsLevel | ... | [2-3 sentences] |

List 4-5 competitors per product (NO links in this section—links only in Themes at Play).
"Why It's Dangerous" should be 2-3 sentences providing enough context for execs to understand the threat.
Threat types to use: Platform bundling, Vertical disruption, Speed disruption, Context capture, AI-native disruption, Open source erosion, Business model attack

## Capability Gaps

| Capability | Severity | Recommendation |
|------------|----------|----------------|

For Recommendation column:
- Use softer language: "Consider evaluating...", "Worth exploring..."
- Include brief reasoning: "Consider CodeRabbit or similar—AI review is table stakes and build time is 12+ months"
- NEVER say "Acquire X within Y months"—instead frame as capability need with options

## The Core Choice
One blockquote framing THE strategic dilemma. Not a list—one genuine either/or. Keep it tight and quotable.

## Strategic Paths

For each of 2-3 paths, use this compact format. Use CONCRETE path names (good: "Hybrid Acquisition", "Enterprise Fortress"; bad: "Developer Labs Pivot", "Fast Follower").

**Path A: [Name]**
- Bet: [one line]
- Sacrifice: [one line]
- Gaps: [one line]
- Wins if: [one line]
- Dies if: [one line]

## Bottom Line
2-3 punchy sentences. This is what the CEO says in the earnings call. End strong—"half-measures guarantee failure" is better than "the safest path combines elements of all three."

---

Be direct. Be opinionated. Execs want the answer, not the analysis."""


META_SYSTEM = get_meta_system()


def load_theme_documents(use_deep: bool = False) -> dict:
    """Load all theme synthesis documents."""
    themes = {}

    for theme_key, theme_config in CONFIG["themes"].items():
        if use_deep:
            filename = theme_config["output_file"].replace(".md", "_deep.md")
        else:
            filename = theme_config["output_file"]

        filepath = THEMES_DIR / filename

        if filepath.exists():
            with open(filepath) as f:
                themes[theme_key] = {
                    "title": theme_config["title"],
                    "content": f.read()
                }
            print(f"  Loaded: {filepath.name}")
        else:
            print(f"  Missing: {filepath.name}")

    return themes


def build_themes_context(themes: dict) -> str:
    """Build context from all theme documents."""
    context_parts = []

    for theme_key, data in themes.items():
        context_parts.append(f"""
{'='*60}
## THEME: {data['title']}
{'='*60}

{data['content']}
""")

    return "\n\n".join(context_parts)


def run_meta_synthesis(themes: dict) -> str:
    """Run the meta-synthesis across all themes."""
    client = anthropic.Anthropic()

    context = build_themes_context(themes)
    context_tokens = len(context) // 4
    print(f"Total context: ~{context_tokens:,} tokens across {len(themes)} themes")

    user_prompt = f"""## Cross-Theme Strategic Analysis

You have synthesis documents for {len(themes)} strategic themes affecting Atlassian's developer tools portfolio.

The themes are:
{chr(10).join(f"- **{d['title']}**" for d in themes.values())}

---

{context}

---

Now synthesize across all themes. What's the unified strategic picture? Where do themes reinforce each other? Where do they conflict? What are the biggest bets Atlassian must make?"""

    print("Calling Claude for meta-synthesis...")

    # Use streaming for large context (>10 min timeout)
    output_parts = []
    with client.messages.stream(
        model=CONFIG["synthesis"]["model"],
        max_tokens=4000,  # Tight exec summary
        temperature=0.2,
        system=META_SYSTEM,
        messages=[{"role": "user", "content": user_prompt}]
    ) as stream:
        for text in stream.text_stream:
            print(text, end="", flush=True)
            output_parts.append(text)

    print()  # Newline after streaming
    return "".join(output_parts)


def main():
    parser = argparse.ArgumentParser(description="Cross-Theme Meta-Synthesis")
    parser.add_argument("--deep", action="store_true",
                        help="Use deep synthesis files (*_deep.md)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be processed")

    args = parser.parse_args()

    print(f"\n{'='*60}")
    print("Cross-Theme Meta-Synthesis")
    print(f"{'='*60}")

    print("\nLoading theme documents...")
    themes = load_theme_documents(use_deep=args.deep)

    if len(themes) < 3:
        print(f"\nError: Need at least 3 themes for meta-synthesis, found {len(themes)}")
        print("Run theme synthesis first:")
        print("  python 03_synthesize.py --theme all")
        print("  # or")
        print("  python 03_synthesize_deep.py --theme all")
        return

    if args.dry_run:
        print(f"\nDRY RUN - Would synthesize across {len(themes)} themes:")
        for key, data in themes.items():
            print(f"  - {data['title']}")
        print(f"\nEstimated cost: ~$8-12 with Opus")
        return

    # Run meta-synthesis
    meta_output = run_meta_synthesis(themes)

    # Build final document
    suffix = "_deep" if args.deep else ""
    final_doc = f"""---
type: executive-summary
title: "Competitive Landscape: Executive Summary"
created: {datetime.now().strftime("%Y-%m-%d")}
themes_analyzed: {len(themes)}
---

{meta_output}

---

**Themes Analyzed:** {", ".join(f"[[{CONFIG['themes'][k]['output_file'].replace('.md', '')}|{v['title']}]]" for k, v in themes.items())}

*Generated {datetime.now().strftime("%Y-%m-%d")}*
"""

    output_file = THEMES_DIR / "_ExecutiveSummary.md"
    with open(output_file, "w") as f:
        f.write(final_doc)

    print(f"\n✅ Saved to {output_file}")


if __name__ == "__main__":
    main()
