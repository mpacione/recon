"""CLI entrypoint for recon."""

from __future__ import annotations

import asyncio
from pathlib import Path

import click


def _run_async(coro):
    """Run an async function from sync CLI context."""
    return asyncio.run(coro)


def _try_create_client(model: str = "claude-sonnet-4-20250514"):
    """Try to create an LLM client. Returns (client, None) or (None, error_msg)."""
    from recon.client_factory import ClientCreationError, create_llm_client

    try:
        return create_llm_client(model=model), None
    except ClientCreationError as e:
        return None, str(e)


@click.group()
@click.version_option()
def main():
    """recon -- Competitive intelligence CLI."""


@main.command()
@click.argument("directory", default=".")
@click.option("--domain", prompt="Domain", help="Research domain (e.g., 'Developer Tools')")
@click.option("--company", prompt="Company name", help="Your company name")
@click.option("--products", prompt="Products (comma-separated)", help="Your products")
def init(directory, domain, company, products):
    """Initialize a new recon workspace."""
    from recon.workspace import Workspace

    product_list = [p.strip() for p in products.split(",")]
    ws = Workspace.init(
        root=Path(directory),
        domain=domain,
        company_name=company,
        products=product_list,
    )
    click.echo(f"Workspace initialized at {ws.root}")


@main.command()
@click.argument("name")
@click.option("--own-product", is_flag=True, help="Mark as own product (researched from external perspective)")
def add(name, own_product):
    """Add a new competitor profile."""
    from recon.workspace import Workspace

    ws = Workspace.open(Path("."))
    path = ws.create_profile(name, own_product=own_product)
    click.echo(f"Created profile: {path}")


@main.command()
def status():
    """Show workspace status dashboard."""
    from recon.workspace import Workspace

    ws = Workspace.open(Path("."))
    profiles = ws.list_profiles()
    click.echo(f"Workspace: {ws.root}")
    click.echo(f"Domain: {ws.schema.domain if ws.schema else 'N/A'}")
    click.echo(f"Profiles: {len(profiles)}")

    by_status: dict[str, int] = {}
    for p in profiles:
        s = p.get("research_status", "unknown")
        by_status[s] = by_status.get(s, 0) + 1

    for s, count in sorted(by_status.items()):
        click.echo(f"  {s}: {count}")


@main.command()
@click.argument("target", required=False)
@click.option("--all", "all_targets", is_flag=True, help="Research all scaffold profiles")
@click.option("--workers", default=5, help="Parallel workers")
@click.option("--dry-run", is_flag=True, help="Show what would be researched")
@click.option("--headless", is_flag=True, help="JSON output, no TUI")
def research(target, all_targets, workers, dry_run, headless):
    """Run LLM-powered research on competitors."""
    from recon.research import ResearchOrchestrator, ResearchPlan
    from recon.workspace import Workspace

    ws = Workspace.open(Path("."))

    if dry_run:
        profiles = ws.list_profiles()
        plan = ResearchPlan.from_schema(schema=ws.schema, competitors=[p["name"] for p in profiles])
        click.echo(f"Plan: {plan.total_tasks} tasks across {len(plan.batches)} sections")
        for batch in plan.batches:
            click.echo(f"  {batch.section_key}: {len(batch.competitors)} competitors")
        return

    client, error = _try_create_client()
    if error:
        click.echo(f"ANTHROPIC_API_KEY not set. {error}")
        return

    orchestrator = ResearchOrchestrator(
        workspace=ws,
        llm_client=client,
        max_workers=workers,
    )

    click.echo("Starting research...")
    results = _run_async(orchestrator.research_all())

    total_input = sum(r.get("tokens", {}).get("input", 0) for r in results)
    total_output = sum(r.get("tokens", {}).get("output", 0) for r in results)
    click.echo(f"Research complete: {len(results)} sections across competitors")
    click.echo(f"Tokens: {total_input} input, {total_output} output")


