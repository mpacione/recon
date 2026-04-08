#!/usr/bin/env python3
"""
P4.5 Pipeline - Distill Deep Synthesis to Reviewable Summaries

Reads the deep synthesis files (*_deep.md) and distills each into a
tight, executive-friendly summary focused on:
- What keeps us up at night
- Our advantages / disadvantages
- Out of left field competitors
- Talking points for facilitation

Usage:
    python _Prompts/p4_pipeline/06_distill.py --theme agentic_shift
    python _Prompts/p4_pipeline/06_distill.py --theme all

Output:
    Themes/_AgenticShift_distilled.md (etc.)

Cost estimate: ~$1-2 per theme with Opus (single focused pass)
"""

import argparse
import re
import yaml
from pathlib import Path
from datetime import datetime

import anthropic
import frontmatter

# Load config
SCRIPT_DIR = Path(__file__).parent.resolve()
BASE_DIR = SCRIPT_DIR.parent.parent

with open(SCRIPT_DIR / "config.yaml") as f:
    CONFIG = yaml.safe_load(f)

THEMES_DIR = BASE_DIR / CONFIG["paths"]["themes_dir"]
COMPETITORS_DIR = BASE_DIR / CONFIG["paths"]["competitors_dir"]


def load_competitor_urls() -> dict:
    """Load demo_url from all competitor files."""
    urls = {}
    for filepath in COMPETITORS_DIR.glob("*.md"):
        try:
            post = frontmatter.load(filepath)
            name = post.metadata.get("name", filepath.stem)
            demo_url = post.metadata.get("demo_url", "")
            if demo_url:
                urls[name.lower()] = demo_url
                # Also store by filename stem for matching
                urls[filepath.stem.lower()] = demo_url
        except Exception:
            pass
    return urls


def get_demo_links(competitors: list, out_of_left_field: list, url_lookup: dict) -> str:
    """Generate demo links table rows for competitors."""
    links = []
    seen = set()

    # Gather all competitor names
    all_competitors = []
    for c in competitors:
        if c.get("name"):
            all_competitors.append(c["name"])
    for c in out_of_left_field:
        if c.get("name"):
            all_competitors.append(c["name"])

    for name in all_competitors:
        if name.lower() in seen:
            continue
        seen.add(name.lower())

        # Try to find URL
        url = url_lookup.get(name.lower(), "")
        if not url:
            # Try with common variations
            url = url_lookup.get(name.lower().replace(" ", ""), "")
        if not url:
            url = url_lookup.get(name.lower().replace(".", ""), "")

        if url:
            links.append(f"| {name} | {url} |")
        else:
            links.append(f"| {name} | *URL not found* |")

    return "\n".join(links)


def get_distill_system():
    """Generate system prompt with current date."""
    today = datetime.now()
    current_month = today.strftime("%B %Y")
    current_year = today.year

    return f"""You are a strategic advisor distilling competitive analysis for a VP-level leadership meeting.

Your task: Take a detailed analytical document and extract the essential insights into a tight, talkable format.

The VP wants to:
1. Walk through competitors live (tabs open, toggling between them)
2. Facilitate discussion about "what keeps us up at night"
3. Build shared language/POV on the competitive landscape
4. Cover 3 product areas in 90 minutes total

Your output must be:
- Punchy, not academic
- Specific, not abstract ("Backstage has 89% share" not "competitors are gaining traction")
- Two-sided (advantages AND disadvantages)
- Talkable (talking points are questions/provocations, not conclusions)
- Honest about "out of left field" players that should be on radar

CRITICAL - Acquisition language:
- NEVER casually recommend "acquire X" - corp dev is complex and requires extensive due diligence
- Frame as CAPABILITY GAPS first (e.g., "L3+ code generation capability gap")
- If mentioning specific companies as potential solutions, use softer language:
  - "worth evaluating if exploring inorganic options"
  - "potential candidate for further diligence"
  - "companies addressing this gap include X, Y, Z"
- The insight is the GAP, not the M&A prescription

CRITICAL - Date awareness:
- Today's date is {current_month}
- Any dates before {current_month} have ALREADY PASSED
- Do NOT use past dates as future deadlines (e.g., don't say "by Q3 {current_year - 1}")
- If source material mentions past dates, either:
  - Update to a realistic future timeframe (e.g., "within 6 months", "by Q3 {current_year}")
  - Reframe as current state (e.g., "Linear already shipped agent teammates" not "Linear shipping in July {current_year - 1}")
- Use relative timeframes when possible ("within 90 days", "next 12 months")

Write in a direct, confident voice. No hedging. No "it's worth noting." Just the insight."""


