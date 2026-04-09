"""CLI entrypoint for recon."""

from __future__ import annotations

import asyncio
from pathlib import Path

import click


def _run_async(coro):
    """Run an async function from sync CLI context."""
    return asyncio.run(coro)


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
    from recon.research import ResearchPlan
    from recon.workspace import Workspace

    ws = Workspace.open(Path("."))

    if dry_run:
        profiles = ws.list_profiles()
        plan = ResearchPlan.from_schema(schema=ws.schema, competitors=[p["name"] for p in profiles])
        click.echo(f"Plan: {plan.total_tasks} tasks across {len(plan.batches)} sections")
        for batch in plan.batches:
            click.echo(f"  {batch.section_key}: {len(batch.competitors)} competitors")
        return

    click.echo("Research requires an API key. Set ANTHROPIC_API_KEY and use --headless for non-interactive mode.")


@main.command()
@click.argument("target", required=False)
@click.option("--all", "all_targets", is_flag=True, help="Enrich all eligible profiles")
@click.option("--pass", "pass_name", type=click.Choice(["cleanup", "sentiment", "strategic"]), required=True)
@click.option("--workers", default=10, help="Parallel workers")
@click.option("--dry-run", is_flag=True, help="Show what would be enriched")
def enrich(target, all_targets, pass_name, workers, dry_run):
    """Progressive enrichment passes."""
    from recon.workspace import Workspace

    ws = Workspace.open(Path("."))
    profiles = ws.list_profiles()

    if dry_run:
        eligible = [p for p in profiles if p.get("research_status") not in ("scaffold", None)]
        click.echo(f"Enrich ({pass_name}): {len(eligible)} eligible profiles")
        return

    click.echo("Enrichment requires an API key. Set ANTHROPIC_API_KEY.")


@main.command()
@click.option("--incremental/--full", default=True, help="Only index new/changed files")
def index(incremental):
    """Build local vector database from profiles."""
    from recon.index import IndexManager, chunk_markdown
    from recon.workspace import Workspace

    ws = Workspace.open(Path("."))
    manager = IndexManager(persist_dir=str(ws.root / ".vectordb"))

    if not incremental:
        manager.clear()

    profiles = ws.list_profiles()
    total_chunks = 0
    for profile_meta in profiles:
        full = ws.read_profile(profile_meta["_slug"])
        if not full or not full.get("_content", "").strip():
            continue

        chunks = chunk_markdown(
            content=full["_content"],
            source_path=str(profile_meta["_path"]),
            frontmatter_meta={k: v for k, v in profile_meta.items() if not k.startswith("_")},
        )
        manager.add_chunks(chunks)
        total_chunks += len(chunks)

    click.echo(f"Indexed {total_chunks} chunks from {len(profiles)} profiles")
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

    click.echo("Synthesis requires an API key. Set ANTHROPIC_API_KEY.")


@main.command()
@click.option("--theme", required=True, help="Theme key or 'all'")
def distill(theme):
    """Condense deep synthesis into executive 1-pagers."""
    click.echo(f"Distill requires synthesis output for: {theme}")


@main.command()
@click.option("--deep", is_flag=True, help="Use deep synthesis files")
@click.option("--dry-run", is_flag=True, help="Show cost estimate")
def summarize(deep, dry_run):
    """Cross-theme meta-synthesis executive summary."""
    click.echo("Meta-synthesis requires distilled theme summaries and API key.")


@main.command()
@click.option("--dry-run", is_flag=True, help="Preview changes")
@click.option("--threshold", default=0.3, help="Minimum relevance score")
@click.option("--top-n", default=30, help="Competitors per theme")
def tag(dry_run, threshold, top_n):
    """Write theme tags to competitor frontmatter."""
    click.echo("Tagging requires indexed profiles.")


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

    click.echo("Full pipeline requires API key. Set ANTHROPIC_API_KEY.")


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
