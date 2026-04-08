# Prompts & Pipelines

This folder contains all the prompts, orchestrators, and pipelines used to build and maintain the competitive landscape.

## Folder Structure

```
_Prompts/
├── README.md                    # This file
├── _BatchCleanup/               # P2/P3 Data Enrichment Orchestrators
├── p4_pipeline/                 # P4 Synthesis Pipeline
├── ReplitPrompts/               # Replit Agent prompts for presentation app
├── _Archive/                    # Deprecated prompts (safe to delete)
└── *.md                         # Manual prompt templates
```

## _BatchCleanup/ — Data Enrichment Orchestrators

Python scripts for batch processing competitor profiles with Claude API.

| Script | Purpose | When to Use |
|--------|---------|-------------|
| `p2_orchestrator.py` | Format cleanup & schema alignment | After adding new competitors |
| `p3_orchestrator.py` | Sentiment enrichment (HN, Reddit, G2) | After P2, to add real quotes |
| `p3_5_orchestrator.py` | Presentation fields (demo_url, tagline) | After P3, before exec presentation |
| `atlassian_orchestrator.py` | Research Atlassian products externally | One-time, already complete |

**Usage:**
```bash
cd CompetitiveLandscape-2025
python _Prompts/_BatchCleanup/p3_orchestrator.py --file "Cursor.md"
python _Prompts/_BatchCleanup/p3_orchestrator.py --workers 5
```

## p4_pipeline/ — Synthesis Pipeline

Local vector database + Claude synthesis for strategic themes.

| Script | Purpose | When to Use |
|--------|---------|-------------|
| `01_index.py` | Index all competitors into ChromaDB | After adding many new competitors |
| `02_retrieve.py` | Semantic retrieval for themes | Before synthesis |
| `03_synthesize.py` | Generate theme documents | After retrieval |
| `03_synthesize_deep.py` | Deep theme synthesis (longer output) | For exec-ready themes |
| `04_tag_themes.py` | Tag competitors with relevant themes | After synthesis |
| `05_meta_synthesis.py` | Executive summary across all themes | Final step |
| `06_distill.py` | Distill deep themes to 1-pagers | After deep synthesis |

**Usage:**
```bash
cd CompetitiveLandscape-2025
python _Prompts/p4_pipeline/01_index.py
python _Prompts/p4_pipeline/02_retrieve.py --theme all
python _Prompts/p4_pipeline/03_synthesize_deep.py --theme all
python _Prompts/p4_pipeline/05_meta_synthesis.py --deep
```

See `p4_pipeline/README.md` for detailed documentation.

## ReplitPrompts/ — Presentation App

Sequential prompts for building an interactive competitor browser with Replit Agent.

See `ReplitPrompts/README.md` for build order and usage.

## Manual Prompt Templates

| File | Purpose |
|------|---------|
| `00_ScaffoldCompetitors.md` | Create new competitor file from scratch |
| `00_SingleCompetitorProfile.md` | Deep research on single competitor |
| `01_PersistP1Research.md` | Initial research pass |
| `02_CapabilitiesDepth.md` | Deep dive on capabilities |
| `03_SentimentEvidence.md` | Add sentiment data manually |
| `04_ImplicationsSynthesis.md` | Write implications section |
| `05_ExecDeliverable.md` | Create exec presentation |
| `_Schema.md` | Competitor file schema reference |
| `_CompetitorTemplate.md` | Blank competitor template |
| `_AtlassianProductTemplate.md` | Template for Atlassian products |
| `_FormatStandards.md` | Formatting rules |
| `_FormatCleanup.md` | Fix formatting issues |

## Processing Order

For a full refresh:

1. **P2**: `_BatchCleanup/p2_orchestrator.py` — Format cleanup
2. **P3**: `_BatchCleanup/p3_orchestrator.py` — Sentiment enrichment
3. **P3.5**: `_BatchCleanup/p3_5_orchestrator.py` — Presentation fields
4. **P4 Index**: `p4_pipeline/01_index.py` — Build vector DB
5. **P4 Retrieve**: `p4_pipeline/02_retrieve.py --theme all`
6. **P4 Synthesize**: `p4_pipeline/03_synthesize_deep.py --theme all`
7. **P4 Distill**: `p4_pipeline/06_distill.py --theme all`
8. **P4 Exec Summary**: `p4_pipeline/05_meta_synthesis.py --deep`
