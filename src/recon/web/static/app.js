// recon web UI — Phase 4 SPA shell.
//
// Architecture: a hash-based router with a screen registry. The
// shell renders persistent chrome (header, flow progress, keybinds);
// the router clones the matching <template id="screen-<key>"> into
// #screen-slot whenever the hash changes.
//
// Screen-specific Alpine factories (welcomeScreen, etc.) are defined
// further down. Future phases will split them into screens/*.js once
// there are enough of them to warrant the file boundaries.

// ---------------------------------------------------------------------------
// Theme system
// ---------------------------------------------------------------------------
//
// Palette vocabulary inspired by unremarkablegarden/cyberspace-tui-go.
// The catalog below is the single source of truth for:
//   - the picker menu shown in the header
//   - the [t] global keybind (cycles in array order)
//   - the preflight allowlist (mirrored inline in index.html; both
//     lists must agree)
//
// Rendering is CSS-only: each entry's `key` is written to
// <html data-theme="..."> and theme.css overrides the --recon-* tokens
// for that attribute. No re-render or class swap is needed.

const THEMES = [
  { key: 'amber',  label: 'Amber',  description: 'VT320 phosphor (default)' },
  { key: 'dark',   label: 'Dark',   description: 'Warm cream on black' },
  { key: 'matrix', label: 'Matrix', description: 'Green-on-black terminal' },
  { key: 'crypt',  label: 'Crypt',  description: 'Emergency red console' },
];

const THEME_STORAGE_KEY = 'recon:theme';
const DEFAULT_THEME = 'amber';

function readPersistedTheme() {
  try {
    const saved = localStorage.getItem(THEME_STORAGE_KEY);
    if (THEMES.some((t) => t.key === saved)) return saved;
  } catch (_err) { /* localStorage disabled */ }
  return DEFAULT_THEME;
}

function writePersistedTheme(key) {
  try {
    localStorage.setItem(THEME_STORAGE_KEY, key);
  } catch (_err) { /* localStorage disabled — theme applies for the
                      current page only */ }
}

function applyTheme(key) {
  // Keep :root clean when the default is active so CSS debugging via
  // devtools shows the canonical values rather than an override.
  if (key === DEFAULT_THEME) {
    document.documentElement.removeAttribute('data-theme');
  } else {
    document.documentElement.setAttribute('data-theme', key);
  }
}

const CRT_STORAGE_KEY = 'recon:crt';

function readPersistedCrt() {
  try {
    return localStorage.getItem(CRT_STORAGE_KEY) !== 'off';
  } catch (_err) { return true; }
}

function writePersistedCrt(on) {
  try {
    localStorage.setItem(CRT_STORAGE_KEY, on ? 'on' : 'off');
  } catch (_err) { /* noop */ }
}

function applyCrt(on) {
  if (on) {
    document.documentElement.removeAttribute('data-crt');
  } else {
    document.documentElement.setAttribute('data-crt', 'off');
  }
}

// ---------------------------------------------------------------------------
// Flow definition (kept in sync with design/v2-spec.md and the TUI
// FlowProgress widget).
// ---------------------------------------------------------------------------

const FLOW_STEPS = [
  { key: 'describe',  label: 'describe' },
  { key: 'discover',  label: 'discovery' },
  { key: 'template',  label: 'template' },
  { key: 'confirm',   label: 'confirm' },
  { key: 'run',       label: 'run' },
  { key: 'results',   label: 'results' },
];

// Screens that are *not* part of the linear flow. They suppress the
// flow-progress breadcrumb. curation/browser/selector are currently
// TUI-only placeholders; see web-ui-spec.md for the porting plan.
const NON_FLOW_SCREENS = new Set([
  'welcome', 'dashboard', 'not-found',
  'curation', 'browser', 'selector',
]);

// Per-screen keybind hints. The shell renders these in the footer.
// Listeners are attached at the document level by the router.
const SCREEN_KEYBINDS = {
  welcome: [
    { key: 'n', label: 'new project' },
    { key: '1-9', label: 'recent project' },
    { key: 'q', label: 'quit' },
  ],
  describe:  [{ key: 'enter', label: 'continue' }, { key: 'esc', label: 'back' }],
  discover:  [{ key: 'space', label: 'toggle' }, { key: 's', label: 'search more' }, { key: 'enter', label: 'done' }, { key: 'esc', label: 'back' }],
  template:  [{ key: 'space', label: 'toggle' }, { key: 'enter', label: 'proceed' }, { key: 'esc', label: 'back' }],
  confirm:   [{ key: 'enter', label: 'start run' }, { key: 'esc', label: 'back' }],
  run:       [{ key: 'esc', label: 'back to dashboard' }],
  results:   [{ key: 'b', label: 'dashboard' }, { key: 'h', label: 'home' }],
  dashboard: [{ key: 'r', label: 'run' }, { key: 'b', label: 'back' }, { key: 'q', label: 'quit' }],
  curation:  [{ key: 'h', label: 'home' }],
  browser:   [{ key: 'h', label: 'home' }],
  selector:  [{ key: 'h', label: 'home' }],
  'not-found': [{ key: 'h', label: 'home' }],
};

