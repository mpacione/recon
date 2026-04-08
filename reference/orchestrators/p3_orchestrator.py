#!/usr/bin/env python3
"""
P3 Orchestrator: Sentiment & Presentation Enrichment

Enriches competitor AND Atlassian product profiles with:
- Real developer sentiment (HN, Reddit, G2 quotes)
- Traction signals
- Presentation frontmatter (demo_url, tagline, etc.)
- Talking Points section for exec presentation

Usage:
    python p3_orchestrator.py --workers 5 --dry-run
    python p3_orchestrator.py --workers 5
    python p3_orchestrator.py --file "Cursor.md"
    python p3_orchestrator.py --atlassian-only       # Process only Atlassian products
    python p3_orchestrator.py --competitors-only    # Process only competitors

Requirements:
    pip install anthropic

Environment:
    ANTHROPIC_API_KEY must be set

Note: Uses fewer workers than P2 cleanup because each call involves web search.
"""

import asyncio
import json
import os
import sys
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional
import anthropic

# Configuration - paths relative to script location
SCRIPT_DIR = Path(__file__).parent.resolve()
BASE_DIR = SCRIPT_DIR.parent.parent  # CompetitiveLandscape-2025

COMPETITORS_DIR = BASE_DIR / "Competitors"
ATLASSIAN_DIR = BASE_DIR / "Atlassian"
PROMPTS_DIR = BASE_DIR / "_Prompts"
SCHEMA_FILE = PROMPTS_DIR / "_Schema.md"
P3_PROMPT_FILE = PROMPTS_DIR / "03_SentimentEvidence.md"  # Single source of truth
P3_PROCESSED_LOG = SCRIPT_DIR / "p3_processed.json"

MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 16384  # Larger for research + full file rewrite
TIMEOUT_SECONDS = 120  # Longer timeout for web searches


def load_p3_prompt() -> str:
    """Load the P3 prompt (single source of truth)."""
    with open(P3_PROMPT_FILE, "r") as f:
        return f.read()


def load_schema() -> str:
    """Load the canonical schema."""
    with open(SCHEMA_FILE, "r") as f:
        return f.read()


def get_competitor_files() -> list[Path]:
    """Get all .md files in the Competitors directory."""
    return sorted(COMPETITORS_DIR.glob("*.md"))


def get_atlassian_files() -> list[Path]:
    """Get all .md files in the Atlassian directory."""
    return sorted(ATLASSIAN_DIR.glob("*.md"))


def get_all_files(competitors_only: bool = False, atlassian_only: bool = False) -> list[Path]:
    """Get files from both directories, with optional filtering."""
    files = []

    if not atlassian_only:
        files.extend(get_competitor_files())

    if not competitors_only:
        files.extend(get_atlassian_files())

    return files


def get_file_type(filepath: Path) -> str:
    """Determine if file is competitor or atlassian product."""
    if ATLASSIAN_DIR in filepath.parents or filepath.parent == ATLASSIAN_DIR:
        return "atlassian"
    return "competitor"


def is_p2_complete(filepath: Path) -> bool:
    """Check if file has research_status: p2-complete."""
    with open(filepath, "r") as f:
        content = f.read()
    return "research_status: p2-complete" in content


def load_processed() -> dict:
    """Load the P3 processed files log."""
    if P3_PROCESSED_LOG.exists():
        with open(P3_PROCESSED_LOG, "r") as f:
            return json.load(f)
    return {"processed": [], "results": []}


def save_processed(data: dict):
    """Save the P3 processed files log."""
    P3_PROCESSED_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(P3_PROCESSED_LOG, "w") as f:
        json.dump(data, f, indent=2)