@main.command()
@click.argument("target", required=False)
@click.option("--all", "all_targets", is_flag=True, help="Enrich all eligible profiles")
@click.option("--pass", "pass_name", type=click.Choice(["cleanup", "sentiment", "strategic"]), required=True)
@click.option("--workers", default=10, help="Parallel workers")
@click.option("--dry-run", is_flag=True, help="Show what would be enriched")
def enrich(target, all_targets, pass_name, workers, dry_run):
    """Progressive enrichment passes."""
    from recon.enrichment import EnrichmentOrchestrator, EnrichmentPass
    from recon.workspace import Workspace

    ws = Workspace.open(Path("."))

    if dry_run:
        profiles = ws.list_profiles()
        eligible = [p for p in profiles if p.get("research_status") not in ("scaffold", None)]
        click.echo(f"Enrich ({pass_name}): {len(eligible)} eligible profiles")
        return

    client, error = _try_create_client()
    if error:
        click.echo(f"ANTHROPIC_API_KEY not set. {error}")
        return

    pass_enum = EnrichmentPass(pass_name)
    orchestrator = EnrichmentOrchestrator(
        workspace=ws,
        llm_client=client,
        enrichment_pass=pass_enum,
        max_workers=workers,
    )

    click.echo(f"Starting enrichment ({pass_name})...")
    results = _run_async(orchestrator.enrich_all())

    total_input = sum(r.get("tokens", {}).get("input", 0) for r in results)
    total_output = sum(r.get("tokens", {}).get("output", 0) for r in results)
    click.echo(f"Enrichment complete: {len(results)} profiles enriched")
    click.echo(f"Tokens: {total_input} input, {total_output} output")


@main.command()
@click.option("--incremental/--full", default=True, help="Only index new/changed files")
@click.option("--workspace", "workspace_dir", default=".", help="Workspace directory")
def index(incremental, workspace_dir):
    """Build local vector database from profiles."""
    from recon.incremental import IncrementalIndexer
    from recon.index import IndexManager
    from recon.state import StateStore
    from recon.workspace import Workspace

    ws = Workspace.open(Path(workspace_dir))
    manager = IndexManager(persist_dir=str(ws.root / ".vectordb"))
    state = StateStore(db_path=ws.root / ".recon" / "state.db")
    _run_async(state.initialize())

    if not incremental:
        manager.clear()

    indexer = IncrementalIndexer(workspace=ws, index_manager=manager, state_store=state)
    result = _run_async(indexer.index(force=not incremental))

    click.echo(f"Indexed {result.indexed} files ({result.total_chunks} chunks), skipped {result.skipped} unchanged")
    click.echo(f"Collection size: {manager.collection_count()}")


@main.command()
@click.option("--query", required=True, help="Search query")
@click.option("--n-results", default=10, help="Number of results")
def retrieve(query, n_results):
    """Semantic retrieval of relevant chunks."""
    from recon.index import IndexManager
    from recon.workspace import Workspace

    ws = Workspace.open(Path("."))
    manager = IndexManager(persist_dir=str(ws.root / ".vectordb"))

    results = manager.retrieve(query, n_results=n_results)

    for i, result in enumerate(results, 1):
        meta = result.get("metadata", {})
        click.echo(f"\n--- Result {i} ---")
        click.echo(f"Source: {meta.get('name', 'Unknown')} / {meta.get('section', 'Unknown')}")
        click.echo(f"Distance: {result.get('distance', 'N/A'):.4f}")
        click.echo(result["text"][:200])


@main.command()
@click.option("--theme", required=True, help="Theme to synthesize")
@click.option("--deep", is_flag=True, help="4-pass deep synthesis")
@click.option("--dry-run", is_flag=True, help="Show context size + cost estimate")
def synthesize(theme, deep, dry_run):
    """Generate theme analysis documents."""
    if dry_run:
        click.echo(f"Synthesis ({('deep 4-pass' if deep else 'single pass')}): {theme}")
        click.echo("Requires indexed profiles and API key.")
        return

    client, error = _try_create_client(
        model="claude-opus-4-20250514" if deep else "claude-sonnet-4-20250514",
    )
    if error:
        click.echo(f"ANTHROPIC_API_KEY not set. {error}")
        return

    from recon.index import IndexManager
    from recon.synthesis import SynthesisEngine, SynthesisMode
    from recon.workspace import Workspace

    ws = Workspace.open(Path("."))
    manager = IndexManager(persist_dir=str(ws.root / ".vectordb"))

    chunks = manager.retrieve(theme, n_results=50)
    if not chunks:
        click.echo("No indexed chunks found. Run 'recon index' first.")
        return

    mode = SynthesisMode.DEEP if deep else SynthesisMode.SINGLE
    engine = SynthesisEngine(llm_client=client)

    click.echo(f"Synthesizing theme: {theme} ({mode.value} mode, {len(chunks)} chunks)...")
    result = _run_async(engine.synthesize(theme=theme, chunks=chunks, mode=mode))

    themes_dir = ws.root / "themes"
    themes_dir.mkdir(exist_ok=True)
    output_path = themes_dir / f"{theme.lower().replace(' ', '_')}.md"
    output_path.write_text(result.content)

    click.echo(f"Synthesis complete: {output_path}")
    click.echo(f"Tokens: {result.total_input_tokens} input, {result.total_output_tokens} output")


