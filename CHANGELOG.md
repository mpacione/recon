# Changelog

All notable changes to recon are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added -- Option U: TUI cleanup and polish

- **Cost preview in the run planner.** `RunPlannerScreen` accepts an
  `estimated_full_run_cost` arg and renders a `$X.XX (~$Y.YY per
  competitor)` line below the workspace stats. `DashboardScreen._push_planner`
  computes the estimate by walking the schema's sections and asking
  `CostTracker.estimate_section_cost` for each one across every
  profile at the section's verification tier, then adds a 15% overhead
  for synthesize/deliver/themes. Renders nothing if the estimate is 0
  (empty workspace, no schema, etc).
- **`DiscoveryScreen` "Add Manually" button is wired.** Clicking it
  mounts inline `name` and `url` inputs, submitting the name input
  commits via `DiscoveryState.add_manual` (the existing engine
  helper) and tears the inputs back down. Empty name = silent
  cancel. Catches the case where the LLM agent returns no candidates
  but the user already knows who to add.
- **`tui/widgets.py` shrunk from 219 lines to ~50.** Removed
  `StatusPanel`, `CompetitorTable`, `ProgressBar`, `ThemeCurationPanel`,
  and `RunMonitorPanel` — five widget classes that were defined as a
  reusable rendering layer but were never adopted by any screen. Kept
  the three formatter functions (`format_theme_list`,
  `format_progress_bar`, `format_worker_list`) since they're still
  used by `RunScreen` and the model tests.

### Tests

- 4 new TUI tests covering the new behavior:
  `test_tui_planner.py::test_cost_preview_shows_when_estimate_provided`,
  `test_cost_preview_hidden_when_estimate_zero`,
  `test_tui_discovery_screen.py::test_add_manually_button_mounts_inputs_and_adds_candidate`,
  `test_add_manually_with_empty_name_does_nothing`.
- 611 → 615 passing.

### Fixed -- ChromaDB test flake

- **`test_init_add_index_status_flow`** intermittent failures fixed.
  Root cause: ChromaDB caches a `SharedSystemClient` per `persist_dir`
  for the process lifetime, and pytest tmp_path teardowns left the
  Rust hnsw segment readers holding stale file handles, which a
  later test then crashed on with "Failed to pull logs from the log
  store" or `SQLITE_CANTOPEN`.
- New autouse pytest fixture in `tests/conftest.py` that calls
  `chromadb.api.client.SharedSystemClient.clear_system_cache()` after
  every test.
- New `IndexManager.close()` clears the cache and drops the local
  client/collection references. Used by the `recon index` CLI
  command in a `try/finally` so the production CLI also stops
  leaking handles between sequential invocations.
- Verified by 3 consecutive clean full-suite runs (previously failed
  ~1 in 3).

### Added -- Real Pause/Resume

- **Pause/Resume semantics** via an `asyncio.Event` where
  `set = running` and `cleared = paused`. Plumbed through:
  - `WorkerPool.run(pause_event=)` -- workers `_wait_for_resume()`
    before dispatching each task, polling so they can also notice a
    `cancel_event` becoming set during the pause.
  - `ResearchOrchestrator.research_all` and
    `EnrichmentOrchestrator.enrich_all` forward the pause_event to
    the pool.
  - `Pipeline` gains a `pause_event` attribute and an
    `_await_resume()` helper that blocks at every stage transition.
    Cancel always wins over pause.
- **TUI Pause button works.** First press clears `pause_event`, flips
  the button label to "Resume", sets `current_phase = "paused"`, and
  notifies. Second press sets the event, flips back to "Pause",
  resumes work.
- **Stop while paused** also sets `pause_event` so a wedged worker
  can observe the cancel and exit cleanly.
- 8 new tests covering the worker pool flag, the pipeline stage-
  boundary block, the button toggle, and a full TUI integration that
  drives planner → FULL_PIPELINE → Pause mid-flight (asserts no
  steps advance) → Resume → asserts COMPLETED.

