#!/usr/bin/env python3
"""
P4 Pipeline - Step 3: Synthesize theme documents using Claude

This script takes the retrieved chunks and sends them to Claude (Sonnet/Opus)
to generate a theme synthesis document.

Usage:
    cd CompetitiveLandscape-2025
    python _Prompts/p4_pipeline/03_synthesize.py --theme agentic_shift
    python _Prompts/p4_pipeline/03_synthesize.py --theme all

Environment:
    ANTHROPIC_API_KEY must be set

Output:
    Creates theme documents in Themes/ directory
"""

import argparse
import json
import os
import yaml
from pathlib import Path
from datetime import datetime

import anthropic

# Load config
SCRIPT_DIR = Path(__file__).parent.resolve()
BASE_DIR = SCRIPT_DIR.parent.parent  # CompetitiveLandscape-2025

with open(SCRIPT_DIR / "config.yaml") as f:
    CONFIG = yaml.safe_load(f)

# Paths - relative to script location
RETRIEVED_DIR = SCRIPT_DIR / ".retrieved"
THEMES_DIR = BASE_DIR / CONFIG["paths"]["themes_dir"]

# Theme document template
THEME_TEMPLATE = '''---
type: theme
title: "{title}"
created: {date}
status: draft
synthesized_by: claude-{model}
---

# {title}

## Key Question

> {key_question}

## Pattern Summary

{pattern_summary}

## Evidence

{evidence_table}

## Atlassian Implications

### For Jira
{jira_implications}

### For Confluence
{confluence_implications}

### For Bitbucket
{bitbucket_implications}

### For Compass
{compass_implications}

### For Rovo Dev
{rovo_implications}

## Recommended Response

### Immediate (0-3 months)
{immediate_response}

### Near-term (3-12 months)
{nearterm_response}

### Strategic (12+ months)
{strategic_response}

## Related Competitors

{related_competitors}

---

*Synthesized from {num_competitors} competitor profiles using semantic retrieval.*
'''


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


def build_context(retrieved: dict, max_competitors: int = 30) -> str:
    """Build context string from retrieved chunks."""
    context_parts = []

    for comp in retrieved["competitors"][:max_competitors]:
        comp_section = f"\n### {comp['name']}\n"
        comp_section += f"**Threat Level:** {comp['threat_level']} | "
        comp_section += f"**Autonomy:** {comp['autonomy_level']} | "
        comp_section += f"**Overlaps:** {', '.join(comp['atlassian_overlap']) if comp['atlassian_overlap'] else 'N/A'}\n\n"

        for chunk in comp["top_chunks"][:3]:  # Top 3 chunks per competitor
            comp_section += f"*[{chunk['section']}]*\n{chunk['text']}\n\n"

        context_parts.append(comp_section)

    return "\n".join(context_parts)


def synthesize_theme(theme_key: str, retrieved: dict) -> str:
    """Send context to Claude and generate synthesis."""
    client = anthropic.Anthropic()

    theme_config = CONFIG["themes"][theme_key]
    key_question = get_key_question(theme_key)
    context = build_context(retrieved)

    # Count tokens roughly (4 chars per token approximation)
    context_tokens = len(context) // 4
    print(f"Context size: ~{context_tokens:,} tokens")

    system_prompt = """You are a senior product strategist analyzing competitive intelligence for Atlassian's developer tools portfolio (Jira, Confluence, Bitbucket, Compass, Rovo Dev).

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
Include 8-12 rows with the most compelling evidence.

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
Bulleted list of the 5-10 most relevant competitors to watch for this theme, using [[wikilink]] format.

Be direct. Be specific. Be useful."""

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

    print(f"Calling Claude ({CONFIG['synthesis']['model']})...")

    response = client.messages.create(
        model=CONFIG["synthesis"]["model"],
        max_tokens=CONFIG["synthesis"]["max_tokens"],
        temperature=CONFIG["synthesis"]["temperature"],
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}]
    )

    return response.content[0].text


