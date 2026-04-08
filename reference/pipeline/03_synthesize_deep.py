#!/usr/bin/env python3
"""
P4 Pipeline - Deep Multi-Pass Synthesis

Enhanced synthesis with multiple passes for deeper insights:
- Pass 1: Initial pattern synthesis (same as 03_synthesize.py)
- Pass 2: Devil's Advocate - challenge insights, find counterexamples
- Pass 3: Atlassian Gap Analysis - compare against actual product capabilities
- Pass 4: Cross-Theme Meta-Synthesis - find compounding threats and contradictions

Usage:
    python _Prompts/p4_pipeline/03_synthesize_deep.py --theme agentic_shift
    python _Prompts/p4_pipeline/03_synthesize_deep.py --theme all
    python _Prompts/p4_pipeline/03_synthesize_deep.py --theme all --skip-pass1  # If pass1 already done

Cost estimate: ~$5-8 per theme with Opus (3-4x single pass)
"""

import argparse
import json
import os
import yaml
from pathlib import Path
from datetime import datetime

import anthropic
import frontmatter

# Load config
SCRIPT_DIR = Path(__file__).parent.resolve()
BASE_DIR = SCRIPT_DIR.parent.parent  # CompetitiveLandscape-2025

with open(SCRIPT_DIR / "config.yaml") as f:
    CONFIG = yaml.safe_load(f)

# Paths
RETRIEVED_DIR = SCRIPT_DIR / ".retrieved"
THEMES_DIR = BASE_DIR / CONFIG["paths"]["themes_dir"]
ATLASSIAN_DIR = BASE_DIR / CONFIG["paths"]["atlassian_dir"]

# Ensure output directory exists
THEMES_DIR.mkdir(exist_ok=True)


def get_key_question(theme_key: str) -> str:
    """Return the key question for each theme."""
    questions = {
        "agentic_shift": "How is the L1→L5 autonomy transition reshaping developer tools, and what does this mean for Atlassian's product strategy?",
        "platform_wars": "Who will own the orchestration layer for AI-assisted development, and how should Atlassian position its platform?",
        "trust_and_governance": "What enterprise control, compliance, and governance capabilities are becoming table stakes, and where are the gaps in Atlassian's offering?",
        "workflow_embedding": "How are AI tools embedding into developer workflows (sidecar vs. autonomous vs. ambient), and what UX patterns are winning?",
        "time_to_value": "What onboarding and activation patterns drive adoption, and how does Atlassian's time-to-value compare to competitors?",
        "developer_love": "What patterns emerge in tools developers love, and how does Atlassian stack up against these expectations?",
        "consolidation_patterns": "How are platforms expanding and consolidating, and what does this mean for Atlassian's market position?",
        "alignment_infrastructure": "How are teams capturing the chain from intent→spec→code→review, and what new 'system of record' is emerging?",
        "conductor_model": "How is the engineer's role shifting from code-writer to code-reviewer/orchestrator, and what tools are enabling this transition?"
    }
    return questions.get(theme_key, "What strategic patterns emerge from the competitive landscape?")


def load_atlassian_products() -> dict:
    """Load all Atlassian product files for gap analysis."""
    products = {}
    for filepath in ATLASSIAN_DIR.glob("*.md"):
        try:
            post = frontmatter.load(filepath)
            name = post.metadata.get("name", filepath.stem)
            products[name] = {
                "metadata": dict(post.metadata),
                "content": post.content[:8000]  # Truncate for context limits
            }
        except Exception as e:
            print(f"  Warning: Could not load {filepath.name}: {e}")
    return products


def build_context(retrieved: dict, max_competitors: int = 50) -> str:
    """Build context string from retrieved chunks - expanded for deep synthesis."""
    context_parts = []

    for comp in retrieved["competitors"][:max_competitors]:
        comp_section = f"\n### {comp['name']}\n"
        comp_section += f"**Threat Level:** {comp['threat_level']} | "
        comp_section += f"**Autonomy:** {comp['autonomy_level']} | "
        comp_section += f"**Overlaps:** {', '.join(comp['atlassian_overlap']) if comp['atlassian_overlap'] else 'N/A'}\n\n"

        # Include more chunks for deeper context
        for chunk in comp["top_chunks"][:4]:
            comp_section += f"*[{chunk['section']}]*\n{chunk['text']}\n\n"

        context_parts.append(comp_section)

    return "\n".join(context_parts)


