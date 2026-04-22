// recon web UI — v4 shell
//
// Architecture:
//   - Hash-based router: #/  = home (RECON), #/p/<path>/<tab> = project
//   - Five flow tabs: plan, schema, comps, agents, output (numbered 1-5)
//   - Screen registry: each route maps to a <template id="screen-<key>">
//   - Hotkey registry: scoped stack. Screens push a scope on mount,
//     pop on unmount. Global keys live at the bottom of the stack.
//
// Phase 1 scope: shell chrome + routing + hotkeys + stub screen
// factories. Each subsequent phase replaces one stub with a real
// implementation.

// ---------------------------------------------------------------------------
// Tabs
// ---------------------------------------------------------------------------
//
// Tab metadata is the single source of truth for:
//   - the top-nav link order
//   - the 1-5 numeric hotkeys (bound at the project scope)
//   - the Lucide icon shown in the nav
//
// "home" is not a tab — the RECON brand button is a separate affordance
// that lives to the left of the tab list and owns its own route.

const TABS = [
  { key: 'plan',   label: 'PLAN',    number: 1, icon: 'map' },
  { key: 'schema', label: 'SCHEMA',  number: 2, icon: 'square-stack' },
  { key: 'comps',  label: "COMP'S",  number: 3, icon: 'shapes' },
  { key: 'agents', label: 'AGENTS',  number: 4, icon: 'rabbit' },
  { key: 'output', label: 'OUTPUT',  number: 5, icon: 'folder-open' },
];

const TAB_KEYS = new Set(TABS.map((t) => t.key));
const DEFAULT_TAB = 'plan';

// ---------------------------------------------------------------------------
// Hotkey registry
// ---------------------------------------------------------------------------
//
// Scopes stack top-to-bottom: global at the bottom, project in the
// middle, screen-level above that, modals on top. handle() walks from
// the top down and fires the first match, preventing default so keys
// like "1" don't end up typed into focused inputs.
//
// A binding can declare `hint: 'left' | 'right'` and an optional
// `icon` so the bottom nav renders its own shortcut bar — screens
// don't have to hand-write hint lists.
//
// Key normalization: we match on event.key, lowercased. Modifiers are
// encoded as prefixes: "ctrl+k", "shift+?", "meta+enter". Single
// chars match themselves. Special keys use their event.key value
// (lower-cased): "escape", "arrowup", "enter".

const KEY_ALIAS = {
  ' ': 'space',
  'arrowup': 'up',
  'arrowdown': 'down',
  'arrowleft': 'left',
  'arrowright': 'right',
};

function normalizeKey(event) {
  let k = (event.key || '').toLowerCase();
  k = KEY_ALIAS[k] || k;
  const parts = [];
  if (event.ctrlKey) parts.push('ctrl');
  if (event.metaKey) parts.push('meta');
  if (event.altKey) parts.push('alt');
  if (event.shiftKey && k.length > 1) parts.push('shift');  // shift already changes char for single keys
  parts.push(k);
  return parts.join('+');
}

// Keys we never intercept when focus is on an editable element.
const EDITABLE_TAGS = new Set(['INPUT', 'TEXTAREA', 'SELECT']);

function isEditableTarget(event) {
  const el = event.target;
  if (!el) return false;
  if (EDITABLE_TAGS.has(el.tagName)) return true;
  if (el.isContentEditable) return true;
  return false;
}

