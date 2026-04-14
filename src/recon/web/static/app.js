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

// Screens that are *not* part of the linear flow (welcome, dashboard,
// not-found). They suppress the flow-progress breadcrumb.
const NON_FLOW_SCREENS = new Set(['welcome', 'dashboard', 'not-found']);

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
  confirm:   [{ key: 'enter', label: 'start research' }, { key: 'esc', label: 'back' }],
  run:       [{ key: 'p', label: 'pause' }, { key: 's', label: 'stop' }, { key: 'q', label: 'quit' }],
  results:   [{ key: 'v', label: 'view summary' }, { key: 'b', label: 'dashboard' }, { key: 'q', label: 'quit' }],
  dashboard: [{ key: 'r', label: 'run' }, { key: 'b', label: 'back' }, { key: 'q', label: 'quit' }],
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
});

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
      const tpl = document.getElementById(`screen-${screenKey}`)
        || document.getElementById('screen-not-found');
      const slot = this.$refs.slot;
      slot.innerHTML = '';
      slot.appendChild(tpl.content.cloneNode(true));
      this.activeScreen = screenKey;
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

    get keybinds() {
      return SCREEN_KEYBINDS[this.activeScreen] || [];
    },

    // -------------------------------------------------------------
    // Global keyboard shortcuts
    // -------------------------------------------------------------

    handleKey(event) {
      // Don't steal focus from form inputs.
      const tag = (event.target && event.target.tagName) || '';
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') {
        return;
      }
      // Welcome-only shortcuts.
      if (this.activeScreen === 'welcome') {
        if (event.key === 'n') {
          Alpine.store('router').navigate('#/describe');
          event.preventDefault();
        } else if (/^[1-9]$/.test(event.key)) {
          // Forwarded to the welcome component via a custom event so
          // it can look up the index in its own state.
          document.dispatchEvent(new CustomEvent('recon:welcome-pick', {
            detail: { index: Number(event.key) - 1 },
          }));
          event.preventDefault();
        }
      }
      if (event.key === 'h') {
        Alpine.store('router').navigate('#/welcome');
        event.preventDefault();
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
        // Persist any newly-typed API keys first so workspace creation
        // can pick them up via load_api_keys.
        await this.persistKeys();
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
        Alpine.store('router').navigate(
          `#/discover/${encodeURIComponent(ws.path)}`,
        );
      } catch (err) {
        this.error = err.message;
      } finally {
        this.submitting = false;
      }
    },

    async persistKeys() {
      // Best-effort: skip empty fields. We don't have a workspace path
      // yet (the workspace is being created), so saving keys here
      // would need the workspace to already exist. For now, defer
      // key-save to a follow-up step after workspace creation.
      // This stub keeps the UI shape stable while the multi-step
      // dance lands in a follow-up commit.
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
      // Resume = land on the dashboard for that workspace. Path is
      // URL-encoded so it survives the hash router round-trip.
      Alpine.store('router').navigate(
        `#/dashboard/${encodeURIComponent(project.path)}`,
      );
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
  };
}