def build_outlier_context(retrieved: dict) -> str:
    """Build context specifically from experimental/out-of-left-field competitors."""
    outliers = [c for c in retrieved["competitors"]
                if c.get("tier") == "Experimental" or c.get("out_of_left_field")]

    if not outliers:
        # Fall back to lower-ranked competitors that might have unique signals
        outliers = retrieved["competitors"][30:50]

    context_parts = []
    for comp in outliers[:15]:
        comp_section = f"\n### {comp['name']} (Outlier/Experimental)\n"
        for chunk in comp["top_chunks"][:2]:
            comp_section += f"{chunk['text']}\n\n"
        context_parts.append(comp_section)

    return "\n".join(context_parts)


# =============================================================================
# PASS 1: Initial Pattern Synthesis
# =============================================================================

PASS1_SYSTEM = """You are a senior product strategist analyzing competitive intelligence for Atlassian's developer tools portfolio (Jira, Confluence, Bitbucket, Compass, Rovo Dev).

Your task is to synthesize patterns from competitor research into actionable strategic insights.

## Guidelines

1. **Go beyond reporting — analyze**: Find non-obvious insights, challenge conventional wisdom, identify second-order effects
2. **Be specific, not generic**: Instead of "AI is changing tools", say "Autonomous agents executing Jira issues directly threaten Jira's UI relevance within 18 months"
3. **Quantify where possible**: Market sizes, funding as conviction signal, adoption timelines
4. **Challenge assumptions**: Is the threat real? What's overhyped? What's underhyped?
5. **Atlassian-specific**: Every insight should connect to a concrete Atlassian product decision

## Output Format

Return your synthesis as a complete markdown document following this structure:

### Pattern Summary
2-3 paragraphs describing the key pattern across the landscape. What's actually happening?

### Evidence Table
A markdown table with columns: Competitor | Signal | Implication
Include 10-15 rows with the most compelling evidence. Include the table header.

### Atlassian Implications
Use EXACTLY these subsection headers (required for parsing):
#### For Jira
2-3 specific implications with concrete product decisions.

#### For Confluence
2-3 specific implications with concrete product decisions.

#### For Bitbucket
2-3 specific implications with concrete product decisions.

#### For Compass
2-3 specific implications with concrete product decisions.

#### For Rovo Dev
2-3 specific implications with concrete product decisions.

### Recommended Response
Use EXACTLY these subsection headers (required for parsing):

#### Immediate (0-3 months)
Quick wins, no-regret moves. Bullet points.

#### Near-term (3-12 months)
Strategic initiatives to start. Bullet points.

#### Strategic (12+ months)
Bets to place, investments to make. Bullet points.

### Related Competitors
Bulleted list of the 8-12 most relevant competitors to watch for this theme, using [[wikilink]] format.

Be direct. Be specific. Be useful."""


def pass1_synthesis(client: anthropic.Anthropic, theme_key: str, retrieved: dict) -> str:
    """Pass 1: Initial pattern synthesis."""
    print("\n--- Pass 1: Initial Pattern Synthesis ---")

    theme_config = CONFIG["themes"][theme_key]
    key_question = get_key_question(theme_key)
    context = build_context(retrieved, max_competitors=50)

    context_tokens = len(context) // 4
    print(f"Context size: ~{context_tokens:,} tokens")

    user_prompt = f"""## Theme: {theme_config['title']}

## Key Question
{key_question}

## Retrieved Competitor Intelligence

The following content was semantically retrieved from {len(retrieved['competitors'])} competitor profiles based on these queries:
{chr(10).join('- ' + q for q in retrieved['queries'])}

---

{context}

---

Now synthesize this intelligence into a cohesive theme document. Focus on patterns, not just listing facts. What's the strategic "so what?" for Atlassian?"""

    print("Calling Claude for Pass 1...")
    response = client.messages.create(
        model=CONFIG["synthesis"]["model"],
        max_tokens=CONFIG["synthesis"]["max_tokens"],
        temperature=0.3,
        system=PASS1_SYSTEM,
        messages=[{"role": "user", "content": user_prompt}]
    )

    return response.content[0].text