document.addEventListener('alpine:init', () => {
  Alpine.store('hotkeys', {
    scopes: [],  // [{ id, bindings: [{ key, label, run, hint, icon, allowInEditable }] }]

    register(id, bindings) {
      this.unregister(id);
      this.scopes.push({ id, bindings });
    },

    unregister(id) {
      this.scopes = this.scopes.filter((s) => s.id !== id);
    },

    // Clear all scopes whose id starts with "screen:". Called by the
    // shell before mounting a new screen so stale bindings from the
    // previous screen don't leak into the new one. (Alpine doesn't
    // emit a teardown event on x-data removal, so we can't rely on
    // per-component unregister.)
    clearScreens() {
      this.scopes = this.scopes.filter((s) => !s.id.startsWith('screen:'));
    },

    handle(event) {
      const key = normalizeKey(event);
      const editable = isEditableTarget(event);
      for (let i = this.scopes.length - 1; i >= 0; i--) {
        const hit = this.scopes[i].bindings.find((b) => b.key === key);
        if (!hit) continue;
        if (editable && !hit.allowInEditable) return;
        event.preventDefault();
        hit.run(event);
        return;
      }
    },

    // Derived hint lists for the bottom nav. Merge all active scopes so
    // global hints stay visible while screen-specific ones layer on
    // top. Later scopes win on key collisions so a screen can override
    // a global binding without losing the hint slot.
    get leftHints() {
      return this._hints('left');
    },
    get rightHints() {
      return this._hints('right');
    },
    _hints(side) {
      const byKey = new Map();
      for (const scope of this.scopes) {
        for (const b of scope.bindings) {
          if (b.hint !== side || !b.label) continue;
          byKey.set(b.key, { key: b.displayKey || b.key, label: b.label, icon: b.icon });
        }
      }
      return Array.from(byKey.values());
    },
  });

  // Screen teardown — screens push cleanup callbacks here (close SSE,
  // cancel fetches, etc.) and the shell fires them all before mounting
  // the next screen.
  Alpine.store('screen', {
    teardowns: [],
    onTeardown(fn) { this.teardowns.push(fn); },
    flush() {
      const fns = this.teardowns;
      this.teardowns = [];
      for (const fn of fns) { try { fn(); } catch (_e) { /* swallow */ } }
    },
  });

  // ---------------------------------------------------------------------
  // Router store
  // ---------------------------------------------------------------------
  //
  // Routes:
  //   #/                  home (projects list)
  //   #/p/<path>          project — defaults to #/p/<path>/plan
  //   #/p/<path>/<tab>    project at a specific tab
  //
  // parse() is called on load and on hashchange. It sets `screen`
  // (home | project | not-found) and `params` (path, tab).
  Alpine.store('router', {
    hash: '',
    screen: 'home',
    params: { path: '', tab: DEFAULT_TAB },

    parse() {
      const raw = location.hash || '#/';
      this.hash = raw;
      // Split off any ?query tail first so the last segment doesn't
      // get stuck with "agents?run=xyz" when parsing tabs.
      const [pathPart, queryPart] = raw.replace(/^#\/?/, '').split('?');
      const segs = pathPart.split('/').filter(Boolean).map(decodeURIComponent);
      const query = Object.fromEntries(new URLSearchParams(queryPart || ''));

      if (segs.length === 0) {
        this.screen = 'home';
        this.params = { path: '', tab: DEFAULT_TAB, query };
        return;
      }
      if (segs[0] === 'p' && segs[1]) {
        const tab = segs[2] && TAB_KEYS.has(segs[2]) ? segs[2] : DEFAULT_TAB;
        this.screen = 'project';
        this.params = { path: segs[1], tab, query };
        return;
      }
      this.screen = 'not-found';
    },

    navigate(hash) {
      if (location.hash === hash) {
        // Same hash — hashchange won't fire. Force a re-parse so the
        // screen remounts (useful on "open same project again").
        this.parse();
      } else {
        location.hash = hash;
      }
    },

    goHome() {
      this.navigate('#/');
    },

    goTab(tab) {
      if (!this.params.path) return;
      this.navigate('#/p/' + encodeURIComponent(this.params.path) + '/' + tab);
    },
  });
});

// ---------------------------------------------------------------------------
// Shell component
// ---------------------------------------------------------------------------
//
// Owns: header state (active screen / tab), global hotkeys, screen-slot
// mounting. Screens themselves are dumb components cloned into the
// slot on route change.

function reconShell() {
  return {
    tabs: TABS,

    // Router state mirrors
    get screen() { return this.$store.router.screen; },
    get params() { return this.$store.router.params; },
    get workspacePath() { return this.$store.router.params.path; },
    get activeTab() { return this.$store.router.params.tab; },
    get hasProject() { return this.$store.router.screen === 'project' && !!this.workspacePath; },

    init() {
      this.$store.router.parse();
      window.addEventListener('hashchange', () => {
        this.$store.router.parse();
        this.mountScreen();
      });
      this.registerGlobalHotkeys();
      this.mountScreen();
    },

    // -----------------------------------------------------------------
    // Tab helpers
    // -----------------------------------------------------------------

    tabHref(tab) {
      const path = this.workspacePath;
      if (!path) return '#/';
      return '#/p/' + encodeURIComponent(path) + '/' + tab;
    },

    isTabActive(tab) {
      return this.screen === 'project' && this.activeTab === tab;
    },

    // -----------------------------------------------------------------
    // Hotkeys
    // -----------------------------------------------------------------

    registerGlobalHotkeys() {
      const bindings = [
        {
          key: 'q', label: 'QUIT', hint: 'left',
          run: () => window.close(),
        },
        {
          key: 's', label: 'SAVE PROGRESS', hint: 'left',
          run: () => {
            // TODO(phase 3+): broadcast a save intent; for now, no-op.
          },
        },
        {
          key: 'z', label: 'SETTINGS', hint: 'right', icon: 'settings',
          run: () => {
            // TODO(phase 9): open settings palette.
          },
        },
      ];
      this.$store.hotkeys.register('global', bindings);

      // Project-scope: numbered tab switches + 0 to home. Only fires
      // when a project is loaded, so the home screen doesn't steal "1"
      // from inputs.
      const projectBindings = TABS.map((tab) => ({
        key: String(tab.number),
        label: tab.label,
        run: () => {
          if (this.hasProject) this.$store.router.goTab(tab.key);
        },
      }));
      projectBindings.push({
        key: '0',
        label: 'RECON',
        run: () => this.$store.router.goHome(),
      });
      this.$store.hotkeys.register('project-tabs', projectBindings);
    },

    // -----------------------------------------------------------------
    // Screen mounting
    // -----------------------------------------------------------------
    //
    // We clone the matching <template> into #screen-slot. Alpine's
    // x-data on the cloned root boots the factory. Using template
    // cloning (vs x-if + big inline template) keeps the DOM diffs
    // small and lets each screen own its own lifecycle.

    mountScreen() {
      const slot = this.$refs.slot;
      if (!slot) return;
      // Clear any screen-owned hotkeys before the new screen mounts and
      // registers its own. (Alpine doesn't fire a teardown event when
      // x-data subtrees are removed.)
      this.$store.hotkeys.clearScreens();
      this.$store.screen.flush();
      const key = this.screen === 'project' ? this.activeTab : this.screen;
      const tmpl = document.getElementById('screen-' + key) || document.getElementById('screen-not-found');
      slot.replaceChildren();
      if (tmpl) slot.appendChild(tmpl.content.cloneNode(true));
    },
  };
}

// ---------------------------------------------------------------------------
// Screen factories — STUBS for phase 1
// ---------------------------------------------------------------------------
//
// Each screen factory is a tiny Alpine component. Phase 1 ships empty
// shells; later phases replace them.

// ---------------------------------------------------------------------------
// Home screen — projects list + NEW PROJECT modal
// ---------------------------------------------------------------------------

function homeScreen() {
  return {
    loading: true,
    error: '',
    projects: [],
    selectedIndex: 0,

    // Modal state
    newModalOpen: false,
    submitting: false,
    formError: '',
    keysStatus: { anthropic: false, google_ai: false },
    form: {
      company: '',
      anthropic: '',
      google: '',
    },

    async init() {
      await this.load();
      this.registerKeys();
      this.loadGlobalKeys();  // non-blocking
    },

    // -----------------------------------------------------------------
    // Data
    // -----------------------------------------------------------------

    async load() {
      this.loading = true;
      this.error = '';
      try {
        const r = await fetch('/api/recents');
        if (!r.ok) throw new Error('Failed to load projects: ' + r.status);
        const data = await r.json();
        this.projects = data.projects || [];
        this.selectedIndex = Math.min(this.selectedIndex, Math.max(0, this.projects.length - 1));
      } catch (e) {
        this.error = e.message || String(e);
      } finally {
        this.loading = false;
      }
    },

    async loadGlobalKeys() {
      try {
        const r = await fetch('/api/api-keys/global');
        if (!r.ok) return;
        this.keysStatus = await r.json();
      } catch (_err) { /* non-fatal */ }
    },

    // -----------------------------------------------------------------
    // Row formatters — keep presentation in the factory, not the template
    // -----------------------------------------------------------------

    formatStatus(s) {
      if (!s) return 'NEW';
      return s.toUpperCase();
    },
    formatDate(iso) {
      if (!iso) return '—';
      const d = new Date(iso);
      if (isNaN(d)) return '—';
      const mm = String(d.getMonth() + 1).padStart(2, '0');
      const dd = String(d.getDate()).padStart(2, '0');
      const yy = String(d.getFullYear()).slice(-2);
      return `${mm}/${dd}/${yy}`;
    },
    formatCompCount(p) {
      // comp count isn't in /api/recents; placeholder for phase 6+.
      return (p.competitor_count != null ? p.competitor_count : '—') + " Comp's";
    },
    formatPath(path) {
      if (!path) return '';
      const home = this.homeDir();
      return home && path.startsWith(home) ? '~' + path.slice(home.length) : path;
    },
    homeDir() {
      // Best-effort: backend currently doesn't expose this; try to
      // infer from paths we've already loaded. Safe fallback returns ''.
      if (typeof window !== 'undefined' && window._reconHome) return window._reconHome;
      return '';
    },

    // -----------------------------------------------------------------
    // Selection + navigation
    // -----------------------------------------------------------------

    moveSelection(delta) {
      if (!this.projects.length) return;
      const next = (this.selectedIndex + delta + this.projects.length) % this.projects.length;
      this.selectedIndex = next;
    },

    openSelected() {
      const p = this.projects[this.selectedIndex];
      if (!p) return;
      this.$store.router.navigate('#/p/' + encodeURIComponent(p.path) + '/plan');
    },

    deleteSelected() {
      // Recents list is informational; there's no backend "delete
      // project" yet. Remove from the local list so the UX responds,
      // and rely on the backend to not re-surface stale paths. This
      // matches v3 behavior.
      const p = this.projects[this.selectedIndex];
      if (!p) return;
      if (!confirm(`Remove "${p.name}" from the recents list?`)) return;
      this.projects = this.projects.filter((x) => x.path !== p.path);
      this.selectedIndex = Math.min(this.selectedIndex, Math.max(0, this.projects.length - 1));
    },

    // -----------------------------------------------------------------
    // NEW PROJECT modal
    // -----------------------------------------------------------------

    openNew() {
      this.form = { company: '', anthropic: '', google: '' };
      this.formError = '';
      this.newModalOpen = true;
      // Focus the input once Alpine has rendered the modal.
      this.$nextTick(() => this.$refs.companyInput?.focus());
    },

    closeNew() {
      this.newModalOpen = false;
    },

    async submitNew() {
      const company = this.form.company.trim();
      if (!company) { this.formError = 'Company name required'; return; }
      this.submitting = true;
      this.formError = '';
      try {
        const r = await fetch('/api/workspaces', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            description: `Competitive research for ${company}`,
            company_name: company,
          }),
        });
        if (!r.ok) {
          const body = await r.json().catch(() => ({}));
          throw new Error(body.detail || `Create failed (${r.status})`);
        }
        const workspace = await r.json();

        // Save API keys if provided. Non-blocking — surface errors but
        // still navigate on success since the workspace is created.
        const keyWrites = [];
        if (this.form.anthropic) {
          keyWrites.push(this._saveKey(workspace.path, 'anthropic', this.form.anthropic));
        }
        if (this.form.google) {
          keyWrites.push(this._saveKey(workspace.path, 'google_ai', this.form.google));
        }
        if (keyWrites.length) await Promise.all(keyWrites);

        this.newModalOpen = false;
        this.$store.router.navigate('#/p/' + encodeURIComponent(workspace.path) + '/plan');
      } catch (e) {
        this.formError = e.message || String(e);
      } finally {
        this.submitting = false;
      }
    },

    async _saveKey(path, name, value) {
      const r = await fetch('/api/api-keys', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path, name, value }),
      });
      if (!r.ok) throw new Error(`Saving ${name} key failed (${r.status})`);
    },

    // -----------------------------------------------------------------
    // Hotkey registration
    // -----------------------------------------------------------------

    registerKeys() {
      // Screen-scoped bindings. The shell leaves the [1]-[5] project-
      // tab bindings in place but they noop on home (no project). We
      // push a "home" scope above them so j/k/enter/n/del/escape are
      // handled before the shell sees them.
      const bindings = [
        { key: 'arrowup',   label: 'UP',       run: () => this.moveSelection(-1) },
        { key: 'arrowdown', label: 'DOWN',     run: () => this.moveSelection(+1) },
        { key: 'k',         run: () => this.moveSelection(-1) },
        { key: 'j',         run: () => this.moveSelection(+1) },
        // enter + escape are allowed in editable targets so they work
        // inside the new-project modal inputs. The handlers branch on
        // newModalOpen so list-level behavior only fires when no modal.
        { key: 'enter',     label: 'OPEN',     allowInEditable: true,
          run: () => this.newModalOpen ? this.submitNew() : this.openSelected() },
        { key: 'escape',    allowInEditable: true,
          run: () => { if (this.newModalOpen) this.closeNew(); } },
        { key: 'n',         label: 'NEW',      run: () => this.openNew() },
        { key: 'delete',    label: 'DEL',      run: () => this.deleteSelected() },
        { key: 'backspace', run: () => this.deleteSelected() },  // mac delete
      ];
      this.$store.hotkeys.register('screen:home', bindings);
    },
  };
}

