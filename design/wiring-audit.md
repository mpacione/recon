# TUI Wiring Audit (2026-04-09)

**Goal:** determine, for every interactive control in the TUI, whether it actually reaches the intended engine behavior or dead-ends somewhere inside the interface layer.

**Method:** code-graph-mcp index (1516 nodes / 747 edges / 112 files) + targeted grep. Every reference in each `on_button_pressed` handler was traced to either (a) a real engine API, (b) another TUI method, or (c) a dead end.

---

## Update 2026-04-10: run path is now wired

The major gap described in this audit has been closed. The original
conclusion -- "the TUI never calls the pipeline engine" -- no longer
holds. Here's what changed:

- `src/recon/tui/pipeline_runner.py` is new. It owns the planner
  `Operation` → `PipelineConfig` mapping, the `PipelineFn` factory, and
  the set of operations that require a selector push before starting.
- `DashboardScreen.handle_planner_result` now builds a `PipelineFn` via
  `build_pipeline_fn(workspace_path=..., operation=..., targets=...)`
  and queues it on the app under `_pending_pipeline_fn`.
- `RunScreen.on_mount` consumes the queued pipeline_fn and starts the
  worker. This handshake was needed because `switch_mode("run")` does
  not guarantee the RunScreen is mounted by the time the handler returns.
- `Pipeline.progress_callback` is a new optional async hook called
  before and after each stage. The TUI runner uses it to update
  `RunScreen.current_phase` / `RunScreen.progress` reactively and
  append to the activity log.
- `PipelineConfig.targets` is a new optional competitor name filter
  threaded through `ResearchOrchestrator.research_all(targets=...)`
  and `EnrichmentOrchestrator.enrich_all(targets=...)`.
- `CompetitorSelectorScreen` is reachable for the first time:
  `handle_planner_result` pushes it when the chosen operation is in
  `OPERATIONS_REQUIRING_SELECTION` (currently `UPDATE_SPECIFIC`), and
  the resolved names are plumbed into `PipelineConfig.targets`.

**What still doesn't work:** `DIFF_SPECIFIC`, `DIFF_ALL`, and
`RERUN_FAILED` planner options notify the user they are not yet
implemented. This is intentional — the pipeline engine has no
diff/rerun logic to call.

All of this is covered by:
- `tests/test_tui_pipeline_runner.py` (8 tests)
- `tests/test_tui_integration.py::TestPlannerStartsPipelineWithRunScreen`
- `tests/test_tui_integration.py::TestPlannerUpdateSpecificFlow`
- `tests/test_pipeline.py::TestPipeline::test_progress_callback_fires_for_each_stage`
- `tests/test_pipeline.py::TestPipeline::test_targets_are_forwarded_to_research_stage`

The original audit content below is preserved for historical reference.

---

## TL;DR

| Flow | Status |
|---|---|
| Welcome → Wizard → Workspace created | **works** — wires through `Workspace.init` + yaml write |
| Welcome → Open recent workspace | **works** — posts message, app switches modes |
| Dashboard → Discover → live search | **works** — the one thing fully wired (after last commit) |
| Dashboard → Add Manually → profile created | **works** — wires through `Workspace.create_profile` |
| Dashboard → Browse competitors | **works** for display, but detail panel only updates on cursor highlight |
| Dashboard → Run → pick operation → pipeline runs | **BROKEN** — dead reference to `_run_full_pipeline` (does not exist) |
| Run screen → Pause | **no-op** — prints "not yet implemented" |
| Run screen → Stop | **no-op** — prints "not yet implemented" |
| Theme curation gate (during pipeline) | **never reached** — no pipeline ever runs |

## The one-line summary

**The TUI never calls the pipeline engine.** `src/recon/tui/` contains zero imports and zero instantiations of `Pipeline`, `ResearchOrchestrator`, `EnrichmentOrchestrator`, `SynthesisEngine`, `MetaSynthesizer`, `Distiller`, `Tagger`, `ThemeDiscovery`, `IndexManager`, `IncrementalIndexer`, or `StateStore`. The only engine classes the TUI touches are `Workspace`, `DiscoveryAgent`, `create_llm_client`, and schema data types (`WizardState`, `DiscoveryCandidate`, `DiscoveredTheme`).

---

## Per-screen audit

### WelcomeScreen