DISTILL_TEMPLATE = """# {title}
> {subtitle}

**One-liner:** {one_liner}

## The Shift
{the_shift}

## What Keeps Us Up at Night
{keeps_us_up}

## Our Position

**Advantages**
{our_advantage}

**Gaps**
{our_gaps}

## Competitive Landscape

| Competitor | Threat | Why It Matters |
|------------|--------|----------------|
{competitive_landscape}

### Out of Left Field
| Competitor | Why They Matter |
|------------|-----------------|
{out_of_left_field}

## Impact by Product

| Product | Risk | What Changes |
|---------|------|--------------|
{product_impact}

## Key Questions
{key_questions}

## Demo Links
| Competitor | URL |
|------------|-----|
{demo_links}

---
**Threat Level:** {threat_level} | **Confidence:** {confidence}

**One Thing to Remember:** {one_thing}
"""


def distill_theme(theme_key: str) -> dict:
    """Distill a deep synthesis file into structured summary."""

    theme_config = CONFIG["themes"][theme_key]
    filename = theme_config["output_file"].replace(".md", "_deep.md")
    deep_path = THEMES_DIR / filename

    if not deep_path.exists():
        print(f"  Error: {deep_path.name} not found. Run deep synthesis first.")
        return None

    # Read the deep synthesis
    deep_content = deep_path.read_text()

    # Build the prompt
    user_prompt = f"""## Source Document

{deep_content}

---

## Your Task

Distill this into the following structure. Be specific and punchy. Extract the best insights, don't summarize everything.

Respond with ONLY the following fields, one per line, using the exact format shown:

TITLE: [Theme title, e.g., "Platform Wars"]
SUBTITLE: [Short descriptor, e.g., "Who Owns the Orchestration Layer"]
ONE_LINER: [One sentence that captures the strategic essence - make it memorable]

THE_SHIFT: [2-3 sentences explaining what's changing, why it matters, why now. Set context before the fear.]

KEEPS_US_UP_1: [First thing that should worry Atlassian leadership - be specific with numbers/names]
KEEPS_US_UP_2: [Second thing]
KEEPS_US_UP_3: [Third thing]

ADVANTAGE_1: [First genuine advantage Atlassian has]
ADVANTAGE_2: [Second advantage]
ADVANTAGE_3: [Third advantage]

GAP_1: [First honest capability gap - frame as gap, not "disadvantage"]
GAP_2: [Second gap]
GAP_3: [Third gap]

COMPETITOR_1_NAME: [Top competitor name]
COMPETITOR_1_THREAT: [Critical/High/Medium]
COMPETITOR_1_WHY: [One sentence - why this competitor matters for this theme]
COMPETITOR_2_NAME: [Second competitor]
COMPETITOR_2_THREAT: [Critical/High/Medium]
COMPETITOR_2_WHY: [One sentence]
COMPETITOR_3_NAME: [Third competitor]
COMPETITOR_3_THREAT: [Critical/High/Medium]
COMPETITOR_3_WHY: [One sentence]
COMPETITOR_4_NAME: [Fourth competitor]
COMPETITOR_4_THREAT: [Critical/High/Medium]
COMPETITOR_4_WHY: [One sentence]
COMPETITOR_5_NAME: [Fifth competitor]
COMPETITOR_5_THREAT: [Critical/High/Medium]
COMPETITOR_5_WHY: [One sentence]

OUT_OF_LEFT_FIELD_1_NAME: [Surprise competitor name]
OUT_OF_LEFT_FIELD_1_WHY: [One sentence on why they matter - the surprise factor]
OUT_OF_LEFT_FIELD_2_NAME: [Second surprise competitor]
OUT_OF_LEFT_FIELD_2_WHY: [One sentence on why they matter]

PRODUCT_1_NAME: [Atlassian product most impacted]
PRODUCT_1_RISK: [Critical/High/Medium]
PRODUCT_1_CHANGE: [One sentence - what specifically changes for this product, why fear is warranted]
PRODUCT_2_NAME: [Second product]
PRODUCT_2_RISK: [Critical/High/Medium]
PRODUCT_2_CHANGE: [One sentence]
PRODUCT_3_NAME: [Third product]
PRODUCT_3_RISK: [Critical/High/Medium]
PRODUCT_3_CHANGE: [One sentence]

KEY_QUESTION_1: [Strategic question for leadership discussion - provocative, not rhetorical]
KEY_QUESTION_2: [Second question]
KEY_QUESTION_3: [Third question]

THREAT_LEVEL: [Critical / High / Medium / Low]
CONFIDENCE: [High / Medium / Low - how confident are we in this analysis]

ONE_THING: [The single most important takeaway - what must they remember]"""

    client = anthropic.Anthropic()

    print(f"  Calling Claude to distill...")

    # Use streaming for long content
    output_parts = []
    with client.messages.stream(
        model=CONFIG["synthesis"]["model"],
        max_tokens=2000,
        temperature=0.1,  # Low temp for extraction
        system=get_distill_system(),
        messages=[{"role": "user", "content": user_prompt}]
    ) as stream:
        for text in stream.text_stream:
            output_parts.append(text)

    response_text = "".join(output_parts)

    # Parse the structured response
    return parse_distill_response(response_text, theme_config)


