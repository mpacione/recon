# Step 0: Export Competitor Data to JSON

Run this Python script locally to generate `competitors.json` from your markdown files.

## Prerequisites

```bash
pip install pyyaml
```

## Script

Save as `export_competitors.py` and run from the `CompetitiveLandscape-2025` directory:

```python
#!/usr/bin/env python3
"""
Export competitor markdown files to JSON for the presentation app.
"""

import json
import re
import yaml
from pathlib import Path

COMPETITORS_DIR = Path("Competitors")
ATLASSIAN_DIR = Path("Atlassian")
OUTPUT_FILE = Path("competitors.json")


def parse_frontmatter(content: str) -> dict:
    """Extract YAML frontmatter from markdown."""
    match = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
    if match:
        try:
            return yaml.safe_load(match.group(1)) or {}
        except yaml.YAMLError:
            return {}
    return {}


def parse_talking_points(content: str) -> dict:
    """Extract Talking Points section from markdown."""
    talking_points = {
        "keeps_up_at_night": [],
        "their_edge": [],
        "our_edge": [],
        "discussion_prompt": ""
    }

    # Find Talking Points section
    tp_match = re.search(r'## Talking Points\s*\n(.*?)(?=\n## |\Z)', content, re.DOTALL)
    if not tp_match:
        return talking_points

    tp_content = tp_match.group(1)

    # Parse subsections
    sections = {
        "keeps_up_at_night": r'### What keeps us up at night\s*\n(.*?)(?=\n### |\Z)',
        "their_edge": r'### Their (?:competitive )?advantage\s*\n(.*?)(?=\n### |\Z)',
        "our_edge": r'### Our (?:competitive )?advantage\s*\n(.*?)(?=\n### |\Z)',
        "discussion_prompt": r'### Discussion prompt\s*\n(.*?)(?=\n### |\Z)'
    }

    for key, pattern in sections.items():
        match = re.search(pattern, tp_content, re.DOTALL | re.IGNORECASE)
        if match:
            bullets = re.findall(r'^[-*]\s*(.+)$', match.group(1), re.MULTILINE)
            if key == "discussion_prompt":
                talking_points[key] = bullets[0] if bullets else ""
            else:
                talking_points[key] = bullets

    return talking_points


def process_file(filepath: Path, file_type: str) -> dict | None:
    """Process a single markdown file."""
    with open(filepath, 'r') as f:
        content = f.read()

    frontmatter = parse_frontmatter(content)

    # Skip files without proper frontmatter
    if not frontmatter.get('name'):
        return None

    # Skip scaffolds and skipped files
    status = frontmatter.get('research_status', '')
    if status in ['scaffold', 'skipped']:
        return None

    talking_points = parse_talking_points(content)

    return {
        "id": filepath.stem.lower().replace(" ", "-"),
        "name": frontmatter.get('name', filepath.stem),
        "type": file_type,
        "tagline": frontmatter.get('tagline', ''),
        "website": frontmatter.get('website', ''),
        "threat_level": frontmatter.get('threat_level', 'Medium'),
        "autonomy_level": frontmatter.get('autonomy_level', 'L1'),
        "funding_display": frontmatter.get('funding_display', ''),
        "atlassian_overlap": frontmatter.get('atlassian_overlap', []),
        "demo_url": frontmatter.get('demo_url', frontmatter.get('website', '')),
        "demo_account": frontmatter.get('demo_account', ''),
        "logo_url": frontmatter.get('logo_url', ''),
        "out_of_left_field": frontmatter.get('out_of_left_field', False),
        "presentation_priority": frontmatter.get('presentation_priority', 3),
        "themes": frontmatter.get('themes', []),  # Theme tags from P4 synthesis

        # P3.5 Strategic fields
        "platform": {
            "marketplace_size": frontmatter.get('marketplace_size', ''),
            "api_surface": frontmatter.get('api_surface', []),
            "partner_ecosystem": frontmatter.get('partner_ecosystem', ''),
            "lock_in_signals": frontmatter.get('lock_in_signals', '')
        },
        "trust": {
            "compliance_certs": frontmatter.get('compliance_certs', []),
            "audit_capabilities": frontmatter.get('audit_capabilities', ''),
            "admin_controls": frontmatter.get('admin_controls', '')
        },
        "workflow": {
            "interaction_model": frontmatter.get('interaction_model', ''),
            "context_sources": frontmatter.get('context_sources', []),
            "trigger_pattern": frontmatter.get('trigger_pattern', '')
        },
        "time_to_value": {
            "onboarding_friction": frontmatter.get('onboarding_friction', 0),
            "time_to_first_value": frontmatter.get('time_to_first_value', ''),
            "free_tier_limits": frontmatter.get('free_tier_limits', ''),
            "self_serve": frontmatter.get('self_serve', True)
        },

        # Engineering Evolution fields
        "engineering_evolution": {
            "left_of_code_value": frontmatter.get('left_of_code_value', []),
            "right_of_code_value": frontmatter.get('right_of_code_value', []),
            "alignment_artifact_support": frontmatter.get('alignment_artifact_support', ''),
            "conductor_model_fit": frontmatter.get('conductor_model_fit', ''),
            "decision_trace_capability": frontmatter.get('decision_trace_capability', '')
        },

        "talking_points": talking_points
    }


def main():
    competitors = []

    # Process competitor files
    if COMPETITORS_DIR.exists():
        for filepath in sorted(COMPETITORS_DIR.glob("*.md")):
            data = process_file(filepath, "competitor")
            if data:
                competitors.append(data)
                print(f"✓ {data['name']}")

    # Process Atlassian files
    if ATLASSIAN_DIR.exists():
        for filepath in sorted(ATLASSIAN_DIR.glob("*.md")):
            data = process_file(filepath, "atlassian")
            if data:
                competitors.append(data)
                print(f"✓ {data['name']} (Atlassian)")

    # Write output
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(competitors, f, indent=2)

    print(f"\n✅ Exported {len(competitors)} entries to {OUTPUT_FILE}")

    # Summary by threat level
    high = len([c for c in competitors if c['threat_level'] == 'High'])
    medium = len([c for c in competitors if c['threat_level'] == 'Medium'])
    low = len([c for c in competitors if c['threat_level'] == 'Low'])
    print(f"   High: {high}, Medium: {medium}, Low: {low}")


if __name__ == "__main__":
    main()
```

