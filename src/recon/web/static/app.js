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

// ---------------------------------------------------------------------------
// Paradigm: workspace, not wizard
// ---------------------------------------------------------------------------
//
// Routes:
//   #/                          Home — project list + first-run panel
//   #/p/<path>/<tab>            Project — one of 6 tabs active
//   #/p/<path>/runs/<run_id>    Project · Runs with slide-over open
//
// Legacy #/welcome, #/describe, #/discover/<path>, #/template/<path>,
// #/confirm/<path>, #/run/<path>/<run_id>, #/results/<path>,
// #/dashboard/<path> all forward to the new shape in parse() so old
// bookmarks keep working.

const TABS = [
  { key: 'overview',    label: 'Overview',    number: 1 },
  { key: 'competitors', label: 'Competitors', number: 2 },
  { key: 'template',    label: 'Template',    number: 3 },
  { key: 'runs',        label: 'Runs',        number: 4 },
  { key: 'brief',       label: 'Brief',       number: 5 },
  { key: 'settings',    label: 'Settings',    number: 6 },
];

const TAB_KEYS = new Set(TABS.map((t) => t.key));

// Keybind hints for the footer. Tabs share the project-scoped set;
// home has its own.
const HOME_KEYBINDS = [
  { key: 'n',     label: 'new project' },
  { key: 'j/k',   label: 'select' },
  { key: 'enter', label: 'open' },
  { key: '/',     label: 'filter' },
  { key: '⌘K',    label: 'palette' },
  { key: 't',     label: 'theme' },
];

const PROJECT_KEYBINDS = [
  { key: '1-6',   label: 'tab' },
  { key: 'r',     label: 'run' },
  { key: '/',     label: 'filter' },
  { key: 'esc',   label: 'home' },
  { key: '⌘K',    label: 'palette' },
  { key: 't',     label: 'theme' },
];

// ---------------------------------------------------------------------------
// Router store
// ---------------------------------------------------------------------------

