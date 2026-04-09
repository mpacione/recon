#!/usr/bin/env python3
"""
P3.5 Orchestrator: Strategic Enrichment

Enriches competitor profiles with strategic data for theme synthesis:
- Platform & Ecosystem (marketplace, API, lock-in)
- Trust & Governance (compliance, audit, admin)
- Workflow Embedding (interaction model, context, triggers)
- Time to Value (onboarding, free tier, self-serve)

Usage:
    python p3_5_orchestrator.py --workers 5 --dry-run
    python p3_5_orchestrator.py --workers 5
    python p3_5_orchestrator.py --file "Cursor.md"
    python p3_5_orchestrator.py --priority     # High-priority competitors first
    python p3_5_orchestrator.py --l3-plus      # Only L3+ autonomy level

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
from typing import Optional
import anthropic

# Configuration - paths relative to script location
SCRIPT_DIR = Path(__file__).parent.resolve()
BASE_DIR = SCRIPT_DIR.parent.parent  # CompetitiveLandscape-2025

COMPETITORS_DIR = BASE_DIR / "Competitors"
ATLASSIAN_DIR = BASE_DIR / "Atlassian"
PROMPTS_DIR = BASE_DIR / "_Prompts"
SCHEMA_FILE = PROMPTS_DIR / "_Schema.md"
P3_5_PROMPT_FILE = PROMPTS_DIR / "_Archive/p3_5_worker_prompt.md"
P3_5_PROCESSED_LOG = PROMPTS_DIR / "_BatchCleanup/p3_5_processed.json"

MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 16384
TIMEOUT_SECONDS = 180  # Longer timeout for strategic research


def load_p3_5_prompt() -> str:
    """Load the P3.5 prompt."""
    with open(P3_5_PROMPT_FILE, "r") as f:
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


def is_p3_complete(filepath: Path) -> bool:
    """Check if file has research_status: p3-complete."""
    with open(filepath, "r") as f:
        content = f.read()
    return "research_status: p3-complete" in content


def is_p3_5_complete(filepath: Path) -> bool:
    """Check if file already has P3.5 fields."""
    with open(filepath, "r") as f:
        content = f.read()
    # Check for key P3.5 fields
    return "interaction_model:" in content and "onboarding_friction:" in content


def get_autonomy_level(filepath: Path) -> Optional[str]:
    """Extract autonomy_level from file."""
    with open(filepath, "r") as f:
        content = f.read()
    for line in content.split("\n"):
        if line.strip().startswith("autonomy_level:"):
            level = line.split(":", 1)[1].strip()
            return level
    return None


def load_processed() -> dict:
    """Load the P3.5 processed files log."""
    if P3_5_PROCESSED_LOG.exists():
        with open(P3_5_PROCESSED_LOG, "r") as f:
            return json.load(f)
    return {"processed": [], "results": []}


def save_processed(data: dict):
    """Save the P3.5 processed files log."""
    P3_5_PROCESSED_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(P3_5_PROCESSED_LOG, "w") as f:
        json.dump(data, f, indent=2)


async def process_file(
    client: anthropic.AsyncAnthropic,
    filepath: Path,
    p3_5_prompt: str,
    schema: str,
    dry_run: bool = False
) -> dict:
    """Process a single competitor file for P3.5 enrichment."""

    filename = filepath.name
    relative_path = str(filepath)

    # Read the file content
    with open(filepath, "r") as f:
        file_content = f.read()

    # Extract competitor name
    competitor_name = filename.replace(".md", "")
    for line in file_content.split("\n"):
        if line.startswith("name:"):
            competitor_name = line.split(":", 1)[1].strip().strip('"\'')
            break

    # Determine file type
    file_type = get_file_type(filepath)
    type_label = "Atlassian product" if file_type == "atlassian" else "competitor"

    system_prompt = f"""You are a strategic research agent enriching {type_label} profiles with platform, trust, workflow, and time-to-value data.

You have web search capabilities. Use them to find accurate strategic information.

## Canonical Schema

{schema}

## P3.5 Instructions

{p3_5_prompt}

## CRITICAL RULES

- Only add data you can verify—use "🔍 Needs research" if unsure
- Preserve all existing content—only add/enrich
- Be specific: "SOC2 Type II certified" not just "has compliance"
- Look for official documentation, security pages, pricing pages
- For interaction_model and trigger_pattern, watch demo videos or read docs to verify

Return your response in this exact format:

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

Research this {type_label}'s strategic positioning and enrich with P3.5 fields."""

    if dry_run:
        print(f"  [DRY RUN] Would process: {filename}")
        return {
            "file": relative_path,
            "status": "dry_run",
            "fields_added": {},
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
                "fields_added": {},
                "error_message": "Could not parse report from response"
            }

        return report

    except Exception as e:
        return {
            "file": relative_path,
            "status": "error",
            "fields_added": {},
            "error_message": str(e)
        }