// ---------------------------------------------------------------------------
// Router store
// ---------------------------------------------------------------------------

document.addEventListener('alpine:init', () => {
  Alpine.store('router', {
    hash: location.hash || '#/welcome',
    screen: 'welcome',
    params: {},

    parse() {
      const raw = location.hash || '#/welcome';
      this.hash = raw;
      // Format: #/<screen>(/<param>)*
      const path = raw.replace(/^#\/?/, '').split('/');
      const screen = path[0] || 'welcome';
      const params = {};
      // Param decoding: every screen owns its own param schema. For
      // now we surface a generic `arg` array that screens can pull
      // from. (Welcome ignores params; dashboard reads params.path.)
      params.arg = path.slice(1).map(decodeURIComponent);
      this.screen = screen;
      this.params = params;
    },

    navigate(hash) {
      if (location.hash === hash) {
        // Manually re-trigger so re-clicking the active link still
        // reloads the screen (useful for refresh-style nav).
        this.parse();
        document.dispatchEvent(new CustomEvent('recon:route'));
      } else {
        location.hash = hash;
      }
    },
  });

  // Theme store: the picker component and the [t] keybind both reach
  // in here so the header trigger, popover, and keyboard all stay in
  // sync. Seed from localStorage via readPersistedTheme so the store
  // matches whatever the preflight script already wrote to <html>.
  Alpine.store('theme', {
    active: readPersistedTheme(),
    crt: readPersistedCrt(),
    options: THEMES,

    set(key) {
      if (!THEMES.some((t) => t.key === key)) return;
      this.active = key;
      applyTheme(key);
      writePersistedTheme(key);
    },

    cycle() {
      const idx = THEMES.findIndex((t) => t.key === this.active);
      const next = THEMES[(idx + 1) % THEMES.length].key;
      this.set(next);
    },

    toggleCrt() {
      this.crt = !this.crt;
      applyCrt(this.crt);
      writePersistedCrt(this.crt);
    },
  });
});

// ---------------------------------------------------------------------------
// Theme picker
// ---------------------------------------------------------------------------
//
// Small popover in the header. The store owns the state; this factory
// is a thin view over it so the template stays declarative.

function themePicker() {
  return {
    open: false,

    get active() {
      return Alpine.store('theme').active;
    },

    get options() {
      return Alpine.store('theme').options;
    },

    get crtOn() {
      return Alpine.store('theme').crt;
    },

    activeLabel() {
      const match = this.options.find((o) => o.key === this.active);
      return match ? match.label : 'Theme';
    },

    select(key) {
      Alpine.store('theme').set(key);
    },

    toggleCrt() {
      Alpine.store('theme').toggleCrt();
    },
  };
}

// ---------------------------------------------------------------------------
// Top-level shell component
// ---------------------------------------------------------------------------

function reconShell() {
  return {
    activeScreen: null,
    flowSteps: FLOW_STEPS,

    init() {
      const router = Alpine.store('router');
      router.parse();
      this.mount(router.screen);
      const onHashChange = () => {
        router.parse();
        this.mount(router.screen);
      };
      window.addEventListener('hashchange', onHashChange);
      document.addEventListener('recon:route', onHashChange);
      document.addEventListener('keydown', (e) => this.handleKey(e));
    },

    mount(screenKey) {
      // When the requested screen isn't registered, fall back to the
      // not-found template AND mark the shell's activeScreen as
      // 'not-found' so chrome derived from activeScreen (flow nav,
      // keybinds, subtitle) reflects the actual rendered screen.
      let tpl = document.getElementById(`screen-${screenKey}`);
      let resolvedKey = screenKey;
      if (!tpl) {
        tpl = document.getElementById('screen-not-found');
        resolvedKey = 'not-found';
      }
      const slot = this.$refs.slot;
      slot.innerHTML = '';
      slot.appendChild(tpl.content.cloneNode(true));
      this.activeScreen = resolvedKey;
      this._enhanceTitledSections(slot);
    },

    // Wrap the first .section-divider inside each .section in a span
    // so the theme CSS can carve a gap in the section's top border at
    // the title position (TitledBox effect, ported from
    // cyberspace-tui-go). Kept in JS rather than baked into every
    // template so the markup stays clean and future screens pick it
    // up for free.
    _enhanceTitledSections(root) {
      const dividers = root.querySelectorAll(
        '.section > .section-divider:first-child',
      );
      for (const el of dividers) {
        // Idempotent — skip re-wrapping if a prior mount already did.
        if (el.querySelector(':scope > .section-divider-title')) continue;
        const wrapper = document.createElement('span');
        wrapper.className = 'section-divider-title';
        while (el.firstChild) wrapper.appendChild(el.firstChild);
        el.appendChild(wrapper);
      }
    },

    // -------------------------------------------------------------
    // Header / footer derived state
    // -------------------------------------------------------------

    get headerSubtitle() {
      switch (this.activeScreen) {
        case 'welcome':   return 'competitive intelligence';
        case 'describe':  return 'new project';
        case 'discover':  return 'discovery';
        case 'template':  return 'research template';
        case 'confirm':   return 'ready to research';
        case 'run':       return 'researching';
        case 'results':   return 'complete';
        case 'dashboard': return 'dashboard';
        case 'curation':  return 'theme curation';
        case 'browser':   return 'competitor browser';
        case 'selector':  return 'competitor selector';
        case 'not-found': return 'not found';
        default:          return '';
      }
    },

    get flowVisible() {
      return !NON_FLOW_SCREENS.has(this.activeScreen);
    },

    get flowIndex() {
      return FLOW_STEPS.findIndex((s) => s.key === this.activeScreen);
    },

    get flowStepLabel() {
      const idx = this.flowIndex;
      if (idx < 0) return '';
      return `Step ${idx + 1} of ${FLOW_STEPS.length}: `;
    },

    // Workspace path travels through the hash on every flow screen
    // after /describe. Used to compose nav targets when the user
    // clicks back to a completed step.
    get workspacePath() {
      return Alpine.store('router').params.arg[0] || '';
    },

    flowStepState(idx) {
      const current = this.flowIndex;
      if (idx < current) return 'completed';
      if (idx === current) return 'current';
      return 'future';
    },

    flowStepHash(stepKey) {
      // /describe is the workspace-creation entry point; all other
      // steps hang workspace path off the hash.
      if (stepKey === 'describe') return '#/describe';
      const path = this.workspacePath;
      if (!path) return null;
      return `#/${stepKey}/${encodeURIComponent(path)}`;
    },

    navigateFlowStep(idx) {
      const state = this.flowStepState(idx);
      // Only completed steps navigate; current is a no-op, future is
      // disabled entirely.
      if (state !== 'completed') return;
      const hash = this.flowStepHash(FLOW_STEPS[idx].key);
      if (!hash) return;
      Alpine.store('router').navigate(hash);
    },

    get keybinds() {
      // [t] is a universal theme-cycle shortcut. Appending it here
      // (rather than inside every SCREEN_KEYBINDS entry) keeps the
      // registry focused on screen-specific actions.
      const base = SCREEN_KEYBINDS[this.activeScreen] || [];
      return [...base, { key: 't', label: 'theme' }];
    },

    // -------------------------------------------------------------
    // Global keyboard shortcuts
    // -------------------------------------------------------------

    // Grab the Alpine reactive proxy for the currently-mounted screen
    // so we can invoke its factory methods (proceed/back/etc) from
    // global keybinds.
    screenData() {
      const slot = this.$refs.slot;
      const root = slot && slot.firstElementChild;
      if (!root) return null;
      try {
        return Alpine.$data(root);
      } catch (_) {
        return null;
      }
    },

    handleKey(event) {
      const tag = (event.target && event.target.tagName) || '';
      const isFormField = tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT';
      // Escape always escapes — even from inputs. Other keys yield to
      // form-field focus so users can type normally.
      if (isFormField && event.key !== 'Escape') {
        return;
      }

      const key = event.key;
      const screen = this.activeScreen;
      const data = this.screenData();
      const router = Alpine.store('router');

      // Flow screens reserve Enter/Escape for proceed/back. Outside
      // the flow (and on the terminal 'results' screen), `h` is the
      // universal "home" shortcut.
      const reservesH = ['describe', 'discover', 'template', 'confirm', 'run'].includes(screen);
      if (key === 'h' && !reservesH) {
        router.navigate('#/welcome');
        event.preventDefault();
        return;
      }

      // `t` is the universal theme-cycle shortcut. Works on every
      // screen (no screen currently reserves it) so users can retint
      // mid-flow without losing their place.
      if (key === 't') {
        Alpine.store('theme').cycle();
        event.preventDefault();
        return;
      }

      switch (screen) {
        case 'welcome':
          if (key === 'n') {
            router.navigate('#/describe');
            event.preventDefault();
          } else if (/^[1-9]$/.test(key)) {
            document.dispatchEvent(new CustomEvent('recon:welcome-pick', {
              detail: { index: Number(key) - 1 },
            }));
            event.preventDefault();
          }
          break;

        case 'describe':
          if (key === 'Escape' && data && typeof data.back === 'function') {
            data.back();
            event.preventDefault();
          }
          // Enter submits via the form's native @submit.prevent, so
          // no extra handling is needed here.
          break;

        case 'discover':
          if (key === 'Enter' && data && typeof data.proceed === 'function') {
            data.proceed();
            event.preventDefault();
          } else if (key === 'Escape' && data && typeof data.back === 'function') {
            data.back();
            event.preventDefault();
          }
          break;

        case 'template':
          if (key === 'Enter' && data && typeof data.proceed === 'function') {
            data.proceed();
            event.preventDefault();
          } else if (key === 'Escape' && data && typeof data.back === 'function') {
            data.back();
            event.preventDefault();
          }
          break;

        case 'confirm':
          if (key === 'Escape' && data && typeof data.back === 'function') {
            data.back();
            event.preventDefault();
          } else if (key === 'Enter' && data && typeof data.start === 'function') {
            data.start();
            event.preventDefault();
          }
          break;

        case 'run':
          if (key === 'Escape' && this.workspacePath) {
            router.navigate(`#/dashboard/${encodeURIComponent(this.workspacePath)}`);
            event.preventDefault();
          }
          break;

        case 'results':
          if (key === 'b' && this.workspacePath) {
            router.navigate(`#/dashboard/${encodeURIComponent(this.workspacePath)}`);
            event.preventDefault();
          }
          break;

        default:
          break;
      }
    },
  };
}

// ---------------------------------------------------------------------------
// Describe screen
// ---------------------------------------------------------------------------

function describeScreen() {
  return {
    description: '',
    providers: [
      { name: 'anthropic', label: 'Anthropic', placeholder: 'sk-ant-...', value: '', saved: false },
      { name: 'google_ai', label: 'Google AI', placeholder: 'AIza...',     value: '', saved: false },
    ],
    submitting: false,
    error: null,

    init() {
      // Focus the textarea so the user can start typing immediately.
      this.$refs.description?.focus();
    },

    async submit() {
      this.submitting = true;
      this.error = null;
      try {
        const res = await fetch('/api/workspaces', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ description: this.description }),
        });
        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          this.error = body.detail || `server returned ${res.status}`;
          return;
        }
        const ws = await res.json();
        // Save typed API keys to the fresh workspace's .env so the
        // discovery/research stages downstream can pick them up via
        // recon.api_keys.load_api_keys.
        await this.persistKeys(ws.path);
        Alpine.store('router').navigate(
          `#/discover/${encodeURIComponent(ws.path)}`,
        );
      } catch (err) {
        this.error = err.message;
      } finally {
        this.submitting = false;
      }
    },

    async persistKeys(workspacePath) {
      if (!workspacePath) return;
      // Best-effort: failures don't block navigation. Users can retry
      // by revisiting the workspace's settings later.
      for (const provider of this.providers) {
        const value = (provider.value || '').trim();
        if (!value) continue;
        try {
          const res = await fetch('/api/api-keys', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              path: workspacePath,
              name: provider.name,
              value,
            }),
          });
          if (res.ok) {
            provider.saved = true;
            provider.value = '';
          }
        } catch (_) {
          // Non-fatal — continue with the remaining providers.
        }
      }
    },

    back() {
      Alpine.store('router').navigate('#/welcome');
    },
  };
}