# =============================================================================
# PASS 2: Devil's Advocate / Contrarian Analysis
# =============================================================================

PASS2_SYSTEM = """You are a skeptical analyst whose job is to stress-test strategic recommendations. You've been given an initial synthesis about competitive threats to Atlassian.

Your task is to find weaknesses in the analysis:

1. **Challenge assumptions**: What if these trends reverse? What signals would indicate the thesis is wrong?
2. **Find counterexamples**: Which competitors are betting AGAINST this trend? Are they stupid or do they know something?
3. **Identify overhype**: Which signals are actually noise? What's the base rate for these "threats" actually materializing?
4. **Surface underhyped risks**: What's missing from this analysis? What adjacent threats aren't being considered?
5. **Question timelines**: Are the urgency levels appropriate? What if this takes 5 years instead of 18 months?

## Output Format

### Assumption Challenges
For each major assumption in the synthesis, provide:
- The assumption
- Evidence that challenges it
- Probability estimate that the assumption is wrong (Low/Medium/High)

### Counterexamples
Competitors or market signals that contradict the main thesis.

### Overhyped Signals
Which evidence points are weaker than presented? What's the actual base rate?

### Underhyped Risks
What's missing? What adjacent threats should Atlassian worry about?

### Revised Confidence Levels
For each major recommendation, provide a confidence level (Low/Medium/High) and explain why.

### What Would Change Our Mind
Specific signals that would indicate this thesis is wrong.

Be ruthlessly honest. Sacred cows make the best hamburgers."""


def pass2_contrarian(client: anthropic.Anthropic, theme_key: str, pass1_output: str, retrieved: dict) -> str:
    """Pass 2: Devil's advocate analysis."""
    print("\n--- Pass 2: Devil's Advocate Analysis ---")

    theme_config = CONFIG["themes"][theme_key]
    outlier_context = build_outlier_context(retrieved)

    user_prompt = f"""## Theme: {theme_config['title']}

## Initial Synthesis (from Pass 1)

{pass1_output}

## Additional Context: Outlier & Experimental Competitors

These are smaller players or contrarian bets that might reveal blind spots:

{outlier_context}

---

Now challenge this synthesis. What's wrong with it? What's overhyped? What's missing?"""

    print("Calling Claude for Pass 2...")
    response = client.messages.create(
        model=CONFIG["synthesis"]["model"],
        max_tokens=CONFIG["synthesis"]["max_tokens"],
        temperature=0.4,  # Slightly higher for more creative challenges
        system=PASS2_SYSTEM,
        messages=[{"role": "user", "content": user_prompt}]
    )

    return response.content[0].text


# =============================================================================
# PASS 3: Atlassian Gap Analysis
# =============================================================================

PASS3_SYSTEM = """You are a product gap analyst comparing Atlassian's actual capabilities against competitive threats.

You've been given:
1. A strategic synthesis about a competitive theme
2. Detailed profiles of Atlassian's actual products (Jira, Confluence, Bitbucket, Compass, Rovo Dev)

Your task is to provide a REALISTIC gap analysis:

1. **Current State**: What does Atlassian actually have today that addresses this theme?
2. **Gap Severity**: Rate each gap as Critical (existential), Major (significant disadvantage), Minor (nice to have), or Non-Issue
3. **Build vs Buy vs Partner**: For each gap, recommend the best approach
4. **Realistic Timeline**: Given Atlassian's typical velocity, how long would it take to close each gap?
5. **Prioritized Backlog**: If Atlassian could only do 3 things, what should they be?

## Output Format

### Current Atlassian Capabilities
What Atlassian already has that's relevant to this theme. Be specific about features, not vague claims.

### Gap Analysis Table

| Gap | Severity | Best Approach | Timeline | Rationale |
|-----|----------|---------------|----------|-----------|
| ... | Critical/Major/Minor | Build/Buy/Partner | Q months | Why |

### Build Recommendations
Specific features to build, with effort estimates.

### Buy Targets
Specific companies to acquire and why they're the right fit.

### Partner Opportunities
Integrations or partnerships that could close gaps faster.

### Prioritized Top 3
If resources are constrained, these are the three things Atlassian must do.

Be realistic about Atlassian's execution capacity. They're a large company with many priorities."""