### Added -- Integration and end-to-end test coverage

Filled the gaps in integration / e2e coverage so every feature shipped
in the 0.2.0 line through the diff/rerun/cancellation work has at
least one test that exercises it through a realistic user path.

**TUI integration tests** (`tests/test_tui_integration.py`):
- `TestPlannerDiffAllFlow` -- planner → DIFF_ALL → asserts the
  pipeline gets `stale_only=True`
- `TestPlannerRerunFailedFlow` -- planner → RERUN_FAILED → asserts
  the pipeline gets `failed_only=True`
- `TestStopButtonCancelsRunningPipeline` -- full mid-run cancellation:
  start a slow pipeline, press Stop, assert the cancel event is
  observed and the run is finalized as `RunStatus.CANCELLED` in the
  state store
- `TestFullPipelineThroughTuiNoMock` -- planner → UPDATE_ALL through
  the **real** `Pipeline` (not a mock), only the LLM client is faked.
  Catches end-to-end wiring regressions that the per-stage
  `Pipeline.execute` patch tests can't see.

**CLI sequential / e2e tests** (`tests/test_cli_e2e_fake_llm.py`):
- `TestCliSequentialWorkflow` -- the realistic happy path from
  `recon init --headless` through `add` → `research --all` →
  `enrich --all --pass cleanup` → `index` → `tag` → `status`,
  asserting profile content, frontmatter `section_status`, and CLI
  output at every step.
- `TestDiffSequentialWorkflow` -- regression test for the diff
  semantics: research once, run `recon diff --all` (asserts no LLM
  calls because content is fresh), force the section to look 90 days
  old, run diff again (asserts exactly one LLM call and that
  `researched_at` was bumped).
- `TestRunCostTracking` -- runs `recon run --from index` and verifies
  `StateStore.get_run_total_cost` is non-zero, proving every stage
  in the deliver chain calls `_record_tokens`.

7 new tests, 596 → 603 passing. Lint clean. The pre-existing
ChromaDB flake on `test_init_add_index_status_flow` is still
intermittent under full-suite load; tracked for a real fix.

### Added -- ADD_NEW handoff and cancellation plumbing

- **`ADD_NEW` planner operation is wired.** Selecting "Add new
  competitors" from the run planner now pushes `DiscoveryScreen`,
  creates profiles for the candidates the user accepts, and starts a
  pipeline run scoped to just those new names. Pre-existing
  competitors are not re-researched.
- **`asyncio.Event` cancellation token plumbed through the pipeline.**
  - `WorkerPool.run(cancel_event=)` checks the event before each task
    and marks any unstarted task as cancelled (`success=False`,
    `error=PipelineCancelledError`).
  - `ResearchOrchestrator.research_all(cancel_event=)` and
    `EnrichmentOrchestrator.enrich_all(cancel_event=)` accept a token
    and pass it down to the pool. They also break out of the
    section-batch loop early when the event fires.
  - `Pipeline(cancel_event=)` checks the event between every stage
    transition and marks the run as `RunStatus.CANCELLED` instead of
    `COMPLETED` if it fires.
- **`RunStatus.CANCELLED`** -- new terminal state distinguishing
  user-stop from a crash. `STOPPING` remains the brief transitional
  state.
- **TUI Stop button works.** `RunScreen._request_stop` finds the
  cancel event the runner stashed on `app._pipeline_cancel_event`,
  sets it, transitions the screen to `stopping`, and adds an activity
  log entry. The pipeline finishes its current stage and exits
  cleanly with status `cancelled`. Pause is still a no-op (real
  pause/resume needs WorkerPool semaphore suspension; deferred).
- **`tui/pipeline_runner.build_pipeline_fn`** creates a fresh
  `asyncio.Event` per run, stashes it on
  `screen.app._pipeline_cancel_event`, passes it into `Pipeline`, and
  always clears the reference in a `finally` so the next run starts
  with a clean slate.
