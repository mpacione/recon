# Changelog

All notable changes to recon are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed -- Web UI v4 redesign (TUI reskin + wizard paradigm)

Full rebuild of the frontend around new Figma designs. The old
workspace-then-6-tabs shape (overview/competitors/template/runs/brief/
settings) is replaced with a 5-step wizard flow behind a numbered top
nav: RECON home → PLAN [1] → SCHEMA [2] → COMP'S [3] → AGENTS [4] →
OUTPUT [5].

#### New frontend architecture

- `static/recon.css` (new) — v4 layout: top/bottom nav, per-tab styles,
  3 responsive tiers (mobile <560, tablet 560–820, desktop).
- `static/primitives.css` rewritten — parchment-on-black token set
  (cream `#ede5c4` on `#000`, body tan `#a59a86`, 4px radius, 4/12
  card padding). Dropped amber/matrix/crypt theme variants; one look.
- `static/app.js` rewritten — hash router with query-param support
  (`?run=<id>`, `?autostart=1`), scoped hotkey store with
  `allowInEditable` escape hatch, screen teardown store for SSE and
  interval cleanup.
- `static/index.html` rewritten — 6 `<template id="screen-*">` blocks,
  iconify-icon script tag for Lucide glyphs.

#### Tab implementations

- **RECON home** — projects table (name/status/count/date/path, grid
  reflows on narrow viewports), NEW PROJECT modal that creates a
  workspace + saves Anthropic/Gemini API keys + jumps to PLAN.
- **PLAN** — path header with LOCAL DIR action, RESEARCH BRIEF
  textarea seeded from `workspace.domain`, model selector with
  per-run `$` cost, worker count stepper (−/+).
- **SCHEMA** — dossier section list with debounced `PUT /api/template`
  on each toggle, preferred-format pill per row.
- **COMP'S** — auto-discovers on entry via `POST /api/discover`,
  deselect dims rows (reconciled on RUN via `DELETE /api/competitors`),
  live cost estimator (`selected_count × per_comp_cost`), EDIT TERMS
  modal, RUN button navigates to AGENTS with `?autostart=1`.
- **AGENTS** — subscribes to `/api/events` (global) and filters by
  `run_id`; POSTs the run *after* SSE attaches to avoid race with
  fast (fake-LLM) runs. Persona worker cards (Scout/Ranger/Scribe/
  Herald/Sentinel with rabbit/squirrel/bird/cat/dog icons, cheeky
  idle pulse every ~15s). Per-competitor rows with `▓▒░` progress.
  Completion modal routes to OUTPUT.
- **OUTPUT** — box-drawing file tree (`├── └── │`), markdown preview
  (currently exec summary only), REVEAL-in-Finder button per file.

#### New backend endpoint

- `POST /api/reveal` — opens a file or directory under the workspace
  root in the host file manager. macOS `open -R`, linux `xdg-open`,
  windows `explorer /select`. Path confinement check refuses targets
  outside the workspace.

#### Hotkey system

- `0` jumps home, `1-5` switch flow tabs. Per-screen bindings layer
  on top (`↑↓`/`jk` for row nav, `↲` primary action, `ESC` back/close,
  context keys like `N`/`S`/`R`/`L`/`T`).
- Registry supports scope IDs (`global`, `project-tabs`, `screen:*`)
  and the `allowInEditable` flag, which lets `enter`/`escape`
  propagate out of focused inputs while keeping number keys from
  being swallowed.

#### Kill list

- v3 workspace-then-6-tabs UI (`overview`, `competitors`, `template`,
  `runs`, `brief`, `settings` routes).
- Theme switcher (`amber` / `dark` / `matrix` / `crypt`).
- Cmd-K palette, API-keys popover, themes-gate modal (deferred).
- `Departure Mono` / Inter-4 hybrid typography (single `SF Mono` via
  `ui-monospace` now).

#### Deferred

- Persisting the research brief (no `PATCH /api/workspace` yet).
- Adding schema sections via UI (backend endpoint missing).
- Pause/resume/restart endpoints for the agent-card menu.
- AI-improve button on COMP'S search terms modal.
- Themes stage re-gated into AGENTS (user chose to defer).

### Added -- Web UI (Phases 1-7 + typography/nav polish)

A third recon interface alongside the CLI and TUI. Local FastAPI app served
via `recon serve` (wraps uvicorn, opens the browser, binds loopback only).
Single-worker by design so the in-process EventBridge can fan engine events
to SSE clients without cross-process state. Static Alpine.js shell —
deliberately no bundler — with a hash router, Alpine stores for navigation
and reactive state, and mock-data injection for visual QA via `Alpine.$data`.

Screens shipped: Welcome (recents picker), Describe (new-project form),
Discovery (manual-mode candidate curation; LLM-driven search is a later
phase), Template (research-section checklist), Confirm (model + workers +
estimate). Dashboard / Run / Results / Curation / Browser / Selector are
placeholder routes that resolve without 404ing — the TUI SVGs in
`docs/screenshots/tui/` are the target shapes for when we port them.

#### Styling pass — neo-retro rather than terminal-emulator

- **Typography:** dropped Departure Mono entirely. Inter 4.0 (rsms.me CDN)
  handles headers/body/nav with uppercase + ~0.08em tracking for the retro
  CLI vibe; JetBrains Mono (Google Fonts) carries data, markers, code, and
  input content. The all-mono original made the browser feel like an
  xterm clone rather than a sibling UI.
- **Markers:** hybrid system — Unicode geometric shapes (U+25xx, safe for
  the no-emoji test) for state, Lucide icons via `<iconify-icon>` for
  click affordances. 3-state candidate marker now reads as a progressive
  fill: `□` scaffold → `▣` researching → `■` researched. Previously
  scaffold and researching both showed `□` and were distinguished only by
  colour, which failed the "glance test."
- **Flow-progress nav:** restructured from a visual breadcrumb into a
  clickable nav. Completed steps are links (underline on hover, `role=
  "link"`, keyboard-accessible); the current step is `aria-current="step"`
  and the future steps are `aria-disabled="true"`. No separate top/side
  nav — the pipeline progression *is* the nav.
- **Dark-theme colour match** to cyberspace.online (`#0d0d0d` panel on
  `#000000` page, `#e0a044` amber accent, `#3a3a3a` borders) plus
  a `code`-tag cream tint for inline markdown.

#### API + CLI

- `recon serve --host/--port/--no-browser/--log-level/--unsafe-bind-all`
- `GET  /api/health`, `/api/recents`, `/api/workspace`, `/api/results`
- `POST /api/workspaces` (create) · `POST /api/discovery/round` (manual
  candidates) · `GET  /api/events` (SSE)
- The recents store was lifted out of `recon.tui.screens.welcome` into a
  shared module so both UIs read the same `~/.recon/recent.json`.

#### Tests

- 84 web tests (`tests/web/`) cover REST smoke, recents parity with the
  TUI, discovery round validation, and a `test_root_does_not_use_emojis`
  guard that forbids codepoints in U+2600–U+27BF. All passing.
- Existing 600+ engine and TUI tests unaffected.

#### Reference captures

- `docs/screenshots/web/*.png` — html2canvas captures of each shipped
  screen at 2x DPR with mock data injected.
- `docs/screenshots/tui/*.svg` — 11 pytest-textual-snapshot baselines,
  used as the target shape for the web screens still to be ported.

### Fixed -- TUI audit Phase Q (wizard completion had the same bug)