document.addEventListener('alpine:init', () => {
  Alpine.store('router', {
    hash: '',
    screen: 'home',
    params: { path: '', tab: 'overview', runId: '', arg: [] },

    parse() {
      const raw = location.hash || '#/';
      this.hash = raw;
      const segs = raw.replace(/^#\/?/, '').split('/').filter(Boolean).map(decodeURIComponent);

      // Home
      if (segs.length === 0) {
        this.screen = 'home';
        this.params = { path: '', tab: 'overview', runId: '', arg: [] };
        return;
      }

      // Project: #/p/<path>/<tab>[/<runId>]
      if (segs[0] === 'p' && segs.length >= 2) {
        const path = segs[1];
        let tab = segs[2] || 'overview';
        let runId = '';
        // #/p/<path>/runs/<run_id> keeps tab='runs' and captures the id
        if (tab === 'runs' && segs[3]) {
          runId = segs[3];
        } else if (!TAB_KEYS.has(tab)) {
          tab = 'overview';
        }
        this.screen = 'project';
        this.params = { path, tab, runId, arg: [path] };
        return;
      }

      // Legacy redirects — keep old bookmarks working.
      const legacyTabMap = {
        discover: 'competitors',
        template: 'template',
        confirm: 'overview',
        results: 'brief',
        dashboard: 'overview',
      };
      if (segs[0] === 'welcome' || segs[0] === 'describe') {
        location.hash = '#/';
        return;
      }
      if (legacyTabMap[segs[0]] && segs[1]) {
        location.hash = `#/p/${encodeURIComponent(segs[1])}/${legacyTabMap[segs[0]]}`;
        return;
      }
      if (segs[0] === 'run' && segs[1] && segs[2]) {
        location.hash = `#/p/${encodeURIComponent(segs[1])}/runs/${encodeURIComponent(segs[2])}`;
        return;
      }

      // Unknown route — not-found view
      this.screen = 'not-found';
      this.params = { path: '', tab: '', runId: '', arg: [] };
    },

    navigate(hash) {
      if (location.hash === hash) {
        this.parse();
        document.dispatchEvent(new CustomEvent('recon:route'));
      } else {
        location.hash = hash;
      }
    },

    // Helpers used all over the place. Encode-safe.
    home() { this.navigate('#/'); },
    project(path, tab) {
      const t = tab && TAB_KEYS.has(tab) ? tab : 'overview';
      this.navigate(`#/p/${encodeURIComponent(path)}/${t}`);
    },
    tab(t) {
      if (this.screen !== 'project' || !this.params.path) return;
      if (!TAB_KEYS.has(t)) return;
      this.navigate(`#/p/${encodeURIComponent(this.params.path)}/${t}`);
    },
    runDetail(runId) {
      if (this.screen !== 'project' || !this.params.path) return;
      this.navigate(`#/p/${encodeURIComponent(this.params.path)}/runs/${encodeURIComponent(runId)}`);
    },
  });

  // Theme store: the picker component and the [t] keybind both reach
  // in here so the header trigger, popover, and keyboard all stay in
  // sync. Seed from localStorage via readPersistedTheme so the store
  // matches whatever the preflight script already wrote to <html>.
  Alpine.store('theme', {
    active: readPersistedTheme(),
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
  });

  // Run slide-over: the overlay UI for starting a run AND watching
  // progress. State lives in a store so the header "● Run in progress"
  // pill can react from anywhere and reopen/reattach works across
  // tab navigation without losing the live connection.
  Alpine.store('runOverlay', {
    visible: false,
    mode: 'closed',   // 'closed' | 'plan' | 'live' | 'terminal'
    path: '',
    runId: '',

    openPlan(path) {
      this.path = path;
      this.runId = '';
      this.mode = 'plan';
      this.visible = true;
    },

    openLive(path, runId) {
      this.path = path;
      this.runId = runId;
      this.mode = 'live';
      this.visible = true;
    },

    close() {
      this.visible = false;
    },
  });

  // Command palette — Cmd-K / Ctrl-K driven action menu.
  Alpine.store('palette', {
    open: false,
    query: '',
    show() { this.open = true; this.query = ''; },
    hide() { this.open = false; },
  });

  // Project scope: holds the currently-loaded workspace so every tab
  // reads from the same snapshot. projectScreen populates this on
  // mount; tabs consume it via $store.project.
  Alpine.store('project', {
    path: '',
    workspace: null,
    loading: true,
    error: null,
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

    activeLabel() {
      const match = this.options.find((o) => o.key === this.active);
      return match ? match.label : 'Theme';
    },

    select(key) {
      Alpine.store('theme').set(key);
    },
  };
}

// ---------------------------------------------------------------------------
// Top-level shell component
// ---------------------------------------------------------------------------

function reconShell() {
  return {
    activeScreen: null,   // 'home' | 'project' | 'not-found'
    activeTab: '',        // when activeScreen === 'project'
    tabs: TABS,

    init() {
      const router = Alpine.store('router');
      router.parse();
      this.mount();
      const onHashChange = () => {
        router.parse();
        this.mount();
      };
      window.addEventListener('hashchange', onHashChange);
      document.addEventListener('recon:route', onHashChange);
      document.addEventListener('keydown', (e) => this.handleKey(e));
    },

    mount() {
      const router = Alpine.store('router');
      const screen = router.screen;
      this.activeScreen = screen;
      this.activeTab = screen === 'project' ? router.params.tab : '';

      // Screen template lookup:
      //   home → #screen-home
      //   project → #screen-project (which reads the tab param itself)
      //   not-found → #screen-not-found
      const tplKey = screen === 'project' ? 'project' : screen;
      let tpl = document.getElementById(`screen-${tplKey}`);
      if (!tpl) tpl = document.getElementById('screen-not-found');
      const slot = this.$refs.slot;
      slot.innerHTML = '';
      slot.appendChild(tpl.content.cloneNode(true));

      // If the project route includes a run_id, tell the overlay to
      // attach to that run. Run slide-over state survives across tabs.
      if (screen === 'project' && router.params.runId) {
        Alpine.store('runOverlay').openLive(router.params.path, router.params.runId);
      }
    },

    get headerSubtitle() {
      if (this.activeScreen === 'home') return 'projects';
      if (this.activeScreen === 'project') {
        const tab = TABS.find((t) => t.key === this.activeTab);
        return tab ? tab.label.toLowerCase() : '';
      }
      if (this.activeScreen === 'not-found') return 'not found';
      return '';
    },

    get workspacePath() {
      return Alpine.store('router').params.path || '';
    },

    get keybinds() {
      const base = this.activeScreen === 'project' ? PROJECT_KEYBINDS : HOME_KEYBINDS;
      return base;
    },

    // Read the currently-mounted screen's factory state so keybinds
    // can invoke its methods (open/search/proceed/etc).
    screenData() {
      const slot = this.$refs.slot;
      const root = slot && slot.firstElementChild;
      if (!root) return null;
      try { return Alpine.$data(root); } catch (_) { return null; }
    },

    // Tab jumps from anywhere in the project.
    goTab(key) {
      if (this.activeScreen !== 'project') return;
      Alpine.store('router').tab(key);
    },

    handleKey(event) {
      const tag = (event.target && event.target.tagName) || '';
      const isFormField = tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT';

      const router = Alpine.store('router');
      const palette = Alpine.store('palette');

      // Cmd-K / Ctrl-K always opens the palette, even from inputs.
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        palette.show();
        event.preventDefault();
        return;
      }

      // Escape closes overlays first, then form fields can still
      // keep their native handling.
      if (event.key === 'Escape') {
        if (palette.open) { palette.hide(); event.preventDefault(); return; }
        const overlay = Alpine.store('runOverlay');
        if (overlay.visible) { overlay.close(); event.preventDefault(); return; }
        if (this.activeScreen === 'project' && !isFormField) {
          router.home();
          event.preventDefault();
          return;
        }
      }

      // Form-field focus yields all other non-modifier keys.
      if (isFormField) return;

      const key = event.key;

      // Universal shortcuts
      if (key === 't') { Alpine.store('theme').cycle(); event.preventDefault(); return; }

      // Home-screen shortcuts
      if (this.activeScreen === 'home') {
        if (key === 'n') {
          document.dispatchEvent(new CustomEvent('recon:home-new'));
          event.preventDefault();
        } else if (/^[1-9]$/.test(key)) {
          document.dispatchEvent(new CustomEvent('recon:home-pick', { detail: { index: Number(key) - 1 } }));
          event.preventDefault();
        } else if (key === '/') {
          document.dispatchEvent(new CustomEvent('recon:home-filter'));
          event.preventDefault();
        }
        return;
      }

      // Project-screen shortcuts
      if (this.activeScreen === 'project') {
        // Number keys 1-6 jump tabs.
        if (/^[1-6]$/.test(key)) {
          const idx = Number(key) - 1;
          if (idx < TABS.length) {
            this.goTab(TABS[idx].key);
            event.preventDefault();
          }
          return;
        }
        if (key === 'r') {
          Alpine.store('runOverlay').openPlan(this.workspacePath);
          event.preventDefault();
          return;
        }
        if (key === '/') {
          document.dispatchEvent(new CustomEvent('recon:tab-filter'));
          event.preventDefault();
          return;
        }
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

    // Mirror server-side _heuristic_company_name + _slugify_for_path
    // so the user sees (roughly) where the workspace will land before
    // submit. The backend may append `-2`, `-3` suffixes on collision,
    // so we surface the *base* path as a preview — not a promise.
    get derivedSlug() {
      const text = (this.description || '').trim();
      if (!text) return '';
      // Take the first meaningful token (skip stop words), lowercase,
      // strip non-alphanumeric. Matches the server's rough shape
      // without pulling the full heuristic over; the server is
      // ultimately authoritative.
      const first = text.split(/\s+/)[0] || '';
      return first.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
    },

    get pathPreview() {
      const slug = this.derivedSlug;
      if (!slug) return '';
      const home = (window.RECON_HOME || '~').replace(/\/$/, '');
      return `${home}/recon-workspaces/${slug}`;
    },

    async init() {
      // Focus the textarea so the user can start typing immediately.
      this.$refs.description?.focus();
      // Preload saved-key status from the global ~/.recon/.env so users
      // aren't prompted to re-enter keys they've already stored. We
      // never fetch the key values — only whether they're set — so
      // this is safe to call before any workspace exists.
      try {
        const res = await fetch('/api/api-keys/global');
        if (!res.ok) return;
        const body = await res.json();
        for (const provider of this.providers) {
          if (body[provider.name]) {
            provider.saved = true;
          }
        }
      } catch (_err) { /* non-fatal — user can still type keys */ }
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
        // Land inside the new workspace at the Overview tab. Discovery
        // is now a tab (/competitors) the user can enter whenever.
        Alpine.store('router').project(ws.path, 'overview');
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
      Alpine.store('router').home();
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
    // Discovery-agent state
    searching: false,
    searchMessage: null,
    searchError: null,
    discovered: [],          // raw candidate list from /api/discover
    importedNames: new Set(), // client-side dedupe

    get workspacePath() {
      return Alpine.store('router').params.arg[0] || '';
    },

    // Candidates the agent returned that aren't already in the
    // workspace (either saved or just-imported this session).
    get pendingDiscovered() {
      const savedNames = new Set(
        this.competitors.map((c) => c.name.toLowerCase()),
      );
      return this.discovered.filter((c) => {
        const key = c.name.toLowerCase();
        return !savedNames.has(key) && !this.importedNames.has(key);
      });
    },

    async init() {
      await this.refresh();
    },

    async search() {
      if (this.searching) return;
      this.searching = true;
      this.searchError = null;
      this.searchMessage = null;
      try {
        const res = await fetch('/api/discover', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            path: this.workspacePath,
            seeds: this.competitors.map((c) => c.name),
          }),
        });
        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          this.searchError = body.detail || `search failed (${res.status})`;
          return;
        }
        const body = await res.json();
        this.discovered = body.candidates || [];
        if (this.discovered.length === 0) {
          this.searchMessage = 'no new candidates found';
        } else {
          const label = body.used_web_search
            ? 'from web search'
            : 'from training-data fallback (no web access)';
          this.searchMessage = `${this.discovered.length} candidate${this.discovered.length === 1 ? '' : 's'} ${label}`;
        }
      } catch (err) {
        this.searchError = err.message;
      } finally {
        this.searching = false;
      }
    },

    async accept(candidate) {
      // Add a discovered candidate to the workspace. On success, mark
      // it imported locally so it disappears from the pending list
      // without needing a full /api/competitors refresh.
      try {
        const res = await fetch('/api/competitors', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            path: this.workspacePath,
            name: candidate.name,
            url: candidate.url || null,
            blurb: candidate.blurb || null,
          }),
        });
        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          this.error = body.detail || `could not add (${res.status})`;
          return;
        }
        const created = await res.json();
        this.competitors = [...this.competitors, created];
        this.importedNames.add(candidate.name.toLowerCase());
      } catch (err) {
        this.error = err.message;
      }
    },

    reject(candidate) {
      this.importedNames.add(candidate.name.toLowerCase());
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
      // In the workspace paradigm, Competitors is just a tab — no
      // next step. "proceed" from here = jump to Template tab.
      Alpine.store('router').tab('template');
    },

    back() {
      Alpine.store('router').tab('overview');
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
        // Template saved — nothing to "proceed" to in the tab world.
        // Opening the run slide-over (plan mode) is the natural next
        // step; users can also ignore this and keep navigating tabs.
        Alpine.store('runOverlay').openPlan(this.workspacePath);
      } catch (err) {
        this.error = err.message;
      } finally {
        this.saving = false;
      }
    },

    back() {
      Alpine.store('router').tab('competitors');
    },
  };
}