// ---------------------------------------------------------------------------
// Discover screen
// ---------------------------------------------------------------------------

function discoverScreen() {
  return {
    loading: true,
    error: null,
    adding: false,
    competitors: [],
    form: { name: '', url: '', blurb: '' },

    get workspacePath() {
      return Alpine.store('router').params.arg[0] || '';
    },

    async init() {
      await this.refresh();
    },

    async refresh() {
      this.loading = true;
      try {
        const qs = new URLSearchParams({ path: this.workspacePath });
        const res = await fetch(`/api/competitors?${qs}`);
        if (!res.ok) {
          this.error = `could not load competitors (${res.status})`;
          return;
        }
        const body = await res.json();
        this.competitors = body.competitors || [];
        this.error = null;
      } catch (err) {
        this.error = err.message;
      } finally {
        this.loading = false;
      }
    },

    async add() {
      if (!this.form.name) return;
      this.adding = true;
      try {
        const res = await fetch('/api/competitors', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            path: this.workspacePath,
            name: this.form.name,
            url: this.form.url || null,
            blurb: this.form.blurb || null,
          }),
        });
        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          this.error = body.detail || `could not add (${res.status})`;
          return;
        }
        const created = await res.json();
        this.competitors = [...this.competitors, created];
        this.form = { name: '', url: '', blurb: '' };
        this.error = null;
      } catch (err) {
        this.error = err.message;
      } finally {
        this.adding = false;
      }
    },

    async remove(candidate) {
      const qs = new URLSearchParams({ path: this.workspacePath });
      const res = await fetch(
        `/api/competitors/${encodeURIComponent(candidate.slug)}?${qs}`,
        { method: 'DELETE' },
      );
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        this.error = body.detail || `could not remove (${res.status})`;
        return;
      }
      this.competitors = this.competitors.filter((c) => c.slug !== candidate.slug);
      this.error = null;
    },

    proceed() {
      if (this.competitors.length === 0) return;
      Alpine.store('router').navigate(
        `#/template/${encodeURIComponent(this.workspacePath)}`,
      );
    },

    back() {
      Alpine.store('router').navigate('#/describe');
    },

    // -------------------------------------------------------------
    // Display helpers
    // -------------------------------------------------------------
    //
    // The backend ships tier/status as raw enum strings (scaffold,
    // researching, researched, own_product). Those read as jargon
    // to end users; map them to friendlier labels at render time
    // rather than in the API response so other clients (TUI, CLI)
    // can keep their own display conventions.

    candidateTierLabel(type) {
      // Backend currently only emits 'competitor' and 'own_product'.
      // If future tiers (adjacent / ancillary) return, extend here.
      return type === 'own_product' ? 'you' : 'competitor';
    },

    candidateStatusLabel(status) {
      switch (status) {
        case 'scaffold':    return 'waiting';
        case 'researching': return 'researching\u2026';
        case 'researched':  return 'ready';
        default:            return status || '';
      }
    },

    candidateHost(url) {
      if (!url) return '';
      try {
        const u = new URL(url);
        return u.hostname.replace(/^www\./, '');
      } catch (_) {
        // Fall back to the raw string when it's not a parseable URL
        // (e.g. "example.com" without a scheme).
        return url.replace(/^https?:\/\//, '').replace(/^www\./, '').split('/')[0];
      }
    },
  };
}