// ---------------------------------------------------------------------------
// PLAN tab  —  brief + model selector + worker count
// ---------------------------------------------------------------------------

function planScreen() {
  return {
    loading: true,
    error: '',

    // Workspace info
    companyName: '',
    brief: '',
    competitorCount: 0,

    // Model selection
    models: [],
    model: '',
    focusIdx: 0,

    // Worker count
    workers: 5,

    get path() { return this.$store.router.params.path; },
    get encodedPath() { return encodeURIComponent(this.path); },
    get displayPath() {
      const p = this.path;
      if (!p) return '';
      // Shorten home prefix where possible; the full path is in the tooltip.
      return p;
    },

    async init() {
      await Promise.all([this.loadWorkspace(), this.loadConfirm()]);
      this.registerKeys();
    },

    async loadWorkspace() {
      try {
        const r = await fetch('/api/workspace?path=' + this.encodedPath);
        if (!r.ok) return;
        const ws = await r.json();
        this.companyName = ws.company_name || '';
        // Seed the brief from domain on first load. No persistence back
        // to the workspace yet — brief changes live in local state
        // until /api/workspaces gains a PATCH route.
        if (!this.brief) this.brief = ws.domain || '';
      } catch (_err) { /* non-fatal */ }
    },

    async loadConfirm() {
      this.loading = true;
      this.error = '';
      try {
        const r = await fetch('/api/confirm?path=' + this.encodedPath);
        if (!r.ok) {
          const body = await r.json().catch(() => ({}));
          throw new Error(body.detail || `Plan data unavailable (${r.status})`);
        }
        const data = await r.json();
        this.competitorCount = data.competitor_count || 0;
        this.models = data.model_options || [];
        this.workers = data.default_workers || 5;

        // Prefer the backend-recommended model; fall back to default,
        // then the first option.
        const rec = this.models.find((m) => m.recommended);
        this.model = rec?.id || data.default_model || this.models[0]?.id || '';
        this.focusIdx = Math.max(0, this.models.findIndex((m) => m.id === this.model));
      } catch (e) {
        this.error = e.message || String(e);
      } finally {
        this.loading = false;
      }
    },

    // -----------------------------------------------------------------
    // Formatters
    // -----------------------------------------------------------------

    formatCost(v) {
      if (v == null || isNaN(v)) return '—';
      return '$' + Number(v).toFixed(2);
    },

    // -----------------------------------------------------------------
    // Actions
    // -----------------------------------------------------------------

    selectFocused() {
      const m = this.models[this.focusIdx];
      if (m) this.model = m.id;
    },

    moveFocus(delta) {
      if (!this.models.length) return;
      const n = this.models.length;
      this.focusIdx = (this.focusIdx + delta + n) % n;
    },

    incWorkers() { if (this.workers < 16) this.workers += 1; },
    decWorkers() { if (this.workers > 1)  this.workers -= 1; },

    back() { this.$store.router.goHome(); },
    next() { this.$store.router.goTab('schema'); },

    async revealInFinder() {
      // Phase 8 will add a /api/reveal backend route; for now, copy
      // the path to clipboard so the user can paste into Finder.
      try {
        await navigator.clipboard.writeText(this.path);
      } catch (_err) { /* noop */ }
    },

    // -----------------------------------------------------------------
    // Hotkeys
    // -----------------------------------------------------------------

    registerKeys() {
      const bindings = [
        { key: 'arrowup',   run: () => this.moveFocus(-1) },
        { key: 'arrowdown', run: () => this.moveFocus(+1) },
        { key: 'k',         run: () => this.moveFocus(-1) },
        { key: 'j',         run: () => this.moveFocus(+1) },
        { key: 'enter',     label: 'SELECT', run: () => this.selectFocused() },
        { key: 'n',         label: 'NEXT',   run: () => this.next() },
        { key: 'escape',    label: 'BACK',   run: () => this.back() },
        { key: 'l',         run: () => this.revealInFinder() },
        { key: '+',         run: () => this.incWorkers() },
        { key: '-',         run: () => this.decWorkers() },
      ];
      this.$store.hotkeys.register('screen:plan', bindings);
    },
  };
}

