# Step 6: Themes Page (Optional)

**This is a Phase 3 enhancement. Skip if time-constrained.**

## Replit Agent Prompt

```
Add a "Themes" page that shows strategic synthesis alongside competitor data.

## Navigation
Add a tab or toggle at the top to switch between:
- "Competitors" (current card grid view)
- "Themes" (new strategic synthesis view)

## Themes Page Layout
Show each strategic theme as a card/section:

For each theme, display:
1. Theme title with icon (🔮 Agentic Shift, 🔌 MCP Ecosystem, etc.)
2. Competitor count badge (e.g., "28 competitors")
3. Key insight (1-2 sentences from theme data)
4. Top 3-5 competitor names as clickable links
5. "View Competitors" button → switches to Competitors view with that theme pre-filtered
6. "Full Analysis" link → opens theme markdown file or Confluence page

## Theme Data
The themes array in competitors.json has this structure:
```json
{
  "themes": [
    {
      "id": "agentic_shift",
      "title": "Agentic Shift",
      "key_insight": "Autonomous agents executing Jira issues directly threaten Jira's UI relevance within 18 months.",
      "competitor_count": 28,
      "top_competitors": ["Devin", "Codex", "Claude Code", "Factory"],
      "threat_level": "High",
      "atlassian_impact": ["Jira", "Rovo Dev"]
    }
  ]
}
```

## Theme Card Styling
- Large cards, one per row on desktop
- Theme title should be prominent
- Use a gradient or colored left border based on threat_level (red for High, yellow for Medium)
- Key insight should be styled as a pull quote
- Top competitors shown as small pill badges that link to their detail panel
- "View Competitors" button should be prominent

## Interaction
- Clicking a competitor name in the theme card opens their detail panel (same as main view)
- Clicking "View Competitors" switches to Competitors tab with theme filter pre-applied
- Theme cards can be expanded/collapsed if there's additional content

## Mobile
- Stack theme cards vertically
- Collapse key insight behind a "Read more" toggle if too long
```

## Expected Result

A strategic overview page that complements the competitor card view, showing Emily the "so what" synthesis.

## If Something Goes Wrong

- **Themes not loading**: Check that themes array exists in JSON
- **Navigation broken**: Simplify to just a link instead of tab system
- **Styling off**: Ask for "card with prominent header and subtle background"

## Data Preparation

Update `export_competitors.py` to include a themes array. You can manually add theme summaries or extract from `Themes/*.md` files:

```python
# Add to export script
themes = [
    {
        "id": "agentic_shift",
        "title": "Agentic Shift",
        "key_insight": "Autonomous agents executing Jira issues...",
        "competitor_count": len([c for c in competitors if "Agentic Shift" in c.get("themes", [])]),
        "top_competitors": ["Devin", "Codex", "Claude Code"],
        "threat_level": "High",
        "atlassian_impact": ["Jira", "Rovo Dev"]
    },
    # ... other themes
]

output = {
    "themes": themes,
    "competitors": competitors
}
```

## When to Use This

Add the Themes page when:
- P4 synthesis is complete and theme docs exist
- Emily wants a strategic narrative layer, not just competitor cards
- There's time after MVP is working

Skip if:
- Still in Phase 1 (competitor cards are the priority)
- Theme synthesis isn't ready
- 90-min meeting doesn't need this depth
