# Reference Files

Original source files from the Atlassian competitive landscape project. These are the production implementations that `recon` generalizes.

## Directory Map

```
reference/
├── prompts/                         # Markdown prompt templates and schemas
│   ├── README.md                    # Original pipeline documentation
│   ├── _Schema.md                   # Competitor profile schema (→ recon schema.md)
│   ├── _CompetitorTemplate.md       # Profile template (→ recon template.md)
│   ├── _AtlassianProductTemplate.md # Own-product template (→ recon own-product template)
│   ├── _FormatStandards.md          # Quality rubric and format rules
│   ├── _FormatCleanup.md            # Format cleanup pass instructions
│   ├── _ModelGuidance.md            # Model selection & prompt robustness guide
│   ├── _ContinuationPrompt.md       # Session resumption kit (context + state tracking)
│   ├── 00_ScaffoldCompetitors.md    # P0: Bulk scaffold competitor files
│   ├── 00_SingleCompetitorProfile.md # P1: Research single competitor (→ recon research)
│   ├── 01_PersistP1Research.md      # P1: Batch persist research to files
│   ├── 02_CapabilitiesDepth.md      # P2: Deep capability enrichment
│   ├── 03_SentimentEvidence.md      # P3: Sentiment enrichment (→ recon enrich --pass sentiment)
│   ├── 04_ImplicationsSynthesis.md  # P4: Theme synthesis (manual version)
│   ├── 05_ExecDeliverable.md        # P5: Executive briefing document
│   └── replit/                      # Interactive presentation app prompts
│       ├── README.md                # Build order and usage guide
│       ├── SPEC_InteractivePresentation.md  # App spec
│       ├── 00_DataExport.md         # Export competitor data to JSON
│       ├── 01_BaseApp.md            # React card grid
│       ├── 02_DetailPanel.md        # Click-to-expand detail
│       ├── 03_Filtering.md          # Product chips, theme, threat filters
│       ├── 04_PresentationMode.md   # Screen-sharing view
│       ├── 05_Polish.md             # Visual refinements
│       └── 06_ThemesPage.md         # Strategic synthesis page
│
├── orchestrators/                   # Async batch processing scripts
│   ├── batch_cleanup_README.md      # Orchestrator documentation
│   ├── p2_orchestrator.py           # Format cleanup (→ recon enrich --pass cleanup)
│   ├── p3_orchestrator.py           # Sentiment enrichment (→ recon enrich --pass sentiment)
│   ├── p3_5_orchestrator.py         # Strategic enrichment (→ recon enrich --pass strategic)
│   ├── atlassian_orchestrator.py    # Own-product research (→ recon research --own-products)
│   └── worker_prompt.md             # Cleanup worker instructions
│
└── pipeline/                        # P4 synthesis pipeline
    ├── README.md                    # Pipeline documentation
    ├── config.yaml                  # Theme definitions (→ recon.yaml themes section)
    ├── requirements.txt
    ├── 00_discover.py               # Emergent theme discovery via clustering
    ├── 01_index.py                  # ChromaDB indexing (→ recon index)
    ├── 02_retrieve.py               # Semantic retrieval (→ recon retrieve)
    ├── 03_synthesize.py             # Single-pass synthesis (→ recon synthesize)
    ├── 03_synthesize_deep.py        # 4-pass synthesis (→ recon synthesize --deep)
    ├── 04_tag_themes.py             # Theme tagging (→ recon tag)
    ├── 05_meta_synthesis.py         # Executive summary v2 (→ recon summarize)
    ├── 05_meta_synthesis_v1_backup.py # Executive summary v1 (opinionated)
    └── 06_distill.py                # Distillation (→ recon distill)
```

## Pipeline Processing Order

```
P0: Scaffold     → 00_ScaffoldCompetitors.md (bulk create empty files)
P1: Research     → 00_SingleCompetitorProfile.md / 01_PersistP1Research.md
P2: Cleanup      → p2_orchestrator.py (format alignment, schema compliance)
P3: Sentiment    → p3_orchestrator.py (HN/Reddit/G2 quotes, traction data)
P3.5: Strategic  → p3_5_orchestrator.py (platform, trust, workflow, time-to-value fields)
P4: Index        → 01_index.py → 02_retrieve.py → 03_synthesize_deep.py
P4.5: Tag        → 04_tag_themes.py (write themes to frontmatter)
P5: Meta         → 05_meta_synthesis.py (cross-theme executive summary)
P5.5: Distill    → 06_distill.py (deep → executive 1-pagers)
```

## What Was Missing (Now Included)

These files were not in the original curated reference/ directory but are important for understanding the full system:

### Prompt lifecycle (P0→P5)
- `00_ScaffoldCompetitors.md` — The scaffolding step that creates empty files for all competitors
- `01_PersistP1Research.md` — Batch research persistence with session state tracking
- `02_CapabilitiesDepth.md` — P2 manual prompt for deep capability research
- `03_SentimentEvidence.md` — P3 prompt (also read by p3_orchestrator.py as source of truth)
- `04_ImplicationsSynthesis.md` — Manual theme synthesis (pre-pipeline approach)
- `05_ExecDeliverable.md` — Executive briefing document creation

### Supporting prompts
- `_AtlassianProductTemplate.md` — Own-product self-assessment template
- `_ContinuationPrompt.md` — Session resumption kit with context, schemas, and quick references
- `_FormatCleanup.md` — Detailed format fix instructions with before/after examples
- `_ModelGuidance.md` — Which model for which task, failure modes, recovery prompts

### Missing orchestrators
- `p3_5_orchestrator.py` — Strategic enrichment (platform, trust, workflow, time-to-value)
- `atlassian_orchestrator.py` — Own-product research from external perspective

### Interactive presentation
- `replit/` — 8-file prompt sequence for building a React competitor browser app with Replit Agent

These files contain Atlassian-specific content that needs to be parameterized during implementation. The SPEC.md documents exactly how each maps to a recon CLI command.