async def process_file(
    client: anthropic.AsyncAnthropic,
    filepath: Path,
    p3_prompt: str,
    schema: str,
    dry_run: bool = False
) -> dict:
    """Process a single competitor file for P3 enrichment."""

    filename = filepath.name
    relative_path = str(filepath)

    # Read the file content
    with open(filepath, "r") as f:
        file_content = f.read()

    # Extract competitor name from frontmatter for search queries
    competitor_name = filename.replace(".md", "")
    for line in file_content.split("\n"):
        if line.startswith("name:"):
            competitor_name = line.split(":", 1)[1].strip().strip('"\'')
            break

    # Determine file type for context-appropriate prompting
    file_type = get_file_type(filepath)
    type_label = "Atlassian product" if file_type == "atlassian" else "competitor"
    research_note = ""

    if file_type == "atlassian":
        research_note = """
## ATLASSIAN PRODUCT NOTE

This is an Atlassian internal product being assessed from an EXTERNAL perspective.
Research what real developers say about this product—complaints, frustrations, praise.
Be honest and critical. This self-assessment is only useful if it reflects real market perception."""

    system_prompt = f"""You are a sentiment research agent enriching {type_label} profiles for an executive presentation.

You have web search capabilities. Use them to find real developer sentiment.

## Canonical Schema

{schema}

## P3 Instructions

{p3_prompt}
{research_note}

## CRITICAL RULES

- Only use REAL quotes you find—never fabricate
- If you can't find sentiment data, mark status as "insufficient_data"
- Preserve all existing content—only add/enrich
- Process ONLY the file provided—do not batch

Return your response in this exact format (see "Orchestrator Output Format" in P3 instructions):

<corrected_file>
[The entire enriched file content goes here]
</corrected_file>

<report>
{{JSON report here}}
</report>
"""

    user_message = f"""## {type_label.title()} to Research

**Name**: {competitor_name}
**File**: {relative_path}
**Type**: {file_type}

## Current File Content

```markdown
{file_content}
```

Research this {type_label}'s developer sentiment and enrich the file per the P3 instructions."""

    if dry_run:
        print(f"  [DRY RUN] Would process: {filename}")
        return {
            "file": relative_path,
            "status": "dry_run",
            "sentiment_found": None,
            "quotes_added": 0,
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

            # Write the enriched file
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
                "error_message": "Could not parse report from response"
            }

        return report

    except Exception as e:
        return {
            "file": relative_path,
            "status": "error",
            "sentiment_found": None,
            "quotes_added": 0,
            "error_message": str(e)
        }