// ---------------------------------------------------------------------------
// SCHEMA tab  —  dossier sections with toggle-to-select
// ---------------------------------------------------------------------------

function schemaScreen() {
  return {
    loading: true,
    error: '',
    sections: [],
    focusIdx: 0,

    // Debounced save state
    saving: false,
    justSaved: false,
    _saveTimer: 0,

    get path() { return this.$store.router.params.path; },
    get encodedPath() { return encodeURIComponent(this.path); },
    get selectedCount() { return this.sections.filter((s) => s.selected).length; },

    async init() {
      await this.load();
      this.registerKeys();
    },

    async load() {
      this.loading = true;
      this.error = '';
      try {
        const r = await fetch('/api/template?path=' + this.encodedPath);
        if (!r.ok) {
          const body = await r.json().catch(() => ({}));
          throw new Error(body.detail || `Schema unavailable (${r.status})`);
        }
        const data = await r.json();
        this.sections = data.sections || [];
      } catch (e) {
        this.error = e.message || String(e);
      } finally {
        this.loading = false;
      }
    },

    // Optimistic toggle: flip local state, debounce the PUT. Debounce
    // coalesces rapid toggles into a single write so a user holding
    // space to cycle through options doesn't hammer the backend.
    toggle(i) {
      const s = this.sections[i];
      if (!s) return;
      s.selected = !s.selected;
      this.scheduleSave();
    },

    scheduleSave() {
      clearTimeout(this._saveTimer);
      this.saving = true;
      this.justSaved = false;
      this._saveTimer = setTimeout(() => this.save(), 300);
    },

    async save() {
      this.saving = true;
      try {
        const section_keys = this.sections.filter((s) => s.selected).map((s) => s.key);
        const r = await fetch('/api/template', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ path: this.path, section_keys }),
        });
        if (!r.ok) throw new Error(`Save failed (${r.status})`);
        this.justSaved = true;
        setTimeout(() => { this.justSaved = false; }, 1500);
      } catch (e) {
        this.error = e.message || String(e);
      } finally {
        this.saving = false;
      }
    },

    moveFocus(delta) {
      if (!this.sections.length) return;
      const n = this.sections.length;
      this.focusIdx = (this.focusIdx + delta + n) % n;
    },

    openAdd() {
      // Add-section support lands with a backend endpoint later. For
      // now the button is a hint only.
      alert('Add section coming soon. For now, edit recon.yaml directly.');
    },

    back() { this.$store.router.goTab('plan'); },
    next() {
      if (this.selectedCount === 0) return;
      this.$store.router.goTab('comps');
    },

    registerKeys() {
      const bindings = [
        { key: 'arrowup',   run: () => this.moveFocus(-1) },
        { key: 'arrowdown', run: () => this.moveFocus(+1) },
        { key: 'k',         run: () => this.moveFocus(-1) },
        { key: 'j',         run: () => this.moveFocus(+1) },
        { key: 'space',     label: 'TOGGLE', run: () => this.toggle(this.focusIdx) },
        { key: 'enter',     run: () => this.toggle(this.focusIdx) },
        { key: 'n',         label: 'NEXT', run: () => this.next() },
        { key: 'escape',    label: 'BACK', run: () => this.back() },
      ];
      this.$store.hotkeys.register('screen:schema', bindings);
    },
  };
}

// ---------------------------------------------------------------------------
// COMP'S tab  —  discovery + selection + run kickoff
// ---------------------------------------------------------------------------