async def run_batch(
    files: list[Path],
    max_workers: int,
    dry_run: bool = False,
    priority_only: bool = False,
    l3_plus_only: bool = False,
    force: bool = False
):
    """Run P3.5 enrichment on a batch of files with controlled concurrency."""

    client = anthropic.AsyncAnthropic()
    p3_5_prompt = load_p3_5_prompt()
    schema = load_schema()
    processed_data = load_processed()

    # Filter to p3-complete files
    p3_complete_files = [f for f in files if is_p3_complete(f)]
    print(f"Files at p3-complete: {len(p3_complete_files)} / {len(files)}")

    if force:
        # Force mode: process all p3-complete files regardless of P3.5 status
        not_p3_5_files = p3_complete_files
        print(f"Force mode: processing all {len(not_p3_5_files)} p3-complete files")
    else:
        # Filter out already P3.5 complete
        not_p3_5_files = [f for f in p3_complete_files if not is_p3_5_complete(f)]
        print(f"Files needing P3.5: {len(not_p3_5_files)}")

    # Filter out already processed (use filename as key for reliability) - skip if force
    already_processed = set(processed_data["processed"])
    if force:
        files_to_process = not_p3_5_files
    else:
        files_to_process = [f for f in not_p3_5_files if f.name not in already_processed]

    # Optional: L3+ filter
    if l3_plus_only:
        l3_plus_levels = {"L3", "L4", "L5"}
        files_to_process = [
            f for f in files_to_process
            if get_autonomy_level(f) in l3_plus_levels
        ]
        print(f"L3+ filter: {len(files_to_process)} files")

    # Optional: priority filter
    if priority_only:
        priority_names = {
            "Cursor", "Linear", "GitHub Copilot", "GitHub", "Devin",
            "Claude Code", "Codex", "Backstage", "Wiz", "Snyk",
            "Notion", "GitLab", "Windsurf", "Factory", "Replit",
            "Codeium", "Tabnine", "Amazon Q", "Gemini Code Assist"
        }
        files_to_process = [
            f for f in files_to_process
            if f.stem in priority_names or any(p.lower() in f.stem.lower() for p in priority_names)
        ]
        print(f"Priority filter: {len(files_to_process)} files")

    if not files_to_process:
        print("All eligible files already processed for P3.5!")
        return

    print(f"Files to process: {len(files_to_process)}")
    print(f"Already processed: {len(already_processed)}")
    print(f"Max workers: {max_workers}")
    print(f"Dry run: {dry_run}")
    print("-" * 50)

    semaphore = asyncio.Semaphore(max_workers)

    async def process_with_semaphore(filepath: Path) -> dict:
        async with semaphore:
            print(f"Processing: {filepath.name}")
            result = await process_file(client, filepath, p3_5_prompt, schema, dry_run)
            status = result.get('status', 'unknown')
            confidence = result.get('confidence', 'N/A')
            print(f"  → {status} | Confidence: {confidence}")
            return result

    # Process all files concurrently
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
    print("P3.5 STRATEGIC ENRICHMENT SUMMARY")
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

    # Field coverage
    print("\nField coverage across enriched files:")
    field_counts = {
        "interaction_model": 0,
        "onboarding_friction": 0,
        "compliance_certs": 0,
        "api_surface": 0
    }
    for r in enriched:
        fields = r.get("fields_added", {})
        for category in fields.values():
            for field in category:
                if field in field_counts:
                    field_counts[field] += 1

    for field, count in field_counts.items():
        pct = (count / len(enriched) * 100) if enriched else 0
        print(f"  {field}: {count}/{len(enriched)} ({pct:.0f}%)")


def main():
    parser = argparse.ArgumentParser(description="P3.5 Strategic Enrichment")
    parser.add_argument("--workers", type=int, default=5, help="Max concurrent workers")
    parser.add_argument("--dry-run", action="store_true", help="Don't actually process files")
    parser.add_argument("--file", type=str, help="Process a single file")
    parser.add_argument("--reset", action="store_true", help="Reset processed log")
    parser.add_argument("--force", action="store_true", help="Force reprocess even if already P3.5 complete")
    parser.add_argument("--priority", action="store_true", help="Process priority competitors first")
    parser.add_argument("--l3-plus", action="store_true", help="Only process L3+ autonomy level")
    parser.add_argument("--atlassian-only", action="store_true", help="Only Atlassian products")
    parser.add_argument("--competitors-only", action="store_true", help="Only competitors")

    args = parser.parse_args()

    if args.atlassian_only and args.competitors_only:
        print("Error: Cannot specify both --atlassian-only and --competitors-only")
        sys.exit(1)

    if args.reset and P3_5_PROCESSED_LOG.exists():
        os.remove(P3_5_PROCESSED_LOG)
        print("Reset P3.5 processed log")

    if args.file:
        competitor_path = COMPETITORS_DIR / args.file
        atlassian_path = ATLASSIAN_DIR / args.file

        if competitor_path.exists():
            files = [competitor_path]
        elif atlassian_path.exists():
            files = [atlassian_path]
        else:
            print(f"File not found: {args.file}")
            sys.exit(1)
    else:
        files = get_all_files(
            competitors_only=args.competitors_only,
            atlassian_only=args.atlassian_only
        )

    competitor_count = len([f for f in files if get_file_type(f) == "competitor"])
    atlassian_count = len([f for f in files if get_file_type(f) == "atlassian"])
    print(f"Found {len(files)} files ({competitor_count} competitors, {atlassian_count} Atlassian products)")

    asyncio.run(run_batch(
        files,
        args.workers,
        args.dry_run,
        args.priority,
        args.l3_plus,
        args.force
    ))


if __name__ == "__main__":
    main()