def parse_synthesis(raw_synthesis: str, theme_key: str, retrieved: dict) -> str:
    """Parse Claude's response and format into final document."""
    theme_config = CONFIG["themes"][theme_key]

    # Extract sections from Claude's response
    # This is a simple extraction - Claude usually follows the format well

    def extract_section(text: str, header: str, next_headers: list) -> str:
        # Try different header levels
        for prefix in ["#### ", "### ", "## "]:
            pattern = f"{prefix}{header}"
            start = text.find(pattern)
            if start != -1:
                break

        if start == -1:
            return ""

        start = start + len(pattern)
        end = len(text)
        for nh in next_headers:
            for prefix in ["#### ", "### ", "## "]:
                idx = text.find(prefix + nh, start)
                if idx != -1 and idx < end:
                    end = idx
        return text[start:end].strip()

    sections = {
        "pattern_summary": extract_section(raw_synthesis, "Pattern Summary",
                                          ["Evidence", "Atlassian"]),
        "evidence_table": extract_section(raw_synthesis, "Evidence",
                                         ["Atlassian", "Recommended"]),
        "jira": extract_section(raw_synthesis, "For Jira",
                               ["For Confluence", "For Bitbucket"]),
        "confluence": extract_section(raw_synthesis, "For Confluence",
                                     ["For Bitbucket", "For Compass"]),
        "bitbucket": extract_section(raw_synthesis, "For Bitbucket",
                                    ["For Compass", "For Rovo"]),
        "compass": extract_section(raw_synthesis, "For Compass",
                                  ["For Rovo", "Recommended"]),
        "rovo": extract_section(raw_synthesis, "For Rovo Dev",
                               ["Recommended", "Related"]),
        "immediate": extract_section(raw_synthesis, "Immediate",
                                    ["Near-term", "Strategic"]),
        "nearterm": extract_section(raw_synthesis, "Near-term",
                                   ["Strategic", "Related"]),
        "strategic": extract_section(raw_synthesis, "Strategic",
                                    ["Related"]),
        "related": extract_section(raw_synthesis, "Related Competitors", [])
    }

    # Clean up evidence table (just get the table part)
    evidence = sections["evidence_table"]
    if "|" in evidence:
        lines = [l for l in evidence.split("\n") if l.strip().startswith("|")]
        sections["evidence_table"] = "\n".join(lines)

    # Build final document
    model_name = CONFIG["synthesis"]["model"].split("-")[1]  # e.g., "sonnet" from "claude-sonnet-4-..."

    document = THEME_TEMPLATE.format(
        title=theme_config["title"],
        date=datetime.now().strftime("%Y-%m-%d"),
        model=model_name,
        key_question=get_key_question(theme_key),
        pattern_summary=sections["pattern_summary"] or raw_synthesis[:1500],  # Fallback
        evidence_table=sections["evidence_table"] or "| TBD | TBD | TBD |",
        jira_implications=sections["jira"] or "Analysis pending.",
        confluence_implications=sections["confluence"] or "Analysis pending.",
        bitbucket_implications=sections["bitbucket"] or "Analysis pending.",
        compass_implications=sections["compass"] or "Analysis pending.",
        rovo_implications=sections["rovo"] or "Analysis pending.",
        immediate_response=sections["immediate"] or "Analysis pending.",
        nearterm_response=sections["nearterm"] or "Analysis pending.",
        strategic_response=sections["strategic"] or "Analysis pending.",
        related_competitors=sections["related"] or "- [[Cursor]]\n- [[GitHub]]\n- [[Linear]]",
        num_competitors=len(retrieved["competitors"])
    )

    return document


def main():
    parser = argparse.ArgumentParser(description="Synthesize theme documents using Claude")
    parser.add_argument("--theme", type=str, required=True, help="Theme key or 'all'")
    parser.add_argument("--dry-run", action="store_true", help="Show context without calling API")

    args = parser.parse_args()

    # Check API key
    if not os.environ.get("ANTHROPIC_API_KEY") and not args.dry_run:
        print("Error: ANTHROPIC_API_KEY environment variable not set")
        return

    # Determine themes to process
    if args.theme == "all":
        themes = list(CONFIG["themes"].keys())
    else:
        if args.theme not in CONFIG["themes"]:
            print(f"Error: Unknown theme '{args.theme}'")
            return
        themes = [args.theme]

    # Process each theme
    for theme_key in themes:
        print(f"\n{'=' * 60}")
        print(f"Synthesizing: {CONFIG['themes'][theme_key]['title']}")
        print(f"{'=' * 60}")

        # Load retrieved data
        retrieved_path = RETRIEVED_DIR / f"{theme_key}.json"
        if not retrieved_path.exists():
            print(f"Error: No retrieved data found at {retrieved_path}")
            print("Run 02_retrieve.py first")
            continue

        with open(retrieved_path) as f:
            retrieved = json.load(f)

        print(f"Loaded {len(retrieved['competitors'])} competitors from retrieval")

        if args.dry_run:
            context = build_context(retrieved)
            print(f"\n--- Context Preview (first 2000 chars) ---\n")
            print(context[:2000])
            print(f"\n--- End Preview ---\n")
            print(f"Total context: {len(context):,} characters (~{len(context)//4:,} tokens)")
            continue

        # Synthesize
        raw_synthesis = synthesize_theme(theme_key, retrieved)

        # Parse and format
        document = parse_synthesis(raw_synthesis, theme_key, retrieved)

        # Save
        THEMES_DIR.mkdir(parents=True, exist_ok=True)
        output_path = THEMES_DIR / CONFIG["themes"][theme_key]["output_file"]

        with open(output_path, "w") as f:
            f.write(document)

        print(f"\n✅ Saved to {output_path}")

    print(f"\nDone! Theme documents are in {THEMES_DIR}/")


if __name__ == "__main__":
    main()
