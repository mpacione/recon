# Session Handoff — 2026-04-12

## What shipped this session (15 phases)

| Phase | Commit | Summary |
|---|---|---|
| E | `b18adb2` | Keyboard-first navigation. Removed action-bar buttons on all 4 full screens, added keybindings. |
| F | `29666f7` | ActivityFeed widget. Subscribes to EventBus, renders 11 typed events with iconography. |
| G | `0134e0c` | RunStatusBar widget. 1-line status strip with stage/bar/elapsed/cost, hidden when idle. |
| H | `8799c86` | Real-terminal PTY smoke tests. Caught and fixed a chrome layout bug (dock:bottom collision). |
| I | `f04ff28` | End-to-end audit + critical fixes: planner labels, [x] markers, chrome header bus updates. |
| J | `cc29d00` | TerminalBox + CardStack primitives. Dashboard adopted the card-stack layout. |
| K | `1e59ec7` | Keybind regression fix. Tests were polluting ~/.recon/recent.json; welcome Input clipped off-screen. |
| L | `0a08582` | Universal Escape on all modals. Planner/Discovery/Selector/Curation all handle ESC now. |
| M | `f6c0398` | Ctrl+C exits the app. Add-manually round-trip test (disk write verified). |
| N | `ec95a30` | Input focus vs screen bindings test. Workspace recovery edge case test. |
| O | `73afc50` | Discovery screen redesign with TerminalBox cards + keybind-driven action bar. |
| P | `35ced39` | Cached-screen lifecycle fix. Pipeline stall via welcome flow. ReconApp.launch_pipeline canonical entry. |
| Q | `dd9942e` | Global button CSS + theme labeling fixes (citation stripping + async LLM labeler + LLM client threading). |
| R | `c90c28f` | Competitor grid run monitor. Per-competitor ASCII progress bars + worker panel. |
| S | `e6b6fe6` | Duplicate project guard + `e` edit schema + DataTable discovery layout. |

**Test count:** 644 → 738 (+94 tests). 25 PTY-based real-terminal tests.

## What's still open (prioritized for next session)

### 1. Auto-retry failed sections (HIGH)

**User report:** "When errors get thrown I don't know how to retry."

The grid shows "1 failed" / "2 failed" per competitor but there's no way to retry from the run screen. The planner has "Re-run failed" (digit 6) but the user has to navigate back to dashboard → planner → digit 6 to use it.

**Proposed fix:**
- Auto-retry once on failure before marking as failed (add a `max_retries=1` parameter to `_research_one` in `research.py`)
- Show inline error detail in the grid: instead of just "1 failed", show "1 failed: rate limit" or "1 failed: timeout"
- Add a keybind on RunScreen (`f` for retry-failed) that re-runs just the failed sections without leaving the run screen

**Files to touch:** `research.py` (retry logic), `events.py` (add error detail to SectionFailed), `run_monitor.py` (show error text in grid), `run.py` (add retry keybind)

### 2. Cost estimate shows $0.00 (HIGH)

**User report:** "It says $0.00 everywhere."

`_estimate_full_run_cost` in `dashboard.py` calculates the estimate but the result depends on `CostTracker.estimate_section_cost` which uses a static pricing model. If the model ID doesn't match the pricing table, it returns 0. Also the header bar's `total_cost` starts at 0 and only increments from `CostRecorded` events during a run — it doesn't read historical cost from state.db on dashboard load.

**Proposed fix:**
- Verify `_estimate_full_run_cost` produces a non-zero estimate for the user's schema (check model ID matching)
- Add a cost confirmation modal before starting expensive runs (>$5): "This run will cost approximately $X.XX. Continue?"
- Pre-populate `workspace_context.total_cost` from `StateStore.get_workspace_total_cost()` on workspace load so the header bar shows cumulative cost from prior runs

**Files to touch:** `dashboard.py` (estimate), `app.py` (populate cost on load), `pipeline_runner.py` (add confirmation modal)

### 3. Theme labels still meaningless (HIGH)

**User report:** Labels show "Enterprise / Developer / Data" — mechanical TF-IDF fallback, not strategic names.

Phase Q fixed the citation stripping and threaded the LLM client, but the theme labels are STILL mechanical. Two remaining root causes:

**A. Random embeddings:** `build_workspace_chunks` in `themes.py` generates hash-seeded random 64-dim vectors. K-means on random vectors produces arbitrary clusters. Even with the LLM labeler working, the clusters fed to it are topically incoherent so it can't produce strategic labels.

**Fix:** Replace random vectors with fastembed embeddings. fastembed is already a dependency. Wire `IndexManager.embed()` into `build_workspace_chunks`. Fall back to random vectors only in CI where fastembed models aren't available.

