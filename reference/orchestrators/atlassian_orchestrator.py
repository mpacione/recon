#!/usr/bin/env python3
"""
Orchestrator for Atlassian product profile research.

Researches Atlassian products from an EXTERNAL perspective—how the market sees us,
not internal metrics. Treats Atlassian products the same way we research competitors.

Usage:
    python atlassian_orchestrator.py --workers 3 --dry-run
    python atlassian_orchestrator.py --workers 3
    python atlassian_orchestrator.py --file "Jira.md"

Requirements:
    pip install anthropic

Environment:
    ANTHROPIC_API_KEY must be set
"""

import asyncio
import json
import os
import sys
import argparse
from pathlib import Path
from datetime import datetime
import anthropic

# Configuration
ATLASSIAN_DIR = Path("Competitors/CompetitiveLandscape-2025/Atlassian")
COMPETITORS_DIR = Path("Competitors/CompetitiveLandscape-2025/Competitors")
PROMPTS_DIR = Path("Competitors/CompetitiveLandscape-2025/_Prompts")
SCHEMA_FILE = PROMPTS_DIR / "_Schema.md"
ATLASSIAN_TEMPLATE_FILE = PROMPTS_DIR / "_AtlassianProductTemplate.md"
ATLASSIAN_PROCESSED_LOG = PROMPTS_DIR / "_BatchCleanup/atlassian_processed.json"

MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 16384  # Larger for research + full file rewrite


def load_schema() -> str:
    """Load the canonical schema."""
    with open(SCHEMA_FILE, "r") as f:
        return f.read()


def load_template() -> str:
    """Load the Atlassian product template."""
    with open(ATLASSIAN_TEMPLATE_FILE, "r") as f:
        return f.read()


def get_atlassian_files() -> list[Path]:
    """Get all .md files in the Atlassian directory."""
    return sorted(ATLASSIAN_DIR.glob("*.md"))


def load_competitor_profiles(product_name: str, top_competitors: list[str]) -> str:
    """Load competitor profiles for context."""
    profiles = []
    for comp_name in top_competitors:
        comp_file = COMPETITORS_DIR / f"{comp_name}.md"
        if comp_file.exists():
            with open(comp_file, "r") as f:
                content = f.read()
                # Truncate to key sections to save tokens
                profiles.append(f"### {comp_name}\n\n{content[:3000]}...\n")
    return "\n".join(profiles) if profiles else "No competitor profiles found."


def extract_top_competitors(file_content: str) -> list[str]:
    """Extract top_competitors from frontmatter."""
    competitors = []
    for line in file_content.split("\n"):
        if line.startswith("top_competitors:"):
            # Parse YAML list: ["Cursor", "GitHub Copilot", "Devin"]
            import re
            matches = re.findall(r'"([^"]+)"', line)
            competitors = matches
            break
    return competitors


def load_processed() -> dict:
    """Load the processed files log."""
    if ATLASSIAN_PROCESSED_LOG.exists():
        with open(ATLASSIAN_PROCESSED_LOG, "r") as f:
            return json.load(f)
    return {"processed": [], "results": []}


def save_processed(data: dict):
    """Save the processed files log."""
    ATLASSIAN_PROCESSED_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(ATLASSIAN_PROCESSED_LOG, "w") as f:
        json.dump(data, f, indent=2)


