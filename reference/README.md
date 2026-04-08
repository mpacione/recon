# Reference Files

Original source files from the Atlassian competitive landscape project. These are the production implementations that `recon` generalizes.

## Directory Map

```
reference/
├── prompts/           # Markdown prompt templates and schemas
│   ├── README.md      # Original pipeline documentation
│   ├── _Schema.md     # Competitor profile schema (→ recon schema.md)
│   ├── _CompetitorTemplate.md  # Profile template (→ recon template.md)
│   ├── _FormatStandards.md     # Quality rubric and format rules
│   └── 00_SingleCompetitorProfile.md  # P1 research prompt
│
├── orchestrators/     # Async batch processing scripts
│   ├── p2_orchestrator.py    # Format cleanup (→ recon enrich --pass cleanup)
│   ├── p3_orchestrator.py    # Sentiment enrichment (→ recon enrich --pass sentiment)
│   └── worker_prompt.md      # Cleanup worker instructions
│
└── pipeline/          # P4 synthesis pipeline
    ├── README.md      # Pipeline documentation
    ├── config.yaml    # Theme definitions (→ recon.yaml themes section)
    ├── requirements.txt
    ├── 01_index.py    # ChromaDB indexing (→ recon index)
    ├── 02_retrieve.py # Semantic retrieval (→ recon retrieve)
    ├── 03_synthesize_deep.py  # 4-pass synthesis (→ recon synthesize --deep)
    ├── 04_tag_themes.py       # Theme tagging (→ recon tag)
    ├── 05_meta_synthesis.py   # Executive summary (→ recon summarize)
    └── 06_distill.py          # Distillation (→ recon distill)
```

These files contain Atlassian-specific content that needs to be parameterized during implementation. The SPEC.md documents exactly how each maps to a recon CLI command.
