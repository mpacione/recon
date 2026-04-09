# Step 1: Base App with Card Grid

**Checkpoint after this step works.**

## Replit Agent Prompt

```
Build a React + Tailwind web app for browsing competitor intelligence data.

## Data Source
Import data from `competitors.json` in the project root. The JSON is an array of competitor objects with these fields:
- id (string)
- name (string)
- type ("competitor" or "atlassian")
- tagline (string)
- threat_level ("High", "Medium", "Low")
- autonomy_level ("L1" through "L5")
- funding_display (string like "$400M Series B")
- atlassian_overlap (array of strings like ["Rovo Dev", "Jira"])
- demo_url (string URL)
- presentation_priority (1, 2, or 3)

## Layout
Create a single-page app with:
- Header bar with title "Competitive Landscape"
- Main content area with a responsive card grid (3 columns on desktop, 2 on tablet, 1 on mobile)

## Card Design
Each card should show:
- Name (large, bold)
- Tagline (smaller, gray text below name)
- Threat level indicator: red circle for "High", yellow for "Medium", green for "Low" — displayed in top right corner
- Autonomy level as a small badge (e.g., "L3")
- Funding amount if available
- Small dots at the bottom showing which Atlassian products it threatens (from atlassian_overlap array)

## Styling
- Clean, professional look suitable for an executive presentation
- White cards with subtle shadows on a light gray background
- Hover state: slight lift effect on cards
- Use Inter or system font stack

## Initial State
Show all competitors sorted by threat_level (High first), then alphabetically within each level.
```

## Expected Result

A working card grid displaying all competitors from the JSON file. No filtering or detail panel yet.

## If Something Goes Wrong

- **JSON not loading**: Check the file path. Ask: "The JSON file is at `/competitors.json`. Can you update the import path?"
- **Cards look cramped**: Ask: "Add more padding to the cards and increase the gap between them"
- **Colors wrong**: Ask: "Use these exact colors: High threat = #EF4444, Medium = #F59E0B, Low = #22C55E"

## Next Step

Once the card grid is working, checkpoint and proceed to `02_DetailPanel.md`.