// ---------------------------------------------------------------------------
// Template screen
// ---------------------------------------------------------------------------

function templateScreen() {
  return {
    loading: true,
    saving: false,
    error: null,
    sections: [],

    get workspacePath() {
      return Alpine.store('router').params.arg[0] || '';
    },

    get selectedCount() {
      return this.sections.filter((s) => s.selected).length;
    },

    async init() {
      try {
        const qs = new URLSearchParams({ path: this.workspacePath });
        const res = await fetch(`/api/template?${qs}`);
        if (!res.ok) {
          this.error = `could not load template (${res.status})`;
          return;
        }
        const body = await res.json();
        this.sections = body.sections || [];
        // Canonical sections are worth researching by default — if
        // the backend hands us a template with nothing pre-selected
        // (first-visit case), opt the user into the full set so
        // they can trim down rather than build up.
        const anySelected = this.sections.some((s) => s.selected);
        if (!anySelected) {
          this.sections.forEach((s) => { s.selected = true; });
        }
      } catch (err) {
        this.error = err.message;
      } finally {
        this.loading = false;
      }
    },

    toggle(section) {
      section.selected = !section.selected;
    },

    selectAll() {
      this.sections.forEach((s) => { s.selected = true; });
    },

    deselectAll() {
      this.sections.forEach((s) => { s.selected = false; });
    },

    async proceed() {
      if (this.selectedCount === 0) return;
      this.saving = true;
      try {
        const res = await fetch('/api/template', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            path: this.workspacePath,
            section_keys: this.sections.filter((s) => s.selected).map((s) => s.key),
          }),
        });
        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          this.error = body.detail || `could not save (${res.status})`;
          return;
        }
        Alpine.store('router').navigate(
          `#/confirm/${encodeURIComponent(this.workspacePath)}`,
        );
      } catch (err) {
        this.error = err.message;
      } finally {
        this.saving = false;
      }
    },

    back() {
      Alpine.store('router').navigate(
        `#/discover/${encodeURIComponent(this.workspacePath)}`,
      );
    },
  };
}

