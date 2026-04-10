# Changelog

All notable changes to recon are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