def pass3_gap_analysis(client: anthropic.Anthropic, theme_key: str, pass1_output: str, atlassian_products: dict) -> str:
    """Pass 3: Atlassian gap analysis."""
    print("\n--- Pass 3: Atlassian Gap Analysis ---")

    theme_config = CONFIG["themes"][theme_key]

    # Build Atlassian product context
    atlassian_context = ""
    for name, data in atlassian_products.items():
        atlassian_context += f"\n## {name}\n"
        atlassian_context += f"**Metadata:** {json.dumps(data['metadata'], indent=2, default=str)}\n\n"
        atlassian_context += f"**Product Details:**\n{data['content'][:4000]}\n\n"

    user_prompt = f"""## Theme: {theme_config['title']}

## Strategic Synthesis

{pass1_output}

---

## Atlassian's Actual Product Capabilities

{atlassian_context}

---

Now provide a realistic gap analysis. What does Atlassian actually have vs. what they need?"""

    print("Calling Claude for Pass 3...")
    response = client.messages.create(
        model=CONFIG["synthesis"]["model"],
        max_tokens=CONFIG["synthesis"]["max_tokens"],
        temperature=0.2,  # Lower for more factual analysis
        system=PASS3_SYSTEM,
        messages=[{"role": "user", "content": user_prompt}]
    )

    return response.content[0].text


# =============================================================================
# PASS 4: Final Integration
# =============================================================================

PASS4_SYSTEM = """You are a chief strategy officer preparing the final brief for Atlassian's executive team.

You've been given three analyses:
1. Initial pattern synthesis (the opportunities and threats)
2. Devil's advocate critique (the challenges and blind spots)
3. Gap analysis (what Atlassian can realistically do)

Your task is to integrate these into a final, actionable strategy document that:

1. **Acknowledges uncertainty**: Where the devil's advocate raised valid concerns, reflect appropriate confidence levels
2. **Is grounded in reality**: Recommendations should match Atlassian's actual capabilities and gaps
3. **Provides clear decisions**: Not wishy-washy "consider" language - actual recommendations
4. **Includes kill criteria**: What would make us abandon this strategy?

## Output Format

Create a final executive brief with these sections:

### Executive Summary
3-4 sentences capturing the strategic imperative.

### Key Insight
The single most important non-obvious insight from this analysis.

### Confidence-Adjusted Threats
Table of threats with confidence levels (accounting for devil's advocate challenges).

### Recommended Actions
Specific, prioritized actions with owners and timelines. Formatted as:

**Immediate (0-3 months)**
- [ ] Action item (Owner: Product/Eng/BD) - Expected outcome

**Near-term (3-12 months)**
- [ ] Action item (Owner: Product/Eng/BD) - Expected outcome

**Strategic (12+ months)**
- [ ] Action item (Owner: Product/Eng/BD) - Expected outcome

### Key Bets
The 2-3 big strategic bets embedded in these recommendations.

### Kill Criteria
Specific signals that would indicate we should abandon or pivot this strategy.

### What We're Choosing NOT To Do
Explicit trade-offs and paths not taken.

Write for a busy executive. Be direct. No hedging."""


def pass4_integration(client: anthropic.Anthropic, theme_key: str, pass1: str, pass2: str, pass3: str) -> str:
    """Pass 4: Final integration of all passes."""
    print("\n--- Pass 4: Final Integration ---")

    theme_config = CONFIG["themes"][theme_key]

    user_prompt = f"""## Theme: {theme_config['title']}

## Pass 1: Initial Pattern Synthesis

{pass1}

---

## Pass 2: Devil's Advocate Critique

{pass2}

---

## Pass 3: Atlassian Gap Analysis

{pass3}

---

Now integrate these three analyses into a final executive brief. Reconcile contradictions, adjust confidence levels, and provide clear recommendations."""

    print("Calling Claude for Pass 4...")
    response = client.messages.create(
        model=CONFIG["synthesis"]["model"],
        max_tokens=CONFIG["synthesis"]["max_tokens"],
        temperature=0.2,
        system=PASS4_SYSTEM,
        messages=[{"role": "user", "content": user_prompt}]
    )

    return response.content[0].text