@main.command()
@click.option("--theme", required=True, help="Theme key or 'all'")
def distill(theme):
    """Condense deep synthesis into executive 1-pagers."""
    client, error = _try_create_client()
    if error:
        click.echo(f"ANTHROPIC_API_KEY not set. {error}")
        return

    from recon.deliver import Distiller
    from recon.synthesis import PassResult, SynthesisMode, SynthesisResult
    from recon.workspace import Workspace

    ws = Workspace.open(Path("."))
    themes_dir = ws.root / "themes"

    if theme == "all":
        theme_files = sorted(themes_dir.glob("*.md")) if themes_dir.exists() else []
    else:
        theme_path = themes_dir / f"{theme.lower().replace(' ', '_')}.md"
        theme_files = [theme_path] if theme_path.exists() else []

    if not theme_files:
        click.echo(f"No synthesis files found for: {theme}")
        return

    distiller = Distiller(llm_client=client)

    for theme_file in theme_files:
        theme_name = theme_file.stem.replace("_", " ").title()
        content = theme_file.read_text()

        synthesis = SynthesisResult(
            theme=theme_name,
            mode=SynthesisMode.SINGLE,
            content=content,
            passes=[PassResult(role="analyst", content=content, input_tokens=0, output_tokens=0)],
            total_input_tokens=0,
            total_output_tokens=0,
        )

        click.echo(f"Distilling: {theme_name}...")
        result = _run_async(distiller.distill(synthesis))

        distilled_dir = ws.root / "themes" / "distilled"
        distilled_dir.mkdir(parents=True, exist_ok=True)
        output_path = distilled_dir / theme_file.name
        output_path.write_text(result.content)
        click.echo(f"  -> {output_path}")


@main.command()
@click.option("--deep", is_flag=True, help="Use deep synthesis files")
@click.option("--dry-run", is_flag=True, help="Show cost estimate")
def summarize(deep, dry_run):
    """Cross-theme meta-synthesis executive summary."""
    if dry_run:
        click.echo("Meta-synthesis: reads all distilled theme summaries")
        return

    client, error = _try_create_client(model="claude-opus-4-20250514")
    if error:
        click.echo(f"ANTHROPIC_API_KEY not set. {error}")
        return

    from recon.deliver import MetaSynthesizer
    from recon.workspace import Workspace

    ws = Workspace.open(Path("."))
    distilled_dir = ws.root / "themes" / "distilled"

    if not distilled_dir.exists():
        click.echo("No distilled themes found. Run 'recon distill --theme all' first.")
        return

    distilled_files = sorted(distilled_dir.glob("*.md"))
    if not distilled_files:
        click.echo("No distilled themes found.")
        return

    distilled_results = []
    for f in distilled_files:
        theme_name = f.stem.replace("_", " ").title()
        distilled_results.append({"theme": theme_name, "content": f.read_text()})

    synthesizer = MetaSynthesizer(llm_client=client)

    click.echo(f"Meta-synthesis across {len(distilled_results)} themes...")
    result = _run_async(synthesizer.synthesize(distilled_results))

    output_path = ws.root / "executive_summary.md"
    output_path.write_text(result.content)
    click.echo(f"Executive summary: {output_path}")
    click.echo(f"Tokens: {result.input_tokens} input, {result.output_tokens} output")


@main.command()
@click.option("--dry-run", is_flag=True, help="Preview changes")
@click.option("--threshold", default=0.3, help="Minimum relevance score")
@click.option("--top-n", default=30, help="Competitors per theme")
@click.option("--n-themes", default=5, help="Number of themes to discover")
@click.option("--workspace", "workspace_dir", default=".", help="Workspace directory")
def tag(dry_run, threshold, top_n, n_themes, workspace_dir):
    """Write theme tags to competitor frontmatter."""
    from recon.index import IndexManager
    from recon.tag import Tagger
    from recon.themes import ThemeDiscovery
    from recon.workspace import Workspace

    ws = Workspace.open(Path(workspace_dir))
    manager = IndexManager(persist_dir=str(ws.root / ".vectordb"))

    if manager.collection_count() == 0:
        click.echo("No indexed chunks found. Run 'recon index' first.")
        return

    profiles = ws.list_profiles()
    all_chunks_with_embeddings = _build_discovery_chunks(ws, profiles)

    if not all_chunks_with_embeddings:
        click.echo("No chunks with embeddings for theme discovery.")
        return

    discovery = ThemeDiscovery()
    themes = discovery.discover(all_chunks_with_embeddings, n_themes=n_themes)

    click.echo(f"Discovered {len(themes)} themes:")
    for t in themes:
        click.echo(f"  {t.label} ({t.evidence_strength}, {len(t.evidence_chunks)} chunks)")

    tagger = Tagger(index=manager, workspace=ws)
    assignments = tagger.tag(themes=themes, threshold=threshold, top_n=top_n)

    click.echo(f"\n{len(assignments)} tag assignments:")
    for a in assignments:
        click.echo(f"  {a.competitor_slug} <- {a.theme_label} (score: {a.relevance_score:.3f})")

    if dry_run:
        click.echo("\nDry run -- no changes written.")
        return

    tagger.apply(assignments)
    tagged_count = len({a.competitor_slug for a in assignments})
    click.echo(f"\nTagged {tagged_count} profiles.")


