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
  confirm:   [{ key: 'esc', label: 'back' }],
  run:       [{ key: 'p', label: 'pause' }, { key: 's', label: 'stop' }, { key: 'q', label: 'quit' }],
  results:   [{ key: 'v', label: 'view summary' }, { key: 'b', label: 'dashboard' }, { key: 'q', label: 'quit' }],
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
      return SCREEN_KEYBINDS[this.activeScreen] || [];
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

      // Flow screens reserve Enter/Escape. Outside the flow, `h` is
      // the universal "home" shortcut.
      const inFlow = ['describe', 'discover', 'template', 'confirm'].includes(screen);
      if (key === 'h' && !inFlow) {
        router.navigate('#/welcome');
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

    back() {
      Alpine.store('router').navigate(
        `#/template/${encodeURIComponent(this.workspacePath)}`,
      );
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