## Usage

```bash
cd Competitors/CompetitiveLandscape-2025
python export_competitors.py
```

## Output

Creates `competitors.json` with this structure:

```json
[
  {
    "id": "cursor",
    "name": "Cursor",
    "type": "competitor",
    "tagline": "AI-native IDE with codebase context",
    "website": "https://cursor.com",
    "threat_level": "High",
    "autonomy_level": "L3",
    "funding_display": "$400M Series B",
    "atlassian_overlap": ["Rovo Dev", "Bitbucket"],
    "demo_url": "https://cursor.com",
    "demo_account": "See 1Password > Competitors",
    "logo_url": "",
    "out_of_left_field": false,
    "presentation_priority": 1,
    "themes": ["Agentic Shift", "Developer Love", "Platform Wars"],
    "platform": {
      "marketplace_size": "100+ extensions",
      "api_surface": ["SDK", "CLI"],
      "partner_ecosystem": "VSCode extension ecosystem",
      "lock_in_signals": "VSCode-based, standard formats, easy migration"
    },
    "trust": {
      "compliance_certs": ["SOC2"],
      "audit_capabilities": "Session history, command logs",
      "admin_controls": "Team management, SSO (Business)"
    },
    "workflow": {
      "interaction_model": "hybrid",
      "context_sources": ["codebase", "docs", "web"],
      "trigger_pattern": "user-invoked"
    },
    "time_to_value": {
      "onboarding_friction": 1,
      "time_to_first_value": "5 minutes",
      "free_tier_limits": "2000 completions/month",
      "self_serve": true
    },
    "engineering_evolution": {
      "left_of_code_value": ["planning", "intent"],
      "right_of_code_value": ["code_review"],
      "alignment_artifact_support": "Conversation history captures intent",
      "conductor_model_fit": "hybrid",
      "decision_trace_capability": "Partial"
    },
    "talking_points": {
      "keeps_up_at_night": ["Tab completion feels psychic", "50% adoption at Enterprise X in 3mo"],
      "their_edge": ["Persistent codebase understanding"],
      "our_edge": ["Enterprise trust and compliance"],
      "discussion_prompt": "Should Rovo Dev aim for Cursor-level context?"
    }
  }
]
```

## Next Step

Upload `competitors.json` to your Replit project, then proceed to `01_BaseApp.md`.