async def run_batch(
    files: list[Path],
    max_workers: int,
    dry_run: bool = False,
    priority_only: bool = False
):
    """Run P3 enrichment on a batch of files with controlled concurrency."""

    client = anthropic.AsyncAnthropic()
    p3_prompt = load_p3_prompt()
    schema = load_schema()
    processed_data = load_processed()

    # Filter to p2-complete files only
    p2_complete_files = [f for f in files if is_p2_complete(f)]

    # Count by type
    competitor_count = len([f for f in p2_complete_files if get_file_type(f) == "competitor"])
    atlassian_count = len([f for f in p2_complete_files if get_file_type(f) == "atlassian"])
    print(f"Files at p2-complete: {len(p2_complete_files)} / {len(files)} ({competitor_count} competitors, {atlassian_count} Atlassian)")

    # Filter out already processed (use filename as key for reliability)
    already_processed = set(processed_data["processed"])
    files_to_process = [f for f in p2_complete_files if f.name not in already_processed]

    if not files_to_process:
        print("All p2-complete files already processed for P3!")
        return

    # Optional: priority filtering
    if priority_only:
        # High-priority competitors to process first
        priority_names = {
            "Cursor", "Linear", "GitHub Copilot", "GitHub", "Devin",
            "Claude Code", "Codex", "Backstage", "Wiz", "Snyk",
            "Notion", "GitLab", "Windsurf", "Factory"
        }
        files_to_process = [
            f for f in files_to_process
            if f.stem in priority_names or any(p.lower() in f.stem.lower() for p in priority_names)
        ]
        print(f"Priority filter: {len(files_to_process)} files")

    print(f"Files to process: {len(files_to_process)}")
    print(f"Already processed: {len(already_processed)}")
    print(f"Max workers: {max_workers}")
    print(f"Dry run: {dry_run}")
    print("-" * 50)

    semaphore = asyncio.Semaphore(max_workers)

    async def process_with_semaphore(filepath: Path) -> dict:
        async with semaphore:
            print(f"Processing: {filepath.name}")
            result = await process_file(client, filepath, p3_prompt, schema, dry_run)
            status = result.get('status', 'unknown')
            quotes = result.get('quotes_added', 0)
            sentiment = result.get('sentiment_found', 'N/A')
            print(f"  → {status} | Sentiment: {sentiment} | Quotes: {quotes}")
            return result

    # Process all files concurrently (respecting semaphore)
    tasks = [process_with_semaphore(f) for f in files_to_process]
    results = await asyncio.gather(*tasks)

    # Update processed log
    for result in results:
        if result["status"] not in ["error", "dry_run"]:
            # Store just filename for reliable matching
            filename = Path(result["file"]).name
            if filename not in processed_data["processed"]:
                processed_data["processed"].append(filename)
        processed_data["results"].append({
            **result,
            "timestamp": datetime.now().isoformat()
        })

    if not dry_run:
        save_processed(processed_data)

    # Summary
    print("\n" + "=" * 50)
    print("P3 ENRICHMENT SUMMARY")
    print("=" * 50)

    enriched = [r for r in results if r["status"] == "enriched"]
    insufficient = [r for r in results if r["status"] == "insufficient_data"]
    already = [r for r in results if r["status"] == "already_complete"]
    errors = [r for r in results if r["status"] == "error"]

    print(f"Enriched: {len(enriched)}")
    print(f"Insufficient data: {len(insufficient)}")
    print(f"Already complete: {len(already)}")
    print(f"Errors: {len(errors)}")

    if errors:
        print("\nErrors:")
        for e in errors:
            print(f"  - {e['file']}: {e['error_message']}")

    if insufficient:
        print("\nInsufficient data (may need manual research):")
        for i in insufficient:
            print(f"  - {i['file']}")

    # Sentiment breakdown
    sentiment_counts = {"🟢 Positive": 0, "🟡 Mixed": 0, "🔴 Negative": 0}
    for r in enriched:
        s = r.get("sentiment_found")
        if s in sentiment_counts:
            sentiment_counts[s] += 1

    print(f"\nSentiment breakdown:")
    for sentiment, count in sentiment_counts.items():
        print(f"  {sentiment}: {count}")

    total_quotes = sum(r.get("quotes_added", 0) for r in enriched)
    print(f"\nTotal quotes added: {total_quotes}")


def main():
    parser = argparse.ArgumentParser(description="P3 Sentiment & Presentation Enrichment")
    parser.add_argument("--workers", type=int, default=5, help="Max concurrent workers (lower than P2 due to search)")
    parser.add_argument("--dry-run", action="store_true", help="Don't actually process files")
    parser.add_argument("--file", type=str, help="Process a single file (for testing)")
    parser.add_argument("--reset", action="store_true", help="Reset P3 processed log and start fresh")
    parser.add_argument("--priority", action="store_true", help="Process priority competitors first")
    parser.add_argument("--atlassian-only", action="store_true", help="Process only Atlassian product files")
    parser.add_argument("--competitors-only", action="store_true", help="Process only competitor files")

    args = parser.parse_args()

    if args.atlassian_only and args.competitors_only:
        print("Error: Cannot specify both --atlassian-only and --competitors-only")
        sys.exit(1)

    if args.reset and P3_PROCESSED_LOG.exists():
        os.remove(P3_PROCESSED_LOG)
        print("Reset P3 processed log")

    if args.file:
        # Check both directories for the file
        competitor_path = COMPETITORS_DIR / args.file
        atlassian_path = ATLASSIAN_DIR / args.file

        if competitor_path.exists():
            files = [competitor_path]
        elif atlassian_path.exists():
            files = [atlassian_path]
        else:
            print(f"File not found in either Competitors or Atlassian directory: {args.file}")
            sys.exit(1)
    else:
        files = get_all_files(
            competitors_only=args.competitors_only,
            atlassian_only=args.atlassian_only
        )

    # Count by type for display
    competitor_count = len([f for f in files if get_file_type(f) == "competitor"])
    atlassian_count = len([f for f in files if get_file_type(f) == "atlassian"])
    print(f"Found {len(files)} files ({competitor_count} competitors, {atlassian_count} Atlassian products)")

    asyncio.run(run_batch(files, args.workers, args.dry_run, args.priority))


if __name__ == "__main__":
    main()