function compsScreen() {
  return {
    error: '',

    // Discovery
    discovering: false,
    discoveryMessage: '',

    // Competitor list
    competitors: [],
    deselected: new Set(),   // slugs the user has opted out of
    focusIdx: 0,

    // Cost estimate — snapshotted from /api/confirm
    costPerCompetitor: 0,
    sectionCount: 0,

    // Run kickoff
    starting: false,

    // Search-terms modal
    termsModalOpen: false,
    terms: { focus: '', seeds: '' },

    get path() { return this.$store.router.params.path; },
    get encodedPath() { return encodeURIComponent(this.path); },
    get selectedCount() { return this.competitors.filter((c) => this.isSelected(c)).length; },
    get estimatedCost() {
      return (this.selectedCount * this.costPerCompetitor).toFixed(2) * 1;
    },

    async init() {
      this.registerKeys();
      await this.loadAll();
      if (this.competitors.length === 0) {
        await this.search({ silent: true });
      }
    },

    // -----------------------------------------------------------------
    // Data
    // -----------------------------------------------------------------

    async loadAll() {
      this.error = '';
      try {
        const [compResp, confResp] = await Promise.all([
          fetch('/api/competitors?path=' + this.encodedPath),
          fetch('/api/confirm?path=' + this.encodedPath),
        ]);
        if (compResp.ok) {
          const data = await compResp.json();
          this.competitors = data.competitors || [];
        }
        if (confResp.ok) {
          const conf = await confResp.json();
          this.sectionCount = conf.section_keys?.length || 0;
          // Per-competitor cost = estimated_total / competitor_count,
          // with a fallback when the workspace has 0 comps yet.
          const total = conf.estimated_total || 0;
          const cc = conf.competitor_count || 1;
          this.costPerCompetitor = total / Math.max(1, cc);
          // If the workspace has no comps yet, the server returns 0
          // for estimated_total — seed a rough minimum so the number
          // doesn't stay at 0 once the user has selected some.
          if (!this.costPerCompetitor && this.sectionCount) {
            this.costPerCompetitor = 0.35 * this.sectionCount;  // ~$0.35/section heuristic
          }
        }
      } catch (e) {
        this.error = e.message || String(e);
      }
    },

    // -----------------------------------------------------------------
    // Discovery
    // -----------------------------------------------------------------

    async search({ silent = false } = {}) {
      if (this.discovering) return;
      this.discovering = true;
      this.discoveryMessage = silent ? 'Discovering competitors…' : 'Searching for more competitors…';
      this.error = '';
      this.termsModalOpen = false;
      try {
        const body = { path: this.path };
        const seeds = this.terms.seeds
          .split(',')
          .map((s) => s.trim())
          .filter(Boolean);
        if (seeds.length) body.seeds = seeds;
        const r = await fetch('/api/discover', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        });
        if (!r.ok) {
          const b = await r.json().catch(() => ({}));
          throw new Error(b.detail || `Discovery failed (${r.status})`);
        }
        const data = await r.json();
        const candidates = data.candidates || [];

        // Persist each candidate as a competitor profile if not already
        // present. Auto-select new ones (they are enabled by default).
        const existing = new Set(this.competitors.map((c) => c.slug));
        for (const cand of candidates) {
          const slug = this._slug(cand.name);
          if (existing.has(slug)) continue;
          try {
            const cr = await fetch('/api/competitors', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                path: this.path,
                name: cand.name,
                url: cand.url || null,
                blurb: cand.blurb || null,
              }),
            });
            if (cr.ok) {
              const created = await cr.json();
              this.competitors.push(created);
            }
          } catch (_err) { /* skip one bad candidate, keep going */ }
        }

        // Refresh cost estimate now that the workspace has more comps.
        await this.loadAll();
      } catch (e) {
        this.error = e.message || String(e);
      } finally {
        this.discovering = false;
      }
    },

    _slug(name) {
      return name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
    },

    // -----------------------------------------------------------------
    // Selection
    // -----------------------------------------------------------------

    isSelected(c) { return !this.deselected.has(c.slug); },

    toggleSelection(c) {
      // Set-of-slugs mutation in Alpine requires reassignment for reactivity.
      const next = new Set(this.deselected);
      if (next.has(c.slug)) next.delete(c.slug);
      else next.add(c.slug);
      this.deselected = next;
    },

    moveFocus(delta) {
      if (!this.competitors.length) return;
      const n = this.competitors.length;
      this.focusIdx = (this.focusIdx + delta + n) % n;
    },

    // -----------------------------------------------------------------
    // Formatters
    // -----------------------------------------------------------------

    formatCost(v) {
      if (v == null || isNaN(v)) return '$—';
      return '$' + Number(v).toFixed(2);
    },
    shortUrl(url) {
      if (!url) return '';
      try {
        const u = new URL(url);
        return u.hostname.replace(/^www\./, '');
      } catch (_err) { return url.slice(0, 40); }
    },

    // -----------------------------------------------------------------
    // Terms modal
    // -----------------------------------------------------------------

    openTerms() {
      this.termsModalOpen = true;
      this.$nextTick(() => this.$refs.termsInput?.focus());
    },
    closeTerms() { this.termsModalOpen = false; },
    improveWithAi() { /* deferred — no backend endpoint yet */ },

    // -----------------------------------------------------------------
    // Run kickoff
    // -----------------------------------------------------------------

    async run() {
      if (this.starting) return;
      if (this.selectedCount === 0) return;
      this.starting = true;
      this.error = '';
      try {
        // Reconcile selection: delete deselected competitors so the
        // pipeline only iterates the chosen set. Do this here (rather
        // than on the agents tab) so the work doesn't happen under a
        // live progress view.
        const slugsToDrop = [...this.deselected];
        for (const slug of slugsToDrop) {
          try {
            await fetch('/api/competitors/' + encodeURIComponent(slug) + '?path=' + this.encodedPath, {
              method: 'DELETE',
            });
          } catch (_err) { /* keep going */ }
        }
        // Hand off to the agents tab with autostart=1. The agents tab
        // opens SSE first, THEN POSTs /api/runs — that ordering avoids
        // a race where fast (fake-LLM) runs finish before SSE attaches.
        this.$store.router.navigate('#/p/' + encodeURIComponent(this.path) + '/agents?autostart=1');
      } catch (e) {
        this.error = e.message || String(e);
      } finally {
        this.starting = false;
      }
    },

    // -----------------------------------------------------------------
    // Hotkeys
    // -----------------------------------------------------------------

    back() { this.$store.router.goTab('schema'); },

    registerKeys() {
      const bindings = [
        { key: 'arrowup',   run: () => this.moveFocus(-1) },
        { key: 'arrowdown', run: () => this.moveFocus(+1) },
        { key: 'k',         run: () => this.moveFocus(-1) },
        { key: 'j',         run: () => this.moveFocus(+1) },
        { key: 'space',     label: 'TOGGLE',
          run: () => { const c = this.competitors[this.focusIdx]; if (c) this.toggleSelection(c); } },
        { key: 'enter',     allowInEditable: true,
          run: () => {
            if (this.termsModalOpen) this.search();
            else { const c = this.competitors[this.focusIdx]; if (c) this.toggleSelection(c); }
          } },
        { key: 's',         label: 'SEARCH', run: () => this.search() },
        { key: 't',         label: 'TERMS',  run: () => this.openTerms() },
        { key: 'r',         label: 'RUN',    run: () => this.run() },
        { key: 'escape',    allowInEditable: true,
          run: () => { if (this.termsModalOpen) this.closeTerms(); else this.back(); } },
      ];
      this.$store.hotkeys.register('screen:comps', bindings);
    },
  };
}

