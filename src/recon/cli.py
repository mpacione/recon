"""CLI entrypoint for recon."""

import click


@click.group()
@click.version_option()
def main():
    """recon — Competitive intelligence CLI."""
    pass


@main.command()
@click.argument("directory", default=".")
def init(directory):
    """Initialize a new recon workspace."""
    click.echo(f"Initializing workspace in {directory}...")
    # TODO: Phase 1 implementation


@main.command()
@click.argument("name")
@click.option("--research", is_flag=True, help="Immediately run P1 research after scaffolding")
def add(name, research):
    """Add a new competitor profile."""
    click.echo(f"Adding competitor: {name}")
    # TODO: Phase 1 implementation


@main.command()
def status():
    """Show workspace status dashboard."""
    click.echo("Workspace status...")
    # TODO: Phase 1 implementation


@main.command()
@click.argument("target", required=False)
@click.option("--all", "all_targets", is_flag=True, help="Research all scaffold profiles")
@click.option("--workers", default=5, help="Parallel workers")
@click.option("--dry-run", is_flag=True, help="Show what would be researched")
def research(target, all_targets, workers, dry_run):
    """Run LLM-powered web research on a competitor."""
    click.echo(f"Researching: {target or 'all'}")
    # TODO: Phase 2 implementation


@main.command()
@click.argument("target", required=False)
@click.option("--all", "all_targets", is_flag=True, help="Enrich all eligible profiles")
@click.option("--pass", "pass_name", type=click.Choice(["cleanup", "sentiment", "strategic"]), required=True)
@click.option("--workers", default=10, help="Parallel workers")
@click.option("--dry-run", is_flag=True, help="Show what would be enriched")
def enrich(target, all_targets, pass_name, workers, dry_run):
    """Progressive enrichment passes."""
    click.echo(f"Enriching ({pass_name}): {target or 'all'}")
    # TODO: Phase 2 implementation


@main.command()
@click.option("--incremental", is_flag=True, help="Only index new/changed files")
def index(incremental):
    """Build local vector database from profiles."""
    click.echo("Indexing profiles into ChromaDB...")
    # TODO: Phase 3 implementation


@main.command()
@click.option("--theme", required=True, help="Theme key or 'all'")
@click.option("--list", "list_themes", is_flag=True, help="List available themes")
def retrieve(theme, list_themes):
    """Semantic retrieval of relevant chunks per theme."""
    click.echo(f"Retrieving for theme: {theme}")
    # TODO: Phase 3 implementation


@main.command()
@click.option("--theme", required=True, help="Theme key or 'all'")
@click.option("--deep", is_flag=True, help="4-pass deep synthesis")
@click.option("--dry-run", is_flag=True, help="Show context size + cost estimate")
def synthesize(theme, deep, dry_run):
    """Generate theme analysis documents."""
    mode = "deep (4-pass)" if deep else "single pass"
    click.echo(f"Synthesizing ({mode}): {theme}")
    # TODO: Phase 4 implementation


@main.command()
@click.option("--theme", required=True, help="Theme key or 'all'")
def distill(theme):
    """Condense deep synthesis into executive 1-pagers."""
    click.echo(f"Distilling: {theme}")
    # TODO: Phase 4 implementation


@main.command()
@click.option("--deep", is_flag=True, help="Use deep synthesis files")
@click.option("--dry-run", is_flag=True, help="Show cost estimate")
def summarize(deep, dry_run):
    """Cross-theme meta-synthesis executive summary."""
    click.echo("Running meta-synthesis...")
    # TODO: Phase 4 implementation


@main.command()
@click.option("--dry-run", is_flag=True, help="Preview changes")
@click.option("--threshold", default=0.3, help="Minimum relevance score")
@click.option("--top-n", default=30, help="Competitors per theme")
def tag(dry_run, threshold, top_n):
    """Write theme tags to competitor frontmatter."""
    click.echo("Tagging competitors with themes...")
    # TODO: Phase 3 implementation


@main.command()
@click.option("--from", "from_stage", type=click.Choice(["collect", "index", "synthesize"]), help="Start from stage")
@click.option("--deep", is_flag=True, help="Use deep synthesis")
@click.option("--dry-run", is_flag=True, help="Show plan + cost estimate")
def run(from_stage, deep, dry_run):
    """Execute the full pipeline end-to-end."""
    click.echo(f"Running full pipeline{' from ' + from_stage if from_stage else ''}...")
    # TODO: Phase 5 implementation


if __name__ == "__main__":
    main()
