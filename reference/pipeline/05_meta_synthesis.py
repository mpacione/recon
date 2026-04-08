#!/usr/bin/env python3
"""
P4 Pipeline - Cross-Theme Meta-Synthesis (v2)

After individual theme synthesis, this script:
1. Reads all theme documents
2. Identifies cross-cutting patterns, contradictions, and compounding threats
3. Creates a unified strategic brief for executive awareness (NOT recommendations)

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

    return f"""You are preparing a competitive landscape briefing for Atlassian's developer tools leadership.

This briefing is for AWARENESS, not action. Leadership wants to understand the landscape before discussing what to do. Your job is to present what's happening in the market clearly and let them draw conclusions.

## CRITICAL: THIS IS NOT A RECOMMENDATIONS DOCUMENT

- NO "Atlassian should..."
- NO "Consider acquiring..."
- NO "Recommended actions..."
- NO capability gap tables with recommendations
- NO strategic paths or options

Frame everything as OBSERVATION: "The market is shifting toward...", "This signals...", "The implication is..."

## CRITICAL: BREVITY

This is an EXECUTIVE SUMMARY. Keep it tight:
- Total output should be ~900-1100 words max
- No filler, no hedging, no "it's important to note"
- Tables over prose where possible
- One sentence per idea

## CRITICAL: CITE YOUR SOURCES

Every claim about funding, acquisitions, partnerships, or market moves MUST include specific data points from the theme documents. No vague assertions.

BAD: "There's been significant consolidation in the AI coding space."
GOOD: "Cognition acquired Codeium/Windsurf while reaching $155M ARR and $10.2B valuation. Cursor hit $500M ARR in under 2 years."

## CRITICAL CONSTRAINTS

### Date Awareness
- Today's date is {current_month}
- Any dates before {current_month} have ALREADY PASSED
- Use relative timeframes ("within 6 months", "by end of {current_year}")

### No Made-Up Statistics
- NEVER invent confidence percentages (e.g., "90% confidence")
- NEVER invent revenue figures unless directly cited in the theme documents
- Stick to qualitative assessments or real numbers from sources

## Output Format

# [Title]: Atlassian's [Timeframe] Window

Use a memorable, specific title. Good: "The Great Inversion: Atlassian's 18-Month Window". Bad: "The AI Development Revolution" (too generic).

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

MINIMUM 2 sentences per theme (preferably 2-3) explaining what it means and why it matters. Do NOT use single-sentence descriptions. End with "Key Examples:" and list 3-4 competitors WITH LINKS (for reference).

IMPORTANT: Use the EXACT theme names from the source documents. Do not rename them.