Continuing the Phase P audit: if "implicit handshake via mutable app
state" is the bug class, then anywhere the codebase does the same
``switch_mode("run") → remove_mode → add_mode → switch_mode("dashboard")``
dance would trip the same cached-RunScreen trap. Grepping for
``switch_mode`` turned up **one more instance** -- the wizard
completion handler had the exact same 4-line dance at the end of
``_create_workspace_from_wizard``.

So: a user who creates a new workspace via the welcome → new →
wizard → confirm flow would hit the same pipeline stall on their
first launch, for the same reason. The Phase P fix only touched
the workspace-selected handler, not the wizard-completed one.

#### Fix

Extracted ``ReconApp._rebuild_dashboard_mode`` helper that both
handlers now call. The helper does the ``_loading`` holding-mode
dance in one place, so the dashboard can be rebuilt without
touching the run mode. Both entry points now flow through the same
code path:

```
on_welcome_screen_workspace_selected -> _rebuild_dashboard_mode()
_create_workspace_from_wizard       -> _rebuild_dashboard_mode()
```

Run mode stays uninstantiated until the user actually wants to
launch a pipeline, regardless of which entry point they came in
through.

This also DRYs up the handler code: both 3-line dances collapsed
to a single ``self._rebuild_dashboard_mode()`` call.

723 still passing. Lint clean.

### Fixed -- TUI audit Phase P (cached-screen lifecycle + bug class analysis)

The user reported: "when I try to run the pipeline, this happens.
it hung, or it's working but there is no terminal logging to show
progress." They attached a log showing the pipeline queued but
never started. They also asked that every flaw be treated as a
symptom of a wider class, not just patched individually.

#### The surface symptom

```
16:17:24 INFO run RunScreen.on_mount has_pending_pipeline_fn=False
16:17:29 INFO dashboard action_run competitors=15
16:17:34 INFO dashboard queued pipeline_fn, switching to run mode
                  (nothing further -- pipeline never started)
```

``RunScreen.on_mount`` fired **once at app startup time** (long
before any pipeline had been queued) and saw no pending pipeline.
When the user later queued a pipeline and the app switched to run
mode, Textual **reused the cached RunScreen instance** -- its
``on_mount`` did NOT fire a second time, so the pending pipeline
sat on ``app._pending_pipeline_fn`` forever. Phase: Idle.

#### Why on_mount fired at startup (unusual)

The Phase-B ``on_welcome_screen_workspace_selected`` handler
contained a hack:

```python
self.switch_mode("run")        # <-- early run-mode activation
self.remove_mode("dashboard")
self.add_mode("dashboard", self._make_dashboard_screen)
self.switch_mode("dashboard")
```

The ``switch_mode("run")`` was used as a holding mode so
``remove_mode("dashboard")`` wouldn't raise ``ActiveModeError``.
Side effect: the run mode's RunScreen instantiated early, fired
``on_mount`` with ``_pending_pipeline_fn=None``, and permanently
cached the instance. Any later pipeline launch via the welcome
flow silently hit the stale one-shot lifecycle.

#### Why my tests missed this

All my PTY tests for the pipeline-launch path spawned with
``recon tui --workspace=...``, bypassing the welcome screen.
``ReconApp(workspace_path=...)`` skips the
``on_welcome_screen_workspace_selected`` handler entirely, so the
early ``switch_mode("run")`` never fired. The test's ``RunScreen``
got its ``on_mount`` at the right time and the handshake worked.
Tests green, real users broken.

### The bug class: "implicit handshake via mutable app state"

Stepping back from the specific symptom: the root problem is a
coupling pattern that shows up in multiple places.

> Component A mutates ``self.app._some_attribute`` and expects
> Component B to read it at exactly the right lifecycle event. No
> type contract, no ownership, no subscription, no backpressure.
> When the lifecycle event doesn't fire or fires at the wrong
> time, the handshake silently breaks and nothing logs.

Instances found in the audit:

| Site | Reads | When | Fragile? |
|---|---|---|---|
| RunScreen.on_mount | ``app._pending_pipeline_fn`` | once, at first instantiation | **YES -- this bug** |
| RunScreen._request_stop | ``app._pipeline_cancel_event`` | every button press | no (runtime read) |
| RunScreen._toggle_pause | ``app._pipeline_pause_event`` | every button press | no (runtime read) |
| ReconScreen.refresh_chrome | ``app.workspace_context`` | every chrome update | no (property-style read) |
| DashboardScreen.on_screen_resume | ``self._workspace_path`` | every mode activation | no (runtime read) |

Only the RunScreen pending-pipeline case was fragile. But the
pattern itself was the smell.

### The systemic fix

Three changes, not one:

**1. Canonical launcher on ReconApp.** ``app.launch_pipeline(fn)``
is now the only supported way to start a pipeline. It owns both
halves of the handshake: queueing the fn on the app AND calling
``switch_mode("run")``. Screens no longer touch
``_pending_pipeline_fn`` directly. The dashboard calls
``self.app.launch_pipeline(pipeline_fn)`` instead of a 3-line
queue + switch_mode sequence. One entry point, one contract.

**2. RunScreen.on_screen_resume replaces on_mount.** The
``_consume_pending_pipeline`` hook fires now on ``on_screen_resume``,
which Textual invokes on **every** mode activation, not just the
first. ``on_mount`` also calls it as a belt-and-suspenders so the
very first activation (which does fire ``on_mount``) still works.
Both lifecycle hooks pass through the same idempotent consumer.

**3. Dedicated holding mode on workspace-selected.** The
``on_welcome_screen_workspace_selected`` handler no longer uses
``switch_mode("run")`` as a holding mode during the dashboard
rebuild. Instead it registers a dedicated ``_loading`` mode
(bare ``Screen`` class) and switches to that before
``remove_mode("dashboard")``. The run mode is untouched, so its
cached instance stays uninstantiated until the user actually
wants to launch a pipeline -- at which point ``launch_pipeline``
kicks off ``switch_mode("run")`` and ``on_screen_resume`` fires
for the first time with a pending pipeline to consume.

#### Collateral improvement

``DashboardScreen.on_screen_resume`` was silently swallowing
exceptions with ``except Exception: pass``. A broken workspace
(deleted, corrupt recon.yaml) would freeze the dashboard at
stale data with no visible indication. Now logs via
``_log.exception`` so the traceback lands in recon.log.

### New regression tests

``TestWelcomeToRunPipelineFlow::test_pipeline_launches_after_welcome_flow``
-- the canonical welcome-flow pipeline test. Seeds a real
workspace as a recent project, spawns ``recon tui`` with a fake
``$HOME``, presses ``1`` on welcome to open the recent, then
drives dashboard → r → 7 → run monitor. Asserts the pipeline
reaches the research stage. This test **would have failed** before
the fix and would have caught the bug on day 1 of Phase M.

This plugs the "test entry points don't match user entry points"
gap identified as part of the bug-class analysis: every new PTY
test for a behavior-after-navigation should go through the same
navigation path a real user takes.

### Why this matters beyond the one bug

The Phase B ``switch_mode`` dance had been in the codebase since
the chrome work landed. Every phase after B (C, D, E, F, G, H, I,
J, K, L, M, N, O) ran through it and passed tests. The bug only
manifests when the user navigates welcome → dashboard → pipeline
**in that specific order**. I shipped 13 phases without catching
it because every test I wrote bypassed the welcome flow.

The lesson: **test the navigation paths users actually take, not
the programmatic shortcuts tests make convenient.**

722 → 723 passing. Lint clean. 11 snapshots.

### Fixed -- TUI audit Phase O (Discovery redesign + stale dashboard data)