| Button | Handler | Goes to | Status |
|---|---|---|---|
| `btn-new` | `_show_new_input` mounts an Input | Input submit → `NewProjectRequested` message → `ReconApp.on_welcome_screen_new_project_requested` → pushes `WizardScreen` | ✓ |
| `btn-open` | `_show_open_input` mounts an Input | Input submit → `WorkspaceSelected` message → `ReconApp.on_welcome_screen_workspace_selected` → mode switch | ✓ |
| `btn-recent-N` | `_open_recent(idx)` → loads from `RecentProjectsManager` → posts `WorkspaceSelected` | Same path as Open | ✓ |

### WizardScreen

| Button | Handler | Goes to | Status |
|---|---|---|---|
| `btn-continue` (identity) | `_harvest_identity` + `state.advance()` | Next phase | ✓ |
| `btn-continue` (sections) | `_sync_sections_state` + `state.advance()` | Next phase | ✓ |
| `btn-continue` (sources) | `state.advance()` | Next phase | ✓ |
| `btn-back` (all phases) | `state.go_back()` | Previous phase | ✓ |
| `btn-confirm` (review) | Builds `WizardResult`, dismisses | ReconApp writes `recon.yaml`, calls `Workspace.init`, switches to dashboard mode | ✓ |

### DashboardScreen

| Button | Handler | Goes to | Status |
|---|---|---|---|
| `btn-run` (≥1 competitor) | `_push_planner` → `RunPlannerScreen` → on dismiss → `handle_planner_result` | `handle_planner_result` builds `pipeline_fn` that awaits `_run_full_pipeline(...)` — **FUNCTION DOES NOT EXIST** | **BROKEN** |
| `btn-run` (0 competitors) | Shows notify "Nothing to run" | - | ✓ |
| `btn-discover` / `btn-empty-discover` | `_push_discovery` → builds `DiscoveryAgent` → `push_screen(DiscoveryScreen)` | `DiscoveryAgent.search` (live LLM + web_search tool) | ✓ |
| `btn-browse` | `_push_browser` → `CompetitorBrowserScreen` | Renders profiles from `DashboardData.competitor_rows` | ✓ |
| `btn-empty-manual` | `_show_manual_add_input` mounts Input → on submit → `Workspace.create_profile` | Profile written to disk, dashboard refreshes | ✓ |
| `btn-quit` | `self.app.exit()` | - | ✓ |

### DiscoveryScreen

| Button | Handler | Goes to | Status |
|---|---|---|---|
| `btn-done` | `dismiss(state.accepted_candidates)` | Dashboard creates profiles via `Workspace.create_profile` | ✓ |
| `btn-search-more` | `_do_search` worker → `self._search_fn(state)` → `DiscoveryAgent.search` → Anthropic API with `web_search_20250305` tool | Live web results, parsed into candidates | ✓ |
| `btn-add-manual` | **No handler!** Button exists, `on_button_pressed` never matches `btn-add-manual` | - | **DEAD BUTTON** |
| `btn-accept-all` | `state.accept_all()` + recompose | - | ✓ |
| `btn-reject-all` | `state.reject_all()` + recompose | - | ✓ |
| `btn-toggle-N` | `state.toggle(N)` + recompose | - | ✓ |

### RunPlannerScreen

| Button | Handler | Goes to | Status |
|---|---|---|---|
| `btn-op-N` (each of 7 options) | `dismiss(selected_operation)` | DashboardScreen `handle_planner_result` | ✓ for dismiss, but destination is broken |
| `btn-back` | `dismiss(None)` | No-op in dashboard | ✓ |

### CompetitorSelectorScreen

| Button | Handler | Goes to | Status |
|---|---|---|---|
| `btn-done` | `dismiss(self.selected)` | **Nothing** — selector is never pushed from anywhere | **ORPHAN SCREEN** |
| `btn-cancel` | `dismiss([])` | Same | ⚠ |
| `btn-select-all` | flag list + recompose | - | ✓ |
| `btn-clear-all` | flag list + recompose | - | ✓ |
| `selector-N` | toggle flag + recompose | - | ✓ |

### ThemeCurationScreen

