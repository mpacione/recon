#!/usr/bin/env python3
"""
P4 Pipeline - Step 4: Tag competitor files with themes

This script reads the retrieval results and updates competitor markdown files
with theme tags in their frontmatter.

Usage:
    cd CompetitiveLandscape-2025
    python _Prompts/p4_pipeline/04_tag_themes.py
    python _Prompts/p4_pipeline/04_tag_themes.py --dry-run
    python _Prompts/p4_pipeline/04_tag_themes.py --threshold 0.5  # Higher = stricter

Prerequisites:
    Run 02_retrieve.py --theme all first to generate retrieval results.

Output:
    - Updates frontmatter in competitor .md files with themes: [] field
    - Creates .retrieved/theme_assignments.json summary
"""

import argparse
import json
import re
import yaml
from pathlib import Path
from collections import defaultdict

import frontmatter

# Load config
SCRIPT_DIR = Path(__file__).parent.resolve()
BASE_DIR = SCRIPT_DIR.parent.parent  # CompetitiveLandscape-2025

with open(SCRIPT_DIR / "config.yaml") as f:
    CONFIG = yaml.safe_load(f)

# Paths - relative to script location
COMPETITORS_DIR = BASE_DIR / CONFIG["paths"]["competitors_dir"]
ATLASSIAN_DIR = BASE_DIR / CONFIG["paths"]["atlassian_dir"]
RETRIEVED_DIR = SCRIPT_DIR / ".retrieved"


def load_retrieval_results() -> dict:
    """Load all theme retrieval results."""
    results = {}

    for theme_key in CONFIG["themes"].keys():
        result_path = RETRIEVED_DIR / f"{theme_key}.json"
        if result_path.exists():
            with open(result_path) as f:
                results[theme_key] = json.load(f)
        else:
            print(f"Warning: No retrieval results for {theme_key}")

    return results


def compute_theme_assignments(results: dict, top_n: int = 30, min_score: float = 0.3) -> dict:
    """
    Determine which competitors should be tagged with which themes.

    Args:
        results: Retrieval results by theme
        top_n: Number of top competitors per theme to tag
        min_score: Minimum aggregate score to qualify

    Returns:
        Dict mapping competitor name -> list of theme titles
    """
    assignments = defaultdict(list)

    for theme_key, data in results.items():
        theme_title = data["title"]

        # Get top N competitors above threshold
        for i, comp in enumerate(data["competitors"][:top_n]):
            if comp["aggregate_score"] >= min_score:
                assignments[comp["name"]].append(theme_title)

    return dict(assignments)


def update_file_frontmatter(filepath: Path, themes: list, dry_run: bool = False) -> bool:
    """Update a markdown file's frontmatter with theme tags."""
    try:
        post = frontmatter.load(filepath)
    except Exception as e:
        print(f"  Error reading {filepath.name}: {e}")
        return False

    # Get current themes (if any)
    current_themes = post.metadata.get("themes", [])

    # Merge (avoid duplicates)
    merged_themes = list(set(current_themes + themes))
    merged_themes.sort()

    if merged_themes == current_themes:
        return False  # No change needed

    if dry_run:
        print(f"  [DRY RUN] Would update {filepath.name}: {merged_themes}")
        return True

    # Update frontmatter
    post.metadata["themes"] = merged_themes

    # Write back
    with open(filepath, "w") as f:
        f.write(frontmatter.dumps(post))

    return True


def find_competitor_file(name: str) -> Path | None:
    """Find the markdown file for a competitor by name."""
    # Try exact match first
    for directory in [COMPETITORS_DIR, ATLASSIAN_DIR]:
        if not directory.exists():
            continue

        # Try exact filename match
        exact_path = directory / f"{name}.md"
        if exact_path.exists():
            return exact_path

        # Try case-insensitive search
        for filepath in directory.glob("*.md"):
            try:
                post = frontmatter.load(filepath)
                if post.metadata.get("name", "").lower() == name.lower():
                    return filepath
            except:
                continue

    return None


def main():
    parser = argparse.ArgumentParser(description="Tag competitor files with themes")
    parser.add_argument("--dry-run", action="store_true", help="Show changes without writing")
    parser.add_argument("--top-n", type=int, default=30, help="Tag top N competitors per theme (default: 30)")
    parser.add_argument("--threshold", type=float, default=0.3, help="Minimum score to tag (default: 0.3)")

    args = parser.parse_args()

    print("=" * 60)
    print("P4 Pipeline - Step 4: Theme Tagging")
    print("=" * 60)

    # Load retrieval results
    results = load_retrieval_results()
    if not results:
        print("Error: No retrieval results found. Run 02_retrieve.py --theme all first.")
        return

    print(f"Loaded results for {len(results)} themes")

    # Compute assignments
    assignments = compute_theme_assignments(results, args.top_n, args.threshold)
    print(f"Computed theme assignments for {len(assignments)} competitors")

    # Theme distribution
    theme_counts = defaultdict(int)
    for themes in assignments.values():
        for theme in themes:
            theme_counts[theme] += 1

    print("\nTheme distribution:")
    for theme, count in sorted(theme_counts.items()):
        print(f"  {theme}: {count} competitors")

    # Update files
    print(f"\n{'[DRY RUN] ' if args.dry_run else ''}Updating competitor files...")

    updated = 0
    not_found = []

    for name, themes in assignments.items():
        filepath = find_competitor_file(name)

        if filepath is None:
            not_found.append(name)
            continue

        if update_file_frontmatter(filepath, themes, args.dry_run):
            updated += 1
            if not args.dry_run:
                print(f"  ✓ {filepath.name}: {themes}")

    # Summary
    print(f"\n{'─' * 60}")
    print(f"Updated: {updated} files")
    print(f"Not found: {len(not_found)} competitors")

    if not_found:
        print("\nCompetitors not found (may need manual check):")
        for name in not_found[:10]:
            print(f"  - {name}")
        if len(not_found) > 10:
            print(f"  ... and {len(not_found) - 10} more")

    # Save assignment summary
    if not args.dry_run:
        summary = {
            "parameters": {
                "top_n": args.top_n,
                "threshold": args.threshold
            },
            "theme_counts": dict(theme_counts),
            "assignments": assignments,
            "not_found": not_found
        }

        summary_path = RETRIEVED_DIR / "theme_assignments.json"
        with open(summary_path, "w") as f:
            json.dump(summary, f, indent=2)

        print(f"\n✅ Saved assignment summary to {summary_path}")


if __name__ == "__main__":
    main()