**B. LLM labeler may be silently failing:** The async `_llm_label` catches all exceptions and falls back to mechanical. Check if the LLM call is actually succeeding or if there's an auth/model error being swallowed.

**Fix:** Log the LLM response (or failure) at INFO level so the user can see in the log pane whether labels were LLM-generated or mechanical.

### 4. Theme curation UX rethink (MEDIUM)

**User report:** "I'm not sure why it would ask. It should just start a cursory synthesis and then return with candidate themes."

The current flow is: engine discovers themes → user curates (toggle on/off) → engine synthesizes selected themes. But the user expects: engine discovers + does a quick synthesis pass → shows candidate themes WITH previews → user accepts/rejects → engine enriches the accepted ones.

**Proposed redesign:**
- Remove the curation gate from the pipeline. Instead, auto-select the top N themes (by evidence strength) and synthesize them all.
- After synthesis, show a "Theme Review" screen that displays each theme's synthesis summary (1-2 sentences) so the user can see what was produced.
- Add an "Enrich" action on the review screen that does the deep 4-pass synthesis on selected themes.
- This changes the pipeline from "gate before synthesis" to "synthesize all, review after."

### 5. Post-run summary screen (MEDIUM)

**User report:** "It just leaves me hanging."

After the pipeline completes, the run screen shows "Phase: Done" and a green progress bar but nothing else. The user doesn't know where to find the output files.

**Proposed fix:**
- When the pipeline completes, the run screen body should show:
  ```
  ── RUN COMPLETE ──  $31.26  36:46
  
  Output files:
    competitors/  .......... 30 profiles (28 ok, 2 partial)
    themes/       .......... 5 themes
    themes/distilled/ ...... 5 executive summaries
    executive_summary.md ... 1 file
  
  Press [b] back to dashboard · [o] open in Finder · [e] open executive summary
  ```
- Add keybinds: `o` to open the workspace directory in Finder (macOS `open` command), `e` to open `executive_summary.md` in `$EDITOR`

### 6. Executive summary not produced (MEDIUM)

**User report:** "It should produce an exec overview, which it currently doesn't appear to do."

The pipeline has a `_stage_deliver` method that calls `Distiller.distill` and `MetaSynthesizer.synthesize`. If themes weren't selected in the curation gate (or the gate was cancelled), these stages are skipped. Also if synthesis fails, deliver is skipped too.

**Check:** Look at the pipeline logs from the user's run. If the themes stage produced themes but the curation gate returned empty (user pressed ESC or the auto-select wasn't wired), synthesis+deliver would be skipped.

### 7. Gemini discovery integration (NEXT SESSION — scoped separately)

Replace Claude's `web_search_20250305` tool with Gemini Flash + Google Search grounding for the discovery stage. 50x cheaper, no hard candidate limit, potentially better search coverage.

**Requires:** `google-genai` dependency, `GOOGLE_API_KEY` env var, new `GeminiDiscoveryClient` wrapper, updated discovery agent prompts.

## Architecture docs produced this session

- `design/tui-audit-2026-04-10.md` — 20 audit findings by severity
- `design/system-improvement-plan-2026-04-10.md` — 8 architectural levers
- `design/systemic-fixes-proposal-2026-04-11.md` — Issue 1/2/3 analysis + competitor grid mockup

## Implementation progress memory

Updated at `~/.claude/projects/-Users-mattpacione-recon/memory/project_implementation_progress.md` — most recent entry is Phase P. Needs updating with Q/R/S.

## Key gotchas for the next agent

1. **Textual caches Screen instances per mode.** `on_mount` fires once. Use `on_screen_resume` for anything that needs to fire on every mode activation.
2. **`_render` is reserved on every Widget.** Don't define a method called `_render` on Static subclasses — it silently breaks the visual pipeline. Use `_render_status`, `_render_grid`, etc.
3. **Rich markup eats `[x]` as an unknown tag.** Escape the open bracket: `\[x]`.
4. **Widget.compose() yields land AFTER positional *children.** Prepend header widgets in `__init__`, not in `compose()`.
5. **Tests that yield Screen as a child widget don't test the real focus model.** Always have at least one PTY-based test per screen that presses real keys.
6. **`~/.recon/recent.json` is global.** Tests MUST use the autouse `_isolate_recent_projects` fixture in conftest.py.
7. **`call_from_thread` raises RuntimeError on the message-loop thread.** The `_schedule_chrome_refresh` helper in app.py tries inline first, falls back to call_from_thread.
8. **The `_loading` holding mode** in `on_welcome_screen_workspace_selected` and `_create_workspace_from_wizard` exists because Textual refuses to remove the active mode. Don't use `switch_mode("run")` as a holding mode — it instantiates the run screen prematurely.

## Current test baseline

738 passing, 4 skipped (real-API), 11 snapshots, lint clean.
Main is at commit `e6b6fe6`.