// ---------------------------------------------------------------------------
// Confirm screen
// ---------------------------------------------------------------------------

function confirmScreen() {
  return {
    loading: true,
    error: null,
    data: null,
    selectedModel: '',
    workers: 5,
    starting: false,

    get workspacePath() {
      return Alpine.store('router').params.arg[0] || '';
    },

    async init() {
      try {
        const qs = new URLSearchParams({ path: this.workspacePath });
        const res = await fetch(`/api/confirm?${qs}`);
        if (!res.ok) {
          this.error = `could not load estimate (${res.status})`;
          return;
        }
        this.data = await res.json();
        this.selectedModel = this.data.default_model;
        this.workers = this.data.default_workers;
      } catch (err) {
        this.error = err.message;
      } finally {
        this.loading = false;
      }
    },

    formatCost(value) {
      if (value == null) return '';
      return '$' + Number(value).toFixed(2);
    },

    formatEta(seconds) {
      if (!seconds) return '';
      if (seconds < 60) return `~${Math.round(seconds)}s`;
      const mins = Math.round(seconds / 60);
      return `~${mins} min`;
    },

    // Kick off a run. The server always injects the fake LLM client
    // for the prototype, so this is cheap by design. We navigate to
    // the run screen as soon as we have a run_id; the SSE stream
    // drives the rest of the UX.
    async start() {
      if (this.starting || this.loading) return;
      this.starting = true;
      this.error = null;
      try {
        const res = await fetch('/api/runs', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            path: this.workspacePath,
            model: this.selectedModel || null,
            workers: this.workers || null,
          }),
        });
        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          this.error = body.detail || `could not start run (${res.status})`;
          return;
        }
        const body = await res.json();
        Alpine.store('router').navigate(
          `#/run/${encodeURIComponent(this.workspacePath)}/${encodeURIComponent(body.run_id)}`,
        );
      } catch (err) {
        this.error = err.message;
      } finally {
        this.starting = false;
      }
    },

    back() {
      Alpine.store('router').navigate(
        `#/template/${encodeURIComponent(this.workspacePath)}`,
      );
    },
  };
}