// ---------------------------------------------------------------------------
// Confirm screen (now rendered inside the Run slide-over)
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
      return Alpine.store('runOverlay').path
          || Alpine.store('router').params.path
          || '';
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
        // Flip the overlay from plan → live mode. Navigating also
        // encodes the run_id in the URL so the user can share it.
        Alpine.store('runOverlay').openLive(this.workspacePath, body.run_id);
        Alpine.store('router').runDetail(body.run_id);
      } catch (err) {
        this.error = err.message;
      } finally {
        this.starting = false;
      }
    },

    back() {
      Alpine.store('runOverlay').close();
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
      // In the workspace paradigm the path lives on the router. For
      // the run overlay we read it from the overlay store so we can
      // be opened without a router change.
      return Alpine.store('runOverlay').path
          || Alpine.store('router').params.path
          || '';
    },

    get runId() {
      return Alpine.store('runOverlay').runId
          || Alpine.store('router').params.runId
          || '';
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
      Alpine.store('runOverlay').close();
      Alpine.store('router').tab('brief');
    },

    goToDashboard() {
      Alpine.store('runOverlay').close();
      Alpine.store('router').tab('overview');
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

function homeScreen() {
  return {
    loading: true,
    projects: [],
    error: null,
    filter: '',
    showFirstRun: false,    // the inline new-project form
    selectedIndex: 0,       // for j/k nav

    get filteredProjects() {
      const q = this.filter.trim().toLowerCase();
      if (!q) return this.projects;
      return this.projects.filter((p) =>
        (p.name || '').toLowerCase().includes(q) ||
        (p.path || '').toLowerCase().includes(q),
      );
    },

    async init() {
      try {
        const response = await fetch('/api/recents');
        if (response.ok) {
          const body = await response.json();
          this.projects = body.projects || [];
        }
      } catch (err) {
        this.error = err.message;
      } finally {
        this.loading = false;
      }

      // Hook keyboard events forwarded from the shell.
      document.addEventListener('recon:home-new', () => {
        this.showFirstRun = true;
      });
      document.addEventListener('recon:home-pick', (e) => {
        const idx = e.detail && e.detail.index;
        const list = this.filteredProjects;
        if (typeof idx === 'number' && idx >= 0 && idx < list.length) {
          this.open(list[idx]);
        }
      });
      document.addEventListener('recon:home-filter', () => {
        this.$refs.filterInput?.focus();
      });
    },

    open(project) {
      if (project.status === 'missing') return;
      // In the workspace paradigm, every valid project lands at its
      // Overview tab. Edge cases (missing recon.yaml, etc) are handled
      // by the tab rendering, not by routing to a different screen.
      Alpine.store('router').project(project.path, 'overview');
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


// ===========================================================================
// Project shell + tab factories
// ===========================================================================

// Bridges the router to the active tab template. Each tab is defined
// in index.html as <template id="tab-<key>">. When the route changes
// tab, we clone the matching template into #tab-slot.
function projectScreen() {
  return {
    activeTab: '',

    get path() {
      return Alpine.store('router').params.path || '';
    },

    async init() {
      this.activeTab = Alpine.store('router').params.tab || 'overview';

      // Seed the project store for this workspace. Tabs read from it.
      const store = Alpine.store('project');
      store.path = this.path;
      store.workspace = null;
      store.loading = true;
      store.error = null;

      this.mountTab();

      const onRoute = () => {
        const t = Alpine.store('router').params.tab || 'overview';
        if (t !== this.activeTab) { this.activeTab = t; this.mountTab(); }
      };
      document.addEventListener('recon:route', onRoute);
      window.addEventListener('hashchange', onRoute);

      await this.loadWorkspace();
    },

    async loadWorkspace() {
      const store = Alpine.store('project');
      if (!this.path) { store.loading = false; return; }
      try {
        const qs = new URLSearchParams({ path: this.path });
        const res = await fetch(`/api/workspace?${qs}`);
        if (res.ok) store.workspace = await res.json();
        else store.error = `could not load workspace (${res.status})`;
      } catch (err) {
        store.error = err.message;
      } finally {
        store.loading = false;
      }
    },

    mountTab() {
      const slot = this.$refs.tabSlot;
      if (!slot) return;
      const tpl = document.getElementById(`tab-${this.activeTab}`);
      if (!tpl) return;
      slot.innerHTML = '';
      slot.appendChild(tpl.content.cloneNode(true));
    },

    isActive(tab) { return tab === this.activeTab; },
    goTab(tab) { Alpine.store('router').tab(tab); },
  };
}

// Runs tab — lists all past runs for this workspace with status,
// cost, task counts. Click a row to open the slide-over for that
// run.
function runsTab() {
  return {
    loading: true,
    runs: [],
    error: null,
    filter: '',

    get path() {
      return Alpine.store('router').params.path || '';
    },

    get filteredRuns() {
      const q = this.filter.trim().toLowerCase();
      if (!q) return this.runs;
      return this.runs.filter((r) =>
        r.run_id.toLowerCase().includes(q) ||
        r.status.toLowerCase().includes(q) ||
        (r.model || '').toLowerCase().includes(q),
      );
    },

    async init() {
      try {
        const qs = new URLSearchParams({ path: this.path });
        const res = await fetch(`/api/runs?${qs}`);
        if (!res.ok) { this.error = `could not load runs (${res.status})`; return; }
        const body = await res.json();
        this.runs = body.runs || [];
      } catch (err) {
        this.error = err.message;
      } finally {
        this.loading = false;
      }

      document.addEventListener('recon:tab-filter', () => {
        this.$refs.filterInput?.focus();
      });
    },

    openRun(run) {
      Alpine.store('runOverlay').openLive(this.path, run.run_id);
      Alpine.store('router').runDetail(run.run_id);
    },

    formatDate(iso) {
      try {
        const d = new Date(iso);
        if (Number.isNaN(d.getTime())) return iso;
        return d.toLocaleString(undefined, {
          month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
        });
      } catch (_) { return iso; }
    },

    formatCost(v) { return '$' + (Number(v) || 0).toFixed(4); },
  };
}

// Keys popover — global API-key management from the header.
function keysPopover() {
  return {
    open: false,
    loading: false,
    providers: [
      { name: 'anthropic', label: 'Anthropic', placeholder: 'sk-ant-...', value: '', saved: false },
      { name: 'google_ai', label: 'Google AI', placeholder: 'AIza...',     value: '', saved: false },
    ],
    message: '',

    async toggle() {
      if (this.open) { this.open = false; return; }
      this.open = true;
      await this.refresh();
    },

    async refresh() {
      this.loading = true;
      try {
        const res = await fetch('/api/api-keys/global');
        if (res.ok) {
          const body = await res.json();
          for (const p of this.providers) p.saved = !!body[p.name];
        }
      } catch (_) { /* non-fatal */ }
      finally { this.loading = false; }
    },

    async save() {
      this.loading = true;
      this.message = '';
      for (const p of this.providers) {
        const val = (p.value || '').trim();
        if (!val) continue;
        try {
          await fetch('/api/api-keys', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: p.name, value: val }),
          });
          p.saved = true;
          p.value = '';
        } catch (_) { /* non-fatal */ }
      }
      this.loading = false;
      this.message = 'Saved.';
      setTimeout(() => { this.message = ''; }, 2000);
    },
  };
}

// Command palette — Cmd-K / Ctrl-K global actions.
function cmdPalette() {
  return {
    get open() { return Alpine.store('palette').open; },
    query: '',
    selectedIndex: 0,

    get actions() {
      const router = Alpine.store('router');
      const inProject = router.screen === 'project';
      const list = [
        { id: 'home', label: 'Go home', hint: 'home', run: () => router.home() },
      ];
      if (inProject) {
        for (const t of TABS) {
          list.push({
            id: 'tab-' + t.key,
            label: `Go to ${t.label}`,
            hint: t.number + ' · ' + t.key,
            run: () => router.tab(t.key),
          });
        }
        list.push({ id: 'run', label: 'Run research', hint: 'r', run: () => Alpine.store('runOverlay').openPlan(router.params.path) });
      }
      for (const th of THEMES) {
        list.push({
          id: 'theme-' + th.key,
          label: `Theme: ${th.label}`,
          hint: th.description,
          run: () => Alpine.store('theme').set(th.key),
        });
      }
      const q = this.query.trim().toLowerCase();
      if (!q) return list;
      return list.filter((a) => a.label.toLowerCase().includes(q));
    },

    init() {
      document.addEventListener('keydown', (e) => {
        if (!this.open) return;
        if (e.key === 'ArrowDown') {
          this.selectedIndex = Math.min(this.selectedIndex + 1, this.actions.length - 1);
          e.preventDefault();
        } else if (e.key === 'ArrowUp') {
          this.selectedIndex = Math.max(this.selectedIndex - 1, 0);
          e.preventDefault();
        } else if (e.key === 'Enter') {
          const a = this.actions[this.selectedIndex];
          if (a) { a.run(); Alpine.store('palette').hide(); }
          e.preventDefault();
        }
      });
    },

    choose(action) {
      action.run();
      Alpine.store('palette').hide();
    },
  };
}

