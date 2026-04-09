# Step 4: Presentation Mode

**Checkpoint after this step works.**

## Replit Agent Prompt

```
Add a "Presentation Mode" toggle for screen-sharing during executive meetings.

## Toggle Location
Add a toggle switch in the header, right side, labeled "Presentation Mode"

## Presentation Mode Changes
When enabled:
1. Hide the filter rows (product chips and threat level selector)
2. Make cards larger (increase padding and font sizes by ~25%)
3. Reduce grid to 2 columns max (easier to read on shared screen)
4. Add more contrast (darker text, crisper shadows)
5. Hide any competitors with presentation_priority = 3 (show only priority 1 and 2)

## Visual Indicator
When presentation mode is on:
- The toggle should be clearly "on" (filled/colored)
- Add a subtle banner or indicator showing "Presentation Mode"

## Keyboard Shortcut
Add keyboard shortcut "P" to toggle presentation mode on/off.

## URL Parameter
Support ?presentation=true URL parameter to open directly in presentation mode.
This is useful for Emily to bookmark the presentation-ready view.
```

## Expected Result

A toggle that switches between normal browsing mode and a cleaner presentation mode.

## If Something Goes Wrong

- **Toggle not visible**: Ask: "Place the toggle in the top-right corner of the header with clear labeling"
- **Cards not resizing**: Ask: "Use CSS classes that change based on a presentationMode state variable"
- **Keyboard shortcut not working**: Ask: "Add a useEffect hook that listens for keydown events on 'p' key"

## Next Step

Once presentation mode is working, checkpoint and proceed to `05_Polish.md`.