// ---------------------------------------------------------------------------
// AGENTS tab  —  live run monitor via SSE
// ---------------------------------------------------------------------------
//
// Two panels:
//   top    N "worker" cards (persona + current stage/task + mini bar)
//   bottom per-competitor rows with aggregate progress
//
// The backend event stream doesn't report which worker slot owns a
// given task — it just emits Section{Started|Researched|Failed} with
// a competitor/section pair. We assign workers client-side: first
// free slot picks up a Started event, frees on Researched/Failed.

const AGENT_PERSONA_POOL = [
  { name: 'SCOUT',    icon: 'rabbit' },
  { name: 'RANGER',   icon: 'squirrel' },
  { name: 'SCRIBE',   icon: 'bird' },
  { name: 'HERALD',   icon: 'cat' },
  { name: 'SENTINEL', icon: 'dog' },
  { name: 'SEEKER',   icon: 'fish' },
  { name: 'FABLE',    icon: 'turtle' },
  { name: 'PILOT',    icon: 'bug' },
];

// Stages we track explicitly (others pass through). Order matters —
// it drives the overall progress calculation.
const PIPELINE_STAGES = [
  'research', 'verify', 'enrich', 'index', 'synthesize', 'deliver',
];

function blockBar(pct, width) {
  const clamped = Math.max(0, Math.min(100, pct || 0));
  const filled = Math.round((clamped / 100) * width);
  const half = (clamped / 100) * width - filled >= 0.5 ? 1 : 0;
  return '▓'.repeat(filled) + (half ? '▒' : '') + '░'.repeat(Math.max(0, width - filled - half));
}

