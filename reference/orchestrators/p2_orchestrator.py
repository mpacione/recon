#!/usr/bin/env python3
"""
Orchestrator for parallel competitor profile cleanup.

Usage:
    python orchestrator.py --workers 10 --dry-run
    python orchestrator.py --workers 10
    python orchestrator.py --workers 10 --file "Linear.md"  # Single file test

Requirements:
    pip install anthropic aiofiles

Environment:
    ANTHROPIC_API_KEY must be set
"""

import asyncio
import json
import os
import re
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
PROMPTS_DIR = BASE_DIR / "_Prompts"
SCHEMA_FILE = PROMPTS_DIR / "_Schema.md"
WORKER_PROMPT_FILE = SCRIPT_DIR / "worker_prompt.md"
PROCESSED_LOG = SCRIPT_DIR / "processed.json"
RESULTS_LOG = SCRIPT_DIR / "results.json"

MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 8192


def load_worker_prompt() -> str:
    """Load the worker prompt template."""
    with open(WORKER_PROMPT_FILE, "r") as f:
        return f.read()


def load_schema() -> str:
    """Load the canonical schema."""
    with open(SCHEMA_FILE, "r") as f:
        return f.read()


def get_all_competitor_files() -> list[Path]:
    """Get all .md files in the Competitors directory."""
    return sorted(COMPETITORS_DIR.glob("*.md"))


def is_p2_complete(filepath: Path) -> bool:
    """Check if file already has research_status: p2-complete or higher."""
    with open(filepath, "r") as f:
        content = f.read()
    # Check for p2-complete or any higher status (p3-complete, p3_5-complete)
    return any(status in content for status in [
        "research_status: p2-complete",
        "research_status: p3-complete",
        "research_status: p3_5-complete"
    ])


def load_processed() -> dict:
    """Load the processed files log."""
    if PROCESSED_LOG.exists():
        with open(PROCESSED_LOG, "r") as f:
            return json.load(f)
    return {"processed": [], "results": []}


def save_processed(data: dict):
    """Save the processed files log."""
    PROCESSED_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(PROCESSED_LOG, "w") as f:
        json.dump(data, f, indent=2)


async def process_file(
    client: anthropic.AsyncAnthropic,
    filepath: Path,
    worker_prompt: str,
    schema: str,
    dry_run: bool = False
) -> dict:
    """Process a single competitor file."""

    filename = filepath.name
    relative_path = str(filepath)

    # Read the file content
    with open(filepath, "r") as f:
        file_content = f.read()

    # Build the prompt
    prompt = worker_prompt.replace("{{FILEPATH}}", relative_path)

    system_prompt = f"""You are a formatting cleanup agent. You will be given a competitor profile file and must fix formatting issues according to the schema.

## Canonical Schema

{schema}

## Instructions

1. Read the file content provided
2. Identify formatting issues (see worker prompt for specific issues)
3. Fix the formatting while preserving all content
4. Return the corrected file content AND a JSON report

IMPORTANT: Return your response in this exact format:

<corrected_file>
[The entire corrected file content goes here]
</corrected_file>

<report>
{{
  "file": "{relative_path}",
  "status": "fixed" | "already_compliant" | "error",
  "issues_found": ["list of issues"],
  "issues_fixed": ["list of fixes"],
  "error_message": null
}}
</report>
"""

    user_message = f"""## Worker Instructions

{prompt}

## File Content to Process

```markdown
{file_content}
```

Process this file and return the corrected content plus JSON report."""

    if dry_run:
        print(f"  [DRY RUN] Would process: {filename}")
        return {
            "file": relative_path,
            "status": "dry_run",
            "issues_found": [],
            "issues_fixed": [],
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

            # Ensure research_status is set to p2-complete (safety net)
            if "research_status:" in corrected_content:
                # Replace any existing status with p2-complete
                corrected_content = re.sub(
                    r'research_status:\s*\S+',
                    'research_status: p2-complete',
                    corrected_content,
                    count=1
                )

            # Write the corrected file
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
                "issues_found": [],
                "issues_fixed": [],
                "error_message": "Could not parse report from response"
            }

        return report

    except Exception as e:
        return {
            "file": relative_path,
            "status": "error",
            "issues_found": [],
            "issues_fixed": [],
            "error_message": str(e)
        }