- **The Agentic Shift**: [2-3 sentences explaining the theme and its implications]. Key Examples: [Linear](https://linear.app), [Devin](https://devin.ai), [Factory](https://factory.ai)
- **Platform Wars**: [2-3 sentences]. Key Examples: [GitHub](https://github.com), [Cursor](https://cursor.com), ...
- etc.

Pull competitor URLs from the theme files where available.

## Threat Landscape

| Product(s) | Competitors | Threat Type | Why It's Dangerous |
|------------|-------------|-------------|-------------------|
| Bitbucket | GitHub, CodeRabbit, GitLab, Graphite | Platform bundling, AI-native disruption | [2-3 sentences explaining the threat] |
| Jira | Linear, ClickUp, GitHub Projects, Notion | Speed disruption, Context capture | [2-3 sentences] |
| Confluence | Mintlify, Notion, README.ai, Swimm | ... | [2-3 sentences] |
| Rovo Dev | Cursor, GitHub Copilot, Cline, Windsurf | ... | [2-3 sentences] |
| Compass | Backstage, Port, Cortex, OpsLevel | ... | [2-3 sentences] |

List 4-5 competitors per product (NO links in this section—links only in Themes at Play).
"Why It's Dangerous" should be 2-3 sentences providing enough context for execs to understand the threat.
Threat types to use: Platform bundling, Vertical disruption, Speed disruption, Context capture, AI-native disruption, Open source erosion, Business model attack

## Funding & Consolidation Signals

This section is about WHERE MONEY IS FLOWING and what it signals about market direction.

Structure as 4-5 bullets. Each bullet MUST be 2-3 sentences of substance, not surface-level observations.

Format:
- **[Pattern Name]**: [Specific deals with amounts, dates, and parties involved]. [Additional context on what drove the deal or why it matters competitively]. *This signals [directional interpretation with specific implication].*

Example:
- **AI coding tools commanding premium valuations**: Cursor reached $2.5B valuation on ~$100M ARR—a 25x revenue multiple that dwarfs typical SaaS benchmarks. Cognition (Devin) hit $2B valuation despite limited production deployments, purely on the promise of autonomous coding. CodeRabbit reached $550M in just 2 years by capturing the AI code review gap incumbents ignored. *This signals investors are pricing in a platform shift where AI coding tools capture value currently held by IDEs, code review, and project management—Atlassian's core categories.*

- **Consolidation accelerating at the edges**: Cursor acquired Graphite for $290M+ to own PR workflow and prevent GitHub from capturing that surface. Cognition acquired Windsurf/Codeium to combine autonomous agents with IDE presence. JetBrains acquired Mellum for on-device AI to counter cloud-dependent competitors. *This signals the land grab phase is ending—players are now buying adjacencies to lock in defensible positions before the window closes.*

Do NOT include recommendations. Just patterns and what they signal.

## Competitor Spotlight

Deep dive on 5-7 competitors that represent existential or strategic threats. Aim for coverage across different threat types:
- **Platform threats** (e.g., GitHub/Microsoft absorbing Atlassian's categories)
- **Speed/UX disruptors** (e.g., Linear capturing next-gen developers)
- **AI-native disruptors** (e.g., Cursor, Devin redefining developer workflows)
- **Open source erosion** (e.g., Backstage commoditizing Compass's market)
- **Governance/enterprise plays** (e.g., Port capturing AI-first enterprise buyers)

For each competitor:

### [Competitor Name]
- **Position**: [One sentence on what they are and their market position]
- **Scale**: [Revenue, users, funding—real numbers from theme docs]
- **Strategic Strength**: [What makes them dangerous—be specific about the capability or moat]
- **Structural Vulnerability**: [Where they're weak—and why that weakness might not matter]
- **Recent Move**: [Latest significant action with date/details and strategic intent]
- **Why This Matters to Atlassian**: [2-3 sentences. Name the specific Atlassian product(s) threatened. Explain the mechanism of threat—is it substitution, bundling, or market capture? Describe trajectory—where is this competitor heading in 12-18 months?]

Example "Why This Matters to Atlassian":
"Linear directly threatens Jira's next-generation user base by positioning as the 'anti-Jira' for developers who associate Jira with enterprise bloat. The mechanism isn't feature competition—it's perception capture. Linear is shipping AI agents as assignable team members in July 2025; if successful, they'll own the 'AI-native project management' category before Jira can respond."

Choose competitors to ensure coverage across the threat types above. Prioritize competitors with: direct product overlap, market momentum, or strategic positioning that threatens Atlassian's core value proposition.

## The Hard Questions

This section surfaces the strategic tensions this landscape creates for Atlassian. NOT recommendations—provocative questions that leadership must wrestle with, backed by evidence.

3 questions maximum. Format as H3 headers with the question itself, followed by 2-3 sentences of evidence that makes the question unavoidable.

### [Provocative Question]?
[2-3 sentences citing specific evidence from the landscape—competitor moves, market data, trend patterns—that forces this question to the surface. Make the question feel inevitable, not hypothetical.]

Example:

### Can Atlassian's integration advantage survive when AI agents build their own integrations?
Atlassian's moat has been connecting Jira→Confluence→Bitbucket into a unified workflow. But Cursor acquired Graphite to own PR workflows natively. GitHub Copilot now creates issues, writes code, and opens PRs without leaving the IDE. Linear's agent API lets AI bypass human-facing interfaces entirely. The platforms that orchestrate AI agents are building direct connections that skip Atlassian's integration layer.

### What happens to per-seat pricing when agents do 40-60% of the work?
Devin charges per "ACU" (agent compute unit), not per developer. Factory's "Droids" are priced by task completion, not headcount. At companies like Shopify, AI-generated code already exceeds 40% of total output. Atlassian's entire revenue model assumes humans are the unit of work—but the market is shifting to agents as the unit of value.

End with the final Hard Question. No summary blockquote—let the questions speak for themselves."""


META_SYSTEM = get_meta_system()


def load_theme_documents(use_deep: bool = False) -> dict:
    """Load all theme synthesis documents."""
    themes = {}

    for theme_key, theme_config in CONFIG["themes"].items():
        if use_deep:
            filename = theme_config["output_file"].replace(".md", "_deep.md")
            filepath = THEMES_DIR / "_Deep_Trend_Analysis" / filename
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

Now synthesize across all themes. What's the unified picture of the competitive landscape? Where do themes reinforce each other? What patterns emerge?

Remember: This is for AWARENESS. Present what's happening. Let leadership decide what to do."""

    print("Calling Claude for meta-synthesis...")

    # Use streaming for large context (>10 min timeout)
    output_parts = []
    with client.messages.stream(
        model=CONFIG["synthesis"]["model"],
        max_tokens=6000,
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