// ---------------------------------------------------------------------------
// Run screen
// ---------------------------------------------------------------------------
//
// Subscribes to /api/runs/<run_id>/events and renders:
//   - a live activity log (capped at MAX_ACTIVITY entries)
//   - a running cost counter from CostRecorded events
//   - a stage progress bar driven by RunStageStarted events
//   - "view results" / "open dashboard" CTAs when the run finishes
//
// Stage weights mirror the TUI's pipeline_runner so users see the
// same rough shape of progress across both UIs.

const _RUN_STAGE_PROGRESS = {
  research: 0.15,
  verify: 0.3,
  enrich: 0.45,
  index: 0.55,
  themes: 0.65,
  synthesize: 0.85,
  deliver: 0.95,
};

const _RUN_MAX_ACTIVITY = 80;

function runScreen() {
  return {
    // The SSE subscription lives on the factory instance so we can
    // tear it down when the component unmounts (the hash router
    // replaces .screen-slot on navigation, which triggers Alpine's
    // destroy() path where we close the stream).
    _source: null,

    activity: [],
    cost: 0,
    progress: 0,
    phase: 'connecting',
    status: 'running',  // 'running' | 'done' | 'failed' | 'cancelled'
    error: null,

    get workspacePath() {
      return Alpine.store('router').params.arg[0] || '';
    },

    get runId() {
      return Alpine.store('router').params.arg[1] || '';
    },

    get progressPercent() {
      return Math.round(this.progress * 100);
    },

    // Render progress as a 42-cell string of Unicode block glyphs.
    // Full cells use █ (U+2588), empty cells use ░ (U+2591), and the
    // head cell uses the partial-block ladder ▏▎▍▌▋▊▉ (U+258F..U+2589)
    // so sub-cell changes read as a smooth 8-level gradient. The
    // monospace font in CSS keeps the track a fixed width regardless
    // of the current value.
    get progressBar() {
      const WIDTH = 42;
      const value = Math.max(0, Math.min(1, this.progress)) * WIDTH;
      const full = Math.floor(value);
      const frac = value - full;
      const partials = ['', '\u258F', '\u258E', '\u258D', '\u258C', '\u258B', '\u258A', '\u2589'];
      const idx = Math.round(frac * 8);
      let head = '';
      let empty = WIDTH - full;
      if (idx >= 8 && full < WIDTH) {
        return '\u2588'.repeat(full + 1) + '\u2591'.repeat(WIDTH - full - 1);
      }
      if (idx > 0 && empty > 0) {
        head = partials[idx];
        empty -= 1;
      }
      return '\u2588'.repeat(full) + head + '\u2591'.repeat(Math.max(0, empty));
    },

    get isTerminal() {
      return this.status !== 'running';
    },

    init() {
      if (!this.runId) {
        this.error = 'no run_id in URL';
        this.status = 'failed';
        return;
      }
      this._connect();
    },

    destroy() {
      this._teardown();
    },

    _teardown() {
      if (this._source) {
        this._source.close();
        this._source = null;
      }
    },

    _connect() {
      const url = `/api/runs/${encodeURIComponent(this.runId)}/events`;
      const source = new EventSource(url);
      this._source = source;

      // sse-starlette serializes events as {event, data} where data is
      // the JSON payload. addEventListener(type) lets us filter by
      // event class without parsing everything.
      const handlers = {
        RunStarted:         (p) => this._onRunStarted(p),
        RunStageStarted:    (p) => this._onStageStarted(p),
        RunStageCompleted:  (p) => this._onStageCompleted(p),
        RunCompleted:       (p) => this._onRunCompleted(p),
        RunFailed:          (p) => this._onRunFailed(p),
        RunCancelled:       (p) => this._onRunCancelled(p),
        CostRecorded:       (p) => this._onCost(p),
        SectionStarted:     (p) => this._pushActivity(`research: ${p.competitor_name} / ${p.section_key}`),
        SectionResearched:  (p) => this._pushActivity(`researched: ${p.competitor_name} / ${p.section_key}`),
        SectionRetrying:    (p) => this._pushActivity(`retry (${p.attempt}): ${p.competitor_name} / ${p.section_key}`),
        SectionFailed:      (p) => this._pushActivity(`failed: ${p.competitor_name} / ${p.section_key}`),
        ThemesDiscovered:   (p) => this._pushActivity(`themes discovered: ${p.theme_count}`),
        EnrichmentStarted:  (p) => this._pushActivity(`enrich: ${p.competitor_name} / ${p.pass_name}`),
        EnrichmentCompleted:(p) => this._pushActivity(`enriched: ${p.competitor_name} / ${p.pass_name}`),
        SynthesisStarted:   (p) => this._pushActivity(`synthesize: ${p.theme_label}`),
        SynthesisCompleted: (p) => this._pushActivity(`synthesized: ${p.theme_label}`),
        DeliveryStarted:    (p) => this._pushActivity(`deliver: ${p.theme_label}`),
        DeliveryCompleted:  (p) => this._pushActivity(`delivered: ${p.theme_label}`),
      };

      for (const [name, handler] of Object.entries(handlers)) {
        source.addEventListener(name, (ev) => {
          const payload = this._parse(ev.data);
          if (payload == null) return;
          handler(payload);
        });
      }

      source.onerror = () => {
        // An onerror during a terminal state is the server closing the
        // stream — not worth showing. Only surface it while the run
        // is still running.
        if (this.status === 'running') {
          this.phase = 'disconnected';
          this._pushActivity('stream disconnected');
        }
      };
    },

    _parse(raw) {
      try {
        return JSON.parse(raw);
      } catch (_err) {
        return null;
      }
    },

    _pushActivity(line) {
      const stamp = new Date().toLocaleTimeString();
      this.activity.push({ stamp, line });
      if (this.activity.length > _RUN_MAX_ACTIVITY) {
        this.activity.splice(0, this.activity.length - _RUN_MAX_ACTIVITY);
      }
    },

    _onRunStarted(_payload) {
      this.phase = 'started';
      this.status = 'running';
      this._pushActivity('run started');
    },

    _onStageStarted(payload) {
      const stage = payload.stage || '';
      this.phase = stage;
      this._pushActivity(`${stage}: start`);
      const weight = _RUN_STAGE_PROGRESS[stage];
      if (weight != null && weight > this.progress) {
        this.progress = weight;
      }
    },

    _onStageCompleted(payload) {
      this._pushActivity(`${payload.stage}: done`);
    },

    _onRunCompleted(payload) {
      this.status = 'done';
      this.phase = 'complete';
      this.progress = 1;
      if (typeof payload.total_cost_usd === 'number') {
        this.cost = payload.total_cost_usd;
      }
      this._pushActivity(`complete — $${this.cost.toFixed(4)}`);
      this._teardown();
    },

    _onRunFailed(payload) {
      this.status = 'failed';
      this.phase = 'failed';
      this.error = payload.error || 'run failed';
      this._pushActivity(`failed: ${this.error}`);
      this._teardown();
    },

    _onRunCancelled(_payload) {
      this.status = 'cancelled';
      this.phase = 'cancelled';
      this._pushActivity('cancelled');
      this._teardown();
    },

    _onCost(payload) {
      if (typeof payload.cost_usd === 'number') {
        this.cost += payload.cost_usd;
      }
    },

    formatCost() {
      return '$' + this.cost.toFixed(4);
    },

    goToResults() {
      Alpine.store('router').navigate(
        `#/results/${encodeURIComponent(this.workspacePath)}`,
      );
    },

    goToDashboard() {
      Alpine.store('router').navigate(
        `#/dashboard/${encodeURIComponent(this.workspacePath)}`,
      );
    },
  };
}

