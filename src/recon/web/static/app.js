// recon web UI — Phase 1 scaffold bootstrap.
//
// Subsequent phases mount per-screen components and the EventSource
// SSE reader here. For now, this exposes a top-level component that
// pings /api/health so the shell visibly proves the server is up.
//
// Pattern: a global factory function invoked from x-data. Avoids the
// Alpine.data() / 'alpine:init' listener-ordering race that bit us
// when both scripts are deferred — Alpine can finish booting before
// our listener registers, leaving x-data unresolved.

function reconShell() {
  return {
    health: 'checking...',

    async init() {
      try {
        const response = await fetch('/api/health');
        if (!response.ok) {
          this.health = `server returned ${response.status}`;
          return;
        }
        const body = await response.json();
        this.health = body.ok ? `ok (v${body.version})` : 'not ok';
      } catch (err) {
        this.health = `error: ${err.message}`;
      }
    },
  };
}