User showed screenshots of a completed discovery round, then
reported: **(1)** the `[x]` checkbox markers on discovery candidates
were invisible, **(2)** the chunky action-bar buttons clashed with
the cyberspace.online visual language, **(3)** "I tried to run the
pipeline on the sources found and it appears to be stalled and not
working -- have we tested that?"

The honest answer on the pipeline stall was no -- I had PTY tests
that press `r` and `7` on a pre-populated dashboard, but no test
that runs discovery FIRST and then tries to launch the pipeline.
Writing that test immediately exposed bug #3.

#### Bug: stale dashboard data after discovery → pipeline never launches

``DashboardScreen.handle_discovery_result`` creates profiles on disk
but doesn't refresh ``self._data``. In Pilot unit tests this is
visible; in real terminals the modal dismissal lifecycle usually
fires ``on_screen_resume`` which refreshes the data, so the bug was
masked most of the time. When the refresh didn't fire,
``action_run`` would see ``total_competitors == 0`` and notify
"Nothing to run" -- silently breaking the pipeline launch and
leaving the user staring at an unchanged dashboard.

**Fix:** ``handle_discovery_result`` now explicitly calls
``self.refresh_data(build_dashboard_data(ws))`` after creating all
the profiles. The local data snapshot is fresh the moment the
discovery modal dismisses, regardless of what Textual's resume
lifecycle does. Now also logs exceptions via ``_log.exception``
instead of swallowing them silently, because the original
``except Exception: pass`` was the other half of why the bug was
invisible.

#### Bug: Discovery `[x]` checkbox markers silently dropped

Same root cause as the selector/curation bug from Phase I --
``Button("[x]")`` passes the label through Rich markup, which
parses ``[x]`` as an unknown tag and drops it. Every accepted
candidate rendered with an empty checkbox button.

**Fix:** Redesigned the candidate list as ``TerminalBox`` cards
(Phase J primitive) with escaped bracket markers embedded in the
card header:

```
╭─────────────────────────────────────────────╮
│ [x]  Cursor  ·  https://cursor.com  ·  Tier: Established │
│                                              │
│ AI-powered code editor with deep codebase... │
│                                              │
│ found via: G2 category leader, 3x lists      │
╰─────────────────────────────────────────────╯
```

Card border colors reflect acceptance state: amber border +
amber `[x]` when accepted, dim-grey border + dim `[ ]` when
rejected. At a glance you can see the accepted roster without
squinting at checkbox columns.

#### Bug: Action-bar buttons clashed with the retro visual language

The 5 action buttons (Done / Search More / Add Manually / Accept
All / Reject All) used Textual's default variant styling -- chunky
3-line chrome with filled primary variant -- which looked like
Bootstrap dropped into a retro terminal.

**Fix:** Flattened the Discovery action bar to match the
cyberspace.online footer pattern:
- `border: none; background: transparent` on every button
- Amber `-primary` variant instead of filled
- Labels prefixed with escaped bracket keybinds:
  `[↵] done`, `[s] search more`, `[n] add manually`,
  `[a] accept all`, `[x] reject all`
- Added keybind shortcuts `d` / `s` / `n` / `a` / `x` so users
  don't need to click at all

#### New PTY test coverage

``TestDiscoveryToPipelineFlow::test_dashboard_action_run_after_discovery_reaches_planner``
-- pre-populates 5 profiles on the filesystem (simulating a freshly
completed discovery round), then spawns recon, presses `r`, presses
`7`, and asserts the pipeline actually transitions through the
research stage. This is the test that would have caught the stale-
data bug on day 1. It runs in ~1.5 seconds.

``TestDiscoveryScreenRendersCards::test_discovery_empty_state_shows_key_hints``
-- spawns recon, presses `d`, asserts all 5 action-bar button
labels are visible with their bracket key hints intact
(`[↵] done`, `[s] search more`, etc). This catches the Rich
markup regression.

#### Diagnostic logging added on the pipeline-launch path

``DashboardScreen.handle_planner_result``, ``_start_pipeline_for_operation``,
``RunScreen.on_mount``, ``start_pipeline``, and ``_execute_pipeline``
all now log at INFO level on entry. If a user ever reports a pipeline
stall in the future, these 5 log lines tell us exactly where the
flow broke:

```
handle_planner_result operation=FULL_PIPELINE
_start_pipeline_for_operation operation=FULL_PIPELINE targets=None
queued pipeline_fn, switching to run mode
RunScreen.on_mount has_pending_pipeline_fn=True
RunScreen.start_pipeline called
RunScreen._execute_pipeline worker entered
```

720 → 722 passing (+2 new PTY tests; snapshot regen for Discovery).
Lint clean.

### Added -- TUI audit Phase N (input focus + workspace recovery)

Two more PTY tests to lock in behaviors that were working but
untested -- both are regressions waiting to happen.

**``TestInputFocusVsScreenBindings::test_r_inside_add_manually_input_types_char``**

Covers a user-facing concern: "if I'm typing a competitor name
that contains 'r', will it accidentally open the run planner?"
The answer is no because Textual's key dispatcher sends keystrokes
to the focused Input first and they never propagate to screen
BINDINGS. But the default focus behavior of widgets is exactly the
kind of thing that breaks silently in a future upgrade. This test
types ``"recon research tool"`` into the manual-add Input and
asserts (a) the text lands in the input, (b) ``RUN PLANNER`` never
appears (proving ``r`` didn't leak), (c) ``DISCOVERY`` never appears
(proving ``d`` didn't leak).

**``TestWorkspaceRecoveryEdgeCases::test_nonexistent_workspace_path_falls_back_to_welcome``**

Covers: ``recon tui --workspace /does/not/exist`` should show the
welcome screen instead of crashing. This already works because
``ReconApp._make_dashboard_screen`` returns a WelcomeScreen when
the path doesn't contain ``recon.yaml``, but nothing was pinning
that behavior. Test spawns recon with a bogus ``--workspace`` and
waits for "RECENT" (welcome chrome) to render.

718 → 720 passing. Lint clean.

#### Other edge cases manually verified (not added as tests yet)

- Running the pipeline without an API key surfaces the warning
  notification and the user can still navigate back to dashboard
  with ``b``.
- Discovery without an API key shows "manual only" notification
  and the screen still renders.
- Wizard ``Tab`` navigates between the 3 Input fields (Company /
  Products / Domain) and typed text is preserved in each.
- Workspace with broken YAML in recon.yaml doesn't crash (captures
  7500+ chars of output).
- Recent project pointing at a deleted directory doesn't crash;
  welcome stays visible.
- Empty submit on the manual-add Input is a no-op (no profile
  written to disk).
- F-keys (F1/F5/F12) don't crash; they're silently ignored.
- Pressing ``m`` + typing + empty Enter does nothing harmful.

### Fixed -- TUI audit Phase M (Ctrl+C, add-manually round trip)

More user-reported issues caught by end-to-end PTY testing. The
theme of this phase: **every keystroke a user expects should actually
do something**, and the way to prove that is to press real keys in
a real terminal.

#### Bug: Ctrl+C didn't quit the app

Textual's default input handling treats Ctrl+C as a regular key
(no effect), not as SIGINT. Users who tried Ctrl+C to exit saw no
response and had to find another way out. Fix: new binding
``Binding("ctrl+c", "quit", "Quit", show=False, priority=True)``
on ``ReconApp``. Priority flag makes sure screen-level bindings
never eat Ctrl+C first.

#### Tests

New ``TestAppLevelKeybinds`` class in test_tui_real_terminal.py:
- ``test_ctrl_c_exits_from_dashboard`` -- verifies Ctrl+C kills
  the app cleanly (WIFEXITED or WIFSIGNALED both accepted)
- ``test_question_mark_shows_help_notification`` -- verifies the
  existing ``?`` binding surfaces the "Keybinds" toast

New ``TestAddManuallyFlow`` class exercises the full round trip:
- empty workspace dashboard renders
- press ``m`` → Input mounts
- type "Acme Widgets" + Enter
- "Added" notification appears
- **profile file actually lands on disk** in ``workspace/competitors/``

The disk-write assertion is the piece the in-process Pilot tests
couldn't catch: you can test widget mount/focus in isolation but you
can't easily verify the workspace state on disk without a full
subprocess. The PTY test does both in ~1.5 seconds.

715 → 718 passing. Lint clean.

#### Edge cases also manually verified

- Wizard Esc → back to welcome (already worked, now confirmed)
- Narrow 80x24 terminal: dashboard renders, ``r`` → planner, Esc
  back all work
- ``?`` key shows help toast
- Unknown keys (like ``z``) don't crash; the app ignores them
- Rapid key bursts in modals don't crash (planner absorbs unknown
  keys silently)

