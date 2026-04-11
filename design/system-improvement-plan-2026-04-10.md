# recon — system-wide improvement plan (2026-04-10)

This plan is the architectural follow-up to the TUI audit
(`tui-audit-2026-04-10.md`). It looks past individual bugs and asks
where the system as a whole is fragile, where it's over-coupled,
and where small structural changes would make the next round of
features cheap instead of expensive.

The plan is organized by **lever** — a structural change that pays
off across multiple features — rather than by individual bug. Each
lever has a bullet list of motivating evidence from the audit /
codebase, a recommended change, and an estimate of the blast radius
(how much code it touches and how risky the change is).

---

## Lever 1: Make the EventBus the single source of truth for run state

**Evidence.**
- The audit caught a Phase C regression where the chrome header bar
  silently stopped reflecting bus events. The fix landed in Phase I
  but the underlying smell remains: `RunScreen` reads from its own
  reactive attrs (`current_phase`, `progress`, `cost_usd`), and
  `workspace_context.run_state` is mutated separately by the bus
  subscriber. Both are kept in sync today only because
  `pipeline_runner.py` writes to both — once.
- The body widget shows `Phase: Research / 42% / $1.09` from the
  reactive attrs. The chrome header shows `running · research` from
  the workspace_context. They're saying the same thing in two
  different formats with two different update paths.
- New chrome widgets (ActivityFeed, RunStatusBar) already subscribe
  to the bus directly. RunScreen is the odd one out.

**Recommended change.**
- Add a `RunState` dataclass on `WorkspaceContext` that holds:
  `phase: str`, `progress: float`, `cost_usd: float`,
  `started_at: datetime | None`, `stage_history: list[str]`,
  `error: str | None`.
- The bus subscriber is the only writer. `pipeline_runner.py` stops
  writing to `RunScreen.current_phase / progress / cost_usd`
  directly.
- `RunScreen` subscribes to `WorkspaceContext` changes (via a new
  `WorkspaceContextChanged` event or via direct widget polling) and
  re-renders its body widgets from `app.workspace_context.run_state`.
- The pipeline emits `RunStageProgress(stage, progress, ...)` events
  that update the progress field. Today the engine doesn't emit
  granular progress, so this is a coupled change: the pipeline
  needs a `progress_callback(stage, progress)` hook on top of the
  existing start/complete callbacks.

**Blast radius.**
- `recon/events.py` (new event types)
- `recon/pipeline.py` (emit progress events)
- `recon/tui/shell.py::WorkspaceContext` (add RunState field)
- `recon/tui/app.py::_on_engine_event` (write to RunState)
- `recon/tui/screens/run.py` (read from workspace_context, drop
  reactive attrs)
- `recon/tui/pipeline_runner.py` (drop direct screen writes)
- ~20 tests need updating

**Payoff.**
- Single source of truth eliminates the entire class of "header
  bar disagrees with body" bugs.
- New screens that need to display run state can subscribe to the
  same bus without re-implementing the plumbing.
- The engine becomes more testable in isolation — you can drive
  it without a TUI and inspect the bus events to verify behavior.
- Multi-window / multi-screen support becomes trivial because all
  consumers read from the same authoritative state.

---

## Lever 2: Promote the chrome layout to a first-class layout primitive

**Evidence.**
- Phase H caught a real layout bug: four `dock: bottom` widgets
  collapsed in real terminals because Textual's layout engine only
  picks one. The Phase H fix wrapped them in a `Vertical#recon-footer`
  container.
- Phase G's RunStatusBar uses `add_class("idle")` + CSS
  `display: none` because mutating `styles.display` directly races
  the render pipeline.
- The audit found that on a 24-line terminal, the chrome takes
  ~17 fixed lines and the body has only ~6 lines for content.
- Snapshot tests for full screens used to yield Screen as a child
  widget, which collapsed the chrome to nothing — a quality bug
  that hid for two phases.

**Recommended change.**
- Create a `recon/tui/chrome.py` module that owns the layout
  contract: `Header` at top, `Body` in the middle, `Footer` at
  bottom. The Footer is itself a stack of optional rows.
- Each chrome row exposes a `should_show()` method or a
  `is_active` reactive that the layout engine respects via CSS
  class toggles (not display:none mutations).
