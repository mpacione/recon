# UI Screenshots

Reference captures of recon's interfaces, kept for Figma mockups + design
review. Regenerate by re-running the capture commands below.

## Web (`web/`)

PNG captures at 2x scale (1498 × ~1500), captured via `html2canvas` inside
the Claude Preview browser at `http://localhost:8787`. Screens shown with
mock data injected via the Alpine store.

| File          | Screen                              |
|---------------|-------------------------------------|
| `welcome.png` | Project picker with recent projects |
| `describe.png`| New-project describe form           |
| `discover.png`| Competitor discovery / curation     |
| `template.png`| Research-template checklist         |
| `confirm.png` | Estimate + model + workers confirm  |

Regenerate: start the web server (`uv run uvicorn recon.web.app:app --port 8787`),
open the preview, and run the `html2canvas` capture flow described in
`app.js` dev notes.

## TUI (`tui/`)

SVG captures from `pytest-textual-snapshot`, terminal size 100 × 40. These
are the actual Textual render (crisp vector, fonts preserved). Perfect for
Figma import — drag the SVG onto the canvas.

| File                             | Screen                                 |
|----------------------------------|----------------------------------------|
| `welcome_empty.svg`              | Welcome with no recent projects        |
| `welcome_with_recents.svg`       | Welcome with 3 recent projects         |
| `dashboard_empty.svg`            | Fresh workspace, no competitors yet    |
| `dashboard_populated.svg`        | Workspace with 47 competitors + stats  |
| `discovery_with_candidates.svg`  | Discovery round with candidate rows    |
| `planner_menu.svg`               | Run planner (model/workers/confirm)    |
| `run_idle.svg`                   | Run screen pre-start                   |
| `run_active.svg`                 | Run screen mid-pipeline with activity  |
| `curation_with_themes.svg`       | Theme curation with evidence strength  |
| `browser_with_competitors.svg`   | Competitor browser                     |
| `selector_with_competitors.svg`  | Competitor picker                      |

Regenerate: `uv run pytest tests/test_tui_snapshots.py --snapshot-update`
and then copy from `tests/__snapshots__/test_tui_snapshots/*.svg` into
`docs/screenshots/tui/` (drop the `Test<X>Snapshots.test_` prefix).

## Using these in Figma

- **SVG (TUI):** Drag directly onto the canvas. Textual's SVG output
  preserves the terminal grid and the amber-on-black palette, so it
  reads as a faithful artifact of the running app.
- **PNG (web):** Place as a frame background at 1x (they're 2x DPR) and
  build your mockup on top. The captures already reflect the current
  Inter + JetBrains Mono + Lucide styling pass.