### Fixed -- TUI audit Phase L (universal Escape on modals)

Continuing the keybind audit after Phase K's real-terminal coverage
exposed a gap: four modal screens (planner, discovery, selector,
theme curation) had NO ``escape`` binding. Users who pushed into a
modal and wanted to back out could only click the "Back" / "Cancel"
button -- on a keyboard-first TUI, that's broken. Every other modal
in the ecosystem (vim, k9s, lazygit, fzf, etc.) treats Esc as the
universal "back out" key. recon should too.

#### Fix

Added ``Binding("escape", "cancel", ..., show=False)`` to all four
modal screens, plus the corresponding ``action_cancel`` methods:

- **RunPlannerScreen.action_cancel** -> ``dismiss(None)``  (same as
  the existing Back button)
- **DiscoveryScreen.action_cancel** -> ``dismiss(state.accepted_candidates)``
  (preserves whatever the user has already accepted -- matching the
  Done button, NOT the Cancel semantics. Escape = "I'm done", not
  "throw it all away", which is the less surprising default when
  you've been curating for a while.)
- **CompetitorSelectorScreen.action_cancel** -> ``dismiss([])``
- **ThemeCurationScreen.action_cancel** -> ``dismiss([])``
  (empty selection tells the pipeline to skip synthesis without
  failing the run)

#### Tests

New ``TestModalEscapeKeybinds`` class in
``tests/test_tui_real_terminal.py`` with 3 PTY-based tests:

- planner Esc returns to dashboard
- discovery Esc returns to dashboard
- selector Esc returns to dashboard (requires the user to traverse
  planner -> digit 2 -> selector first, which exercises the full
  navigation chain)

712 -> 715 passing. Lint clean.

Wizard modal already had ``escape`` wired to ``action_go_back``
(Phase B). Browser screen already had it (Phase E). Every modal in
the app now backs out on Esc.

### Fixed -- TUI audit Phase K (keybind regression + test pollution)

User reported "none of the keyboard commands do anything" and asked
whether the test suites actually verify real keyboard wiring. The
honest answer was "no" -- the Phase E unit tests verified the action
methods work when called directly but never pressed real keys end-to-
end, and the Phase H smoke test only checked ``q`` (an App-level
binding) which meant every screen-level binding could have been
broken and the suite would still be green. This phase closes that
gap and fixes two production bugs the new coverage caught.

#### Bug #1: tests polluted the user's real ``~/.recon/recent.json``

Three integration tests (``test_welcome_new_project_wizard_to_dashboard``,
``test_open_workspace_switches_to_dashboard``, and friends) called
``ReconApp()`` without patching ``_DEFAULT_RECENT_PATH``, so every
test run wrote pytest tmp paths to the global recents file. After a
normal dev session that file accumulated 10+ stale entries, which
then rendered in the welcome screen's "Recent Projects" list the
next time the user ran ``recon tui``. Beyond the visual garbage,
it caused **Bug #2**.

**Fix (two parts):**
1. New autouse fixture in ``tests/conftest.py::_isolate_recent_projects``
   monkey-patches ``recon.tui.screens.welcome._DEFAULT_RECENT_PATH``
   to a per-test tmp dir. Every test now writes to isolated state.
2. ``WelcomeScreen.__init__`` used to capture ``_DEFAULT_RECENT_PATH``
   as a default argument value -- which is evaluated at function
   definition time, NOT call time. That meant monkey-patching the
   module variable had no effect on screens constructed later.
   Fixed to read the module variable at call time:
   ``self._recent_path = recent_projects_path or _DEFAULT_RECENT_PATH``.
   This is the small-but-important distinction between default args
   and runtime lookups in Python that bites everyone once.

#### Bug #2: welcome screen clipped its Input off-screen on ``n`` press

``WelcomeScreen._show_new_input`` mounted an Input into the
``#welcome-container`` Vertical and called ``.focus()``. On a clean
install this was fine -- banner + tagline + hint + empty recents +
Input all fit in the viewport. But with a polluted recents file (or
any user with 3+ real recents), the container overflowed the
``align: center middle`` parent and the new Input clipped below the
viewport fold. Users saw no visible change, concluded the key was
broken, and gave up. Dashboard ``m`` (manual add) had the same
structure but the empty-prompt container sat at the top of the body
region instead of being vertically centered, so it never triggered
the overflow path.

**Fix:**
1. ``#welcome-body`` now uses ``align: center top`` (was
   ``center middle``) and sets ``overflow-y: auto`` so the container
   scrolls when its contents grow.
2. New ``WelcomeScreen._scroll_input_into_view`` helper calls
   ``call_after_refresh(widget.scroll_visible, animate=False)`` after
   mounting the Input. ``scroll_visible`` walks ancestor scrollables
   until the widget is in frame -- which is exactly the behavior
   that was missing. The ``call_after_refresh`` defer matters
   because ``mount`` is async-ish and calling ``scroll_visible``
   inline races the layout pass.

#### Test coverage gap that masked both bugs

Before this phase the TUI had three layers of tests:
- **Unit tests** called ``screen.action_xxx()`` directly. These
  verified action methods do the right thing when invoked, but
  did NOT verify the key→action wiring at all.
- **Integration tests** used ``pilot.press()`` via a full
  ``ReconApp``. These DID exercise the binding path, but ran
  in Textual's Pilot harness which has a different focus model
  than a real terminal. Passed even when real terminals failed.
- **One real-terminal smoke test** sent ``q`` to quit. ``q`` is an
  App-level binding, not screen-level, so it would fire even if
  every screen binding on every screen was broken.

**New coverage:** ``tests/test_tui_real_terminal.py`` gained 13 new
PTY-based keybind tests that press real keys and assert on the
rendered output:

- ``TestDashboardKeybinds`` -- r→planner, d→discovery, b→browser,
  m on empty→Input mount
- ``TestWelcomeKeybinds`` -- n with 0 recents, n with 2 recents,
  **n with 10 recents** (the regression from Bug #2), o→open Input,
  **digit 1→first recent** (verifies the recent project bindings)
- ``TestRunScreenKeybinds`` -- b→back to dashboard (via planner
  digit 6 → run mode → b)
- ``TestBrowserKeybinds`` -- b→back, escape→back
- ``TestPlannerDigitKeybinds`` -- digit 6→full pipeline→run mode

Each test is **hermetic**: spawns ``recon tui`` in a fresh PTY with
a fake ``$HOME`` pointing at a tmp dir with its own ``.recon/``
subdirectory, so the tests can't see or write to the user's real
state. The ``_spawn_tui`` helper honors a ``recent_path`` argument
that pre-seeds the welcome screen with the exact recents list the
test wants, which made the 10-recents regression trivially
reproducible.

#### Bonus fixes

- ``_ANSI_RE`` in the smoke test now also strips OSC sequences
  (``\x1b] ... \x07``) that Textual emits for title and color
  palette updates. Without this, substring assertions on output
  that contained these sequences were flaky.