function agentsScreen() {
  return {
    error: '',

    // Run state
    runId: '',
    status: '',        // planned | running | complete | failed | cancelled
    currentStage: 'RESEARCH',
    cost: 0,

    // Task counts — aggregate across all stages
    totalTasks: 0,
    doneTasks: 0,
    failedTasks: 0,

    // Workers + competitors
    agents: [],               // [{ id, name, icon, stage, task, taskPct, state }]
    competitorsByName: {},    // { [name]: { name, total, done, failed, currentSection, pct, status } }

    // UI
    completionModalOpen: false,
    menuOpen: null,
    runPaused: false,

    // SSE
    _es: null,

    get path() { return this.$store.router.params.path; },
    get encodedPath() { return encodeURIComponent(this.path); },
    get terminal() { return ['complete', 'failed', 'cancelled'].includes(this.status); },
    get progressPct() {
      if (!this.totalTasks) return 0;
      return Math.round((this.doneTasks / this.totalTasks) * 100);
    },
    get competitorList() {
      return Object.values(this.competitorsByName).sort((a, b) => a.name.localeCompare(b.name));
    },

    async init() {
      this.registerKeys();
      this.$store.screen.onTeardown(() => {
        this._es?.close();
        clearInterval(this._pollTimer);
      });

      this._initAgents();
      // Always open the global event stream first. Filtering to a
      // specific run happens client-side once we know the run_id.
      this._openStream();

      const autostart = this.$store.router.params.query?.autostart === '1';
      if (autostart) {
        await this._autostart();
      } else {
        this.runId = this._extractRunIdFromHash() || await this._findActiveRun();
      }

      if (this.runId) {
        this._loadSnapshot();
        this._loadExpectedTotal();
        this._pollTimer = setInterval(() => {
          if (this.terminal) { clearInterval(this._pollTimer); return; }
          this._loadSnapshot();
        }, 1500);
      }
    },

    async _autostart() {
      this.currentStage = 'STARTING';
      try {
        const r = await fetch('/api/runs', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ path: this.path, use_fake_llm: true }),
        });
        if (!r.ok) {
          const b = await r.json().catch(() => ({}));
          throw new Error(b.detail || `Run start failed (${r.status})`);
        }
        const data = await r.json();
        this.runId = data.run_id;
        // Rewrite the URL so a reload lands on the same run without
        // re-triggering autostart.
        const p = encodeURIComponent(this.path);
        history.replaceState(null, '', '#/p/' + p + '/agents?run=' + encodeURIComponent(this.runId));
      } catch (e) {
        this.error = e.message || String(e);
      }
    },

    _extractRunIdFromHash() {
      return this.$store.router.params.query?.run || '';
    },

    async _findActiveRun() {
      try {
        const r = await fetch('/api/runs?path=' + this.encodedPath);
        if (!r.ok) return '';
        const data = await r.json();
        const runs = data.runs || [];
        const live = runs.find((x) => ['planned', 'running', 'paused'].includes(x.status));
        return live?.run_id || runs[0]?.run_id || '';
      } catch (_err) { return ''; }
    },

    async _loadSnapshot() {
      try {
        const r = await fetch('/api/runs/' + encodeURIComponent(this.runId) + '?path=' + this.encodedPath);
        if (!r.ok) throw new Error(`Run snapshot failed (${r.status})`);
        const d = await r.json();
        this.status = d.status;
        // Prefer authoritative counts from the run state store when
        // they're populated. Some pipelines skip DB writes (fake-LLM)
        // and return 0; in that case keep whatever SSE counted.
        if (d.task_count) this.totalTasks = d.task_count;
        if (d.completed_tasks > this.doneTasks) this.doneTasks = d.completed_tasks;
        if (d.failed_tasks) this.failedTasks = d.failed_tasks;
        this.cost = d.total_cost_usd || 0;
        if (d.status === 'complete' || d.status === 'completed') {
          this.status = 'complete';
          if (!this.completionModalOpen && this._completionSeen !== true) {
            this._completionSeen = true;
            this.completionModalOpen = true;
          }
        }
      } catch (e) {
        this.error = e.message || String(e);
      }
    },

    // Ask /api/confirm for the expected task total — sections × comps.
    // Gives us a denominator for the overall progress bar even when
    // task_count on the run snapshot is 0 (fake-LLM mode).
    async _loadExpectedTotal() {
      try {
        const r = await fetch('/api/confirm?path=' + this.encodedPath);
        if (!r.ok) return;
        const d = await r.json();
        const est = (d.competitor_count || 0) * (d.section_keys?.length || 0);
        if (est && !this.totalTasks) this.totalTasks = est;
      } catch (_err) { /* non-fatal */ }
    },

    _initAgents() {
      // Size the grid to the default worker count from /api/confirm;
      // fall back to 5 if we can't resolve it.
      const n = Math.min(AGENT_PERSONA_POOL.length, 5);
      this.agents = Array.from({ length: n }, (_, i) => ({
        id: i,
        name: AGENT_PERSONA_POOL[i % AGENT_PERSONA_POOL.length].name,
        icon: AGENT_PERSONA_POOL[i % AGENT_PERSONA_POOL.length].icon,
        stage: '',
        task: '',
        taskPct: 0,
        state: 'idle',
      }));
    },

    _openStream() {
      if (this._es) this._es.close();
      // Use the global event stream. We don't know the run_id until
      // /api/runs responds (in autostart mode), so filtering has to
      // happen client-side anyway. The helper below drops events that
      // carry a run_id for a *different* run.
      const es = new EventSource('/api/events');
      this._es = es;

      const sub = (name, fn) => es.addEventListener(name, (ev) => {
        let d = {};
        try { d = JSON.parse(ev.data); } catch (_err) { /* keep default */ }
        if (d.run_id && this.runId && d.run_id !== this.runId) return;
        fn(d);
      });

      sub('RunStarted',         (d) => {
        if (!this.runId && d.run_id) this.runId = d.run_id;
        this.status = 'running';
      });
      sub('RunCompleted',       (d) => {
        this.status = 'complete';
        this.cost = d.total_cost_usd ?? this.cost;
        this.completionModalOpen = true;
      });
      sub('RunFailed',          (d) => { this.status = 'failed'; this.error = d.error || 'Run failed'; });
      sub('RunCancelled',       () => { this.status = 'cancelled'; });
      sub('RunPaused',          () => { this.runPaused = true; });
      sub('RunResumed',         () => { this.runPaused = false; });
      sub('RunStageStarted',    (d) => { this.currentStage = (d.stage || '').toUpperCase(); });
      sub('RunStageCompleted',  () => { /* advance implicit via next start */ });

      sub('CostRecorded',       (d) => { this.cost += d.cost_usd || 0; });

      sub('SectionStarted',     (d) => {
        this._trackCompetitor(d, 'start');
        this._assignWorker(d, this.currentStage.toLowerCase() || 'research');
      });
      sub('SectionResearched',  (d) => {
        this._trackCompetitor(d, 'done');
        this._releaseWorker(d);
        this.doneTasks += 1;
      });
      sub('SectionFailed',      (d) => {
        this._trackCompetitor(d, 'failed');
        this._releaseWorker(d);
        this.failedTasks += 1;
      });

      sub('EnrichmentStarted',  (d) => this._assignWorker(d, 'enrich'));
      sub('EnrichmentCompleted',(d) => this._releaseWorker(d));
      sub('SynthesisStarted',   () => { this.currentStage = 'SYNTHESIZE'; });
      sub('DeliveryStarted',    () => { this.currentStage = 'DELIVER'; });

      es.addEventListener('error', () => {
        if (!this.terminal) this.currentStage = 'RECONNECTING';
      });
    },

    _trackCompetitor(d, kind) {
      const name = d.competitor_name;
      if (!name) return;
      let c = this.competitorsByName[name];
      if (!c) {
        c = { name, total: 0, done: 0, failed: 0, currentSection: '', pct: 0, status: 'pending' };
        this.competitorsByName = { ...this.competitorsByName, [name]: c };
      }
      if (kind === 'start') {
        c.currentSection = (d.section_key || '').toUpperCase();
        c.status = 'running';
        // We don't know the total up front — increment optimistically.
        if (c.done + c.failed + 1 > c.total) c.total = c.done + c.failed + 1;
      } else if (kind === 'done') {
        c.done += 1;
        if (c.done + c.failed >= c.total) c.status = 'done';
      } else if (kind === 'failed') {
        c.failed += 1;
        c.status = 'failed';
      }
      c.pct = c.total ? Math.round((c.done / c.total) * 100) : 0;
      // Reassign to trigger Alpine reactivity.
      this.competitorsByName = { ...this.competitorsByName };
    },

    _assignWorker(d, stage) {
      const slot = this.agents.find((a) => !a.task);
      if (!slot) return;
      slot.stage = (stage || '').toUpperCase();
      slot.task = `${d.competitor_name || '—'} · ${(d.section_key || d.pass_name || '—').toUpperCase()}`;
      slot.taskPct = 25;
      slot.state = 'busy';
      // Reassign array for Alpine reactivity.
      this.agents = [...this.agents];
    },

    _releaseWorker(d) {
      const needle = d.competitor_name;
      const slot = this.agents.find((a) => a.task && a.task.startsWith((needle || '') + ' · '));
      if (!slot) return;
      slot.stage = '';
      slot.task = '';
      slot.taskPct = 0;
      slot.state = 'idle';
      this.agents = [...this.agents];
    },

    // -----------------------------------------------------------------
    // Formatters / helpers exposed to template
    // -----------------------------------------------------------------

    formatCost(v) { return '$' + Number(v || 0).toFixed(2); },
    progressBar(pct, width) { return blockBar(pct, width); },

    // -----------------------------------------------------------------
    // Actions
    // -----------------------------------------------------------------

    openAgentMenu(i) { this.menuOpen = i; },
    pauseRun()     { alert('Pause endpoint not wired — coming in a later phase.'); this.menuOpen = null; },
    restartTask()  { alert('Restart endpoint not wired — coming in a later phase.'); this.menuOpen = null; },
    debugTask()    { alert('Debug overlay not wired — coming in a later phase.');    this.menuOpen = null; },

    closeCompletion() { this.completionModalOpen = false; },
    goOutput() {
      this.completionModalOpen = false;
      this.$store.router.goTab('output');
    },

    back() { this.$store.router.goTab('comps'); },

    registerKeys() {
      const bindings = [
        { key: 'escape', allowInEditable: true,
          run: () => {
            if (this.menuOpen != null) { this.menuOpen = null; return; }
            if (this.completionModalOpen) { this.closeCompletion(); return; }
            this.back();
          } },
        { key: 'enter', allowInEditable: true,
          run: () => {
            if (this.completionModalOpen) this.goOutput();
          } },
      ];
      this.$store.hotkeys.register('screen:agents', bindings);
    },

    destroyStream() {
      if (this._es) this._es.close();
      this._es = null;
    },
  };
}

