# recon

Competitive intelligence CLI. Structured research, local vector search, LLM-powered synthesis.

**Status:** Spec complete, implementation starting. See [SPEC.md](SPEC.md) for full architecture.

## What it does

1. **Collect** — LLM-driven web research fills structured competitor profiles (markdown + YAML frontmatter)
2. **Index** — Local vector DB (ChromaDB + sentence-transformers) for semantic retrieval across hundreds of profiles
3. **Synthesize** — Multi-pass theme analysis: pattern recognition → devil's advocate → gap analysis → executive integration

## Quick start

```bash
pip install recon-cli
recon init my-landscape
cd my-landscape
recon add "Competitor Name" --research
recon index
recon synthesize --theme all --deep
```

## Prior art

Extracted from a production system that analyzed 288 competitors across 9 strategic themes. See SPEC.md for the full pipeline mapping.
