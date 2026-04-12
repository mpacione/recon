# Systemic Fixes Proposal — 2026-04-11

Three user-reported defects, each a symptom of a deeper class.

---

## Issue 1: Theme labels are garbage ("2026 / Accessed / April")

### What the user sees
All 5 theme labels contain date fragments from source citations
instead of strategic names like "Platform Consolidation".

### The bug class: "placeholder internals behind a production shell"

Three stacked prototypes shipped as production code. Each
"works" (produces output, passes tests) but produces garbage:

| Layer | Placeholder | Real implementation needed |
|---|---|---|
| Embeddings | Hash-seeded random 64-dim vectors | fastembed (already a dep) |
| Clustering input | Raw chunks with citation noise | Strip all `(Accessed ...)` citation dates + URL lines before TF-IDF |
| Label generation | Mechanical top-3 term frequency fallback | LLM labeling via the existing `_llm_label` path |

**Root causes:**

1. **`pipeline.py:518`** constructs `ThemeDiscovery()` with NO
   `llm_client`. Comment says "avoid nested event loop" but the
   result is the LLM label path is dead in production. Every label
   comes from the mechanical `_label_cluster` fallback.

2. **`themes.py::_strip_sources`** only removes content after a
   `## Sources` heading. But citation lines like
   `(Accessed April 12, 2026)` appear inline within chunks before
   the heading. These date tokens appear in every chunk across all
   profiles and dominate term frequency for every cluster.

3. **`themes.py::build_workspace_chunks`** generates random
   embeddings: `rng.random(64)`. K-means on random vectors produces
   arbitrary clusters with no topical coherence. Even with perfect
   labeling, the clusters are meaningless.

### Proposed fix (3 changes)

**A. Pass the LLM client through.** Pipeline already has one.
Thread it to `ThemeDiscovery(llm_client=self._llm_client)`. The
"nested event loop" concern is solved by making `_llm_label` an
`async def` and calling it with `await` instead of `asyncio.run()`.

**B. Fix source stripping.** Add a regex that strips all
`(Accessed ... 20XX)` citation date parentheticals, numbered
citation lines (`1. Name. "..." https://...`), and bare URL lines
before computing term frequency. This is a ~10-line regex fix in
`_strip_sources`.

**C. Use real embeddings.** Replace the random-vector hack in
`build_workspace_chunks` with calls to the existing
`IndexManager.embed()` (which uses fastembed). If fastembed isn't
available (CI environments), fall back to the current random
vectors but log a warning.

**Blast radius:** `themes.py`, `pipeline.py`, `index.py` (minor).
~15 tests need updating (they assert on label structure, not
content).

**The broader pattern this fixes:** "structural tests that verify
shape but not value." After the fix, add a smoke test that asserts
theme labels do NOT contain "Accessed", "2026", or other citation
noise — a content-level assertion, not just a structure-level one.

---

## Issue 2: Buttons and interactive elements don't match cyberspace.online

### What the user sees
The theme curation screen has thick blue "Done" buttons with
Textual's default 3-line-tall borders. cyberspace.online uses thin
1px-bordered buttons with monospace text and no fill color.

### The bug class: "no global design system"