- The chrome adapts to terminal height: on `LINES < 30`, the
  ActivityFeed and LogPane collapse into a single 4-line shared
  pane with a tab to switch between them. On `LINES >= 50`, they
  get a 12-line stack.
- A `ChromeContract` test fixture that asserts every full screen
  composes the chrome correctly via push_screen (no more yield-as-
  child traps).

**Blast radius.**
- New `recon/tui/chrome.py` module
- `recon/tui/shell.py::ReconScreen` becomes a thin wrapper
- All four full screens (Welcome, Dashboard, Run, Browser) just
  override `compose_body`
- ~30 tests need to be migrated to the new chrome contract
- Snapshot baselines regenerated once

**Payoff.**
- The layout engine bug class disappears.
- Adding new chrome widgets is a one-line change in `chrome.py`,
  not a four-place CSS edit.
- Adaptive sizing for small/large terminals becomes a single CSS
  rule, not per-widget logic.

---

## Lever 3: Replace Rich-markup labels with a typed Label primitive

**Evidence.**
- The selector `[x]` bug. The curation `[x]` bug. Same root cause:
  Rich markup parses `[x]` as an unknown tag and silently drops it.
- The selector title `── SELECT COMPETITORS ──` doesn't render in
  the plain-text capture because the SVG-to-text script drops bold
  markup. Even when the markup IS valid, it's hard to verify.
- We've shipped 3+ Rich-markup-related fixes in this audit cycle
  alone.

**Recommended change.**
- Create a `recon/tui/labels.py` module with composable label
  builders:
  ```python
  Label.text("plain text")
  Label.icon("✓").color("green").space().text("Cursor.overview")
  Label.kbd("r").space().text("run")
  Label.checkbox(checked=True).space().text("Cursor")
  ```
- Builders escape Rich markup automatically and produce a string
  that's safe to pass to `Static.update()`.
- A `Label.checkbox(checked=False)` would always produce a marker
  the user can see — no more "bare `[x]` text" bugs.
- A `Label.kbd("r")` produces a uniformly-styled key indicator
  used by every keybind hint strip.

**Blast radius.**
- New `recon/tui/labels.py` module
- ~50 inline f-string label builds across the screens migrate to
  the new API
- New unit tests for the builders
- No CSS or layout changes

**Payoff.**
- The "Rich markup is a footgun" smell goes away.
- Visual consistency across screens is enforced by the type system
  rather than by manual copy-paste of color hex codes.
- A future theme system (light/dark/highcontrast) becomes a
  swap-the-color-table change instead of a 50-place edit.

---

## Lever 4: Pluggable LLM provider

**Evidence.**
- Today: hardcoded `claude-sonnet-4-5` in
  `pipeline.py::Pipeline._DEFAULT_MODEL`, in
  `dashboard.py::_estimate_full_run_cost`, in tests, in
  `client_factory.py`. ~15 places.
- The wizard step 4 asks for an "Anthropic API key" — no other
  option.
- Cost estimation hardcodes Anthropic's pricing. EUR/GBP/JPY users
  see dollars.

**Recommended change.**
- Define a `LLMProvider` protocol in `recon/llm.py`:
  ```python
  class LLMProvider(Protocol):
      name: str
      models: list[str]
      def create_client(self, model: str, api_key: str) -> LLMClient: ...
      def estimate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float: ...
  ```
- Ship two implementations: `AnthropicProvider` (current behavior)
  and a stub `OpenAIProvider` that demonstrates the contract.
- The wizard asks "Which provider?" → "Which model?" → "API key?".
  Workspace `recon.yaml` records the choice.
- Cost rendering uses the provider's currency (USD by default,
  configurable per workspace).

**Blast radius.**
- `recon/llm.py` (new protocol)
- `recon/client_factory.py` (provider registry)
- `recon/pipeline.py` (read provider from workspace)
- `recon/cost.py` (currency support)
- `recon/tui/screens/wizard.py` (provider step)
- ~10 tests for the new protocol

**Payoff.**
- Removes a single point of vendor lock-in.
- Makes recon usable in environments without Anthropic access.
- Enables A/B testing different models on the same workspace.
- Foundation for cost-aware routing (use cheaper models for some
  sections).

