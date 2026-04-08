# P4 Synthesis Pipeline

Local vector database approach for synthesizing strategic themes from 300+ competitor profiles.

## Why This Approach

- **300 files × 250 lines** = too much for any LLM context window
- **Semantic retrieval** finds relevant content across all files without filtering by metadata
- **Multiple queries per theme** ensures coverage (a low-autonomy tool might reveal UX patterns)
- **Runs locally** — no external vector DB service needed

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  01_index.py                                                │
│  - Reads all .md files                                      │
│  - Chunks by section (~500 tokens)                          │
│  - Embeds with local model (all-MiniLM-L6-v2)              │
│  - Stores in ChromaDB (local, persistent)                   │
└─────────────────────────┬───────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  02_retrieve.py --theme agentic_shift                       │
│  - Runs 4-5 semantic queries per theme                      │
│  - Retrieves top-50 chunks per query                        │
│  - Aggregates + ranks by competitor                         │
│  - Outputs .retrieved/{theme}.json                          │
└─────────────────────────┬───────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  03_synthesize.py --theme agentic_shift                     │
│  - Loads retrieved chunks                                   │
│  - Builds context (~30 competitors, top chunks)             │
│  - Sends to Claude (Sonnet/Opus) with synthesis prompt      │
│  - Outputs Themes/_AgenticShift.md                          │
└─────────────────────────────────────────────────────────────┘
```

## Setup

### 1. Install Dependencies

```bash
cd CompetitiveLandscape-2025
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r _Prompts/p4_pipeline/requirements.txt
```

First run will download the embedding model (~90MB).

### 2. Set API Key

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

Or create a `.env` file (add to .gitignore).

## Usage

### Step 1: Index All Files (One-Time)

```bash
python _Prompts/p4_pipeline/01_index.py
```

Takes 5-10 minutes on CPU. Creates `.chroma_db/` directory.

### Step 2: Retrieve for a Theme

```bash
# List available themes
python _Prompts/p4_pipeline/02_retrieve.py --list

# Retrieve for one theme
python _Prompts/p4_pipeline/02_retrieve.py --theme agentic_shift

# Retrieve for all themes
python _Prompts/p4_pipeline/02_retrieve.py --theme all
```

Creates `.retrieved/{theme}.json` with ranked competitors and chunks.

### Step 3: Synthesize Theme Document

```bash
# Dry run (see context without API call)
python _Prompts/p4_pipeline/03_synthesize.py --theme agentic_shift --dry-run

# Generate theme document
python _Prompts/p4_pipeline/03_synthesize.py --theme agentic_shift

# Generate all themes
python _Prompts/p4_pipeline/03_synthesize.py --theme all
```

Creates `Themes/_AgenticShift.md` (or other theme file).

## Configuration

Edit `config.yaml` to customize:

- **Embedding model**: Change to `all-mpnet-base-v2` for better quality (slower)
- **Chunk size**: Adjust for longer/shorter context chunks
- **Top-K retrieval**: More chunks = more context but higher cost
- **Synthesis model**: Switch between Sonnet (faster/cheaper) and Opus (better quality)
- **Theme queries**: Add/modify semantic queries per theme

## Themes

| Key | Output File | Focus |
|-----|-------------|-------|
| `agentic_shift` | `_AgenticShift.md` | L1→L5 autonomy transition |
| `platform_wars` | `_PlatformWars.md` | Ecosystem lock-in, IDE control surface |
| `trust_and_governance` | `_TrustGovernance.md` | Enterprise compliance, audit trails |
| `workflow_embedding` | `_WorkflowEmbedding.md` | UX architecture (sidecar vs autonomous) |
| `time_to_value` | `_TimeToValue.md` | Onboarding friction, quick wins |
| `developer_love` | `_DeveloperLoveTrends.md` | What devs actually like/hate |
| `consolidation_patterns` | `_ConsolidationPatterns.md` | Platform bundling strategies |
| `alignment_infrastructure` | `_AlignmentInfrastructure.md` | Left-of-code, specs→code traceability |
| `conductor_model` | `_ConductorModel.md` | Engineer as reviewer, not builder |

## Troubleshooting

### "No module named chromadb"
```bash
pip install -r _Prompts/p4_pipeline/requirements.txt
```

### Indexing is slow
- Normal: 5-10 min on CPU for 300 files
- GPU acceleration: Uncomment `torch` in requirements.txt

### "ANTHROPIC_API_KEY not set"
```bash
export ANTHROPIC_API_KEY="your-key-here"
```

### Retrieved results seem off
- Check `config.yaml` queries for the theme
- Add more specific queries
- Increase `top_k` in retrieval settings

### Synthesis is too generic
- Switch to Opus model in config.yaml
- Increase `max_competitors` in 03_synthesize.py
- Add more specific queries to find niche signals

## Cost Estimate

| Step | Cost |
|------|------|
| Indexing | Free (local embeddings) |
| Retrieval | Free (local embeddings) |
| Synthesis (Sonnet) | ~$0.15-0.30 per theme |
| Synthesis (Opus) | ~$1.50-3.00 per theme |
| **Total (9 themes, Sonnet)** | ~$2-3 |
| **Total (9 themes, Opus)** | ~$15-25 |

## Files Created

```
CompetitiveLandscape-2025/
├── .chroma_db/              # Vector database (gitignore this)
│   ├── chroma.sqlite3
│   └── index_meta.yaml
├── _Prompts/p4_pipeline/
│   └── .retrieved/          # Retrieval results (gitignore this)
│       ├── agentic_shift.json
│       └── ...
└── Themes/
    ├── _AgenticShift.md
    ├── _MCPEcosystem.md
    └── ...
```

## Plausible Deniability

"I wrote some Python scripts that chunk the competitor files, embed them with a local sentence-transformer model, store them in ChromaDB, and then retrieve relevant chunks for each synthesis theme. The retrieval uses multiple semantic queries to find connections I might miss with keyword search. Then I feed the retrieved context to Claude to write the synthesis."

That's... exactly what this does. 🤷