def parse_distill_response(response: str, theme_config: dict) -> dict:
    """Parse the structured response into a dict."""

    def extract(key: str, default: str = "") -> str:
        for line in response.split("\n"):
            if line.startswith(f"{key}:"):
                return line[len(key)+1:].strip()
        return default

    return {
        "title": extract("TITLE", theme_config["title"]),
        "subtitle": extract("SUBTITLE", ""),
        "one_liner": extract("ONE_LINER", ""),
        "the_shift": extract("THE_SHIFT", ""),
        "keeps_us_up": [
            extract("KEEPS_US_UP_1"),
            extract("KEEPS_US_UP_2"),
            extract("KEEPS_US_UP_3"),
        ],
        "advantages": [
            extract("ADVANTAGE_1"),
            extract("ADVANTAGE_2"),
            extract("ADVANTAGE_3"),
        ],
        "gaps": [
            extract("GAP_1"),
            extract("GAP_2"),
            extract("GAP_3"),
        ],
        "competitors": [
            {"name": extract("COMPETITOR_1_NAME"), "threat": extract("COMPETITOR_1_THREAT"), "why": extract("COMPETITOR_1_WHY")},
            {"name": extract("COMPETITOR_2_NAME"), "threat": extract("COMPETITOR_2_THREAT"), "why": extract("COMPETITOR_2_WHY")},
            {"name": extract("COMPETITOR_3_NAME"), "threat": extract("COMPETITOR_3_THREAT"), "why": extract("COMPETITOR_3_WHY")},
            {"name": extract("COMPETITOR_4_NAME"), "threat": extract("COMPETITOR_4_THREAT"), "why": extract("COMPETITOR_4_WHY")},
            {"name": extract("COMPETITOR_5_NAME"), "threat": extract("COMPETITOR_5_THREAT"), "why": extract("COMPETITOR_5_WHY")},
        ],
        "out_of_left_field": [
            {"name": extract("OUT_OF_LEFT_FIELD_1_NAME"), "why": extract("OUT_OF_LEFT_FIELD_1_WHY")},
            {"name": extract("OUT_OF_LEFT_FIELD_2_NAME"), "why": extract("OUT_OF_LEFT_FIELD_2_WHY")},
        ],
        "product_impact": [
            {"name": extract("PRODUCT_1_NAME"), "risk": extract("PRODUCT_1_RISK"), "change": extract("PRODUCT_1_CHANGE")},
            {"name": extract("PRODUCT_2_NAME"), "risk": extract("PRODUCT_2_RISK"), "change": extract("PRODUCT_2_CHANGE")},
            {"name": extract("PRODUCT_3_NAME"), "risk": extract("PRODUCT_3_RISK"), "change": extract("PRODUCT_3_CHANGE")},
        ],
        "key_questions": [
            extract("KEY_QUESTION_1"),
            extract("KEY_QUESTION_2"),
            extract("KEY_QUESTION_3"),
        ],
        "threat_level": extract("THREAT_LEVEL", "High"),
        "confidence": extract("CONFIDENCE", "Medium"),
        "one_thing": extract("ONE_THING"),
    }