// ---------------------------------------------------------------------------
// OUTPUT tab  —  file tree + markdown preview + open-in-Finder
// ---------------------------------------------------------------------------

function outputScreen() {
  return {
    loading: true,
    error: '',
    tree: [],          // flat structure for rendering
    treeLines: [],     // [{ prefix, name, ref }] — ref points to a file or null for dirs
    treeHeader: '',
    fileCount: 0,
    selected: null,    // one of the file entries
    execPreview: '',

    get path() { return this.$store.router.params.path; },
    get encodedPath() { return encodeURIComponent(this.path); },

    async init() {
      this.registerKeys();
      await this.load();
    },

    async load() {
      this.loading = true;
      this.error = '';
      try {
        const r = await fetch('/api/results?path=' + this.encodedPath);
        if (!r.ok) {
          const b = await r.json().catch(() => ({}));
          throw new Error(b.detail || `Outputs unavailable (${r.status})`);
        }
        const data = await r.json();
        this.execPreview = data.executive_summary_preview || '';
        this._buildTree(data);
        if (this.tree.length) {
          // Default selection: exec summary (or first file).
          const exec = this.tree.find((n) => n.kind === 'exec_summary');
          this.selected = exec || this.tree[0];
        }
      } catch (e) {
        this.error = e.message || String(e);
      } finally {
        this.loading = false;
      }
    },

    _buildTree(data) {
      const files = [];
      if (data.executive_summary_path) {
        files.push({
          name: this._basename(data.executive_summary_path),
          path: data.executive_summary_path,
          kind: 'exec_summary',
          group: 'output',
        });
      }
      for (const f of data.output_files || []) {
        if (f.kind === 'exec_summary') continue; // listed above
        files.push({ name: f.name, path: f.path, kind: f.kind, group: 'output' });
      }
      for (const t of data.theme_files || []) {
        files.push({
          name: this._basename(t.path),
          path: t.path,
          kind: 'theme',
          title: t.title,
          group: 'themes',
        });
        if (t.distilled_path) {
          files.push({
            name: this._basename(t.distilled_path),
            path: t.distilled_path,
            kind: 'distilled',
            group: 'themes/distilled',
          });
        }
      }
      this.tree = files;
      this.fileCount = files.length;
      this._buildTreeLines();
    },

    _buildTreeLines() {
      // Group by `group` path so distilled lands under themes/distilled/.
      const groups = new Map();
      for (const f of this.tree) {
        if (!groups.has(f.group)) groups.set(f.group, []);
        groups.get(f.group).push(f);
      }
      const sorted = Array.from(groups.keys()).sort();
      const lines = [];
      const wsName = this._basename(this.path);
      this.treeHeader = wsName + '/';
      const groupKeys = sorted;
      for (let gi = 0; gi < groupKeys.length; gi++) {
        const g = groupKeys[gi];
        const isLastGroup = gi === groupKeys.length - 1;
        // Dir node
        lines.push({
          prefix: (isLastGroup ? '└── ' : '├── '),
          name: g + '/',
          ref: null,
        });
        const items = groups.get(g);
        for (let i = 0; i < items.length; i++) {
          const isLast = i === items.length - 1;
          const pipe = isLastGroup ? '    ' : '│   ';
          lines.push({
            prefix: pipe + (isLast ? '└── ' : '├── '),
            name: items[i].name,
            ref: items[i],
          });
        }
      }
      this.treeLines = lines;
    },

    _basename(p) {
      if (!p) return '';
      const parts = p.split('/');
      return parts[parts.length - 1] || p;
    },

    select(file) { this.selected = file; },

    async reveal(file) {
      if (!file?.path) return;
      try {
        const r = await fetch('/api/reveal', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ path: this.path, target: file.path }),
        });
        if (!r.ok) {
          const b = await r.json().catch(() => ({}));
          throw new Error(b.detail || `Reveal failed (${r.status})`);
        }
      } catch (e) {
        this.error = e.message || String(e);
      }
    },

    async revealWorkspace() {
      try {
        const r = await fetch('/api/reveal', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ path: this.path, target: this.path }),
        });
        if (!r.ok) {
          // Fallback: copy path to clipboard.
          try { await navigator.clipboard.writeText(this.path); } catch (_err) { /* noop */ }
        }
      } catch (_e) { /* soft-fail */ }
    },

    back() { this.$store.router.goTab('agents'); },

    registerKeys() {
      const bindings = [
        { key: 'escape', label: 'BACK', run: () => this.back() },
        { key: 'l',      label: 'LOCAL DIR', run: () => this.revealWorkspace() },
        { key: 'arrowup',   run: () => this._moveSelection(-1) },
        { key: 'arrowdown', run: () => this._moveSelection(+1) },
        { key: 'k',         run: () => this._moveSelection(-1) },
        { key: 'j',         run: () => this._moveSelection(+1) },
        { key: 'enter',     run: () => { if (this.selected) this.reveal(this.selected); } },
      ];
      this.$store.hotkeys.register('screen:output', bindings);
    },

    _moveSelection(delta) {
      const files = this.tree;
      if (!files.length) return;
      const idx = Math.max(0, files.indexOf(this.selected));
      const next = (idx + delta + files.length) % files.length;
      this.selected = files[next];
    },
  };
}