- **`tui/pipeline_runner` ADD_NEW support**: ADD_NEW is no longer in
  the "not implemented" branch -- the dashboard handles the discovery
  push and then re-uses the UPDATE_SPECIFIC pipeline shape with the
  new names. The runner test for unsupported operations now uses a
  synthetic enum value to keep the no-op branch tested.
- **8 new tests**:
  - `test_workers.py::TestWorkerPoolCancellation` (3 tests covering
    pre-set, mid-run, and no-event behavior)
  - `test_research.py::test_research_all_honors_cancel_event`
  - `test_pipeline.py::TestPipelineCancellation` (2 tests:
    cancelled-before-start, mid-pipeline cancel)
  - `test_tui_run_screen.py` (Stop button sets event, Stop with no
    active pipeline notifies)
  - `test_tui_integration.py::TestPlannerAddNewFlow` (full ADD_NEW
    journey from planner → discovery → profile creation → pipeline
    scoped to new names)

### Added -- Diff and rerun operations (engine follow-ups)

- **Per-section `section_status` frontmatter.** Each profile now
  tracks `section_status: {<section_key>: {status, researched_at}}`
  in its frontmatter. `status` is `researched` or `failed`;
  `researched_at` is an ISO-8601 UTC timestamp set when the section
  is successfully appended. This is the durable record of which
  sections worked, which didn't, and when.
- **`ResearchOrchestrator.research_all(stale_only=, max_age_days=, failed_only=)`**.
  Three new scoping flags:
  - `stale_only=True` only researches sections older than
    `max_age_days` (default 30) per their `researched_at` stamp,
    including sections that have no stamp at all (never researched).
  - `failed_only=True` only researches sections whose
    `section_status.status` is not `researched` (so failed attempts
    and never-touched sections).
  - Flags can be combined with the existing `targets=` filter.
- **Research marks sections failed on exception.** When the LLM call
  raises (including after the web-search fallback), the orchestrator
  now writes `section_status[section_key] = {status: failed}` and
  re-raises. `rerun` / `failed_only` can pick it up next time.
- **`PipelineConfig.stale_only` / `max_age_days` / `failed_only`**
  threaded through `Pipeline._stage_research`.
- **TUI planner operations wired**: `DIFF_ALL`, `DIFF_SPECIFIC`, and
  `RERUN_FAILED` now build real `PipelineFn`s via
  `tui/pipeline_runner.py`. `DIFF_SPECIFIC` pushes the competitor
  selector first (same flow as `UPDATE_SPECIFIC`). `ADD_NEW` is the
  only operation still marked not-implemented — it needs a discovery
  round before research, which the planner doesn't hand off yet.
- **`recon diff [target | --all] [--max-age-days N]`** -- new CLI
  command that re-researches stale sections only. Supports
  `--dry-run` for a plan preview.
- **`recon rerun [target | --all]`** -- new CLI command that
  re-researches failed or missing sections only. Supports `--dry-run`.
- **Shared `_resolve_target(ws, target, all_targets)` helper** in
  `cli.py` so `research`, `enrich`, `diff`, and `rerun` all use the
  same case-insensitive target-matching and usage-hint path.
- **6 new orchestrator tests** covering section_status writes,
  stale_only behaviour (skip fresh, research old), failed_only
  behaviour (target failed, skip researched), and failure marking.
- **3 new CLI e2e tests** (`diff --all` with mixed ages, `diff
  --dry-run`, `rerun --all` with failed sections) that would catch
  regressions in either the flags or the CLI → orchestrator wiring.
- **4 new `tui/pipeline_runner` tests** asserting DIFF_ALL /
  DIFF_SPECIFIC / RERUN_FAILED are supported and map to the right
  `stale_only` / `failed_only` config flags.

## [0.2.0] -- 2026-04-10

## [0.2.0] -- 2026-04-10

