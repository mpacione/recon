# Visual Brief

This brief distills the architecture into diagram-ready stories. It is written for making visuals, not for implementing the system.

## What the product is

Recon is a local-first competitive intelligence pipeline.

It takes:

- a schema (`recon.yaml`)
- a set of competitor profiles
- an LLM client

And produces:

- researched markdown profiles
- discovered themes
- per-theme synthesis documents
- distilled theme summaries
- a final executive summary

## The simplest one-line description

`recon` is a staged research engine with CLI and TUI front ends, markdown workspace outputs, SQLite state, and local vector retrieval.

## The 5 visuals worth making

### 1. System overview

Purpose:
- show the major boxes and where artifacts live

Recommended nodes:
- CLI
- TUI
- Pipeline engine
- LLM provider
- Workspace files
- SQLite state
- ChromaDB vector store
- Event bus

Key message:
- both interfaces drive the same engine
- the engine writes local artifacts and state
- the TUI listens to events for live monitoring

Suggested layout:
- left: CLI and TUI
- center: engine
- right: data stores
- bottom or side: event bus feeding back into TUI

### 2. End-to-end pipeline flow

Purpose:
- show the staged transformation of data from empty profiles to final summary

Recommended stages:
- Research
- Verify
- Enrich
- Index
- Themes
- Synthesize
- Deliver

Key message:
- each stage consumes outputs from the previous stage
- markdown profiles are the backbone artifact until theme synthesis begins

Important annotation:
- full `recon run` currently skips `Verify` in the wired CLI/TUI runner, even though the engine supports it

### 3. Research execution model

Purpose:
- explain the unusual batching strategy

Recommended framing:
- not competitor-by-competitor
- yes section-by-section across all competitors

Example visual:

```text
Overview   -> Cursor, Copilot, Codeium, Continue
Pricing    -> Cursor, Copilot, Codeium, Continue
Enterprise -> Cursor, Copilot, Codeium, Continue
...
```

Key message:
- recon optimizes for comparability across competitors
- worker concurrency exists inside each section batch

### 4. Data lifecycle

Purpose:
- show where information is stored as it moves through the system

Recommended artifact path:
- `recon.yaml`
- `competitors/*.md`
- `.recon/state.db`
- `.vectordb/`
- `themes/*.md`
- `themes/distilled/*.md`
- `executive_summary.md`

Key message:
- the workspace is the human-readable source of truth
- SQLite tracks operational state
- vector storage powers retrieval and theme work

### 5. TUI live-monitor loop

Purpose:
- explain how the run screen stays live without polling

Recommended flow:
- pipeline publishes event
- event bus broadcasts
- TUI monitor widgets update

Key message:
- the TUI is an observer and controller over the same engine, not a separate pipeline implementation

## Diagram-ready narratives

### Narrative A: “Thin UI, heavy engine”

Use this when the audience needs architecture clarity.

Script:
- user acts through CLI or TUI
- interfaces translate intent into pipeline config
- engine modules execute the work
- outputs land in local files and state stores

### Narrative B: “Profiles become themes become strategy”

Use this when the audience cares about the knowledge flow.

Script:
- research fills profiles
- indexing turns profile sections into retrievable chunks
- clustering discovers emergent themes
- synthesis converts those themes into analysis
- delivery compresses analysis into executive outputs

### Narrative C: “Observable long-running workflow”

Use this when the audience cares about operations or UX.

Script:
- long-running pipeline emits typed events
- UI subscribes to events
- progress, cost, worker activity, and stage state update live

## Visual language recommendations

### Good emphasis

- local-first
- staged progression
- explicit artifact handoff
- same engine behind both interfaces
- event-driven monitoring

### Avoid

- drawing it as a generic agent swarm
- implying a server/backend that owns the data
- implying the TUI and CLI are separate implementations
- implying all advertised stages are always enabled in every run path

## Labels and captions you can reuse

Short labels:

- Thin Interface Layer
- Async Pipeline Engine
- Markdown Workspace
- Operational State
- Local Retrieval Layer
- Theme Discovery
- Executive Distillation
- Event-Driven Run Monitor

Caption lines:

- "Research is section-batched across competitors for comparability."
- "Workspace markdown is the primary user-facing artifact layer."
- "SQLite stores operational state; ChromaDB stores retrieval context."
- "The TUI observes engine events rather than polling files."
- "Theme discovery is emergent from embeddings and clustering, not predefined in the schema."

## If you only make 2 diagrams

Make these:

1. a system overview with interfaces -> engine -> local stores
2. a pipeline flow showing profiles -> chunks -> themes -> executive summary

That pair explains almost everything important.
