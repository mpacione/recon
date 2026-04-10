# Getting started with recon

This guide walks you from an empty shell through a full competitive
intelligence run: install, set up a workspace, discover competitors,
research them, and produce an executive summary. About 10 minutes of
hands-on time, plus whatever the LLM spends on research.

## 1. Prerequisites

- **Python 3.11 or newer** (`python3 --version`)
- **An Anthropic API key** — sign up at <https://console.anthropic.com/>
  and create one. Budget ~$7 for a full first run on a 5-competitor
  workspace.
- **macOS or Linux**. Windows isn't tested.

## 2. Install

### Option A: From PyPI (when published)

```bash
pip install recon-cli
```

This gives you the `recon` command on your `PATH`.

### Option B: From source

```bash
git clone https://github.com/mpacione/recon.git
cd recon
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

The editable install lets you run the test suite and iterate on the
code.

### Verify

```bash
recon --version
# recon, version 0.2.0
```

## 3. Set your API key

recon reads `ANTHROPIC_API_KEY` from either:

1. The shell environment (`export ANTHROPIC_API_KEY=sk-ant-...`)
2. A `.env` file in the workspace root (written by the TUI wizard,
   or created manually as `ANTHROPIC_API_KEY=sk-ant-...`)

The `.env` file is preferred for workspace-scoped keys so different
projects can use different keys.

## 4. Create a workspace

A recon workspace is just a directory with a `recon.yaml` schema, a
`competitors/` folder, and some hidden state under `.recon/`. You can
put it anywhere.

### Option A: headless init (fastest)

```bash
mkdir my-research
cd my-research

recon init --headless \
  --domain "AI code assistants" \
  --company "Acme" \
  --products "Acme Copilot"
```

This seeds `recon.yaml` with the 8 default sections (overview,
capabilities, pricing, integration, enterprise, developer love,
head-to-head, strategic notes).

### Option B: interactive TUI wizard

```bash
recon tui
```

Pick **New project**, choose a directory, and fill in the
identity/sections/sources/API-key screens. The wizard writes
`recon.yaml` and a `.env` file for you.

## 5. Discover competitors

Let the LLM find candidates in your domain:

```bash
recon discover --rounds 3 --batch-size 15
```

Each round uses Anthropic's `web_search_20250305` tool to surface
live candidates, deduped by URL domain across rounds. Pass `--seed`
one or more times to prime the search with names you already know:

```bash
recon discover --seed Cursor --seed "GitHub Copilot" --rounds 2
```

If you want to accept everything non-interactively:

```bash
recon discover --auto-accept
```

## 6. Run the full pipeline

```bash
recon run --from research
```

This walks the pipeline end-to-end:

1. **research** — per section, per competitor, with live web search
2. **verify** — per section at the schema's tier (skipped if
   `verification_tier: standard`)
3. **enrich** — cleanup → sentiment → strategic passes
4. **index** — chunks every profile into a local ChromaDB vector store
5. **themes** — discovers themes via K-means clustering, tags profiles
6. **synthesize** — one file per theme under `themes/<slug>.md`
7. **deliver** — distills each theme under `themes/distilled/<slug>.md`,
   then writes a cross-theme `executive_summary.md` at the root

When it's done you'll have:

```
my-research/
  recon.yaml
  competitors/
    cursor.md
    github-copilot.md
    ...
  themes/
    ai_code_generation.md
    enterprise_compliance.md
    ...
    distilled/
      ai_code_generation.md
      ...
  executive_summary.md
  .recon/
    state.db
  .vectordb/
  .env
```

### Partial runs

Each stage is independently callable:

```bash
recon research --all          # or `recon research Cursor`
recon enrich --all --pass cleanup
recon index
recon tag
recon synthesize --theme "AI Code Generation"
recon distill --theme "AI Code Generation"
recon summarize
```

`recon run --from <stage>` lets you resume from any point (`research`,
`enrich`, `index`, `synthesize`).

## 7. Browse the results

Everything is markdown with YAML frontmatter — open `my-research/` in
[Obsidian](https://obsidian.md), VS Code, or any plain-text editor.

If you prefer an interactive view:

```bash
recon tui --workspace .
```

The TUI dashboard shows section progress, discovered themes, index
stats, and cost history. The "Run" button drives the same pipeline
as the CLI, with a live progress monitor and a theme curation gate
that pauses synthesis until you approve the discovered themes.

## 8. Costs, logging, and troubleshooting

### Cost estimate

Full run on ~5 competitors with the 8 default sections: roughly
**$7** total at `claude-sonnet-4-5` pricing.

- discovery: ~$0.70
- research (~40 section calls with web search): ~$6
- enrich / synth / deliver: ~$0.50

Per-run totals are tracked in `.recon/state.db`. Check them with:

```bash
recon status
```

### Logging

Every command writes to `~/.recon/logs/recon.log`. To watch live:

```bash
tail -f ~/.recon/logs/recon.log
```

To get debug output:

```bash
recon --log-level DEBUG research --all
```

### "No API key configured"

recon looked in `ANTHROPIC_API_KEY` (env) and `.env` (workspace root)
and found nothing. Either:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

or create `.env` next to `recon.yaml`:

```
ANTHROPIC_API_KEY=sk-ant-...
```

### "Unknown target: <name>"

`recon research Cursor` and `recon enrich Cursor` match profile
names case-insensitively against the workspace. Run `recon status`
to see the canonical names, then try again. Use `--all` to process
every profile.

### The TUI hangs or shows empty discovery

Check `~/.recon/logs/recon.log` for errors. The two most common
causes are (a) no API key in the workspace, (b) the plugin running
inside a GUI-launched Claude Desktop that doesn't inherit your
shell's environment — in that case write the key to `.env` instead.

## 9. Next steps

- Read [`design/pipeline.md`](../design/pipeline.md) for the
  architecture behind each stage
- Read [`design/wiring-audit.md`](../design/wiring-audit.md) for
  which TUI controls reach the engine and which are still WIP
- Check [`CHANGELOG.md`](../CHANGELOG.md) for what changed in each
  release
- File issues at <https://github.com/mpacione/recon/issues>