---

## Lever 5: Workspace state is too implicit

**Evidence.**
- Workspace state lives in 4 places: `recon.yaml` (schema),
  `competitors/*.md` (profiles), `.recon/state.db` (runs/tasks/
  hashes), `.env` (API key). Each is loaded by a different module.
- `Workspace.open()` returns an object with no clear ownership:
  is the schema cached? Is state.db opened? Is the
  IncrementalIndexer initialized? Different call sites get
  different combinations.
- `_estimate_full_run_cost(workspace)` re-reads the workspace
  from scratch even though we just opened it.
- The audit script and the test fixtures both have to manually
  create directories, write recon.yaml, mkdir competitors, etc.
- Recents file (`~/.recon/recent.json`) is global, not per-
  workspace.

**Recommended change.**
- A `WorkspaceContext` (overlapping name with the TUI's, rename
  one) that owns the full workspace state lifecycle:
  ```python
  ctx = await WorkspaceContext.open(path)
  ctx.schema           # cached
  ctx.profiles         # lazy
  ctx.state            # opened state.db
  ctx.index            # opened ChromaDB
  ctx.cost_estimator   # bound to schema
  await ctx.close()    # idempotent cleanup
  ```
- Used as an async context manager so cleanup is automatic.
- The TUI app holds a single `WorkspaceContext` for the active
  workspace and passes it to screens instead of `workspace_path`.
- A `Workspace.create()` helper for the test/audit case that does
  all the directory setup, schema write, and state.db init in
  one call.

**Blast radius.**
- New `recon/workspace_context.py` module
- `recon/workspace.py::Workspace` becomes the underlying data
  layer; `WorkspaceContext` is the cached facade
- `recon/tui/app.py` and screens migrate to ctx
- `recon/cli.py` migrates to ctx
- `tests/conftest.py` exposes a `workspace_ctx` fixture
- ~40 tests
- Audit script collapses to ~10 lines of setup

**Payoff.**
- One place to know "is this workspace ready?".
- Closes ChromaDB / SQLite handles deterministically (the audit
  was the second time we hit a `clear_system_cache` flake).
- Tests get faster because the schema is parsed once per ctx
  instead of once per `Workspace.open()` call.
- Cleanup on workspace switch becomes automatic.

---

## Lever 6: Onboarding-aware UX

**Evidence.**
- The audit found that the empty welcome state and the empty
  dashboard both expect users to know about the keybind hint
  strip. New users will look for buttons (the muscle memory from
  the GUI world).
- The wizard has no Esc hint and no documented exit path.
- The discovery screen says "Click Search More..." (mouse-first).
- The cost preview vs running cost vs total cost confusion has
  three different cost numbers in three different places.

**Recommended change.**
- Add a `--first-run` flag (or auto-detect via the absence of
  `~/.recon/seen.json`) that triggers a one-time onboarding overlay
  on the first launch:
  - "press n to create a project, o to open one"
  - arrow pointing at the keybind hint strip
  - Esc to dismiss