async def run_batch(
    files: list[Path],
    max_workers: int,
    dry_run: bool = False
):
    """Run cleanup on a batch of files with controlled concurrency."""

    client = anthropic.AsyncAnthropic()
    worker_prompt = load_worker_prompt()
    schema = load_schema()
    processed_data = load_processed()

    # Filter out files already at p2-complete or higher (check file content)
    not_p2_complete = [f for f in files if not is_p2_complete(f)]
    print(f"Files needing P2: {len(not_p2_complete)} / {len(files)} total")

    # Also filter out files in processed log (use filename as key for reliability)
    already_processed = set(processed_data["processed"])
    files_to_process = [f for f in not_p2_complete if f.name not in already_processed]

    if not files_to_process:
        print("All files already at p2-complete or processed!")
        return

    print(f"Files to process: {len(files_to_process)}")
    print(f"Already p2-complete: {len(files) - len(not_p2_complete)}")
    print(f"In processed log: {len(already_processed)}")
    print(f"Max workers: {max_workers}")
    print(f"Dry run: {dry_run}")
    print("-" * 50)

    semaphore = asyncio.Semaphore(max_workers)

    async def process_with_semaphore(filepath: Path) -> dict:
        async with semaphore:
            print(f"Processing: {filepath.name}")
            result = await process_file(client, filepath, worker_prompt, schema, dry_run)
            print(f"  Result: {result['status']} - {len(result.get('issues_fixed', []))} fixes")
            return result

    # Process all files concurrently (respecting semaphore)
    tasks = [process_with_semaphore(f) for f in files_to_process]
    results = await asyncio.gather(*tasks)

    # Update processed log (store filename only for reliable matching)
    for result in results:
        if result["status"] != "error":
            # Store just filename, not full path
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
    print("SUMMARY")
    print("=" * 50)

    fixed = [r for r in results if r["status"] == "fixed"]
    compliant = [r for r in results if r["status"] == "already_compliant"]
    errors = [r for r in results if r["status"] == "error"]

    print(f"Fixed: {len(fixed)}")
    print(f"Already compliant: {len(compliant)}")
    print(f"Errors: {len(errors)}")

    if errors:
        print("\nErrors:")
        for e in errors:
            print(f"  - {e['file']}: {e['error_message']}")

    # Issue summary
    all_issues = []
    all_sources_added = []
    for r in fixed:
        all_issues.extend(r.get("issues_found", []))
        all_sources_added.extend(r.get("sources_added", []))

    if all_issues:
        print(f"\nTotal issues fixed: {len(all_issues)}")
        # Count issue types
        from collections import Counter
        issue_counts = Counter(all_issues)
        for issue, count in issue_counts.most_common(10):
            print(f"  - {issue}: {count}")

    if all_sources_added:
        print(f"\nNew sources added: {len(all_sources_added)}")
        for src in all_sources_added[:10]:  # Show first 10
            print(f"  - {src}")


def main():
    parser = argparse.ArgumentParser(description="Orchestrate competitor profile cleanup")
    parser.add_argument("--workers", type=int, default=10, help="Max concurrent workers")
    parser.add_argument("--dry-run", action="store_true", help="Don't actually process files")
    parser.add_argument("--file", type=str, help="Process a single file (for testing)")
    parser.add_argument("--reset", action="store_true", help="Reset processed log and start fresh")

    args = parser.parse_args()

    if args.reset and PROCESSED_LOG.exists():
        os.remove(PROCESSED_LOG)
        print("Reset processed log")

    if args.file:
        files = [COMPETITORS_DIR / args.file]
        if not files[0].exists():
            print(f"File not found: {files[0]}")
            sys.exit(1)
    else:
        files = get_all_competitor_files()

    print(f"Found {len(files)} competitor files")

    asyncio.run(run_batch(files, args.workers, args.dry_run))


if __name__ == "__main__":
    main()