- ``~/.recon/recent.json`` was cleaned of the 10 polluted pytest
  paths that accumulated during development.

#### Tests
- 699 → 712 passing (+13 new PTY tests). Lint clean.
- Verified manually across 0, 1, 3, 5, 10, and 15 recents that
  pressing ``n`` still lands the Input visibly on screen every time.
- Production ``~/.recon/recent.json`` stays empty after a full
  test run, confirming the isolation fixture works.

Lesson for future phases: **when a test setup yields a Screen as a
child widget instead of pushing it, you're not testing the focus
model that real terminals use.** The unit tests and the in-process
Pilot tests are both useful but neither catches a whole class of
real-terminal bugs. Every new screen needs at least one PTY-based
smoke test that presses its primary keybinding.

### Added -- TUI audit Phase J (TerminalBox + CardStack primitives)

Closes the remaining visual gap with cyberspace.online by giving
screens a first-class container primitive for body content.
Previously every screen hand-rolled its card borders inline via
`[bold #e0a044]── HEADING ──[/]` Statics plus wrapped Vertical
containers with manually-repeated CSS. Now screens compose a
``CardStack`` of ``TerminalBox`` children and the primitive owns
the border / padding / title / meta treatment.

- **`recon/tui/primitives.py`** -- new module:
  - ``TerminalBox`` -- bordered card container extending
    ``Vertical``. Ships with the recon border style baked in
    (``border: round #3a3a3a``, ``padding: 0 1``, zero margin so
    stacks are tight). Accepts optional ``title=`` and ``meta=``
    parameters that render a compact ``── HEADING ──  dim meta``
    row at the top of the card. Title and meta share a single
    row so a 4-card stack still fits in a 40-row terminal.
  - ``CardStack`` -- thin ``Vertical`` wrapper that gives a stack
    of TerminalBox children consistent vertical rhythm. Nothing
    fancy (``height: auto``, ``width: 100%``) but the name makes
    screen compose methods self-documenting.
- **Dashboard adopted the primitive.** The populated dashboard now
  renders as a ``CardStack`` of four ``TerminalBox`` cards:
  COMPETITORS (with status breakdown body), SECTIONS (with per-
  section dot-leader progress), THEMES (header-only stat card), and
  COST (with last-run sub-line). The result visually matches the
  cyberspace.online emulation's card feed pattern -- rounded
  borders, ``── HEADING ──`` dividers on the left of each card
  header, dim meta lines on the right, dense body content inside.
- **Gotcha captured.** ``Widget.compose()`` yields land AFTER
  positional ``*children`` passed via ``with Container(): yield X``.
  The first draft of TerminalBox yielded the title from ``compose()``
  and ended up rendering the title at the BOTTOM of each card.
  Fix: build the header Static in ``__init__`` and prepend it to
  the positional children tuple before calling ``super().__init__``.
  ``compose()`` returns an empty tuple. Phase B already has the
  ``_render`` and ``_context`` reserved-name traps documented;
  add the positional-vs-compose ordering to the same list.

#### Tests
- **`tests/test_tui_primitives.py`** -- 8 new tests covering:
  - ``TerminalBox`` subclasses ``Vertical``
  - renders its positional children
  - has border styling by default (no per-screen CSS needed)
  - ``title=`` renders a ``── HEADING ──`` divider
  - ``meta=`` renders a dim subtitle line
  - no title/meta renders without the header widget
  - ``CardStack`` stacks three TerminalBox children in order
- 691 → 699 passing.

### Fixed -- TUI audit Phase I (end-to-end walkthrough fixes)

Drove the recon TUI through every screen via the
``/tmp/recon-audit/capture.py`` script (updated for the new keybind
flow), inspected each capture, and fixed the bugs that the audit
exposed. Most of these were either pre-existing regressions or
silent rendering bugs that the snapshot tests had been "passing"
with broken baselines.

#### Critical bugs fixed

1. **Planner buttons rendered with no labels** (pre-existing
   regression). The 7 operation rows were declared with
   ``height: 1`` in CSS, but Textual ``Button`` widgets occupy 3
   lines (top border + content + bottom border) — the 1-line cap
   clipped the content row entirely, leaving only the borders. The
   user saw 7 empty boxes and the keybind hint "press 1-7" with no
   indication of what each number did. The snapshot baseline had
   been "passing" because it captured the same broken render.
   **Fix:** ``height: 3`` on ``.operation-row``. Now each option
   shows ``[1]  Add new competitors  — discover then research the
   new ones`` etc. on its own row.
2. **Selector ``[x]`` checkbox markers silently disappeared.** Rich
   markup parses ``[x]`` as an unknown tag and drops it. The
   selected items in ``CompetitorSelectorScreen`` showed only the
   competitor name with no marker, making selection state
   invisible. **Fix:** escape the open bracket as ``\\[x][/]``
   (Rich only requires escaping the open bracket; the close
   bracket is fine on its own).
3. **Theme curation ``[x]`` markers had the same Rich-markup bug.**
   Same fix in ``ThemeCurationScreen._theme_label``.
4. **Chrome header bar didn't update from engine bus events.**
   Phase C had wired ``RunStarted`` / ``CostRecorded`` /
   ``RunCompleted`` events to mutate ``workspace_context``, but
   the chrome refresh used ``call_from_thread`` exclusively — and
   ``call_from_thread`` raises ``RuntimeError`` when called from
   the message-loop thread. The exception was caught in a bare
   ``except`` and silently dropped. The audit caught this when the
   header still showed ``$0.00 · 0 runs · idle`` after publishing
   3 ``CostRecorded`` events totaling $1.09. **Fix:** new
   ``ReconApp._schedule_chrome_refresh`` helper that calls
   ``screen.refresh_chrome()`` inline first and only falls back to
   ``call_from_thread`` if the inline path raises (worker-thread
   case). The header now updates live as engine events fire.

#### Audit findings deferred (not blocking)

- Welcome banner ASCII art truncates at the right edge of the
  70-char container in some terminals.
- Wizard modals have no chrome (no header, no Esc hint) — by
  design (Phase B opt-out), but worth a small "press Esc to
  cancel" hint.
- Discovery screen says "Click Search More..." which is mouse-first
  language even though the screen is keyboard-navigable.
- Selector and curation modals scale poorly when there are many
  items because each Button takes 3 lines. Fix would be Static-row
  rendering with custom click/key handling.
- The TUI body has two sources of truth for the active run: the
  reactive attrs on ``RunScreen`` (set by the pipeline runner) and
  the ``workspace_context`` mutated by the bus subscriber. They're
  consistent today but rely on the pipeline runner doing both.

#### Tests
- 691 still passing. Lint clean. 11 snapshots regenerated to
  capture the fixed planner labels and selector/curation
  checkboxes.
- The audit script ``/tmp/recon-audit/capture.py`` was migrated
  off the removed action-bar buttons (Phase E) onto direct
  ``screen.action_xxx()`` calls and bus event publishes.

### Added -- TUI audit Phase H (real-terminal smoke test)