async def process_file(
    client: anthropic.AsyncAnthropic,
    filepath: Path,
    schema: str,
    template: str,
    dry_run: bool = False
) -> dict:
    """Process a single Atlassian product file."""

    filename = filepath.name
    relative_path = str(filepath)
    product_name = filename.replace(".md", "")

    # Read the file content
    with open(filepath, "r") as f:
        file_content = f.read()

    # Get top competitors for context
    top_competitors = extract_top_competitors(file_content)
    competitor_context = load_competitor_profiles(product_name, top_competitors)

    system_prompt = f"""You are a competitive intelligence researcher analyzing Atlassian products from an EXTERNAL perspective.

## CRITICAL: External View Only

Research this Atlassian product the SAME WAY you would research a competitor:
- Use public sources: G2 reviews, HN discussions, Reddit, Twitter, product docs
- Be HONEST about weaknesses and gaps
- Include real developer sentiment (positive AND negative)
- Compare objectively against competitors
- Do NOT use insider knowledge or assume internal metrics

The goal is to see Atlassian products as customers see them, not as Atlassian sees itself.

## Canonical Schema

{schema}

## Atlassian Product Template

{template}

## Top Competitor Profiles (for comparison context)

{competitor_context}

## Research Queries to Run

For {product_name}, search:
- site:news.ycombinator.com "{product_name}"
- site:reddit.com "{product_name}" review
- site:g2.com "{product_name}"
- "{product_name} vs {top_competitors[0] if top_competitors else 'alternatives'}"
- "{product_name}" developer experience 2025
- "{product_name}" complaints OR frustrations OR issues

## What to Research

1. **Capabilities**: Rate honestly vs market (not marketing claims)
2. **Developer Love**: Real external sentiment—include criticisms
3. **Head-to-Head**: Objective comparison with top competitors
4. **Gap Analysis**: Where competitors genuinely beat us
5. **Talking Points**: Honest "what keeps us up at night"

Return your response in this exact format:

<corrected_file>
[The entire researched file content goes here]
</corrected_file>

<report>
{{
  "file": "{relative_path}",
  "status": "researched" | "insufficient_data" | "error",
  "sentiment_found": "🟢 Positive" | "🟡 Mixed" | "🔴 Negative",
  "quotes_added": 3,
  "gaps_identified": ["list of gaps vs competitors"],
  "sources_added": ["list of sources"],
  "error_message": null
}}
</report>
"""

    user_message = f"""## Atlassian Product to Research

**Product**: {product_name}
**File**: {relative_path}
**Top Competitors**: {', '.join(top_competitors) if top_competitors else 'See file'}

## Current File Content (scaffold)

```markdown
{file_content}
```

Research this Atlassian product from an external perspective. Fill in all 🔍 placeholders with real data from public sources. Be honest about gaps and weaknesses."""

    if dry_run:
        print(f"  [DRY RUN] Would process: {filename}")
        return {
            "file": relative_path,
            "status": "dry_run",
            "sentiment_found": None,
            "quotes_added": 0,
            "gaps_identified": [],
            "sources_added": [],
            "error_message": None
        }

    try:
        response = await client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}]
        )

        response_text = response.content[0].text

        # Parse the corrected file
        if "<corrected_file>" in response_text and "</corrected_file>" in response_text:
            corrected_start = response_text.index("<corrected_file>") + len("<corrected_file>")
            corrected_end = response_text.index("</corrected_file>")
            corrected_content = response_text[corrected_start:corrected_end].strip()

            # Write the researched file
            with open(filepath, "w") as f:
                f.write(corrected_content)

        # Parse the report
        if "<report>" in response_text and "</report>" in response_text:
            report_start = response_text.index("<report>") + len("<report>")
            report_end = response_text.index("</report>")
            report_json = response_text[report_start:report_end].strip()
            report = json.loads(report_json)
        else:
            report = {
                "file": relative_path,
                "status": "error",
                "sentiment_found": None,
                "quotes_added": 0,
                "gaps_identified": [],
                "sources_added": [],
                "error_message": "Could not parse report from response"
            }

        return report

    except Exception as e:
        return {
            "file": relative_path,
            "status": "error",
            "sentiment_found": None,
            "quotes_added": 0,
            "gaps_identified": [],
            "sources_added": [],
            "error_message": str(e)
        }