First pipeline-complete release. `recon run` now actually runs the
whole pipeline end-to-end: research, verify, enrich, index, themes,
synthesize, deliver. The distribution is published to PyPI as
`recon-cli`; the binary on `PATH` is still `recon`.

### Added -- Packaging and docs (Option D)

- **PyPI-ready `pyproject.toml`.** Added `[project.urls]` (Homepage,
  Repository, Issues, Changelog), Python 3.13 classifier, expanded
  keywords and topic classifiers, and bumped the version to `0.2.0`.
- **`docs/getting-started.md`** — hands-on walkthrough from fresh
  install through `recon init`, `discover`, `run`, and browsing the
  results. Includes cost estimates, logging, and troubleshooting.
- **`docs/release.md`** — maintainer release process: bump, build,
  smoke test in a fresh venv, tag, publish to PyPI, create a GitHub
  release, and roll back if needed.
- **README `Install` section rewritten** to lead with
  `pip install recon-cli`, keep the editable source install for
  contributors, and link to the new getting-started guide.
- **Wheel smoke test in a throwaway venv** is now part of the
  release checklist. This caught the packaging bug fixed below.

### Fixed -- Packaging

- **`recon --version` crashed on fresh wheel installs.**
  `click.version_option()` was called without `package_name`, so it
  looked up the import name `recon` on PyPI, which doesn't exist
  (the distribution is `recon-cli`), and raised
  `RuntimeError: 'recon' is not installed. Try passing 'package_name' instead.`
  Fixed by passing `package_name="recon-cli"` and `prog_name="recon"`
  so `recon --version` prints `recon, version 0.2.0`. Guarded by a
  new regression test (`test_cli_e2e_fake_llm.py::TestVersionFlag`).

### Added -- Deep verification (Option V)

- **Per-section verification honoring schema tiers.** `Pipeline._stage_verify`
  now splits each researched profile by `##` heading, looks up each
  section's declared `verification_tier` in the schema, and runs the
  verification engine only on sections whose tier is `verified` or
  `deep`. Sections with `standard` tier are skipped with no LLM cost.
- **Verification summary attached to profile frontmatter.** Each
  verified profile gets a `verification:` block in its frontmatter
  keyed by section, with counts for `confirmed`, `corroborated`,
  `disputed`, `unverified`, and the per-source list (`url`, `status`,
  `notes`). Users can see the verification state of any profile
  without re-running the pipeline.
- **Verification cost recorded through the state store.** The verify
  stage now calls `_record_tokens` per outcome so `get_run_total_cost`
  reflects verification spend alongside research/enrich/synthesize.
- **`VerificationOutcome`** gained optional `competitor_name`,
  `section_key`, `input_tokens`, and `output_tokens` fields so
  downstream consumers (pipeline, CLI, frontmatter writer) can trace
  outcomes back to profiles and cost.
- **`recon verify [target | --all]` CLI command.** Runs just the
  verify stage, respecting per-section tiers. Supports `--tier`
  override (`standard` / `verified` / `deep`) and `--dry-run` to show
  which sections would be verified. Prints a per-section confirmed /
  disputed / unverified breakdown.
- **3 new `recon verify` fake-LLM e2e tests** (`test_cli_e2e_fake_llm.py`)
  covering `--all`, `--dry-run`, and single-target filter behavior.
- **3 new `Pipeline._stage_verify` tests** covering schema tier
  honoring, frontmatter summary writing, and cost recording.

### Added -- Pipeline completeness (Option P)

- **New `THEMES` pipeline stage.** `Pipeline` now discovers themes
  between `INDEX` and `SYNTHESIZE`, applies an optional curation
  callback, and tags competitors via the existing `Tagger`. This is
  the stage that used to be missing entirely — `recon run` never
  reached theme discovery before this change.