def render_distilled(data: dict, url_lookup: dict) -> str:
    """Render the distilled data to markdown."""

    # Format lists
    keeps_us_up = "\n".join(f"- {item}" for item in data["keeps_us_up"] if item)
    our_advantage = "\n".join(f"- {item}" for item in data["advantages"] if item)
    our_gaps = "\n".join(f"- {item}" for item in data["gaps"] if item)

    # Competitive landscape table
    competitive_landscape = "\n".join(
        f"| {c['name']} | {c['threat']} | {c['why']} |"
        for c in data["competitors"] if c["name"]
    )

    out_of_left_field = "\n".join(
        f"| {item['name']} | {item['why']} |"
        for item in data["out_of_left_field"] if item["name"]
    )

    # Product impact table
    product_impact = "\n".join(
        f"| {p['name']} | {p['risk']} | {p['change']} |"
        for p in data["product_impact"] if p["name"]
    )

    key_questions = "\n".join(f"- {item}" for item in data["key_questions"] if item)

    # Demo links
    demo_links = get_demo_links(data["competitors"], data["out_of_left_field"], url_lookup)

    return DISTILL_TEMPLATE.format(
        title=data["title"],
        subtitle=data["subtitle"],
        one_liner=data["one_liner"],
        the_shift=data["the_shift"],
        keeps_us_up=keeps_us_up,
        our_advantage=our_advantage,
        our_gaps=our_gaps,
        competitive_landscape=competitive_landscape,
        out_of_left_field=out_of_left_field,
        product_impact=product_impact,
        key_questions=key_questions,
        demo_links=demo_links,
        threat_level=data["threat_level"],
        confidence=data["confidence"],
        one_thing=data["one_thing"],
    )


def save_distilled(theme_key: str, content: str) -> Path:
    """Save the distilled markdown."""

    theme_config = CONFIG["themes"][theme_key]
    filename = theme_config["output_file"].replace(".md", "_distilled.md")
    output_path = THEMES_DIR / filename

    output_path.write_text(content)
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Distill deep synthesis to reviewable summaries")
    parser.add_argument("--theme", required=True,
                        help="Theme key (e.g., 'agentic_shift') or 'all'")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be processed without calling API")

    args = parser.parse_args()

    print("=" * 60)
    print("P4.5 Pipeline - Distill Deep Synthesis")
    print("=" * 60)

    # Determine which themes to process
    if args.theme == "all":
        themes_to_process = list(CONFIG["themes"].keys())
    else:
        if args.theme not in CONFIG["themes"]:
            print(f"Error: Unknown theme '{args.theme}'")
            print(f"Available: {', '.join(CONFIG['themes'].keys())}")
            return
        themes_to_process = [args.theme]

    print(f"Themes to distill: {len(themes_to_process)}")

    if args.dry_run:
        for theme in themes_to_process:
            theme_config = CONFIG["themes"][theme]
            deep_file = theme_config["output_file"].replace(".md", "_deep.md")
            out_file = theme_config["output_file"].replace(".md", "_distilled.md")
            exists = (THEMES_DIR / deep_file).exists()
            print(f"  {theme}: {deep_file} → {out_file} {'✓' if exists else '✗ (missing)'}")
        return

    # Load competitor URLs for demo links
    print("Loading competitor URLs...")
    url_lookup = load_competitor_urls()
    print(f"  Found {len(url_lookup)} URLs")

    # Process each theme
    results = {}
    for theme in themes_to_process:
        theme_config = CONFIG["themes"][theme]
        print(f"\n{'='*60}")
        print(f"Distilling: {theme_config['title']}")
        print("=" * 60)

        data = distill_theme(theme)
        if data:
            markdown = render_distilled(data, url_lookup)
            output_path = save_distilled(theme, markdown)
            results[theme] = output_path
            print(f"  ✓ Saved: {output_path.name}")

    # Summary
    print(f"\n{'='*60}")
    print("DISTILLATION COMPLETE")
    print("=" * 60)
    print(f"Themes processed: {len(results)}")
    for theme, path in results.items():
        print(f"  - {theme}: {path}")


if __name__ == "__main__":
    main()