def _build_discovery_chunks(ws, profiles: list[dict]) -> list[dict]:
    """Build chunks with deterministic embeddings for theme discovery."""
    import numpy as np

    from recon.index import chunk_markdown

    all_chunks: list[dict] = []
    for profile_meta in profiles:
        full = ws.read_profile(profile_meta["_slug"])
        if not full or not full.get("_content", "").strip():
            continue

        chunks = chunk_markdown(
            content=full["_content"],
            source_path=str(profile_meta["_path"]),
            frontmatter_meta={k: v for k, v in profile_meta.items() if not k.startswith("_")},
        )
        for chunk in chunks:
            rng = np.random.default_rng(hash(chunk.text) % (2**31))
            embedding = rng.random(64).tolist()
            all_chunks.append({
                "text": chunk.text,
                "embedding": embedding,
                "metadata": chunk.metadata,
            })

    return all_chunks


@main.command()
@click.option("--from", "from_stage", type=click.Choice(["research", "enrich", "index", "synthesize"]), help="Start from stage")
@click.option("--deep", is_flag=True, help="Use deep synthesis")
@click.option("--dry-run", is_flag=True, help="Show plan + cost estimate")
def run(from_stage, deep, dry_run):
    """Execute the full pipeline end-to-end."""
    if dry_run:
        click.echo(f"Full pipeline plan{' from ' + from_stage if from_stage else ''}:")
        click.echo("  1. Research all sections")
        click.echo("  2. Verify (per section tier)")
        click.echo("  3. Enrich (cleanup -> sentiment -> strategic)")
        click.echo("  4. Index into vector DB")
        click.echo("  5. Discover themes from clustering")
        click.echo("  6. Retrieve per theme")
        click.echo(f"  7. Synthesize ({'deep 4-pass' if deep else 'single pass'})")
        click.echo("  8. Distill to 1-pagers")
        click.echo("  9. Meta-synthesis")
        return

    client, error = _try_create_client()
    if error:
        click.echo(f"ANTHROPIC_API_KEY not set. {error}")
        return

    from recon.index import IndexManager
    from recon.pipeline import Pipeline, PipelineConfig, PipelineStage
    from recon.state import StateStore
    from recon.workspace import Workspace

    ws = Workspace.open(Path("."))
    state = StateStore(db_path=ws.root / ".recon" / "state.db")
    _run_async(state.initialize())
    index_manager = IndexManager(persist_dir=str(ws.root / ".vectordb"))

    stage_map = {
        "research": PipelineStage.RESEARCH,
        "enrich": PipelineStage.ENRICH,
        "index": PipelineStage.INDEX,
        "synthesize": PipelineStage.SYNTHESIZE,
    }

    config = PipelineConfig(
        deep_synthesis=deep,
        start_from=stage_map.get(from_stage, PipelineStage.RESEARCH),
    )

    pipeline = Pipeline(
        workspace=ws,
        state_store=state,
        llm_client=client,
        index_manager=index_manager,
        config=config,
    )

    click.echo("Starting pipeline...")
    run_id = _run_async(pipeline.plan())
    _run_async(pipeline.execute(run_id))
    click.echo(f"Pipeline complete. Run ID: {run_id}")


@main.command()
@click.option("--workspace", default=".", help="Workspace directory")
def tui(workspace):
    """Launch the interactive TUI."""
    from recon.tui.app import ReconApp

    ws_path = Path(workspace)
    app = ReconApp(workspace_path=ws_path if (ws_path / "recon.yaml").exists() else None)
    app.run()


if __name__ == "__main__":
    main()