# =============================================================================
# Main Orchestration
# =============================================================================

def synthesize_theme_deep(theme_key: str, skip_pass1: bool = False) -> dict:
    """Run all synthesis passes for a theme."""

    # Load retrieved data
    retrieved_file = RETRIEVED_DIR / f"{theme_key}.json"
    if not retrieved_file.exists():
        print(f"Error: No retrieved data for {theme_key}")
        print(f"Run: python 02_retrieve.py --theme {theme_key}")
        return None

    with open(retrieved_file) as f:
        retrieved = json.load(f)

    print(f"\n{'='*60}")
    print(f"Deep Synthesis: {CONFIG['themes'][theme_key]['title']}")
    print(f"{'='*60}")
    print(f"Competitors in context: {len(retrieved['competitors'])}")

    client = anthropic.Anthropic()
    atlassian_products = load_atlassian_products()
    print(f"Atlassian products loaded: {list(atlassian_products.keys())}")

    # Check for existing pass1 output if skip_pass1
    output_file = THEMES_DIR / CONFIG["themes"][theme_key]["output_file"]

    if skip_pass1 and output_file.exists():
        print("Loading existing Pass 1 output...")
        with open(output_file) as f:
            pass1_output = f.read()
    else:
        pass1_output = pass1_synthesis(client, theme_key, retrieved)

    # Run remaining passes
    pass2_output = pass2_contrarian(client, theme_key, pass1_output, retrieved)
    pass3_output = pass3_gap_analysis(client, theme_key, pass1_output, atlassian_products)
    pass4_output = pass4_integration(client, theme_key, pass1_output, pass2_output, pass3_output)

    # Build final document
    theme_config = CONFIG["themes"][theme_key]
    final_doc = f"""---
type: theme
title: "{theme_config['title']}"
created: {datetime.now().strftime("%Y-%m-%d")}
status: deep-synthesis
synthesized_by: claude-opus
passes: 4
---

# {theme_config['title']}

> **Key Question:** {get_key_question(theme_key)}

---

## Executive Brief

{pass4_output}

---

## Supporting Analysis

### Pass 1: Pattern Synthesis

{pass1_output}

---

### Pass 2: Devil's Advocate Critique

{pass2_output}

---

### Pass 3: Gap Analysis

{pass3_output}

---

*Deep synthesis from {len(retrieved['competitors'])} competitor profiles across 4 analysis passes.*
"""

    # Save
    output_file = THEMES_DIR / CONFIG["themes"][theme_key]["output_file"].replace(".md", "_deep.md")
    with open(output_file, "w") as f:
        f.write(final_doc)

    print(f"\n✅ Saved to {output_file}")

    return {
        "theme": theme_key,
        "output_file": str(output_file),
        "passes": 4,
        "competitors": len(retrieved["competitors"])
    }


def main():
    parser = argparse.ArgumentParser(description="Deep Multi-Pass Theme Synthesis")
    parser.add_argument("--theme", required=True, help="Theme key or 'all'")
    parser.add_argument("--skip-pass1", action="store_true",
                        help="Skip Pass 1 if output already exists")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be processed without calling API")

    args = parser.parse_args()

    if args.theme == "all":
        themes = list(CONFIG["themes"].keys())
    else:
        if args.theme not in CONFIG["themes"]:
            print(f"Error: Unknown theme '{args.theme}'")
            print(f"Available: {list(CONFIG['themes'].keys())}")
            return
        themes = [args.theme]

    if args.dry_run:
        print("DRY RUN - Would process these themes:")
        for theme in themes:
            print(f"  - {theme}: {CONFIG['themes'][theme]['title']}")
        print(f"\nEstimated cost: ~${len(themes) * 6}-{len(themes) * 8} with Opus")
        return

    results = []
    for theme in themes:
        result = synthesize_theme_deep(theme, skip_pass1=args.skip_pass1)
        if result:
            results.append(result)

    print(f"\n{'='*60}")
    print("DEEP SYNTHESIS COMPLETE")
    print(f"{'='*60}")
    print(f"Themes processed: {len(results)}")
    for r in results:
        print(f"  - {r['theme']}: {r['output_file']}")


if __name__ == "__main__":
    main()