// ---------------------------------------------------------------------------
// Results screen
// ---------------------------------------------------------------------------
//
// Read-only surface over the workspace's delivered artifacts:
// executive_summary.md (preview up to ~2KB from the backend),
// per-theme markdown under themes/, and any other top-level output
// files. Everything is file-backed on disk so dropping files in a
// workspace and visiting #/results/<path> is enough to exercise it.

function resultsScreen() {
  return {
    loading: true,
    error: null,
    data: null,

    get workspacePath() {
      return Alpine.store('router').params.arg[0] || '';
    },

    async init() {
      if (!this.workspacePath) {
        this.loading = false;
        this.error = 'no workspace path in URL';
        return;
      }
      try {
        const qs = new URLSearchParams({ path: this.workspacePath });
        const res = await fetch(`/api/results?${qs}`);
        if (!res.ok) {
          this.error = `could not load results (${res.status})`;
          return;
        }
        this.data = await res.json();
      } catch (err) {
        this.error = err.message;
      } finally {
        this.loading = false;
      }
    },

    get hasSummary() {
      return !!this.data?.executive_summary_path;
    },

    get hasAnyArtifact() {
      return this.hasSummary || (this.data?.theme_files?.length || 0) > 0;
    },

    dashboardHash() {
      return `#/dashboard/${encodeURIComponent(this.workspacePath)}`;
    },
  };
}