Every screen hardcodes its own CSS. There are no shared design
tokens for interactive elements. When Textual's defaults leak
through (e.g., Button's default `variant="primary"` → blue fill),
the result is visually jarring against the Gruvbox palette.

### cyberspace.online's interactive element system

From my earlier Chrome inspection:

| Element | cyberspace.online | Textual default |
|---|---|---|
| Button bg | `transparent` (no fill) | `#004578` (blue primary) |
| Button border | `1px solid #3a3a3a` | 3-line tall `▔▔▔/▁▁▁` decoration |
| Button text | `#efe5c0` (same as body) | White on blue |
| Button hover | `border-color: #a89984` | Background darkens |
| Button padding | `4px 12px` (tight) | `0 2` (2 chars left/right) |
| Button height | 1 line | 3 lines (border + content + border) |
| Primary variant | `border-color: #efe5c0` | Blue fill |
| Tag/chip | `1px solid #3a3a3a`, `2px 8px` padding | N/A |
| Toggle/checkbox | `[x]` amber / `[ ]` dim in text | N/A |

### Proposed fix: global design tokens in `theme.py`

Textual supports component-level CSS overrides. Add these to the
existing `RECON_CSS` constant in `tui/theme.py`:

```css
/* --- Global button overhaul --- */
Button {
    background: transparent;
    color: #efe5c0;
    border: solid #3a3a3a;
    height: 3;
    min-width: 10;
    padding: 0 1;
}
Button:hover {
    background: #1a1510;
    border: solid #a89984;
}
Button:focus {
    border: solid #e0a044;
}
Button.-primary {
    border: solid #efe5c0;
}
Button.-primary:hover {
    background: #2a1f10;
}
Button.-error {
    color: #cc241d;
    border: solid #cc241d;
}
```

This makes every Button in the app look like cyberspace.online's
thin bordered buttons by default. No per-screen CSS needed.

### Keyboard navigation (d-pad + Enter)

Textual already supports Tab to cycle focus between Buttons and
Enter to press the focused one. The user asked for d-pad (arrow
key) navigation too. This needs:

1. `BINDINGS` on modal screens for up/down arrow → focus
   prev/next Button
2. Or: use Textual's built-in `focus_next` / `focus_previous`
   which already respond to Tab/Shift+Tab

The Tab path already works. Arrow keys need explicit bindings
per modal screen, or a global app-level binding.

### Blast radius

- `tui/theme.py` (add ~30 lines of CSS)
- Remove per-screen `.action-bar Button { ... }` CSS overrides
  that now conflict with the global tokens
- Snapshot baselines regenerated (every screen with buttons changes)
- ~0 test code changes (CSS is visual, tests are structural)

---

## Issue 3: Run monitor is uninformative during real pipeline runs

### What the user sees

The run monitor body shows 3 static lines ("Planning run...",
"Run started", "research: start") and nothing updates as sections
complete. The ActivityFeed at the bottom shows per-section events
but they're small and buried in the chrome footer. The user can't
tell what's happening across 15 competitors and 8 sections.

### The bug class: "demo-quality monitoring for production workloads"

The run monitor was designed for a 1-competitor demo. It has:
- One progress bar (global, not per-competitor)
- One phase label (stage name, not per-section)
- A flat text log (no structure)

### Research findings

Surveyed: cargo build, Ansible, Terraform, rich MultiProgress,
indicatif MultiProgress, htop, lazydocker, k9s. Key insight:
**the overflow problem is the core challenge** — 15 competitors
x 8 sections = 120 potential status items.

### Recommended: Option B — "Competitor Grid" (htop-inspired)

Each competitor gets one row. Sections are encoded as 2-char
status tokens in a compact grid. Fits 15 competitors in <25 lines.

```
── RESEARCH MONITOR ──    00:04:32    $0.42    Workers: 3/5
─────────────────────────────────────────────────────────────
Sections: Ov=Overview  Ca=Capabilities  Pr=Pricing  In=Integration
          En=Enterprise  Dv=Developer Love  Hh=Head-to-Head  St=Strategic

COMPETITOR          Ov  Ca  Pr  In  En  Dv  Hh  St
Dell Technologies   ok  ok  ok  ok  ok  >>  --  --
HP Inc.             ok  ok  ok  >>  --  --  --  --
Lenovo Group        ok  ok  ok  ok  >>  --  --  --
Apple Inc.          ok  ok  ok  ok  ok  ok  --  --
ASUS                ok  ok  ok  ok  >>  --  --  --
Supermicro          ok  ok  >>  --  --  --  --  --
MSI                 ok  ok  ok  ok  ok  ok  ok  ok  ✓
CyberPowerPC        ok  >>  --  --  --  --  --  --
Framework           ok  ok  ok  >>  --  --  --  --
System76            ..  --  --  --  --  --  --  --
NZXT                --  --  --  --  --  --  --  --
BOXX Technologies   --  --  --  --  --  --  --  --

Legend: ok=done  >>=active  !!=failed  ..=queued  --=waiting
████████████████░░░░░░░░░░░░░░░░  38/120 sections  31.6%
```

### Implementation

Replace the current `RunScreen.compose_body()` with a Textual
`DataTable` widget that has one row per competitor and one column
per section. Cell content is a 2-char status token (`ok`, `>>`,
`!!`, `..`, `--`) color-coded:
- `ok` → green (#98971a)
- `>>` → amber (#e0a044)
- `!!` → red (#cc241d)
- `..` → dim (#a89984)
- `--` → dark (#3a3a3a)

The engine already emits `SectionResearched` and `SectionFailed`
events per competitor+section. The grid subscribes to these and
updates the matching cell. The existing progress bar, cost, and
elapsed time move to a header row above the grid.

### For narrow terminals (<80 cols)

Fall back to Option A (worker slots + summary counts):

```
Progress: 7/15 done    Cost: $0.42    Workers: 3/5
████████████████░░░░░░░░░░░░░░░░  38/120  31.6%

ACTIVE WORKERS
[1] Figma       Pricing         ████████░░  80%
[2] Sketch      Team Structure  ██░░░░░░░░  20%
[3] InVision    Market Position ██████░░░░  60%
```

### Blast radius

- `tui/screens/run.py` (major rewrite of `compose_body`)
- `tui/shell.py` (RunStatusBar already shows stage+elapsed+cost;
  might merge into the grid header)
- `events.py` (may need `SectionStarted` event for the `>>` state)
- `research.py` (publish `SectionStarted` before LLM call)
- ~10 tests for the new grid widget
- Snapshot baselines for run screens

---

## Execution sequencing

| Priority | Fix | Risk | Effort | Payoff |
|---|---|---|---|---|
| 1 | **Issue 2: Global button CSS** | Low | Small (30 lines CSS) | Every modal instantly matches the aesthetic |
| 2 | **Issue 1B: Fix source stripping** | Low | Small (~10 lines regex) | Eliminates citation noise from labels |
| 3 | **Issue 1A: Thread LLM client to ThemeDiscovery** | Medium | Small (2 lines + async refactor) | Real strategic labels instead of TF-IDF |
| 4 | **Issue 3: Competitor grid run monitor** | Medium | Large (rewrite compose_body + new events) | Transforms the run experience |
| 5 | **Issue 1C: Real embeddings** | Medium | Medium (wire fastembed into themes) | Topically coherent clusters |

Items 1-3 can ship as a single commit (fast, low-risk). Item 4 is
a feature and should ship separately. Item 5 is the deepest fix but
also the highest-risk (fastembed dependency, CI implications).