- **`SYNTHESIZE` stage actually synthesizes.** It retrieves chunks
  per theme from the live ChromaDB index, runs `SynthesisEngine`
  (single-pass by default, deep 4-pass if `config.deep_synthesis=True`),
  writes one file per theme under `themes/<slug>.md`, and records the
  token cost per call.
- **`DELIVER` stage distills and summarizes.** Runs `Distiller` per
  theme (writing `themes/distilled/<slug>.md`), then `MetaSynthesizer`
  across the distilled corpus, writing `executive_summary.md` to the
  workspace root.
- **`VERIFY` stage wired to `VerificationEngine`.** When
  `verification_enabled=True`, iterates researched profiles, extracts
  source URLs via regex, and runs the configured verification tier
  (`standard` / `verified` / `deep`). Outcomes are captured on
  `Pipeline.verification_results`. No-op when disabled or when no
  profiles have sources.
- **`Pipeline.theme_curation_callback`** -- optional
  `async (list[DiscoveredTheme]) -> list[DiscoveredTheme]` hook that
  fires between theme discovery and tagging. The TUI runner passes
  one that uses `push_screen_wait(ThemeCurationScreen)` so the user
  gets an interactive gate before expensive synthesis runs. Headless
  CLI runs leave this unset and auto-accept.
- **`PipelineConfig.theme_count`** and **`verification_tier`** knobs.
- **`recon.themes.build_workspace_chunks(workspace)`** -- shared
  helper extracted from the CLI's `_build_discovery_chunks`. Used by
  both `recon tag` and `Pipeline._stage_themes` so the two code paths
  cluster the same chunks the same way.
- **`tests/test_cli_e2e_fake_llm.py::test_run_command_full_pipeline_writes_synthesis_and_summary`**
  -- regression test that invokes `recon run --from index` with a
  fake LLM and asserts `themes/<theme>.md`, `themes/distilled/*.md`,
  and `executive_summary.md` all exist on disk.
- **8 new pipeline tests** covering themes discovery, curation
  filtering, synthesize file writes, deliver summary writes, verify
  wired/no-op modes, and progress callback stage coverage.

### Changed

- `recon run` now prints a manifest of what the pipeline produced:
  discovered themes, number of syntheses written, and the executive
  summary path.
- `recon tag` imports `build_workspace_chunks` from `recon.themes`
  instead of maintaining its own private `_build_discovery_chunks`.

### Fixed

- **`recon research <target>` now honors its positional argument.** The
  command previously ignored the target and always ran `--all`, silently
  researching every profile. Now it matches the name case-insensitively
  against the workspace, errors clearly on unknown names, and fails fast
  if neither a target nor `--all` is passed.
- **`recon enrich <target>` also honors its positional argument**, with
  the same semantics as `research`.
- **`recon run` no longer crashes on startup.** The CLI was passing an
  `index_manager` kwarg to `Pipeline()` that the dataclass doesn't accept.
  Removed the dead argument and wired the command through the existing
  `Pipeline` config.
- **TUI Run button now executes the engine.** `DashboardScreen.handle_planner_result`
  used to switch to the run mode and leave the screen idle. It now builds
  a real `PipelineFn` via `tui/pipeline_runner.py` and queues it on the
  app so `RunScreen.on_mount` can kick off the worker. Supports
  `FULL_PIPELINE`, `UPDATE_ALL`, and `UPDATE_SPECIFIC`; other operations
  notify the user they are not implemented yet.
- **`CompetitorSelectorScreen` is now reachable.** Selecting "Update
  specific" from the planner pushes the selector, and the resolved
  competitor list is plumbed all the way through `PipelineConfig.targets`
  into both `ResearchOrchestrator.research_all(targets=...)` and
  `EnrichmentOrchestrator.enrich_all(targets=...)`.

### Added

- `tests/test_cli_e2e_fake_llm.py` -- 5 end-to-end CLI tests that drive
  `recon research`, `recon enrich`, and `recon run` through `CliRunner`
  with the Anthropic client faked at `recon.client_factory.create_llm_client`.
  These would have caught both the `<target>` regression and the
  `recon run` `index_manager` crash before they shipped.