PTY-based smoke tests that spawn the actual ``recon tui`` binary,
drive it with real keystrokes, and read the rendered ANSI output
back through the master file descriptor. Catches a class of bugs
that the in-process Pilot tests miss: ANSI escapes not flushed,
keyboard handling that works in the test harness but not in a real
terminal, startup-time crashes, and clean shutdown on q.

- **`tests/test_tui_real_terminal.py`** -- new test file with two
  end-to-end happy-path walks:
  - ``test_dashboard_renders_quits_cleanly`` -- spawns
    ``recon tui --workspace=<tmp>`` against a populated workspace,
    waits for the dashboard chrome to render, asserts on header bar
    contents (workspace company + domain), body content
    (`COMPETITORS` divider), keybind hint strip
    (`r run · d discover · b browse · m add manually`), and the
    ActivityFeed/LogPane placeholders. Then sends ``q`` and asserts
    clean exit.
  - ``test_no_workspace_shows_welcome`` -- spawns
    ``recon tui`` from an empty cwd, waits for the welcome chrome,
    asserts on the recon banner, the `competitive intelligence research`
    subtitle, and the `n new · o open` keybind hint. Quits with q.
- **`_PtyReader`** helper -- stateful accumulating reader so callers
  can drain in stages (e.g. wait for body marker, then keep
  draining for the bottom chrome) without losing earlier content.
  Strips ANSI/CSI/OSC escape sequences with a regex, decodes as
  UTF-8 with replacement, exposes a ``buffer`` property for full
  capture and ``drain_until(marker, timeout)`` for advancement.
- **`_wait_or_kill`** helper -- escalation path for child shutdown:
  waits for natural exit, sends SIGINT after 1s, SIGTERM after 3s,
  reports the result. Handles the case where Textual swallows the
  first keystroke during a re-layout.
- Skipped on Windows / non-POSIX via ``pytest.mark.skipif`` on
  ``hasattr(pty, "fork")``. Skipped if the recon binary isn't found
  in ``.venv/bin`` or on PATH.
- 689 → 691 passing.

#### Real bug uncovered: chrome layout was broken in real terminals

Writing the smoke test exposed a serious chrome rendering bug that
the in-process Pilot tests had been missing for two phases. The
``ReconScreen.compose()`` was yielding four separate ``dock: bottom``
widgets (KeybindHint, LogPane, ActivityFeed, RunStatusBar) directly
under the screen. In headless test mode this looked correct in
snapshot SVGs, but in a real terminal Textual's layout engine
chose only one of them to render -- the rest collapsed to zero
height and the keybind hints, log tail, and run status bar were
all invisible to actual users.

**Fix:** all bottom chrome now lives inside a single
``Vertical#recon-footer`` container that itself docks to the bottom
with ``height: auto`` and ``layout: vertical``. The four pieces are
ordered top-to-bottom inside the footer (RunStatusBar →
ActivityFeed → LogPane → KeybindHint), and Textual lays them out
sequentially. Each individual widget no longer has ``dock: bottom``
in its CSS (only the wrapping container does).

This is exactly the kind of bug the smoke test was designed to
catch on its first run, and it did. Snapshot baselines for all six
full-screen variants were regenerated to capture the corrected
layout.

### Added -- TUI audit Phase G (RunStatusBar widget)

A thin one-line status strip in the persistent chrome that surfaces
the active run's stage, progress bar, elapsed time, and running cost.
Hidden when the workspace is idle, fades in the moment a `RunStarted`
event lands, fades back out on `RunCompleted` / `RunFailed` /
`RunCancelled`.

- **`recon/tui/shell.py::RunStatusBar`** -- new bottom-docked
  Static widget. 1 line tall, dark background. Renders
  `● stage  [progress bar]  M:SS  $X.XX` where:
  - `stage` is the most recent `RunStageStarted` (or
    `stage ✓` after `RunStageCompleted`)
  - the progress bar is the existing `format_progress_bar` helper
    in running state
  - elapsed time ticks once a second via `set_interval(1.0, _tick)`
    so the counter advances even when no events fire
  - cost is the cumulative sum of `CostRecorded.cost_usd` since the
    most recent `RunStarted` (resets to 0 on a fresh run)
- **Visibility model** -- the widget always exists in the DOM but
  carries an ``idle`` CSS class while inactive. The class sets
  ``display: none`` so the bar collapses to zero height. On
  ``RunStarted`` the class is removed (via ``remove_class``) and
  the bar appears; on terminal events the class is added back. This
  is more reliable than mutating ``self.styles.display`` at runtime,
  which races with Textual's render pipeline.
- **`ReconScreen` chrome composition** -- RunStatusBar now docks
  at the very bottom of the screen footer. Final visual stack from
  top to bottom: ReconHeaderBar, body, RunStatusBar (1 line, hidden
  when idle), ActivityFeed (8 lines), LogPane (8 lines), KeybindHint
  (1 line). New ``show_run_status_bar`` class flag mirrors the
  existing ``show_log_pane`` and ``show_activity_feed`` flags.

#### Tests
- **`tests/test_tui_run_status_bar.py`** -- 12 new tests covering:
  - hidden when idle / visible after `RunStarted` / hidden again
    after each terminal event (Completed / Failed / Cancelled)
  - stage label updates from `RunStageStarted`
  - cumulative cost from multiple `CostRecorded` events
  - elapsed time string format (`M:SS`)
  - progress bar renders inside the status string
  - cost resets to $0.00 on a fresh run
  - subscription lifecycle (unsubscribed on unmount)
  - chrome integration (RunStatusBar + LogPane both present in a
    test ReconScreen subclass)
- 677 → 689 passing.

Gotcha captured for posterity
- Static subclasses must NOT define a method named ``_render`` -
  it's the Textual rendering hook on every Widget. The previous
  Phase B commit message warned about it; I tripped over it again
  while writing RunStatusBar (renamed to ``_render_status``). Add
  this to the "Textual gotchas" list alongside ``_context``,
  ``_render``, and the LogPane subscription deadlock.

### Added -- TUI audit Phase F (ActivityFeed widget)

A second pane in the persistent chrome that renders typed engine
events from the in-process bus, side-by-side with the existing raw
LogPane. This is the "what is the engine doing right now" pane that
the user can scan at a glance, while LogPane remains the verbose
unfiltered tail of the in-memory log buffer for debugging.

- **`recon/tui/shell.py::ActivityFeed`** -- new bottom-docked
  Static widget. 8-line tall, dark background, top border. Holds a
  bounded ``deque`` of the last 20 typed events; renders the most
  recent 6 with iconography:
  - `▶ run started · full_pipeline` (RunStarted)
  - `→ stage : research` (RunStageStarted)
  - `✓ stage : research` (RunStageCompleted)
  - `✓ run complete · $4.27` (RunCompleted)
  - `✗ run failed · <error>` (RunFailed)
  - `⊘ run cancelled` (RunCancelled)
  - `$ $0.42 (claude-sonnet-4-5)` (CostRecorded)
  - `✓ Cursor.overview` (SectionResearched)
  - `✗ Linear.pricing` (SectionFailed)
  - `◎ 5 themes discovered` (ThemesDiscovered)
  - `+ profile : Cursor` (ProfileCreated)
- **Subscription lifecycle** -- subscribe in ``on_mount``,
  unsubscribe in ``on_unmount``. Events from any thread are routed
  through ``app.call_from_thread`` so deque mutation and re-render
  happen on the message loop. A short ``set_interval`` poll catches
  events that arrive between mount and the first render.
