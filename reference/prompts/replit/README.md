# Replit Prompts for Competitor Presentation App

Sequential prompts for building the interactive competitor landscape app using Replit Agent.

## Build Order

| Step | File | What It Does |
|------|------|--------------|
| 0 | `00_DataExport.md` | Python script to export competitor data to JSON |
| 1 | `01_BaseApp.md` | Initial React app with card grid |
| 2 | `02_DetailPanel.md` | Click-to-expand detail panel |
| 3 | `03_Filtering.md` | Product chips, theme filter, and threat level filters |
| 4 | `04_PresentationMode.md` | Screen-sharing optimized view |
| 5 | `05_Polish.md` | Visual refinements + optional enhancements |
| 6 | `06_ThemesPage.md` | (Optional) Strategic synthesis page |

## How to Use

1. **Run the export script** (Step 0) locally to generate `competitors.json`
2. **Create a new Replit project** (React template)
3. **Upload `competitors.json`** to the project root
4. **Copy each prompt** into Replit Agent, one at a time
5. **Checkpoint** after each successful step
6. **Rollback** if something breaks, then simplify and retry

## Key Principles

- **One feature at a time** — Don't combine prompts
- **Checkpoint religiously** — Save working states
- **Be specific** — Field names, colors, exact behaviors
- **Iterate** — First attempt may need refinement

## Time Estimate

| Step | Time |
|------|------|
| Data export | 5 min |
| Base app | 10-15 min |
| Detail panel | 10-15 min |
| Filtering | 15-20 min |
| Presentation mode | 10 min |
| Polish | 15-20 min |
| **Total** | ~1-1.5 hours |

## Troubleshooting

### "Agent seems stuck"
- Simplify the prompt
- Break into smaller pieces
- Check console for errors

### "JSON not loading"
- Verify file is in project root
- Check JSON syntax with a validator
- Try hardcoding a small test array

### "Styling looks wrong"
- Be more specific about colors (use hex codes)
- Reference Tailwind classes directly
- Ask Agent to "use shadcn/ui components"

### "Feature not working"
- Ask Agent to "add console.log statements to debug"
- Check the browser console
- Rollback and try a simpler approach

## After Deployment

1. Test on mobile (should be responsive)
2. Test with `?presentation=true` URL parameter
3. Share URL with stakeholders for feedback
4. Note any issues for iteration