- `Pipeline.progress_callback` -- async `(stage, phase) -> None` hook
  called before and after each stage. Used by the TUI runner to update
  `RunScreen.current_phase` / `RunScreen.progress` reactively.
- `PipelineConfig.targets` -- optional competitor name filter threaded
  through research and enrich stages.
- `ResearchOrchestrator.research_all(targets=...)` and
  `EnrichmentOrchestrator.enrich_all(targets=...)` both accept a
  case-insensitive name list and raise `ValueError` on unknown names.
- `src/recon/tui/pipeline_runner.py` -- new module holding the planner
  `Operation` → `PipelineConfig` mapping, the `PipelineFn` factory, and
  the set of operations that require a selector push.

### Changed

- `.gitignore` now excludes `.coverage`, `logs_llm/`, and `vectors.db`
  so `git status` stays quiet after running the test suite or scratch
  workspaces.

## [0.1.0] -- 2026-04-09

First alpha release. The CLI is fully functional end-to-end against the
live Anthropic API. The TUI is usable for workspace setup, discovery, and
browsing but the pipeline-execution path is not yet wired; use the CLI for
research runs until the TUI is finished.

### Added

**Engine layer**

- Schema-driven research pipeline: Pydantic v2 schemas define sections,
  formats, rating scales, and source preferences. All worker prompts are
  composed at runtime from schema metadata -- no hardcoded per-section
  prompts.
- `discovery.py` -- iterative competitor discovery with an LLM agent using
  Anthropic's `web_search_20250305` tool. Candidates are deduped by URL
  domain across rounds. Falls back to training-data mode if the tool is
  unavailable.
- `research.py` -- section-by-section research orchestrator. Batches by
  section (all competitors for overview, then all for pricing, etc.) for
  consistency and clean resume points. Uses `web_search_20250305` by
  default so profiles cite live sources.
- `verification.py` -- multi-agent consensus at three tiers (standard,
  verified, deep).
- `enrichment.py` -- three progressive passes (cleanup, sentiment, strategic).
- `index.py` + `incremental.py` -- markdown chunking, local fastembed
  embeddings, ChromaDB vector store, SHA-256-hash-based incremental indexing.
- `themes.py` -- K-means clustering theme discovery with optional
  LLM-generated strategic labels. Sources sections are stripped before
  clustering so citation dates no longer dominate the feature space.
