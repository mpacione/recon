// recon web UI — v4 shell
//
// Architecture:
//   - Hash-based router: #/  = home (RECON), #/p/<path>/<tab> = project
//   - Five project tabs: plan, schema, comp's, agents, output
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
  { key: 'plan',   label: 'PLAN', number: 1, icon: 'map' },
  { key: 'schema', label: 'SCHEMA',  number: 2, icon: 'square-stack' },
  { key: 'comps',  label: "COMP'S", number: 3, icon: 'shapes' },
  { key: 'agents', label: 'AGENTS',  number: 4, icon: 'bot' },
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

  // Settings overlay toggle — global, opens from [Z] on any screen.
  Alpine.store('settings', { open: false });

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
          run: () => { this.$store.settings.open = !this.$store.settings.open; },
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
      return (p.competitor_count != null ? p.competitor_count : '—') + ' companies';
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

    async deleteSelected() {
      const p = this.projects[this.selectedIndex];
      if (!p) return;
      if (!confirm(`Remove "${p.name}" from the recents list?`)) return;
      try {
        const r = await fetch('/api/recents?path=' + encodeURIComponent(p.path), { method: 'DELETE' });
        if (!r.ok && r.status !== 404) {
          const b = await r.json().catch(() => ({}));
          throw new Error(b.detail || `Delete failed (${r.status})`);
        }
      } catch (e) {
        // Soft-fail: still remove from the UI so the user isn't stuck.
        // Surface the error but don't block.
        this.error = e.message || String(e);
      }
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
// PLAN tab  —  brief + settings + cost estimate
// ---------------------------------------------------------------------------

function planScreen() {
  return {
    loading: true,
    error: '',

    // Workspace info
    companyName: '',
    brief: '',
    _briefOriginal: '',
    _briefSaveTimer: 0,
    briefSaving: false,
    briefSaved: false,
    workspaceTotalCost: 0,
    workspaceRunCount: 0,

    // Settings + estimate
    models: [],
    modelName: 'sonnet',
    workers: 5,
    verificationMode: 'standard',
    confirm: null,

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
        const initial = ws.domain || '';
        this.brief = initial;
        this._briefOriginal = initial;
        this.workspaceTotalCost = ws.total_cost || 0;
      } catch (_err) { /* non-fatal */ }
    },

    // Debounced save-on-type. Watch the textarea via x-model so every
    // keystroke calls onBriefInput; we coalesce into one PATCH per
    // ~600ms idle window. Don't fire if the text hasn't actually
    // changed from what we last saved.
    onBriefInput() {
      clearTimeout(this._briefSaveTimer);
      this.briefSaving = true;
      this.briefSaved = false;
      this._briefSaveTimer = setTimeout(() => this._saveBrief(), 600);
    },

    async _saveBrief() {
      const next = (this.brief || '').trim();
      if (next === this._briefOriginal.trim()) {
        this.briefSaving = false;
        return;
      }
      this.briefSaving = true;
      try {
        const r = await fetch('/api/workspace', {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ path: this.path, brief: next }),
        });
        if (!r.ok) throw new Error(`Save failed (${r.status})`);
        this._briefOriginal = next;
        this.briefSaved = true;
        setTimeout(() => { this.briefSaved = false; }, 1500);
      } catch (_err) {
        // Quiet error — reload the page will restore from disk.
      } finally {
        this.briefSaving = false;
      }
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
        this.confirm = data;
        this.models = data.model_options || [];
        this.modelName = data.default_model || this.models[0]?.name || this.models[0]?.id || 'sonnet';
        this.workers = data.default_workers || 5;
        this.verificationMode = data.default_verification_mode || 'standard';
        this.workspaceTotalCost = data.current_tracked_spend || this.workspaceTotalCost;
        this.workspaceRunCount = data.run_count || 0;
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

    currentModelOption() {
      return this.models.find((m) => modelNameFromOption(m) === this.modelName) || this.models[0] || null;
    },

    cycleModel(delta = 1) {
      if (!this.models.length) return;
      const names = this.models.map((m) => modelNameFromOption(m));
      const current = Math.max(0, names.indexOf(this.modelName));
      this.modelName = names[(current + delta + names.length) % names.length];
      this.persistSettings();
    },

    cycleVerification() {
      const current = Math.max(0, WEB_VERIFICATION_MODES.indexOf(this.verificationMode));
      this.verificationMode = WEB_VERIFICATION_MODES[(current + 1) % WEB_VERIFICATION_MODES.length];
      this.persistSettings();
    },

    incWorkers() {
      if (this.workers >= 16) return;
      this.workers += 1;
      this.persistSettings();
    },
    decWorkers() {
      if (this.workers <= 1) return;
      this.workers -= 1;
      this.persistSettings();
    },

    async persistSettings() {
      try {
        const r = await fetch('/api/plan-settings', {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            path: this.path,
            model_name: this.modelName,
            workers: this.workers,
            verification_mode: this.verificationMode,
          }),
        });
        if (!r.ok) {
          const body = await r.json().catch(() => ({}));
          throw new Error(body.detail || `Settings save failed (${r.status})`);
        }
        const data = await r.json();
        this.modelName = data.model_name || this.modelName;
        this.workers = data.workers || this.workers;
        this.verificationMode = data.verification_mode || this.verificationMode;
        await this.loadConfirm();
      } catch (e) {
        this.error = e.message || String(e);
      }
    },

    back() { this.$store.router.goHome(); },
    next() { this.$store.router.goTab('schema'); },

    async revealInFinder() {
      try {
        const r = await fetch('/api/reveal', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ path: this.path, target: this.path }),
        });
        if (!r.ok) {
          try { await navigator.clipboard.writeText(this.path); } catch (_err) { /* noop */ }
        }
      } catch (_err) {
        try { await navigator.clipboard.writeText(this.path); } catch (_copyErr) { /* noop */ }
      }
    },

    // -----------------------------------------------------------------
    // Hotkeys
    // -----------------------------------------------------------------

    registerKeys() {
      const bindings = [
        { key: 'm',         label: 'MODEL', run: () => this.cycleModel(1) },
        { key: 'v',         label: 'VERIFY', run: () => this.cycleVerification() },
        { key: '+',         label: 'MORE', run: () => this.incWorkers() },
        { key: '-',         label: 'LESS', run: () => this.decWorkers() },
        { key: 'n',         label: 'NEXT', run: () => this.next() },
        { key: 'escape',    label: 'BACK',   run: () => this.back() },
        { key: 'l',         label: 'OPEN FOLDER', run: () => this.revealInFinder() },
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
    editorOpen: false,
    editorMode: 'edit',
    editorTitle: '',
    editorDescription: '',

    // Debounced save state
    saving: false,
    justSaved: false,
    _saveTimer: 0,

    get path() { return this.$store.router.params.path; },
    get encodedPath() { return encodeURIComponent(this.path); },
    get selectedCount() { return this.sections.filter((s) => s.selected).length; },
    get selectedSection() { return this.sections[this.focusIdx] || null; },
    get selectedMeta() {
      const section = this.selectedSection;
      if (!section) return '';
      return section.selected ? 'enabled' : 'disabled';
    },

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
        this.focusIdx = Math.min(this.focusIdx, Math.max(0, this.sections.length - 1));
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
        const r = await fetch('/api/template', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ path: this.path, sections: this.sections }),
        });
        if (!r.ok) throw new Error(`Save failed (${r.status})`);
        const data = await r.json().catch(() => ({ sections: this.sections }));
        const selectedKey = this.selectedSection?.key || '';
        this.sections = data.sections || this.sections;
        const nextIdx = this.sections.findIndex((section) => section.key === selectedKey);
        this.focusIdx = nextIdx >= 0 ? nextIdx : Math.min(this.focusIdx, Math.max(0, this.sections.length - 1));
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

    selectAll() {
      this.sections = this.sections.map((section) => ({ ...section, selected: true }));
      this.scheduleSave();
    },

    deselectAll() {
      this.sections = this.sections.map((section) => ({ ...section, selected: false }));
      this.scheduleSave();
    },

    openEdit() {
      const section = this.selectedSection;
      if (!section) return;
      this.editorMode = 'edit';
      this.editorTitle = section.title || '';
      this.editorDescription = section.description || '';
      this.editorOpen = true;
      this.$nextTick(() => this.$refs.sectionTitleInput?.focus());
    },

    openAdd() {
      this.editorMode = 'add';
      this.editorTitle = '';
      this.editorDescription = '';
      this.editorOpen = true;
      this.$nextTick(() => this.$refs.sectionTitleInput?.focus());
    },

    closeEditor() {
      this.editorOpen = false;
      this.editorTitle = '';
      this.editorDescription = '';
    },

    submitEditor() {
      const title = this.editorTitle.trim();
      const description = this.editorDescription.trim();
      if (!title || !description) {
        this.error = 'Section title and description are required';
        return;
      }
      this.error = '';
      if (this.editorMode === 'add') {
        const key = this._uniqueKey(title);
        this.sections = [
          ...this.sections,
          {
            key,
            title,
            description,
            selected: true,
            when_relevant: '',
            allowed_formats: ['prose'],
            preferred_format: 'prose',
          },
        ];
        this.focusIdx = this.sections.length - 1;
      } else if (this.selectedSection) {
        const key = this.selectedSection.key;
        this.sections = this.sections.map((section) => (
          section.key === key
            ? { ...section, title, description }
            : section
        ));
      }
      this.closeEditor();
      this.scheduleSave();
    },

    _uniqueKey(title) {
      const base = title
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '_')
        .replace(/^_+|_+$/g, '') || 'custom_section';
      let key = base;
      let suffix = 2;
      const existing = new Set(this.sections.map((section) => section.key));
      while (existing.has(key)) {
        key = `${base}_${suffix}`;
        suffix += 1;
      }
      return key;
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
        { key: 'space',     label: 'NEXT', run: () => this.next() },
        { key: 'enter',     run: () => this.toggle(this.focusIdx) },
        { key: 'a',         label: 'ALL', run: () => this.selectAll() },
        { key: 'd',         label: 'NONE', run: () => this.deselectAll() },
        { key: 'e',         label: 'EDIT', run: () => this.openEdit() },
        { key: 'm',         label: 'ADD', run: () => this.openAdd() },
        { key: 'n',         label: 'NEXT', run: () => this.next() },
        { key: 'escape',    label: 'BACK',
          run: () => { if (this.editorOpen) this.closeEditor(); else this.back(); } },
      ];
      this.$store.hotkeys.register('screen:schema', bindings);
    },
  };
}