- Audit every screen for mouse-first language ("click", "press
  the button"). Replace with "press X" or "X to run".
- Document Esc as the universal back-out keybind for every modal.
- Unify the cost display: use the same icon (`$`) and the same
  precision (`$0.42`) in every place. Add labels: "this run",
  "running total", "estimate".

**Blast radius.**
- New `~/.recon/seen.json` flag
- New `recon/tui/onboarding.py` overlay
- ~10 copy edits across screens
- ~5 tests

**Payoff.**
- Drops the new-user time-to-first-discovery from "read the
  README + watch a video" to "30 seconds in the TUI".
- Makes recon's keyboard-first model legible without docs.

---

## Lever 7: Snapshot tests should fail loudly when the chrome is empty

**Evidence.**
- The dashboard / run / welcome snapshot baselines were ~14KB
  blank canvases for two phases (B and C) before Phase H caught
  them. The tests "passed" because broken baseline + broken
  render = byte-equal.
- The planner snapshot was missing button labels for *many* phases
  before Phase I caught it. Same root cause.
- Snapshot tests are a great regression-prevention tool but a
  terrible regression-detection tool: they only fire when something
  *changes*, not when something is *wrong*.

**Recommended change.**
- Add "presence assertions" to every snapshot test: after
  `snap_compare`, also assert that the captured SVG contains a
  set of expected text markers.
- For example, the dashboard populated snapshot must contain:
  - "COMPETITORS"
  - "discover" (in the keybind hint)
  - the company name from the test fixture
- For the planner: must contain "Add new", "Update specific",
  "Full pipeline" (so empty buttons fail loudly).
- For the selector: must contain "[x]" or "[ ]" markers.

**Blast radius.**
- New `tests/snapshot_assertions.py` helper
- ~11 snapshot tests get a presence assertion each
- One-time audit of every existing baseline to define the
  expected markers

**Payoff.**
- The "broken baseline freezes a broken render" failure mode
  goes away.
- New rendering bugs that affect *currently-tested* screens are
  caught immediately by the existing tests, with no extra setup.

---

## Lever 8: Engine progress is too coarse

**Evidence.**
- The pipeline emits `RunStageStarted(stage)` and
  `RunStageCompleted(stage)`. There's no per-section progress
  during research (which is the longest stage and the one users
  care about).
- The RunStatusBar shows a 0% bar even when 6 of 8 sections are
  done because there's no progress event to update it.
- The dashboard shows section status from disk frontmatter but
  only after the stage completes — there's no live "Cursor's
  pricing section is in flight" indication.

**Recommended change.**
- Pipeline emits `SectionStarted(competitor, section_key)` and
  `SectionCompleted(...)` events alongside the existing
  `SectionResearched` (which is currently a "wrote-to-disk" event).
- The RunStatusBar computes progress as
  `completed_sections / total_sections` from the bus.
- The chrome header gets a "Cursor: pricing (3/8)" sub-line during
  the research stage.

**Blast radius.**
- `recon/events.py` (2 new events)
- `recon/research.py` (publish at section start/complete)
- `recon/tui/shell.py::RunStatusBar` (compute progress from bus)
- `recon/tui/shell.py::ReconHeaderBar` (add sub-line)
- ~5 tests

**Payoff.**
- Live progress that actually moves during the longest stage.
- Better debugging when a particular section is hanging.
- Foundation for the "show the current LLM prompt" feature
  (would emit a `SectionPromptStarted(text)` event).

---

## Sequencing the levers

Not all 8 levers need to land. Here's a recommended execution
order based on risk × payoff:

1. **Lever 7** (snapshot presence assertions) — small, low-risk,
   pays off immediately by catching the next "blank baseline" bug.
2. **Lever 3** (typed Label primitive) — small, low-risk, removes
   a class of footguns we keep tripping over.
3. **Lever 1** (EventBus as run state source of truth) — medium
   risk, big payoff. Enables Lever 2 cleanly.
4. **Lever 2** (chrome layout primitive) — medium risk, fixes
   layout fragility for good. Should ship after Lever 1 so the
   chrome's run-state widgets read from the bus.
5. **Lever 8** (granular engine progress events) — small, isolated,
   makes the existing chrome much more useful.
6. **Lever 5** (WorkspaceContext lifecycle) — medium-large risk,
   touches CLI + TUI + tests. Pays off in test speed and ChromaDB
   reliability. Ship after the run-state work is stable.
7. **Lever 6** (onboarding UX) — small, copy-heavy, ship after
   the structural work to avoid wasted effort.
8. **Lever 4** (pluggable LLM provider) — large change, scope
   decision. Don't start unless someone actually wants to use
   another provider.

Levers 1+2+3+7 form a coherent "TUI quality" milestone that could
ship as a single 0.3.0 release. Levers 5+6+8 form a "engine and
UX polish" milestone for 0.4.0. Lever 4 is its own thing and
should be scoped separately.

## Out of scope (intentional)

- **Multi-user / cloud sync.** Recon is intentionally single-user
  local. Adding multi-user would change the entire data model.
- **Real-time collaboration.** Same reason.
- **Plugin system.** The schema-driven approach already gives a
  lot of customization. A plugin system would multiply complexity
  for marginal gain.
- **Web UI.** The CLI + TUI cover the use cases. A web UI would
  be a separate product.
- **Streaming LLM responses in the TUI.** Nice to have but not
  worth the complexity until we know users want it.
