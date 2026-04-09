# Step 3: Filtering by Atlassian Product & Themes

**Checkpoint after this step works.**

## Replit Agent Prompt

```
Add filtering controls to show competitors by Atlassian product, threat level, and strategic themes.

## Product Chips (Top Row)
Add a row of clickable chips below the header, one for each Atlassian product:
- Rovo Dev
- Jira
- Bitbucket
- Compass
- Confluence

## Theme Filter (Second Row)
Add a dropdown or chip row for strategic themes:
- "All Themes" (default)
- "Agentic Shift"
- "MCP Ecosystem"
- "Developer Love"
- "Consolidation Patterns"
- "Pricing Pressure"

Filter by the `themes` array in each competitor's data. A competitor matches if themes.includes(selectedTheme).

## Chip Behavior
- Chips are toggleable (click to select, click again to deselect)
- Multiple product chips can be selected at once (union/OR logic)
- Theme filter is single-select (radio-button style)
- When chips are selected, filter the card grid to show only competitors where atlassian_overlap includes ANY of the selected products
- When no chips are selected, show all competitors
- Selected chips should have a filled/highlighted state (darker background, white text)
- Unselected chips should have an outline state

## Threat Level Filter
Add a third row with threat level toggles:
- "All" (default, selected)
- "High" (red indicator)
- "Medium" (yellow indicator)
- "Low" (green indicator)

These should be mutually exclusive (radio-button style). Selecting one filters to only that threat level.

## Chip Styling
- Rounded pill shape
- Small count badge showing how many competitors match that filter
- Example: "Rovo Dev (24)"
- Theme chips should have a different color scheme (purple/indigo) to distinguish from product chips

## Filter Combination
All filters work together (AND logic between filter types):
- If "Rovo Dev" chip is selected AND "High" threat is selected AND "Agentic Shift" theme is selected, show only High-threat competitors that overlap with Rovo Dev AND have "Agentic Shift" in their themes array
```

## Expected Result

Three filter rows: product chips, theme selector, and threat level. Clicking filters the card grid in real-time.

## If Something Goes Wrong

- **Theme filtering not working**: Ask: "Show me the filter logic. It should check if themes.includes(selectedTheme)"
- **Filtering not working**: Ask: "Show me the filter logic. It should check if atlassian_overlap.includes(selectedProduct)"
- **Counts wrong**: Ask: "Recalculate the chip counts based on all current filters"
- **UI glitchy**: Ask: "Add a small debounce to the filter to prevent flickering"

## Next Step

Once filtering is working, checkpoint and proceed to `04_PresentationMode.md`.