| Button | Handler | Goes to | Status |
|---|---|---|---|
| `btn-done` | `dismiss(selected_themes)` | **Nothing reaches it** — no pipeline ever pushes this screen in production | ⚠ tests pass with mock pipeline_fn; real path dead |
| `btn-cancel-curation` | `dismiss([])` | Same | ⚠ |
| `btn-select-all-themes` | toggle all + recompose | - | ✓ |
| `btn-clear-all-themes` | clear all + recompose | - | ✓ |
| `theme-N` | `model.toggle(N)` + recompose | - | ✓ |

### RunScreen

| Button | Handler | Goes to | Status |
|---|---|---|---|
| `btn-pause` | `notify("Pause not yet implemented")` | - | **STUB** |
| `btn-stop` | `notify("Stop not yet implemented")` | - | **STUB** |
| `btn-back-to-dashboard` | `self.app.switch_mode("dashboard")` | - | ✓ |

Pipeline execution: `start_pipeline(pipeline_fn)` fires `@work _execute_pipeline()` which awaits the function. The pipeline_fn builder in the dashboard references `_run_full_pipeline` which **does not exist**.

### CompetitorBrowserScreen

| Button | Handler | Goes to | Status |
|---|---|---|---|
| `btn-back` | `self.app.pop_screen()` | Return to dashboard | ✓ |
| (DataTable row highlight) | `on_data_table_row_highlighted` updates detail Static | - | ✓ |

No "View full profile" action, no drill-down. The browser is look-only.

---

## Unused widgets

`src/recon/tui/widgets.py` defines 5 custom widgets. **4 are never used anywhere:**

| Widget | External references |
|---|---|
| `StatusPanel` | 0 |
| `CompetitorTable` | 0 |
| `ThemeCurationPanel` | 0 |
| `RunMonitorPanel` | 0 |
| `ProgressBar` | 1 (unused in practice) |

They were designed as "the reusable rendering layer" and then never adopted — the screens render inline markup instead. These are dead code.

---

## Critical dead references

| Location | Dead reference | Consequence |
|---|---|---|
| `src/recon/tui/screens/dashboard.py:358` | `await _run_full_pipeline(workspace_path, screen)` | **Runtime `NameError`** when user clicks Run → selects any operation → pipeline never starts |

Only one, but it's the most important one in the whole application: the link between the Run button and any engine code.

---

## What actually works end-to-end

1. **Create workspace**: wizard → `recon.yaml` + `Workspace.init` ✓
2. **Discover competitors**: dashboard → `DiscoveryAgent.search` with live web search → accept → `Workspace.create_profile` ✓
3. **Add competitor manually**: empty-prompt → Input → `Workspace.create_profile` ✓
4. **Browse competitors**: dashboard → browser (read-only) ✓

## What doesn't work end-to-end

1. **Run any operation from the planner**: dead function reference
2. **Pause/Stop during a run**: stubs
3. **Theme curation gate**: never reached because no pipeline runs
4. **`CompetitorSelectorScreen`**: never pushed from anywhere
5. **Pipeline progress display**: `RunScreen` reactive attrs exist but nothing updates them in production

---

## Fix scope

To make "Run → operation → pipeline executes" work, the minimum changes are:

1. Define `_run_full_pipeline(workspace_path, run_screen)` as a module-level async function in `dashboard.py` (or extract to a dedicated `tui/pipeline_runner.py`). It must:
   - Build `LLMClient` via `create_llm_client`
   - Open `Workspace`
   - Instantiate `StateStore`, initialize it
   - Build `Pipeline(workspace, state_store, llm_client, config=...)`
   - Call `pipeline.plan()` then `pipeline.execute(run_id)` with progress callbacks
   - Update `run_screen.current_phase`, `run_screen.progress`, `run_screen.cost_usd`, and `run_screen.add_activity(...)` throughout
2. Wire the pipeline's progress to RunScreen reactive attrs (currently nothing updates them at runtime)
3. Handle the theme gate: at phase 5b, `await self.app.push_screen_wait(ThemeCurationScreen(model))` and pass the result to the next phase

Beyond that minimum:

4. Route each of the 7 planner operations to the correct engine method (currently all 7 would run the same full pipeline)
5. Wire `CompetitorSelectorScreen` for operations 2 and 4 (update specific, diff specific)
6. Wire `btn-add-manual` handler in DiscoveryScreen
7. Implement Pause/Stop via `self.workers.cancel_node` or equivalent
8. Remove or adopt the 4 unused widgets in `widgets.py`