async def run_batch(
    files: list[Path],
    max_workers: int,
    dry_run: bool = False
):
    """Run research on Atlassian product files with controlled concurrency."""

    client = anthropic.AsyncAnthropic()
    schema = load_schema()
    template = load_template()
    processed_data = load_processed()

    # Filter out already processed files
    already_processed = set(processed_data["processed"])
    files_to_process = [f for f in files if str(f) not in already_processed]

    if not files_to_process:
        print("All Atlassian product files already processed!")
        return

    print(f"Atlassian products to research: {len(files_to_process)}")
    print(f"Already processed: {len(already_processed)}")
    print(f"Max workers: {max_workers}")
    print(f"Dry run: {dry_run}")
    print("-" * 50)

    semaphore = asyncio.Semaphore(max_workers)

    async def process_with_semaphore(filepath: Path) -> dict:
        async with semaphore:
            print(f"Researching: {filepath.name}")
            result = await process_file(client, filepath, schema, template, dry_run)
            status = result.get('status', 'unknown')
            sentiment = result.get('sentiment_found', 'N/A')
            gaps = len(result.get('gaps_identified', []))
            print(f"  → {status} | Sentiment: {sentiment} | Gaps: {gaps}")
            return result

    # Process all files concurrently (respecting semaphore)
    tasks = [process_with_semaphore(f) for f in files_to_process]
    results = await asyncio.gather(*tasks)

    # Update processed log
    for result in results:
        if result["status"] not in ["error", "dry_run"]:
            processed_data["processed"].append(result["file"])
        processed_data["results"].append({
            **result,
            "timestamp": datetime.now().isoformat()
        })

    if not dry_run:
        save_processed(processed_data)

    # Summary
    print("\n" + "=" * 50)
    print("ATLASSIAN PRODUCT RESEARCH SUMMARY")
    print("=" * 50)

    researched = [r for r in results if r["status"] == "researched"]
    insufficient = [r for r in results if r["status"] == "insufficient_data"]
    errors = [r for r in results if r["status"] == "error"]

    print(f"Researched: {len(researched)}")
    print(f"Insufficient data: {len(insufficient)}")
    print(f"Errors: {len(errors)}")

    if errors:
        print("\nErrors:")
        for e in errors:
            print(f"  - {e['file']}: {e['error_message']}")

    # Sentiment breakdown
    sentiment_counts = {"🟢 Positive": 0, "🟡 Mixed": 0, "🔴 Negative": 0}
    for r in researched:
        s = r.get("sentiment_found")
        if s in sentiment_counts:
            sentiment_counts[s] += 1

    print(f"\nExternal sentiment on Atlassian products:")
    for sentiment, count in sentiment_counts.items():
        print(f"  {sentiment}: {count}")

    # Gaps summary
    all_gaps = []
    for r in researched:
        all_gaps.extend(r.get("gaps_identified", []))

    if all_gaps:
        print(f"\nTotal gaps identified: {len(all_gaps)}")
        for gap in all_gaps[:10]:
            print(f"  - {gap}")


def main():
    parser = argparse.ArgumentParser(description="Research Atlassian products from external perspective")
    parser.add_argument("--workers", type=int, default=3, help="Max concurrent workers (fewer than competitors due to research depth)")
    parser.add_argument("--dry-run", action="store_true", help="Don't actually process files")
    parser.add_argument("--file", type=str, help="Process a single file (for testing)")
    parser.add_argument("--reset", action="store_true", help="Reset processed log and start fresh")

    args = parser.parse_args()

    if args.reset and ATLASSIAN_PROCESSED_LOG.exists():
        os.remove(ATLASSIAN_PROCESSED_LOG)
        print("Reset Atlassian processed log")

    if args.file:
        files = [ATLASSIAN_DIR / args.file]
        if not files[0].exists():
            print(f"File not found: {files[0]}")
            sys.exit(1)
    else:
        files = get_atlassian_files()

    print(f"Found {len(files)} Atlassian product files")

    asyncio.run(run_batch(files, args.workers, args.dry_run))


if __name__ == "__main__":
    main()
