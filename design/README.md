# recon — Design Documents

> Comprehensive design specification for the recon competitive intelligence CLI.
> These documents capture all architectural decisions, pipeline design, and interface specifications agreed during design conversations.

## Documents

| Document | Contents |
|---|---|
| [v2 spec](v2-spec.md) | Canonical UX spec for the v2 TUI flow — progressive disclosure, screen-by-screen walkthrough, keybinds, done criteria |
| [Web UI spec](web-ui-spec.md) | FastAPI + Alpine.js + SSE architecture, route table, Pydantic schemas, build sequence, test strategy |
| [UI audit 2026-04-12](ui-audit-2026-04-12.md) | Cross-UI audit covering TUI/web parity and aesthetic direction |
| [Pipeline](archive/pipeline.md) | Full revised pipeline — 6 phases from setup through delivery, state machine, phase dependencies |
| [Setup and Discovery](archive/setup-and-discovery.md) | Wizard flow, schema design, competitor discovery, theme discovery, own-product research |
| [Research and Verification](archive/research-and-verification.md) | Section-by-section research agents, multi-agent consensus verification, format constraints, source preferences |
| [Architecture](archive/architecture.md) | Three-layer architecture, TUI design, CLI/headless mode, state management, SQLite schema, error logging |
| [Operations](archive/operations.md) | Run planner, incremental runs, diff updates, cost estimation, install and dependencies |

## Design Principles

1. **Schema drives everything.** Worker prompts, verification criteria, enrichment passes, format constraints — all derived from the user's schema. No hardcoded prompts per section.
2. **Verification is first-class.** Multi-agent consensus after every information-gathering step. Per-section source attribution with verification status.
3. **Data-driven themes.** Themes emerge from clustering, not user guesswork. Users curate and can investigate additional topics.
4. **Constrained freedom.** Agents choose from approved format options per section. Uniform enough for consistency, flexible enough for good data presentation.
5. **Provenance chain.** Every claim traces back through the synthesis chain to sources with verification status.
6. **Cost transparency.** Estimates upfront before spending money. Running totals during execution. Per-run cost tracking.
7. **Idempotent and incremental.** Every operation is safe to re-run. Incremental by default — only process what's changed.
8. **Local-first.** Vector search, embeddings, and state all run locally. Only external calls are to Claude's API with the user's own key.

## Relationship to SPEC.md

`SPEC.md` in the repo root is the original specification derived from the legacy Atlassian system. These design documents supersede it where they differ — they reflect the redesigned pipeline with discovery, consensus verification, data-driven themes, and the TUI interface. `SPEC.md` remains useful as reference for the CLI command surface and the original pipeline logic.
