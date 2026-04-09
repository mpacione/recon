# Step 5: Visual Polish

**Checkpoint after this step works.**

## Replit Agent Prompt

```
Polish the visual design for executive presentation quality.

## Card Improvements
- Add subtle gradient or texture to card backgrounds
- Improve the threat level indicator: make it a small badge with text like "HIGH" instead of just a colored dot
- Add company logo placeholder (gray circle with initials if logo_url is empty)
- Improve the Atlassian product dots at the bottom: use small colored pills with the product name abbreviated (RD, JI, BB, CO, CF)

## Typography
- Use Inter font (import from Google Fonts)
- Improve hierarchy: name should be noticeably larger than tagline
- Section headers in the detail panel should use a subtle uppercase style with tracking

## Empty States
- If no competitors match the current filters, show a friendly message: "No competitors match these filters"
- If talking points are empty in the detail panel, show: "Talking points coming soon"

## Loading State
- Add a brief loading skeleton while the JSON loads
- Cards should fade in smoothly when data loads

## Hover & Focus States
- Cards should lift slightly on hover (translateY and shadow change)
- Keyboard navigation: cards should be focusable with visible focus ring
- Buttons should have clear hover states

## Color Palette
Use these exact colors for consistency:
- High threat: #DC2626 (red-600)
- Medium threat: #D97706 (amber-600)
- Low threat: #16A34A (green-600)
- Primary button: #4F46E5 (indigo-600)
- Background: #F9FAFB (gray-50)
- Card background: #FFFFFF
- Text primary: #111827 (gray-900)
- Text secondary: #6B7280 (gray-500)

## Detail Panel Polish
- Add a subtle header background color
- Improve spacing between sections
- Make the "Open Demo" button full-width and more prominent
- Add a subtle divider between sections
```

## Expected Result

A polished, professional-looking app suitable for sharing on screen with executives.

## If Something Goes Wrong

- **Font not loading**: Ask: "Add the Inter font import to the HTML head or use @import in CSS"
- **Colors inconsistent**: Ask: "Create a colors object/constants file and use it everywhere"
- **Animations janky**: Ask: "Use transform and opacity for animations, not layout properties"

## Deployment

Once polished:
1. Click "Deploy" in Replit
2. Copy the deployed URL
3. Test the URL in an incognito window
4. Share with Emily for feedback

## Optional Enhancements

If time permits, consider these follow-up prompts:

### Search
```
Add a search bar that filters competitors by name or tagline. Use fuzzy matching so partial matches work.
```

### Agentic Toggle
```
Add an "Agentic Only" toggle that filters to competitors with autonomy_level of L3, L4, or L5.
```

### Sort Options
```
Add a sort dropdown with options: "Threat Level" (default), "Alphabetical", "Funding"
```

### Comparison Mode
```
Add ability to select 2-3 competitors and see them side-by-side in a comparison view.
```