- **`ReconScreen` chrome composition** -- ActivityFeed now docks
  above LogPane in every full screen. New ``show_activity_feed``
  class flag mirrors the existing ``show_log_pane`` flag so screens
  can opt out if needed.
- **Snapshot baselines** regenerated for all six full-screen
  variants (Welcome, Dashboard×2, Run×2, Browser) to include the
  new pane.

#### Tests
- **`tests/test_tui_activity_feed.py`** -- 16 new tests covering:
  - empty state placeholder
  - one render assertion per event type (11 events)
  - bounded deque (publish 25, only the last 20 are retained)
  - ordering (oldest at top, newest at bottom)
  - subscription lifecycle (unsubscribed on unmount, post-unmount
    publishes do not raise)
  - chrome composition (LogPane and ActivityFeed both present in a
    test ReconScreen subclass)
- 661 → 677 passing.

### Changed -- TUI audit Phase E (keyboard-first navigation)

The action-bar Buttons that lived at the bottom of every full screen
are gone. Every action is now reachable through a key binding declared
on the screen itself, surfaced in the chrome's bottom keybind hint
strip. Modal screens (Wizard, Discovery, Selector, Curation, Planner)
keep their buttons because they're pop-overs and click-driven.

- **DashboardScreen** removes `Run` / `Discover` / `Browse` / `Quit`
  buttons. Adds `r` / `d` / `b` / `m` bindings (run, discover, browse,
  add manually). The empty-prompt panel also drops its CTA buttons in
  favor of an instructional Static (`Press d to discover ...`).
- **RunScreen** removes `Pause` / `Stop` / `Back to Dashboard`
  buttons. Adds `p` / `s` / `b` bindings. The pause-state visual cue
  (previously the button label flipping to "Resume") now lives in
  `current_phase` flipping to `paused`, which the chrome header bar
  and the run-phase widget both reflect. `_toggle_pause` no longer
  touches a Button widget — it mutates `current_phase` only.
- **CompetitorBrowserScreen** removes the `Back to Dashboard` button.
  Adds `b` binding (alongside the existing `escape`).
- **WelcomeScreen** removes `New Project` / `Open Existing` /
  `btn-recent-N` buttons. Adds `n` / `o` bindings plus `1`..`9` for
  recent projects. Recent projects render as numbered Static rows
  (`  1  Acme CI  ·  ~/projects/acme-ci`).
- **Keybind hints refined** on every screen so the bottom strip is
  the canonical place to learn what each screen does.

#### Snapshot quality fix uncovered during this pass

While regenerating snapshot baselines after the visual changes, I
noticed the dashboard / run / welcome snapshot SVGs had been
near-empty since day one (~14KB each, with zero references to the
expected screen content). Root cause: those snapshot test apps were
using `yield ScreenClass()` in `compose()`, which mounts the screen
as a child widget rather than pushing it as the active screen — and
the persistent chrome (header bar, log pane, keybind hint) only
renders for the active screen. The "passing" snapshots were
effectively comparing blank canvases.

Fixed: `_DashboardEmptyApp`, `_DashboardPopulatedApp`, `_RunIdleApp`,
`_RunActiveApp`, `_WelcomeApp`, and `_WelcomeWithRecentsApp` now use
the same `compose: yield Static(""); on_mount: self.push_screen(...)`
pattern that `_BrowserApp` already used. Regenerated baselines are
now 22-42KB each and contain real chrome + body content. This means
future visual regressions on these screens will actually be caught.

#### Tests
- 17 new TUI tests covering the new bindings, action methods, and
  the disappearance of the action-bar buttons. Each screen has:
  - one "BINDINGS list contains expected key entries" assertion
  - one "buttons no longer rendered" assertion
  - one or more "calling action_xxx() does the right thing" assertions
  - a keybind hint string check
- Two end-to-end pilot.press checks live in `test_tui_integration.py`
  via ReconApp (where the screens are pushed properly): one for
  `pilot.press("p")` toggling pause, one for `pilot.press("s")`
  cancelling a slow run. The remaining 11 button-press calls in
  the integration suite were migrated to `pilot.press("r"/"d"/"b")`.
- 644 → 661 passing.

Gotcha captured for posterity
- Textual only walks BINDINGS via the focused widget's ancestor
  chain plus the active screen. When a Screen is yielded as a child
  widget (the unit-test pattern most TUI tests use), pressing a key
  via `pilot.press()` only triggers the screen's bindings if some
  child widget has focus and the screen is one of its ancestors. With
  the action-bar buttons gone there are no focusable children by
  default, so unit tests use direct `screen.action_xxx()` calls and
  the integration tests use ReconApp's mode-switching path which
  pushes the screen as the active screen.

### Changed -- TUI audit Phase D (retro visual language)

A consistent visual pass across every screen so the TUI feels like
htop / lazygit / k9s and not a Bootstrap form rendered in textmode.

- **`── HEADING ──` section dividers** applied uniformly:
  - Dashboard COMPETITORS / SECTIONS / THEMES / COST sections
  - Run monitor RUN MONITOR / ACTIVITY blocks
  - Browser COMPETITORS title
  - Curation THEME CURATION title with hint subtitle
  - Selector SELECT COMPETITORS title with hint subtitle
  - Discovery DISCOVERY title (now uses · separator instead of `--`)
- **Wizard step indicator redesigned** as a 4-dot progress meter
  (`● ● ○ ○`) plus the section name and `step N/4` counter, instead
  of the plain "Step 2 of 4 -- Sections" string.
- **Welcome ASCII banner** -- the recon block-letter logo replaces
  the bare "recon" title.
- **Selector checkboxes** now use color contrast: `[x]` in amber for
  selected, `[ ]` in dim grey for unselected. The selected name is
  bright; the unselected is dim. This was the audit's
  hardest-to-read state and is now legible.
- **Dashboard section progress** uses interpunct dot leaders
  (`section ························ 2/3`) and color-codes the
  progress count (grey for 0, amber for partial, green for
  complete).
- **Status breakdown bullets** use `·` separators with amber
  count and dim label (`scaffold 1 · researched 2`).
- **Discovery summary line** shows rounds, accepted, and rejected
  in a single rule (`rounds: 1 · accepted: 3 · rejected: 0`).

The chrome strip from Phase B already gave every screen a
persistent header / log pane / keybind hint. Phase D unifies the
typography of the body content so it matches.

Snapshot baselines regenerated for Welcome, Discovery, Curation,
Selector, and Planner.

### Added -- TUI audit Phase C (engine event bus)

A small in-process publish/subscribe primitive the engine modules
broadcast meaningful state transitions through. The TUI's persistent
chrome subscribes so the header bar's run state, cost, and counters
update reactively without polling.

- **`recon/events.py`** -- new module:
  - `EventBus` class with synchronous `publish/subscribe/unsubscribe`.
    Subscriber exceptions are caught and logged so a misbehaving
    listener can't poison the engine.
  - Process-wide singleton via `get_bus()` and convenience
    `publish(event)`. Tests reset via `reset_bus()`.
  - Strongly-typed event dataclasses: `WorkspaceOpened`,
    `ProfileCreated`, `DiscoveryStarted`, `DiscoveryComplete`,
    `RunStarted`, `RunStageStarted`, `RunStageCompleted`,
    `RunCompleted`, `RunFailed`, `RunCancelled`, `RunPaused`,
    `RunResumed`, `CostRecorded`, `SectionResearched`,
    `SectionFailed`, `ThemesDiscovered`.
  - `event_to_dict()` helper for logging / serialization.
