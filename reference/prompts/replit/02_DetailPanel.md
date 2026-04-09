# Step 2: Detail Panel

**Checkpoint after this step works.**

## Replit Agent Prompt

```
Add a detail panel that slides in from the right when a competitor card is clicked.

## Behavior
- Clicking a card opens a detail panel on the right side (about 400px wide)
- The panel slides in with a smooth animation
- Clicking outside the panel or clicking an X button closes it
- Only one panel can be open at a time

## Panel Content
The detail panel should show:

1. Header section:
   - Competitor name (large)
   - Threat level indicator (same colored circle as the card)
   - Tagline

2. Info row:
   - "Threatens:" followed by the atlassian_overlap items as pills/badges
   - "Autonomy:" followed by the autonomy_level
   - "Funding:" followed by funding_display

3. Talking Points sections (from the talking_points object in the JSON):
   - "WHAT KEEPS US UP AT NIGHT" — bullet list from talking_points.keeps_up_at_night array
   - "THEIR EDGE" — bullet list from talking_points.their_edge array
   - "OUR EDGE" — bullet list from talking_points.our_edge array
   - "DISCUSSION PROMPT" — single text from talking_points.discussion_prompt

4. Action buttons at bottom:
   - "Open Demo" button — opens demo_url in a new tab
   - "Close" button — closes the panel

## Styling
- Panel has white background with shadow on the left edge
- Section headers in all caps, small, gray, with a bit of letter-spacing
- Bullet points should be clean with good spacing
- "Open Demo" button should be prominent (blue/indigo color)

## Important
If talking_points fields are empty or missing, hide those sections rather than showing empty headers.
```

## Expected Result

Clicking any card opens a slide-in panel with all the competitor details and talking points.

## If Something Goes Wrong

- **Panel doesn't slide**: Ask: "Use CSS transform and transition for the slide animation"
- **Talking points not showing**: Ask: "Log the talking_points object to console so I can see its structure"
- **Demo button not working**: Ask: "Use window.open(demo_url, '_blank') for the Open Demo button"

## Next Step

Once the detail panel is working, checkpoint and proceed to `03_Filtering.md`.