// ---------------------------------------------------------------------------
// COMPANIES tab  —  discovery + selection
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
    workspaceBrief: '',
    discoveryAudit: {
      search_count: 0,
      last_searched_at: '',
      last_candidate_count: 0,
      last_provider: '',
    },

    // Cost estimate — snapshotted from /api/confirm
    costPerCompetitor: 0,
    sectionCount: 0,
    verificationMode: 'standard',

    // Search-terms modal
    termsModalOpen: false,
    terms: { focus: '', seeds: '' },

    get path() { return this.$store.router.params.path; },
    get encodedPath() { return encodeURIComponent(this.path); },
    get selectedCount() { return this.competitors.filter((c) => this.isSelected(c)).length; },
    get blockingMessage() {
      if (!this.workspaceBrief.trim()) return 'Go to PLAN [1] and define the research brief first.';
      if (this.sectionCount <= 0) return 'Go to SCHEMA [2] and enable at least one dossier section first.';
      return '';
    },
    get estimatedCost() {
      return Number(this.selectedCount * this.costPerCompetitor).toFixed(2) * 1;
    },

    async init() {
      this.registerKeys();
      await this.loadAll();
      this._loadSelectionState();
      if (this.competitors.length === 0 && !this.blockingMessage) {
        await this.search({ silent: true });
      }
    },

    // -----------------------------------------------------------------
    // Data
    // -----------------------------------------------------------------

    async loadAll() {
      this.error = '';
      try {
        const [compResp, confResp, workspaceResp, auditResp] = await Promise.all([
          fetch('/api/competitors?path=' + this.encodedPath),
          fetch('/api/confirm?path=' + this.encodedPath),
          fetch('/api/workspace?path=' + this.encodedPath),
          fetch('/api/discovery-audit?path=' + this.encodedPath),
        ]);
        if (compResp.ok) {
          const data = await compResp.json();
          this.competitors = data.competitors || [];
        }
        if (confResp.ok) {
          const conf = await confResp.json();
          this.sectionCount = conf.section_keys?.length || 0;
          this.costPerCompetitor = conf.blended_per_company || conf.total_cost_per_company || 0;
          this.verificationMode = conf.default_verification_mode || 'standard';
        }
        if (workspaceResp.ok) {
          const workspace = await workspaceResp.json();
          this.workspaceBrief = workspace.domain || '';
        }
        if (auditResp.ok) {
          this.discoveryAudit = await auditResp.json();
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
      if (this.blockingMessage) return;
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
        this._loadSelectionState();
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
      this._saveSelectionState();
    },

    selectAll() {
      this.deselected = new Set();
      this._saveSelectionState();
    },

    deselectAll() {
      this.deselected = new Set(this.competitors.map((c) => c.slug));
      this._saveSelectionState();
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
    // Navigation
    // -----------------------------------------------------------------

    next() {
      if (this.selectedCount === 0 || this.blockingMessage) return;
      this.$store.router.goTab('agents');
    },

    formatAuditTimestamp(ts) {
      if (!ts) return '';
      try {
        return new Date(ts).toLocaleString();
      } catch (_err) {
        return ts;
      }
    },

    _loadSelectionState() {
      try {
        const raw = localStorage.getItem(selectionStateKey(this.path));
        if (!raw) return;
        const parsed = JSON.parse(raw);
        if (Array.isArray(parsed)) this.deselected = new Set(parsed);
      } catch (_err) { /* ignore */ }
    },

    _saveSelectionState() {
      try {
        localStorage.setItem(selectionStateKey(this.path), JSON.stringify([...this.deselected]));
      } catch (_err) { /* ignore */ }
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
        { key: 't',         label: 'SEARCH TERMS', run: () => this.openTerms() },
        { key: 'a',         label: 'ACCEPT ALL', run: () => this.selectAll() },
        { key: 'd',         label: 'REJECT ALL', run: () => this.deselectAll() },
        { key: 'n',         label: 'NEXT',   run: () => this.next() },
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

const WEB_VERIFICATION_MODES = ['standard', 'verified', 'deep'];

function modelNameFromOption(option) {
  return option?.name || option?.id || 'sonnet';
}

function selectionStateKey(path) {
  return `recon:web:selection:${path || ''}`;
}

function agentsScreen() {
  return {
    error: '',
    launching: false,

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
    readyState: {
      competitorCount: 0,
      sectionCount: 0,
      selectedCount: 0,
      workers: 5,
      verificationMode: 'standard',
      modelName: 'sonnet',
    },

    // UI
    completionModalOpen: false,
    menuOpen: null,
    runPaused: false,

    // SSE
    _es: null,

    get path() { return this.$store.router.params.path; },
    get encodedPath() { return encodeURIComponent(this.path); },
    get terminal() { return ['complete', 'failed', 'cancelled'].includes(this.status); },
    get blockingMessage() {
      if (this.readyState.sectionCount <= 0) return 'Go to SCHEMA [2] and enable at least one dossier section first.';
      if (this.readyState.selectedCount <= 0) return 'Go to COMPANIES [3] and accept at least one company first.';
      return '';
    },
    get primaryActionLabel() {
      if (this.readyState.sectionCount <= 0) return 'GO TO SCHEMA';
      if (this.readyState.selectedCount <= 0) return 'GO TO COMPANIES';
      return 'RUN';
    },
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

      await this._loadReadyState();
      this._initAgents(this.readyState.workers);
      // Always open the global event stream first. Filtering to a
      // specific run happens client-side once we know the run_id.
      this._openStream();

      const autostart = this.$store.router.params.query?.autostart === '1';
      if (autostart) {
        await this.launchRun();
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

    async _loadReadyState() {
      try {
        const [confirmResp, compResp] = await Promise.all([
          fetch('/api/confirm?path=' + this.encodedPath),
          fetch('/api/competitors?path=' + this.encodedPath),
        ]);
        if (confirmResp.ok) {
          const confirm = await confirmResp.json();
          this.readyState.competitorCount = confirm.competitor_count || 0;
          this.readyState.sectionCount = confirm.section_keys?.length || 0;
          this.readyState.workers = confirm.default_workers || 5;
          this.readyState.verificationMode = confirm.default_verification_mode || 'standard';
          this.readyState.modelName = confirm.default_model || 'sonnet';
        }
        if (compResp.ok) {
          const data = await compResp.json();
          const deselected = this._loadDeselectedSlugs();
          const competitors = data.competitors || [];
          this.readyState.selectedCount = competitors.filter((c) => !deselected.has(c.slug)).length;
          this.readyState.competitorCount = competitors.length;
        }
      } catch (_err) { /* non-fatal */ }
    },

    _loadDeselectedSlugs() {
      try {
        const raw = localStorage.getItem(selectionStateKey(this.path));
        const parsed = raw ? JSON.parse(raw) : [];
        return new Set(Array.isArray(parsed) ? parsed : []);
      } catch (_err) {
        return new Set();
      }
    },

    async _reconcileSelection() {
      const deselected = this._loadDeselectedSlugs();
      if (!deselected.size) return;
      for (const slug of deselected) {
        try {
          await fetch('/api/competitors/' + encodeURIComponent(slug) + '?path=' + this.encodedPath, {
            method: 'DELETE',
          });
        } catch (_err) { /* keep going */ }
      }
      try { localStorage.removeItem(selectionStateKey(this.path)); } catch (_err) { /* ignore */ }
      this.readyState.selectedCount = Math.max(0, this.readyState.competitorCount - deselected.size);
      this.readyState.competitorCount = this.readyState.selectedCount;
    },

    async launchRun() {
      if (this.launching || this.runId) return;
      if (this.blockingMessage) return;
      this.currentStage = 'STARTING';
      this.launching = true;
      try {
        await this._reconcileSelection();
        const r = await fetch('/api/runs', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            path: this.path,
            use_fake_llm: true,
            model: this.readyState.modelName,
            workers: this.readyState.workers,
            verification_mode: this.readyState.verificationMode,
          }),
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
      } finally {
        this.launching = false;
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

    _initAgents(workerCount = 5) {
      // Size the grid to the default worker count from /api/confirm;
      // fall back to 5 if we can't resolve it.
      const n = Math.min(AGENT_PERSONA_POOL.length, Math.max(1, workerCount || 5));
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

    async pauseRun() {
      if (!this.runId) { this.menuOpen = null; return; }
      const endpoint = this.runPaused ? 'resume' : 'pause';
      try {
        const r = await fetch('/api/runs/' + encodeURIComponent(this.runId) + '/' + endpoint, { method: 'POST' });
        if (!r.ok) throw new Error(`${endpoint} failed (${r.status})`);
        // Optimistic flip — SSE RunPaused/RunResumed will reaffirm.
        this.runPaused = !this.runPaused;
      } catch (e) {
        this.error = e.message || String(e);
      } finally {
        this.menuOpen = null;
      }
    },

    async togglePauseResume() {
      if (!this.runId || this.terminal) return;
      await this.pauseRun();
    },

    async cancelRun() {
      if (!this.runId) { this.menuOpen = null; return; }
      if (!confirm('Cancel this run? Workers will stop at the next check.')) {
        this.menuOpen = null;
        return;
      }
      try {
        const r = await fetch('/api/runs/' + encodeURIComponent(this.runId) + '/cancel', { method: 'POST' });
        if (!r.ok) throw new Error(`Cancel failed (${r.status})`);
      } catch (e) {
        this.error = e.message || String(e);
      } finally {
        this.menuOpen = null;
      }
    },

    restartTask() {
      // Per-task restart needs backend support we don't have yet;
      // point the user at the obvious alternative.
      alert('Per-task restart coming later. For now, start a new run from COMPANIES.');
      this.menuOpen = null;
    },

    debugTask() {
      // Debug overlay would pull events for a single (comp, section).
      // Good follow-on but non-trivial; stub for now.
      alert('Debug overlay coming later.');
      this.menuOpen = null;
    },

    closeCompletion() { this.completionModalOpen = false; },
    goOutput() {
      this.completionModalOpen = false;
      this.$store.router.goTab('output');
    },

    primaryAction() {
      if (this.readyState.sectionCount <= 0) {
        this.$store.router.goTab('schema');
        return;
      }
      if (this.readyState.selectedCount <= 0) {
        this.$store.router.goTab('comps');
        return;
      }
      this.launchRun();
    },

    back() { this.$store.router.goTab('comps'); },

    registerKeys() {
      const bindings = [
        { key: 'r', allowInEditable: true, run: () => { if (!this.runId) this.primaryAction(); } },
        { key: 'p', allowInEditable: true, run: () => { if (this.runId && !this.terminal) this.togglePauseResume(); } },
        { key: 's', allowInEditable: true, run: () => { if (this.runId && !this.terminal) this.cancelRun(); } },
        { key: 'o', allowInEditable: true, run: () => { if (this.runId) this.goOutput(); } },
        { key: 'escape', allowInEditable: true,
          run: () => {
            if (this.menuOpen != null) { this.menuOpen = null; return; }
            if (this.completionModalOpen) { this.closeCompletion(); return; }
            this.back();
          } },
        { key: 'enter', allowInEditable: true,
          run: () => {
            if (!this.runId) {
              this.primaryAction();
              return;
            }
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

// ---------------------------------------------------------------------------
// Settings overlay  —  API-keys form, version footer
// ---------------------------------------------------------------------------
//
// Global overlay accessible via [Z]. Loads the per-global saved status
// (boolean per provider) without revealing the actual key values, and
// lets the user write new values via POST /api/api-keys. Writes go to
// ~/.recon/api_keys.yaml (the "global" location), not a per-workspace
// .env, so a single set of keys covers every project.

function settingsOverlay() {
  return {
    providers: [
      { name: 'anthropic', label: 'Anthropic API key', placeholder: 'sk_ant_******************', value: '', saved: false },
      { name: 'google_ai', label: 'Gemini API key',    placeholder: 'AI***************',          value: '', saved: false },
    ],
    version: '',
    saving: false,
    message: '',
    errorMsg: '',

    init() {
      // Re-fetch saved state each time the overlay opens so leaving and
      // reopening reflects any writes we just made.
      this.$watch('$store.settings.open', (open) => {
        if (open) this.refresh();
      });
    },

    async refresh() {
      this.message = '';
      this.errorMsg = '';
      for (const p of this.providers) p.value = '';
      try {
        const [keysR, healthR] = await Promise.all([
          fetch('/api/api-keys/global'),
          fetch('/api/health'),
        ]);
        if (keysR.ok) {
          const data = await keysR.json();
          for (const p of this.providers) p.saved = !!data[p.name];
        }
        if (healthR.ok) {
          const h = await healthR.json();
          this.version = h.version || '';
        }
      } catch (_err) { /* non-fatal */ }
    },

    async save() {
      this.saving = true;
      this.errorMsg = '';
      this.message = '';
      try {
        const writes = this.providers
          .filter((p) => p.value.trim())
          .map((p) => fetch('/api/api-keys', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            // Global path for keys — backend accepts empty path for
            // the ~/.recon/api_keys.yaml file.
            body: JSON.stringify({ path: '', name: p.name, value: p.value.trim(), global: true }),
          }));
        if (!writes.length) {
          this.message = 'Nothing to save — enter a value first.';
          return;
        }
        const results = await Promise.all(writes);
        const bad = results.find((r) => !r.ok);
        if (bad) {
          const b = await bad.json().catch(() => ({}));
          throw new Error(b.detail || `Save failed (${bad.status})`);
        }
        this.message = 'Saved.';
        for (const p of this.providers) p.value = '';
        await this.refresh();
      } catch (e) {
        this.errorMsg = e.message || String(e);
      } finally {
        this.saving = false;
      }
    },
  };
}

function outputScreen() {
  return {
    loading: true,
    error: '',
    tree: [],          // flat structure for rendering
    treeLines: [],     // [{ prefix, name, ref }] — ref points to a file or null for dirs
    treeHeader: '',
    fileCount: 0,
    selected: null,    // one of the file entries

    // Preview pane state
    previewLoading: false,
    previewError: '',
    previewHtml: '',
    _previewCache: {},  // path -> rendered html
    provenance: null,

    get path() { return this.$store.router.params.path; },
    get encodedPath() { return encodeURIComponent(this.path); },

    async init() {
      this.registerKeys();
      await this.load();
      if (this.selected) this._loadPreview(this.selected);
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
        this.provenance = data.provenance || null;
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

    async _loadPreview(file) {
      if (!file?.path) return;
      // Cache-hit: render synchronously from memory. Files don't
      // change mid-session; if they do, a tab re-mount flushes the
      // cache anyway.
      if (this._previewCache[file.path] != null) {
        this.previewHtml = this._previewCache[file.path];
        this.previewError = '';
        this.previewLoading = false;
        return;
      }
      this.previewLoading = true;
      this.previewError = '';
      this.previewHtml = '';
      try {
        const url = '/api/files?path=' + this.encodedPath + '&target=' + encodeURIComponent(file.path);
        const r = await fetch(url);
        if (!r.ok) {
          const b = await r.json().catch(() => ({}));
          throw new Error(b.detail || `File read failed (${r.status})`);
        }
        const data = await r.json();
        this.previewHtml = this._renderMarkdown(data.content || '');
        this._previewCache[file.path] = this.previewHtml;
      } catch (e) {
        this.previewError = e.message || String(e);
      } finally {
        this.previewLoading = false;
      }
    },

    // Markdown → safe HTML. marked() parses, DOMPurify strips anything
    // that could execute. Skip markdown rendering entirely if either
    // library failed to load so we at least show plaintext.
    _renderMarkdown(md) {
      if (typeof marked === 'undefined' || typeof DOMPurify === 'undefined') {
        return md.replace(/[&<>]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));
      }
      try {
        const html = marked.parse(md, { breaks: true, gfm: true });
        return DOMPurify.sanitize(html, { USE_PROFILES: { html: true } });
      } catch (_err) {
        return md.replace(/[&<>]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));
      }
    },

    iconFor(file) {
      if (!file) return 'lucide:file';
      if (file.kind === 'exec_summary') return 'lucide:file-text';
      if (file.kind === 'dossier') return 'lucide:file-user';
      if (file.kind === 'theme') return 'lucide:tag';
      if (file.kind === 'distilled') return 'lucide:sparkles';
      return 'lucide:file-text';
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
        files.push({
          name: this._basename(f.path),
          path: f.path,
          kind: f.kind,
          group: f.kind === 'dossier' ? 'competitors' : 'output',
        });
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

    select(file) {
      this.selected = file;
      this._loadPreview(file);
    },

    provenanceStatus() {
      if (!this.provenance) return '';
      return (this.provenance.status || '').toUpperCase();
    },

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
        { key: 'l',      label: 'OPEN FOLDER', run: () => this.revealWorkspace() },
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
      this._loadPreview(this.selected);
    },
  };
}