- **Engine publishers** -- minimal touch points:
  - `Workspace.create_profile` -> `ProfileCreated`
  - `ResearchOrchestrator._append_to_profile` -> `SectionResearched`
  - `ResearchOrchestrator._mark_section_failed` -> `SectionFailed`
  - `Pipeline.execute` -> `RunStarted`
  - Pipeline stage loop -> `RunStageStarted` / `RunStageCompleted`
  - Pipeline terminal states -> `RunCompleted` / `RunFailed` /
    `RunCancelled`
  - `Pipeline._record_tokens` -> `CostRecorded`
  - `Pipeline._stage_themes` -> `ThemesDiscovered`
- **`ReconApp._on_engine_event`**: subscribes on mount, translates
  each event into a `WorkspaceContext` mutation, and pushes the
  refresh into the visible `ReconScreen`. Run state in the header
  bar now updates the moment the engine starts/finishes a stage,
  and the cost counter increments live as `_record_tokens` fires.

Tests
- `tests/test_events.py` (16 new) covering bus mechanics, the
  singleton, exception isolation, and every event type's payload.
- New autouse pytest fixture in `conftest.py` resets the bus
  between tests so subscribers from earlier tests don't leak.

### Added -- TUI audit Phase B (persistent chrome)

The biggest single UX change since the TUI was rebuilt: every full
screen now wears a persistent chrome layer that stays visible across
mode switches and gives the user constant feedback about workspace
state and engine activity. Modal screens (Discovery, Curation,
Selector, Planner, Wizard) opt out and pop over the chrome.

- **`recon/tui/shell.py`** -- new module with the four chrome
  building blocks:
  - `WorkspaceContext` dataclass: workspace path, domain, company,
    total cost, run count, API key presence, run state, run phase.
  - `ReconHeaderBar`: top status strip (1 line) showing
    `recon │ Acme · AI tools │ ~/path/to/ws │ $7.42 · 3 runs │ API ✓ │ idle`.
    Updates reactively via `set_workspace_context()`.
  - `KeybindHint`: bottom 1-line strip rendering the current
    screen's hint string.
  - `LogPane`: 8-line bottom-docked tail of the in-memory log
    buffer, polled 4x/sec via `set_interval`. Shows last 6 entries
    with level color coding (gray DEBUG, default INFO, yellow WARN,
    red ERROR). Renders "waiting for engine activity..." when the
    buffer is empty.
- **`ReconScreen` base class**: full screens override
  `compose_body()` instead of `compose()`. The base composes
  `ReconHeaderBar -> Vertical#recon-body -> LogPane -> KeybindHint`.
- **Migrated to ReconScreen**: `WelcomeScreen`, `DashboardScreen`,
  `RunScreen`, `CompetitorBrowserScreen`. Modals stay as plain
  `ModalScreen`.
- **`MemoryLogHandler`** in `recon/logging.py`: process-wide
  handler that keeps a deque of the last 200 log entries. Attached
  to the recon root logger by `configure_logging`. The LogPane
  reads from it via `get_memory_handler().tail(n)`.
- **`ReconApp.workspace_context`**: live snapshot the chrome reads.
  `refresh_workspace_context()` rebuilds it whenever the workspace
  state changes (open, wizard finish). Pushed to the visible
  `ReconScreen` via `refresh_chrome()`.
- **Welcome banner**: ASCII-art retro banner replaces the bare
  "recon" title.

Test infrastructure
- New autouse pytest fixture clears the in-memory log buffer
  between tests so snapshot diffs are deterministic.

Gotchas captured for posterity
- Textual's `MessagePump` reserves the attribute name `_context`
  on widgets -- assigning a non-callable value to `self._context`
  raises "object is not callable" on mount. Renamed to `_ws_ctx`.
- Static subclasses must not override `_render` -- it's the
  Textual rendering hook. Renamed to `_render_context`.
- `LogPane` started with an event-bus subscription model that
  deadlocked the test event loop; switched to `set_interval`
  polling.

### Fixed -- TUI audit Phase A (10 bugs)

Driven by an end-to-end TUI screen audit. Each fix is a regression
test plus the smallest change that resolves the audit finding.

- **BUG-1**: ReconApp now records opened workspaces in
  `~/.recon/recent.json` via `RecentProjectsManager.add()` from both
  `on_welcome_screen_workspace_selected` and the wizard handler.
  Previously the file stayed empty forever, so the welcome screen's
  Recent Projects pane never had anything to show.
- **BUG-1 (cont.)**: `RecentProjectsManager.load()` now logs a
  warning when it drops malformed entries instead of silently
  filtering them. Catches schema mismatches in the JSON file.
- **BUG-2**: Dashboard `_build_section_statuses` now reads
  per-section `section_status` frontmatter (the field the diff/rerun
  work introduced). Previously every section was reported as
  "complete" whenever the profile's overall `research_status` was
  non-scaffold, producing dashboards that lied about per-section
  state.
- **BUG-3 + BUG-4**: Planner layout rewritten so the title,
  workspace stats, and cost preview sit OUTSIDE the scrollable
  options list. Operation rows are now single-line buttons with
  short two-line labels instead of two-line buttons with long
  descriptions, so all 7 options fit in a 90-column-wide modal
  along with the Back button. Cost preview is now always visible
  when an estimate exists.
- **BUG-5**: `RunScreen._request_stop` and `_toggle_pause` now
  append to the on-screen activity log when no pipeline is active,
  not just a Textual toast. The log entry survives long enough for
  the user to actually read it.
- **BUG-6**: `format_progress_bar(state=...)` now color-codes the
  bar by phase: orange for running, green for done, yellow for
  paused, red with X-marks for cancelled/error, gray for stopping,
  white dashes for idle. `RunScreen.watch_current_phase` triggers a
  bar repaint so the color updates the moment the phase changes.
- **BUG-7**: New `humanize_path()` helper in `tui/widgets.py`
  collapses `$HOME` to `~`, macOS temp dirs to `$TMP/...`, and
  long paths to `head/…/leaf` form. Dashboard uses it for the
  `Workspace:` line so the path stays readable.
- **BUG-8**: Deferred (test-fixture-only artifact).
- **BUG-9**: `build_dashboard_data` now reads cost history from
  the workspace state.db via the new `StateStore.get_workspace_run_summary()`
  helper. Dashboard shows `COST $X.XX across N runs` plus a
  `last run: $Y.YY` sub-line. Previously every dashboard reported
  `total_cost = 0.0` because the populator never read the state
  store.
- **BUG-10**: Engine logging coverage expanded. Added structured
  INFO/DEBUG logs to:
  - `workspace.create_profile`
  - `enrichment.enrich_all` (start/complete with success/fail counts)
  - `index.IndexManager.add_chunks` and `retrieve` (debug)
  - `tag.Tagger.tag` (start/complete with assignment count)
  - `synthesis.SynthesisEngine.synthesize` (start/complete per theme)
  - `deliver.Distiller.distill` and `MetaSynthesizer.synthesize`
  - `verification.VerificationEngine.verify` (tier + competitor + section)
  - `pipeline.Pipeline.execute` entry/exit/cancel/fail with run_id
  - `cli.main` group now logs full subcommand parameters at INFO

Plus a state-store improvement that fell out of BUG-9:
- `StateStore.list_runs` now tie-breaks on ROWID DESC so two runs
  created in the same second still report a stable ordering (most
  recent insert first). Without this, `get_workspace_run_summary`
  could pick the wrong "latest" run when multiple ran in quick
  succession.
- New `StateStore.get_workspace_total_cost` and
  `StateStore.get_workspace_run_summary` helpers.

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