- `tag.py` -- theme tagging via retrieval relevance aggregation.
- `synthesis.py` -- single-pass and deep 4-pass synthesis (strategist,
  devil's advocate, gap analyst, executive integrator).
- `deliver.py` -- theme distillation and cross-theme meta-synthesis.
- `pipeline.py` -- full pipeline orchestrator with SQLite state tracking,
  run/resume, and per-phase cost recording.
- `state.py` -- async SQLite state store (runs, tasks, file hashes, costs).
- `llm.py` -- async Anthropic client wrapper with 120s default timeout,
  optional `tools` parameter, and token counting.
- `client_factory.py` -- API key validation and client creation.
- `logging.py` -- centralized logging to `~/.recon/logs/recon.log` with
  live flush so `tail -f` shows entries immediately.

**CLI (all 14 commands wired to the engine layer)**

- `recon init [dir] --headless --domain ... --company ... --products ...`
  creates a workspace with the full 8-section default schema (overview,
  capabilities, pricing, integration, enterprise, developer love,
  head-to-head, strategic notes).
- `recon add <name> [--own-product] [--from-list file]`
- `recon status`
- `recon discover [--rounds N] [--batch-size N] [--seed ...] [--auto-accept]`
- `recon research [--all] [--workers N] [--dry-run]`
- `recon enrich --pass {cleanup|sentiment|strategic} [--all]`
- `recon index [--full]` / `recon retrieve --query ...`
- `recon tag [--n-themes N] [--threshold F] [--dry-run]` with LLM-based
  strategic theme labels (haiku).
- `recon synthesize --theme "..." [--deep]`
- `recon distill --theme "..."` / `recon summarize`
- `recon run [--from stage] [--deep] [--dry-run]`
- `recon tui [--workspace dir]`
- `--log-level {DEBUG|INFO|WARNING|ERROR}` and `--log-file path` available
  on the main group.

**TUI (Textual)**

- `WelcomeScreen` with new-project / open-existing / recent-projects
  buttons and a persistent `~/.recon/recent.json`.
- `WizardScreen` -- 4-phase schema wizard (identity, sections, sources,
  review) as a pushable `ModalScreen` so the user never leaves the app.
- `DashboardScreen` with workspace stats, section progress, cost tracking,
  and a button-first action bar. Auto-prompts on empty workspace with
  clickable "Start Discovery" / "Add Manually" buttons.
- `DiscoveryScreen` with accumulating candidate roster, per-candidate
  toggle buttons, live search via `DiscoveryAgent`, and cursor-based
  keyboard navigation.
- `RunPlannerScreen` with 7 clickable operation buttons (number keys 1-7
  as shortcuts).
- `CompetitorBrowserScreen`, `CompetitorSelectorScreen`, `ThemeCurationScreen`.
- `RunScreen` with reactive progress/phase/cost attributes (screen renders
  and responds to buttons; the pipeline wiring is WIP).
- `Modes`-based navigation with independent screen stacks for dashboard
  and run modes.
- Warm amber retro terminal aesthetic via shared CSS theme.

**Tests**

- 534 passing tests, 11 SVG snapshot tests, 4 skippable real-API tests.
- Unit tests for every engine module.
- Integration tests covering wizard → workspace, research → enrichment,
  theme discovery → tagging, synthesis → distill → summarize, incremental
  indexing, pipeline orchestration, state store, cost tracker, and
  CLI end-to-end.
- TUI tests: mode switching, welcome → workspace, dashboard buttons,
  discovery auto-start, pipeline gate via `push_screen_wait`, and full
  wizard → dashboard flow.
- `tests/test_e2e_real.py` -- opt-in tests that call the real Anthropic
  API. Skipped by default, run with `ANTHROPIC_API_KEY=sk-ant-... pytest tests/test_e2e_real.py -v`.

**Documentation**

- `design/` -- six design documents covering pipeline, architecture,
  research/verification, setup/discovery, operations, and TUI design.
- `design/wiring-audit.md` -- explicit audit of TUI → engine wiring
  based on `code-graph-mcp` analysis. Documents which screens, buttons,
  and handlers reach the engine vs. dead-end in the interface layer.
- `CLAUDE.md` at repo root and `~/.claude/CLAUDE.md` -- TDD and code
  style guidelines for collaborative development.

### Known gaps (deferred)

- **TUI Run button does not reach the pipeline engine.** The
  `DashboardScreen.handle_planner_result` callback references a function
  (`_run_full_pipeline`) that was never implemented. Clicking Run in the
  TUI shows the planner but does nothing when an operation is selected.
  Workaround: use `recon run` on the CLI.
- `CompetitorSelectorScreen` is not pushed from any caller. It was built
  for planner operations 2 and 4 (update specific, diff specific) but
  those routes are not wired.
- `DiscoveryScreen` has an "Add Manually" button but no handler branch.
- `RunScreen` Pause/Stop buttons show "not yet implemented" notifications.
- `tui/widgets.py` defines four widgets (`StatusPanel`, `CompetitorTable`,
  `ThemeCurationPanel`, `RunMonitorPanel`) that were designed as a reusable
  rendering layer but were never adopted by the screens.
- `recon research <target>` positional argument is silently ignored --
  the command always runs `--all`.

All of these are tracked in `design/wiring-audit.md`. None affect the
CLI pipeline.