// ---------------------------------------------------------------------------
// Dashboard screen (placeholder-with-context)
// ---------------------------------------------------------------------------
//
// The full dashboard ships alongside the live runner. Until then we
// at least read the workspace back so the user sees *which* project
// they're resuming (not a bare "dashboard is on the way" message).

function dashboardScreen() {
  return {
    loading: true,
    workspace: null,
    error: null,

    get workspacePath() {
      return Alpine.store('router').params.arg[0] || '';
    },

    async init() {
      if (!this.workspacePath) {
        this.loading = false;
        return;
      }
      try {
        const qs = new URLSearchParams({ path: this.workspacePath });
        const res = await fetch(`/api/workspace?${qs}`);
        if (!res.ok) {
          this.error = `could not load workspace (${res.status})`;
          return;
        }
        this.workspace = await res.json();
      } catch (err) {
        this.error = err.message;
      } finally {
        this.loading = false;
      }
    },

    resumeDiscoverHash() {
      return `#/discover/${encodeURIComponent(this.workspacePath)}`;
    },
  };
}

// ---------------------------------------------------------------------------
// Welcome screen
// ---------------------------------------------------------------------------

function welcomeScreen() {
  return {
    loading: true,
    projects: [],
    error: null,

    async init() {
      try {
        const response = await fetch('/api/recents');
        if (!response.ok) {
          this.error = `server returned ${response.status}`;
          this.loading = false;
          return;
        }
        const body = await response.json();
        this.projects = body.projects || [];
      } catch (err) {
        this.error = err.message;
      } finally {
        this.loading = false;
      }
      // Hook keyboard pick events forwarded from the shell.
      document.addEventListener('recon:welcome-pick', (e) => {
        const idx = e.detail && e.detail.index;
        if (typeof idx === 'number' && idx >= 0 && idx < this.projects.length) {
          this.open(this.projects[idx]);
        }
      });
    },

    open(project) {
      // Route by on-disk state so the user lands somewhere useful:
      //   missing  → no-op (directory is gone; the row is dimmed
      //              and the click should feel inert, not routed to
      //              a broken dashboard)
      //   new      → describe flow (no recon.yaml yet)
      //   ready    → resume discovery (workspace exists, no output)
      //   done     → dashboard (has output)
      // Path is URL-encoded so it survives the hash router round-trip.
      if (project.status === 'missing') {
        return;
      }
      const router = Alpine.store('router');
      const encoded = encodeURIComponent(project.path);
      let hash;
      switch (project.status) {
        case 'new':
          hash = '#/describe';
          break;
        case 'ready':
          hash = `#/discover/${encoded}`;
          break;
        case 'done':
        default:
          hash = `#/dashboard/${encoded}`;
          break;
      }
      router.navigate(hash);
    },

    formatDate(iso) {
      try {
        const d = new Date(iso);
        if (Number.isNaN(d.getTime())) return iso;
        return d.toLocaleDateString(undefined, {
          year: 'numeric',
          month: 'short',
          day: 'numeric',
        });
      } catch (_) {
        return iso;
      }
    },

    shortPath(p) {
      // ~/ shortening for HOME-relative paths is the user's
      // preferred display style (per ui-audit RC-8).
      const home = (window.RECON_HOME || '');
      if (home && p.startsWith(home)) {
        return '~' + p.slice(home.length);
      }
      return p;
    },

    // -------------------------------------------------------------
    // Status markers for the recent-projects list.
    //
    // The API maps each path to one of: done / ready / new / missing
    // (see web.api._project_status). We translate that into the same
    // 3-state progressive-fill vocabulary used on Discovery:
    //
    //   done    → \u25A0  filled  (success)
    //   ready   → \u25A3  partial (amber)   — workspace set up, no output
    //   new     → \u25A1  empty   (dim)     — path exists but nothing here
    //   missing → \u2715  cross   (error)   — directory is gone
    //
    // Returning a marker string + class name lets the template render
    // both the glyph and a matching text chip without duplicating the
    // branching in the HTML.
    // -------------------------------------------------------------

    recentStatusMarker(status) {
      switch (status) {
        case 'done':    return '\u25A0';
        case 'ready':   return '\u25A3';
        case 'missing': return '\u2715';
        case 'new':
        default:        return '\u25A1';
      }
    },

    recentStatusLabel(status) {
      switch (status) {
        case 'done':    return 'done';
        case 'ready':   return 'ready';
        case 'missing': return 'missing';
        case 'new':
        default:        return 'new';
      }
    },

    recentStatusClass(status) {
      switch (status) {
        case 'done':    return 'success';
        case 'ready':   return 'amber';
        case 'missing': return 'error';
        case 'new':
        default:        return 'dim';
      }
    },
  };
}
