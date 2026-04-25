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


@click.group(invoke_without_command=True)
@click.version_option(package_name="recon-cli", prog_name="recon")
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"], case_sensitive=False),
    default="INFO",
    help="Log verbosity. Use DEBUG to diagnose hangs or unexpected behavior.",
)
@click.option(
    "--log-file",
    type=click.Path(),
    default=None,
    help="Log file path. Default: ~/.recon/logs/recon.log",
)
@click.pass_context
def main(ctx, log_level, log_file):
    """recon -- Competitive intelligence CLI.

    When run without a subcommand, prints the ``recon status``
    dashboard for the workspace at the current directory (or help if
    there's no workspace there). Matches the shape of ``btop`` /
    ``abtop --once``.
    """
    from recon.logging import configure_logging, get_logger
    from recon.cli_ui import build_console
    from recon.cli_ui.console import install_tracebacks

    log_file_path = (
        Path.home() / ".recon" / "logs" / "recon.log"
        if log_file is None
        else Path(log_file)
    )

    configure_logging(level=log_level, log_file=log_file_path)
    _log = get_logger("cli")
    # Capture command arguments for diagnostic context
    args_repr = " ".join(f"{k}={v}" for k, v in ctx.params.items() if k not in {"log_level", "log_file"})
    _log.info(
        "recon CLI invoked subcommand=%s log_level=%s %s",
        ctx.invoked_subcommand,
        log_level,
        args_repr,
    )
    ctx.ensure_object(dict)
    ctx.obj["log_file"] = log_file_path
    ctx.obj["console"] = build_console()
    install_tracebacks(ctx.obj["console"])

    # Leading blank line so styled output has breathing room between
    # the invoking shell prompt and the first card. Skip for `--help`
    # / `--version` paths (click short-circuits those before we get
    # here anyway, so this is just belt-and-braces).
    if ctx.obj["console"].is_terminal:
        ctx.obj["console"].print()

    # Bare `recon` → v4 dashboard snapshot when we're inside a
    # workspace; recent-projects home when we're not. Mirrors the web
    # UI's home behavior (projects list) vs project behavior (tabs).
    if ctx.invoked_subcommand is None:
        try:
            ctx.invoke(ctx.command.get_command(ctx, "status"))
        except click.ClickException:
            from recon.cli_ui.views import render_home
            render_home(ctx.obj["console"])


@main.command()
@click.argument("directory", default=".")
@click.option("--domain", default=None, help="Research domain (e.g., 'Developer Tools')")
@click.option("--company", default=None, help="Your company name")
@click.option("--products", default=None, help="Your products (comma-separated)")
@click.option("--headless", is_flag=True, help="Non-interactive mode (Click prompts instead of TUI)")
@click.option("--wizard", is_flag=True, hidden=True, help="(deprecated, use --headless for prompt-based flow)")
def init(directory, domain, company, products, headless, wizard):
    """Initialize a new recon workspace."""
    if headless or wizard or (domain and company and products):
        if wizard:
            _run_headless_wizard(Path(directory))
        else:
            _run_headless_init(Path(directory), domain, company, products)
        return

    _run_tui_wizard(Path(directory))


def _run_headless_init(root: Path, domain: str | None, company: str | None, products: str | None) -> None:
    """Non-interactive init using Click prompts."""
    from recon.workspace import Workspace

    domain = domain or click.prompt("Domain")
    company = company or click.prompt("Company name")
    products = products or click.prompt("Products (comma-separated)")

    product_list = [p.strip() for p in products.split(",")]
    ws = Workspace.init(
        root=root,
        domain=domain,
        company_name=company,
        products=product_list,
    )
    click.echo(f"Workspace initialized at {ws.root}")


def _run_tui_wizard(root: Path) -> None:
    """Launch ReconApp starting on the WizardScreen. The user never
    leaves the app -- wizard completes, workspace is created, dashboard
    loads, all in one continuous flow."""
    from recon.tui.app import ReconApp

    app = ReconApp(initial_wizard_dir=root)
    app.run()


def _run_headless_wizard(root: Path) -> None:
    """Run the guided schema wizard for workspace creation."""
    import yaml

    from recon.wizard import DecisionContext, DefaultSections, WizardState

    state = WizardState()

    click.echo("-- recon workspace wizard --\n")

    company_name = click.prompt("Company name")
    products_raw = click.prompt("Products (comma-separated)")
    products = [p.strip() for p in products_raw.split(",")]
    domain = click.prompt("Domain description")

    contexts = list(DecisionContext)
    click.echo("\nDecision contexts:")
    for i, ctx in enumerate(contexts, 1):
        click.echo(f"  {i}. {ctx.value}")

    ctx_input = click.prompt("Select context (number)", type=int)
    selected_ctx = contexts[min(ctx_input, len(contexts)) - 1]

    own_product = click.confirm("Research your own products through the same lens?", default=False)

    state.set_identity(
        company_name=company_name,
        products=products,
        domain=domain,
        decision_contexts=[selected_ctx],
        own_product=own_product,
    )
    state.advance()

    click.echo(f"\nRecommended sections ({len(state.selected_section_keys)}):")
    for section in DefaultSections.ALL:
        marker = "[x]" if section["key"] in state.selected_section_keys else "[ ]"
        click.echo(f"  {marker} {section['title']} -- {section['description']}")

    section_input = click.prompt(
        "Toggle sections (comma-separated keys, or Enter to accept)",
        default="",
    )
    if section_input.strip():
        for key in section_input.split(","):
            state.toggle_section(key.strip())

    state.advance()

    click.echo("\nSource preferences (Enter to accept defaults):")
    source_input = click.prompt("Customize sources? (comma-separated section keys, or Enter)", default="")
    if source_input.strip():
        for key in source_input.split(","):
            key = key.strip()
            sources = state.get_source_preferences(key)
            click.echo(f"  {key}: primary={sources['primary']}")

    state.advance()

    click.echo("\n-- Review --")
    click.echo(f"Domain: {state.domain}")
    click.echo(f"Company: {state.company_name}")
    click.echo(f"Products: {', '.join(state.products)}")
    click.echo(f"Own-product research: {'Yes' if state.own_product else 'No'}")
    click.echo(f"Sections: {len(state.selected_section_keys)}")
    for section in DefaultSections.ALL:
        if section["key"] in state.selected_section_keys:
            click.echo(f"  {section['title']}")

    confirm = click.confirm("\nCreate workspace?", default=True)
    if not confirm:
        click.echo("Cancelled.")
        return

    schema_dict = state.to_schema_dict()

    root.mkdir(parents=True, exist_ok=True)
    (root / "recon.yaml").write_text(yaml.dump(schema_dict, default_flow_style=False, sort_keys=False))

    from recon.workspace import Workspace

    ws = Workspace.init(root=root)
    click.echo(f"Workspace initialized at {ws.root}")


@main.command()
@click.argument("name", required=False)
@click.option("--from-list", "list_file", type=click.Path(exists=True), help="Add competitors from a text file (one per line)")
@click.option("--own-product", is_flag=True, help="Mark as own product (researched from external perspective)")
@click.option("--path", default=None, help="Workspace directory (default: cwd)")
@click.pass_context
def add(ctx, name, list_file, own_product, path):
    """Add a new competitor profile."""
    from recon.cli_ui.messages import info, success, warn

    console = ctx.obj["console"]
    ws = _open_cwd_workspace(path)

    if list_file:
        names = [
            line.strip()
            for line in Path(list_file).read_text().splitlines()
            if line.strip()
        ]
        created = 0
        for n in names:
            try:
                ws.create_profile(n, own_product=own_product)
                info(console, "created", detail=n)
                created += 1
            except FileExistsError:
                warn(console, f"skipped (exists): {n}")
        success(console, f"{created} profile{'s' if created != 1 else ''} created")
        return

    if not name:
        raise click.ClickException("provide a name or --from-list")

    profile_path = ws.create_profile(name, own_product=own_product)
    success(console, "created profile", detail=str(profile_path))


def _open_cwd_workspace(path: str | None) -> "Workspace":
    """Open a workspace at ``--path`` (or cwd). Raises a clean click
    error if there's no recon.yaml there, so users don't get a raw
    FileNotFoundError."""
    from recon.workspace import Workspace

    root = Path(path or ".").resolve()
    if not (root / "recon.yaml").exists():
        raise click.ClickException(
            f"no recon.yaml in {root} — run `recon init` first or pass --path",
        )
    return Workspace.open(root)


def _emit_json(console, data) -> None:
    """Serialize a Pydantic model (or dict) as indented JSON to stdout."""
    import json

    if hasattr(data, "model_dump_json"):
        click.echo(data.model_dump_json(indent=2))
    else:
        click.echo(json.dumps(data, indent=2, default=str))


@main.command()
@click.option("--path", default=None, help="Workspace directory (default: cwd)")
@click.option("--json", "as_json", is_flag=True, help="Emit JSON instead of styled output")
@click.pass_context
def status(ctx, path, as_json):
    """v4 workspace dashboard — all tabs stacked.

    Run from inside a workspace (`cd ~/recon-workspaces/foo`) or pass
    ``--path``. With ``--json`` emits the full DTO under per-tab keys
    for agent consumption.
    """
    from recon.cli_ui.views import render_status

    ws = _open_cwd_workspace(path)
    console = ctx.obj["console"]
    data = render_status(ws, console)
    if as_json:
        _emit_json(console, data)


@main.command()
@click.option("--path", default=None, help="Workspace directory (default: cwd)")
@click.option("--json", "as_json", is_flag=True, help="Emit JSON instead of styled output")
@click.pass_context
def plan(ctx, path, as_json):
    """Research brief + model selector + cost estimate (v4 PLAN tab)."""
    from recon.cli_ui.views import render_plan

    ws = _open_cwd_workspace(path)
    console = ctx.obj["console"]
    if as_json:
        from recon.cli_ui.views.plan import plan_data

        _emit_json(console, plan_data(ws))
        return
    render_plan(ws, console)


@main.command()
@click.option("--path", default=None, help="Workspace directory (default: cwd)")
@click.option("--json", "as_json", is_flag=True, help="Emit JSON instead of styled output")
@click.pass_context
def schema(ctx, path, as_json):
    """Dossier schema sections (v4 SCHEMA tab)."""
    from recon.cli_ui.views import render_schema

    ws = _open_cwd_workspace(path)
    console = ctx.obj["console"]
    if as_json:
        from recon.cli_ui.views.schema import schema_data

        _emit_json(console, schema_data(ws))
        return
    render_schema(ws, console)


@main.command()
@click.option("--path", default=None, help="Workspace directory (default: cwd)")
@click.option("--json", "as_json", is_flag=True, help="Emit JSON instead of styled output")
@click.pass_context
def comps(ctx, path, as_json):
    """Competitor list with research status (v4 COMP'S tab)."""
    from recon.cli_ui.views import render_comps

    ws = _open_cwd_workspace(path)
    console = ctx.obj["console"]
    if as_json:
        from recon.cli_ui.views.comps import comps_data

        _emit_json(console, comps_data(ws))
        return
    render_comps(ws, console)


@main.command()
@click.option("--path", default=None, help="Workspace directory (default: cwd)")
@click.option("--json", "as_json", is_flag=True, help="Emit JSON instead of styled output")
@click.pass_context
def agents(ctx, path, as_json):
    """Run history — each row is one research run (v4 AGENTS tab)."""
    from recon.cli_ui.views import render_agents

    ws = _open_cwd_workspace(path)
    console = ctx.obj["console"]
    if as_json:
        from recon.cli_ui.views.agents import agents_data

        _emit_json(console, agents_data(ws))
        return
    render_agents(ws, console)


@main.command()
@click.option("--path", default=None, help="Workspace directory (default: cwd)")
@click.option("--json", "as_json", is_flag=True, help="Emit JSON instead of styled output")
@click.pass_context
def output(ctx, path, as_json):
    """Output files + exec summary preview (v4 OUTPUT tab)."""
    from recon.cli_ui.views import render_output

    ws = _open_cwd_workspace(path)
    console = ctx.obj["console"]
    if as_json:
        from recon.cli_ui.views.output import output_data

        _emit_json(console, output_data(ws))
        return
    render_output(ws, console)


@main.command()
@click.argument("target", required=False)
@click.option("--all", "all_targets", is_flag=True, help="Research all scaffold profiles")
@click.option("--workers", default=5, help="Parallel workers")
@click.option("--dry-run", is_flag=True, help="Show what would be researched")
@click.option("--headless", is_flag=True, help="JSON output, no live view")
@click.option("--path", default=None, help="Workspace directory (default: cwd)")
@click.pass_context
def research(ctx, target, all_targets, workers, dry_run, headless, path):
    """Run LLM-powered research on competitors.

    Pass a competitor name to research just that one, or --all to research
    every profile in the workspace. Live progress renders in a
    ``▓▒░``-bar card that updates per-competitor as the pipeline runs.
    """
    from rich.text import Text

    from recon.cli_ui.live import LiveRunMonitor
    from recon.cli_ui.renderables import card, tab_breadcrumb
    from recon.research import ResearchOrchestrator, ResearchPlan

    console = ctx.obj["console"]
    ws = _open_cwd_workspace(path)

    if not target and not all_targets:
        raise click.ClickException("Specify a competitor name or pass --all.")
    if target and all_targets:
        raise click.ClickException("Cannot combine a target argument with --all.")

    profiles = ws.list_profiles()
    all_names = [p["name"] for p in profiles]

    if target:
        resolved = next((n for n in all_names if n.lower() == target.lower()), None)
        if resolved is None:
            raise click.ClickException(
                f"Unknown competitor: {target}. Available: {', '.join(all_names) or '(none)'}"
            )
        selected_names: list[str] | None = [resolved]
    else:
        selected_names = None  # None -> research everyone

    if dry_run:
        plan_targets = selected_names if selected_names is not None else all_names
        plan = ResearchPlan.from_schema(schema=ws.schema, competitors=plan_targets)
        lines = [
            Text.assemble(
                (f"{plan.total_tasks}", "accent"),
                (" tasks across ", "body"),
                (f"{len(plan.batches)}", "accent"),
                (" sections", "body"),
            ),
            Text(""),
        ]
        for batch in plan.batches:
            lines.append(
                Text.assemble(
                    ("  ", "body"),
                    (batch.section_key, "accent"),
                    ("  ·  ", "subdued"),
                    (f"{len(batch.competitors)} competitors", "body"),
                )
            )
        console.print(tab_breadcrumb(active="agents"))
        console.print()
        from rich.console import Group
        console.print(
            card(
                Group(*lines),
                title="RESEARCH · DRY RUN",
                meta=f"targets: {len(plan_targets)}",
                footer="run it:  recon research" + ("" if all_targets else f" {target}"),
            )
        )
        return

    client, error = _try_create_client()
    if error:
        raise click.ClickException(f"ANTHROPIC_API_KEY not set. {error}")

    orchestrator = ResearchOrchestrator(
        workspace=ws,
        llm_client=client,
        max_workers=workers,
    )

    label = f"'{selected_names[0]}'" if selected_names else "all profiles"

    if headless:
        # Machine-friendly mode: no Live renderable, emit a single JSON
        # summary at the end.
        import json
        results = _run_async(orchestrator.research_all(targets=selected_names))
        click.echo(json.dumps({
            "label": label,
            "sections": len(results),
            "input_tokens": sum(r.get("tokens", {}).get("input", 0) for r in results),
            "output_tokens": sum(r.get("tokens", {}).get("output", 0) for r in results),
        }, indent=2))
        return

    with LiveRunMonitor(console, title=f"RESEARCH · {label.upper()}") as monitor:
        _run_async(orchestrator.research_all(targets=selected_names))
    monitor.flush_summary()


def _resolve_target(ws, target: str | None, all_targets: bool) -> tuple[list[str] | None, str | None]:
    """Shared target-resolution helper. Returns (names, error_message)."""
    if not target and not all_targets:
        return None, "Specify a competitor name or pass --all."
    if target and all_targets:
        return None, "Cannot combine a target argument with --all."

    profiles = ws.list_profiles()
    all_names = [p["name"] for p in profiles]
    if target:
        resolved = next(
            (name for name in all_names if name.lower() == target.lower()),
            None,
        )
        if resolved is None:
            available = ", ".join(all_names) or "(none)"
            return None, f"Unknown competitor: {target}. Available: {available}"
        return [resolved], None
    return None, None  # None = research everyone


@main.command()
@click.argument("target", required=False)
@click.option("--all", "all_targets", is_flag=True, help="Diff every profile")
@click.option("--max-age-days", default=30, help="Staleness threshold in days")
@click.option("--workers", default=5, help="Parallel workers")
@click.option("--dry-run", is_flag=True, help="Show what would be re-researched")
@click.option("--path", default=None, help="Workspace directory (default: cwd)")
@click.pass_context
def diff(ctx, target, all_targets, max_age_days, workers, dry_run, path):
    """Re-research sections older than --max-age-days.

    Cheaper than a full research pass — only sections whose
    ``researched_at`` frontmatter is older than the threshold.
    """
    from recon.cli_ui.live import LiveRunMonitor
    from recon.cli_ui.messages import info
    from recon.research import ResearchOrchestrator

    console = ctx.obj["console"]
    ws = _open_cwd_workspace(path)

    selected_names, err = _resolve_target(ws, target, all_targets)
    if err:
        raise click.ClickException(err)

    if dry_run:
        n = len(selected_names) if selected_names else len(ws.list_profiles())
        info(console, f"Diff plan · stale sections older than {max_age_days}d across {n} profile(s)")
        return

    client, error = _try_create_client()
    if error:
        raise click.ClickException(f"ANTHROPIC_API_KEY not set. {error}")

    orchestrator = ResearchOrchestrator(workspace=ws, llm_client=client, max_workers=workers)
    label = f"'{selected_names[0]}'" if selected_names else "all profiles"

    with LiveRunMonitor(console, title=f"DIFF · {label.upper()} · >{max_age_days}d") as monitor:
        _run_async(
            orchestrator.research_all(
                targets=selected_names,
                stale_only=True,
                max_age_days=max_age_days,
            ),
        )
    monitor.flush_summary()


@main.command()
@click.argument("target", required=False)
@click.option("--all", "all_targets", is_flag=True, help="Rerun across every profile")
@click.option("--workers", default=5, help="Parallel workers")
@click.option("--dry-run", is_flag=True, help="Show what would be re-run")
@click.option("--path", default=None, help="Workspace directory (default: cwd)")
@click.pass_context
def rerun(ctx, target, all_targets, workers, dry_run, path):
    """Re-research failed / missing sections."""
    from recon.cli_ui.live import LiveRunMonitor
    from recon.cli_ui.messages import info
    from recon.research import ResearchOrchestrator

    console = ctx.obj["console"]
    ws = _open_cwd_workspace(path)

    selected_names, err = _resolve_target(ws, target, all_targets)
    if err:
        raise click.ClickException(err)

    if dry_run:
        n = len(selected_names) if selected_names else len(ws.list_profiles())
        info(console, f"rerun plan · failed/missing sections across {n} profile(s)")
        return

    client, error = _try_create_client()
    if error:
        raise click.ClickException(f"ANTHROPIC_API_KEY not set. {error}")

    orchestrator = ResearchOrchestrator(workspace=ws, llm_client=client, max_workers=workers)
    label = f"'{selected_names[0]}'" if selected_names else "all profiles"

    with LiveRunMonitor(console, title=f"RERUN · {label.upper()}") as monitor:
        _run_async(orchestrator.research_all(targets=selected_names, failed_only=True))
    monitor.flush_summary()


@main.command()
@click.argument("target", required=False)
@click.option("--all", "all_targets", is_flag=True, help="Enrich all eligible profiles")
@click.option("--pass", "pass_name", type=click.Choice(["cleanup", "sentiment", "strategic"]), required=True)
@click.option("--workers", default=10, help="Parallel workers")
@click.option("--dry-run", is_flag=True, help="Show what would be enriched")
@click.option("--path", default=None, help="Workspace directory (default: cwd)")
@click.pass_context
def enrich(ctx, target, all_targets, pass_name, workers, dry_run, path):
    """Progressive enrichment passes (cleanup → sentiment → strategic)."""
    from recon.cli_ui.live import LiveRunMonitor
    from recon.cli_ui.messages import info, success
    from recon.enrichment import EnrichmentOrchestrator, EnrichmentPass

    console = ctx.obj["console"]
    ws = _open_cwd_workspace(path)

    selected_names, err = _resolve_target(ws, target, all_targets)
    if err:
        raise click.ClickException(err)

    if dry_run:
        profiles = ws.list_profiles()
        eligible = [
            p for p in profiles
            if p.get("research_status") not in ("scaffold", None)
            and (selected_names is None or p["name"] in selected_names)
        ]
        info(console, f"enrich ({pass_name})", detail=f"{len(eligible)} eligible profiles")
        return

    client, error = _try_create_client()
    if error:
        raise click.ClickException(f"ANTHROPIC_API_KEY not set. {error}")

    pass_enum = EnrichmentPass(pass_name)
    orchestrator = EnrichmentOrchestrator(
        workspace=ws,
        llm_client=client,
        enrichment_pass=pass_enum,
        max_workers=workers,
    )

    label = f"'{selected_names[0]}'" if selected_names else "all profiles"

    with LiveRunMonitor(console, title=f"ENRICH · {pass_name.upper()} · {label.upper()}") as monitor:
        results = _run_async(orchestrator.enrich_all(targets=selected_names))
    monitor.flush_summary()

    total_input = sum(r.get("tokens", {}).get("input", 0) for r in results)
    total_output = sum(r.get("tokens", {}).get("output", 0) for r in results)
    success(console, f"{len(results)} profiles enriched")
    info(console, f"tokens · in {total_input}  out {total_output}")


@main.command()
@click.argument("target", required=False)
@click.option("--all", "all_targets", is_flag=True, help="Verify every researched profile")
@click.option(
    "--tier",
    type=click.Choice(["standard", "verified", "deep"]),
    default=None,
    help="Override section tiers from the schema",
)
@click.option("--dry-run", is_flag=True, help="Show what would be verified")
@click.option("--path", default=None, help="Workspace directory (default: cwd)")
@click.pass_context
def verify(ctx, target, all_targets, tier, dry_run, path):
    """Verify research sources via multi-agent consensus."""
    from recon.cli_ui.live import LiveRunMonitor
    from recon.cli_ui.messages import info, success, warn
    from recon.pipeline import Pipeline, PipelineConfig, PipelineStage
    from recon.state import StateStore

    console = ctx.obj["console"]
    ws = _open_cwd_workspace(path)

    selected_names, err = _resolve_target(ws, target, all_targets)
    if err:
        raise click.ClickException(err)

    if dry_run:
        schema = ws.schema
        if schema is None:
            raise click.ClickException("no schema loaded; cannot plan verification")
        per_section = [(s.key, (tier or s.verification_tier.value)) for s in schema.sections]
        to_verify = [(k, t) for k, t in per_section if t != "standard"]
        info(console, f"verify plan · {len(to_verify)} section(s) above standard tier")
        for key, eff_tier in to_verify:
            info(console, f"  {key}", detail=eff_tier)
        return

    client, error = _try_create_client()
    if error:
        raise click.ClickException(f"ANTHROPIC_API_KEY not set. {error}")

    state = StateStore(db_path=ws.root / ".recon" / "state.db")
    _run_async(state.initialize())

    config = PipelineConfig(
        verification_enabled=True,
        start_from=PipelineStage.VERIFY,
        stop_after=PipelineStage.VERIFY,
        targets=selected_names,
    )

    if tier is not None and ws.schema is not None:
        # Temporarily flip every section's tier — pipeline reads
        # schema.sections at stage execution, so in-memory mutation works.
        from recon.schema import VerificationTier
        override = VerificationTier(tier)
        for section in ws.schema.sections:
            object.__setattr__(section, "verification_tier", override)

    pipeline = Pipeline(workspace=ws, state_store=state, llm_client=client, config=config)
    label = f"'{selected_names[0]}'" if selected_names else "all profiles"

    with LiveRunMonitor(console, title=f"VERIFY · {label.upper()}") as monitor:
        run_id = _run_async(pipeline.plan())
        _run_async(pipeline.execute(run_id))
    monitor.flush_summary()

    outcomes = pipeline.verification_results
    if not outcomes:
        warn(console, "no sections required verification (check schema tiers)")
        return

    success(console, f"verified {len(outcomes)} section(s)")
    for outcome in outcomes:
        confirmed = sum(1 for s in outcome.source_results if s.status.value == "confirmed")
        disputed = sum(1 for s in outcome.source_results if s.status.value == "disputed")
        unverified = sum(1 for s in outcome.source_results if s.status.value == "unverified")
        info(
            console,
            f"{outcome.competitor_name} / {outcome.section_key} ({outcome.tier})",
            detail=(
                f"{confirmed} confirmed · {disputed} disputed · {unverified} unverified"
            ),
        )


@main.command()
@click.option("--incremental/--full", default=True, help="Only index new/changed files")
@click.option("--workspace", "workspace_dir", default=".", help="Workspace directory")
@click.pass_context
def index(ctx, incremental, workspace_dir):
    """Build local vector database from profiles."""
    from recon.cli_ui.messages import info, success
    from recon.incremental import IncrementalIndexer
    from recon.index import IndexManager
    from recon.state import StateStore

    console = ctx.obj["console"]
    ws = _open_cwd_workspace(workspace_dir if workspace_dir != "." else None)
    manager = IndexManager(persist_dir=str(ws.root / ".vectordb"))
    try:
        state = StateStore(db_path=ws.root / ".recon" / "state.db")
        _run_async(state.initialize())

        if not incremental:
            info(console, "full reindex · clearing collection")
            manager.clear()

        indexer = IncrementalIndexer(workspace=ws, index_manager=manager, state_store=state)
        result = _run_async(indexer.index(force=not incremental))

        success(
            console,
            f"Indexed {result.indexed} files",
            detail=f"{result.total_chunks} chunks · skipped {result.skipped} unchanged",
        )
        info(console, "collection size", detail=str(manager.collection_count()))
    finally:
        manager.close()


@main.command()
@click.option("--query", required=True, help="Search query")
@click.option("--n-results", default=10, help="Number of results")
@click.option("--path", default=None, help="Workspace directory (default: cwd)")
@click.pass_context
def retrieve(ctx, query, n_results, path):
    """Semantic retrieval of relevant chunks."""
    from rich.text import Text

    from recon.cli_ui.renderables import card
    from recon.index import IndexManager

    console = ctx.obj["console"]
    ws = _open_cwd_workspace(path)
    manager = IndexManager(persist_dir=str(ws.root / ".vectordb"))
    results = manager.retrieve(query, n_results=n_results)

    if not results:
        console.print(
            card(
                Text(f"No matches for '{query}'. Try running `recon index` first.", style="subdued"),
                title=f"RETRIEVAL · {query}",
                meta="0 results",
            ),
        )
        return

    for i, result in enumerate(results, 1):
        meta = result.get("metadata", {})
        body = Text.from_markup(
            f"[accent]{meta.get('name', 'Unknown')}[/] "
            f"[subdued]/[/] "
            f"[body]{meta.get('section', 'Unknown')}[/]\n\n"
            f"{result['text'][:500]}"
        )
        console.print(
            card(
                body,
                title=f"RESULT {i}",
                meta=f"distance {result.get('distance', 0):.4f}",
            ),
        )
        console.print()


@main.command()
@click.option("--theme", required=True, help="Theme to synthesize")
@click.option("--deep", is_flag=True, help="4-pass deep synthesis")
@click.option("--dry-run", is_flag=True, help="Show context size + cost estimate")
@click.option("--path", default=None, help="Workspace directory (default: cwd)")
@click.pass_context
def synthesize(ctx, theme, deep, dry_run, path):
    """Generate theme analysis documents."""
    from recon.cli_ui.messages import info, success

    console = ctx.obj["console"]

    if dry_run:
        info(console, f"synthesis ({'deep 4-pass' if deep else 'single pass'}): {theme}")
        info(console, "requires indexed profiles + ANTHROPIC_API_KEY")
        return

    client, error = _try_create_client(
        model="claude-opus-4-20250514" if deep else "claude-sonnet-4-20250514",
    )
    if error:
        raise click.ClickException(f"ANTHROPIC_API_KEY not set. {error}")

    from recon.index import IndexManager
    from recon.synthesis import SynthesisEngine, SynthesisMode

    ws = _open_cwd_workspace(path)
    manager = IndexManager(persist_dir=str(ws.root / ".vectordb"))

    chunks = manager.retrieve(theme, n_results=50)
    if not chunks:
        raise click.ClickException("no indexed chunks — run `recon index` first")

    mode = SynthesisMode.DEEP if deep else SynthesisMode.SINGLE
    engine = SynthesisEngine(llm_client=client)

    info(console, f"synthesizing theme · {theme}", detail=f"{mode.value} mode, {len(chunks)} chunks")
    result = _run_async(engine.synthesize(theme=theme, chunks=chunks, mode=mode))

    themes_dir = ws.root / "themes"
    themes_dir.mkdir(exist_ok=True)
    output_path = themes_dir / f"{theme.lower().replace(' ', '_')}.md"
    output_path.write_text(result.content)

    success(console, "synthesis complete", detail=str(output_path))
    info(console, f"tokens · in {result.total_input_tokens}  out {result.total_output_tokens}")


@main.command()
@click.option("--theme", required=True, help="Theme key or 'all'")
@click.option("--path", default=None, help="Workspace directory (default: cwd)")
@click.pass_context
def distill(ctx, theme, path):
    """Condense deep synthesis into executive 1-pagers."""
    from recon.cli_ui.messages import info, success

    console = ctx.obj["console"]
    client, error = _try_create_client()
    if error:
        raise click.ClickException(f"ANTHROPIC_API_KEY not set. {error}")

    from recon.deliver import Distiller
    from recon.synthesis import PassResult, SynthesisMode, SynthesisResult

    ws = _open_cwd_workspace(path)
    themes_dir = ws.root / "themes"

    if theme == "all":
        theme_files = sorted(themes_dir.glob("*.md")) if themes_dir.exists() else []
    else:
        theme_path = themes_dir / f"{theme.lower().replace(' ', '_')}.md"
        theme_files = [theme_path] if theme_path.exists() else []

    if not theme_files:
        raise click.ClickException(f"no synthesis files found for: {theme}")

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

        info(console, "distilling", detail=theme_name)
        result = _run_async(distiller.distill(synthesis))

        distilled_dir = ws.root / "themes" / "distilled"
        distilled_dir.mkdir(parents=True, exist_ok=True)
        output_path = distilled_dir / theme_file.name
        output_path.write_text(result.content)
        success(console, "wrote", detail=str(output_path))


@main.command()
@click.option("--deep", is_flag=True, help="Use deep synthesis files")
@click.option("--dry-run", is_flag=True, help="Show cost estimate")
@click.option("--path", default=None, help="Workspace directory (default: cwd)")
@click.pass_context
def summarize(ctx, deep, dry_run, path):
    """Cross-theme meta-synthesis executive summary."""
    from recon.cli_ui.messages import info, success

    console = ctx.obj["console"]

    if dry_run:
        info(console, "meta-synthesis", detail="reads all distilled theme summaries")
        return

    client, error = _try_create_client(model="claude-opus-4-20250514")
    if error:
        raise click.ClickException(f"ANTHROPIC_API_KEY not set. {error}")

    from recon.deliver import MetaSynthesizer

    ws = _open_cwd_workspace(path)
    distilled_dir = ws.root / "themes" / "distilled"

    if not distilled_dir.exists():
        raise click.ClickException("no distilled themes — run `recon distill --theme all` first")

    distilled_files = sorted(distilled_dir.glob("*.md"))
    if not distilled_files:
        raise click.ClickException("no distilled themes found")

    distilled_results = []
    for f in distilled_files:
        theme_name = f.stem.replace("_", " ").title()
        distilled_results.append({"theme": theme_name, "content": f.read_text()})

    synthesizer = MetaSynthesizer(llm_client=client)

    info(console, f"meta-synthesis across {len(distilled_results)} themes")
    result = _run_async(synthesizer.synthesize(distilled_results))

    output_path = ws.root / "executive_summary.md"
    output_path.write_text(result.content)
    success(console, "executive summary", detail=str(output_path))
    info(console, f"tokens · in {result.input_tokens}  out {result.output_tokens}")


@main.command()
@click.option("--dry-run", is_flag=True, help="Preview changes")
@click.option("--threshold", default=0.3, help="Minimum relevance score")
@click.option("--top-n", default=30, help="Competitors per theme")
@click.option("--n-themes", default=5, help="Number of themes to discover")
@click.option("--workspace", "workspace_dir", default=".", help="Workspace directory")
@click.pass_context
def tag(ctx, dry_run, threshold, top_n, n_themes, workspace_dir):
    """Write theme tags to competitor frontmatter."""
    from recon.index import IndexManager
    from recon.tag import Tagger
    from recon.themes import ThemeDiscovery

    ws = _open_cwd_workspace(workspace_dir if workspace_dir != "." else None)
    manager = IndexManager(persist_dir=str(ws.root / ".vectordb"))

    from recon.cli_ui.messages import info, success, warn

    console = ctx.obj["console"] if hasattr(ctx, "obj") and ctx.obj else None

    if manager.collection_count() == 0:
        raise click.ClickException("no indexed chunks — run `recon index` first")

    from recon.themes import build_workspace_chunks

    all_chunks_with_embeddings = build_workspace_chunks(ws)

    if not all_chunks_with_embeddings:
        raise click.ClickException("no chunks with embeddings for theme discovery")

    llm_for_labels, _label_err = _try_create_client(model="claude-haiku-4-5")
    if _label_err and console is not None:
        warn(console, f"using mechanical theme labels ({_label_err})")
    import asyncio

    discovery = ThemeDiscovery(llm_client=llm_for_labels)
    themes = asyncio.run(discovery.discover(all_chunks_with_embeddings, n_themes=n_themes))

    if console is not None:
        success(console, f"Discovered {len(themes)} themes")
        for t in themes:
            info(console, t.label, detail=f"{t.evidence_strength} · {len(t.evidence_chunks)} chunks")

    tagger = Tagger(index=manager, workspace=ws)
    assignments = tagger.tag(themes=themes, threshold=threshold, top_n=top_n)

    if console is not None:
        info(console, f"{len(assignments)} tag assignments")
        for a in assignments:
            info(console, a.competitor_slug, detail=f"{a.theme_label} · score {a.relevance_score:.3f}")

    if dry_run:
        if console is not None:
            info(console, "dry run — no changes written")
        return

    tagger.apply(assignments)
    tagged_count = len({a.competitor_slug for a in assignments})
    if console is not None:
        success(console, f"tagged {tagged_count} profile{'s' if tagged_count != 1 else ''}")


@main.command()
@click.option("--rounds", default=3, help="Number of discovery rounds")
@click.option("--batch-size", default=15, help="Candidates per round")
@click.option("--seed", multiple=True, help="Seed competitor names")
@click.option("--auto-accept", is_flag=True, help="Accept all candidates (non-interactive)")
@click.option("--dry-run", is_flag=True, help="Show discovery plan")
@click.option("--workspace", "workspace_dir", default=".", help="Workspace directory")
@click.pass_context
def discover(ctx, rounds, batch_size, seed, auto_accept, dry_run, workspace_dir):
    """Discover competitors in the market domain."""
    from rich.text import Text

    from recon.cli_ui.messages import info, success, warn
    from recon.cli_ui.renderables import tab_breadcrumb

    console = ctx.obj["console"]
    ws = _open_cwd_workspace(workspace_dir if workspace_dir != "." else None)
    domain = ws.schema.domain if ws.schema else "Unknown"

    if dry_run:
        info(console, "discovery plan", detail=f"domain: {domain}")
        info(console, f"{rounds} round{'s' if rounds != 1 else ''} · batch {batch_size}")
        if seed:
            info(console, "seeds", detail=", ".join(seed))
        info(console, "requires ANTHROPIC_API_KEY")
        return

    client, error = _try_create_client()
    if error:
        raise click.ClickException(f"ANTHROPIC_API_KEY not set. {error}")

    from recon.discovery import DiscoveryAgent, DiscoveryState

    agent = DiscoveryAgent(
        llm_client=client,
        domain=domain,
        seed_competitors=list(seed),
    )
    state = DiscoveryState()

    console.print(tab_breadcrumb(active="comps"))
    console.print()

    for round_num in range(1, rounds + 1):
        console.print(Text.assemble(("round ", "dim"), (f"{round_num}/{rounds}", "accent")))
        candidates = _run_async(agent.search(state=state if round_num > 1 else None))

        if not candidates:
            warn(console, "no new candidates found")
            break

        state.add_round(candidates)
        success(console, f"{len(candidates)} candidates")
        for c in state.all_candidates[-len(candidates):]:
            console.print(
                Text.assemble(
                    ("  ▣ ", "accent"),
                    (c.name, "accent"),
                    ("  ", "dim"),
                    (c.url or "", "subdued"),
                )
            )
            if c.blurb:
                console.print(Text(f"      {c.blurb}", style="body"))
            console.print(
                Text.assemble(
                    ("      via ", "dim"),
                    (c.provenance, "body"),
                    ("  ·  ", "subdued"),
                    ("tier ", "dim"),
                    (str(c.suggested_tier), "body"),
                )
            )

        if not auto_accept and round_num < rounds:
            suggestion = _run_async(agent.analyze_patterns(state))
            info(console, "suggestion", detail=str(suggestion))

    accepted = state.accepted_candidates
    console.print()
    success(console, f"{len(accepted)} competitor{'s' if len(accepted) != 1 else ''} accepted")

    created = 0
    for candidate in accepted:
        try:
            ws.create_profile(candidate.name)
            created += 1
        except FileExistsError:
            warn(console, f"skipped (exists): {candidate.name}")
    success(console, f"{created} profile{'s' if created != 1 else ''} created", detail="next: recon research --all")


@main.command()
@click.option("--from", "from_stage", type=click.Choice(["research", "enrich", "index", "synthesize"]), help="Start from stage")
@click.option("--deep", is_flag=True, help="Use deep synthesis")
@click.option("--dry-run", is_flag=True, help="Show plan + cost estimate")
@click.option("--path", default=None, help="Workspace directory (default: cwd)")
@click.pass_context
def run(ctx, from_stage, deep, dry_run, path):
    """Execute the full pipeline end-to-end — research through summarize."""
    from rich.console import Group
    from rich.text import Text

    from recon.cli_ui.live import LiveRunMonitor
    from recon.cli_ui.messages import info, success
    from recon.cli_ui.renderables import card, tab_breadcrumb

    console = ctx.obj["console"]

    if dry_run:
        steps = [
            "Research all sections",
            "Verify (per section tier)",
            "Enrich (cleanup → sentiment → strategic)",
            "Index into vector DB",
            "Discover themes from clustering",
            "Retrieve per theme",
            f"Synthesize ({'deep 4-pass' if deep else 'single pass'})",
            "Distill to 1-pagers",
            "Meta-synthesis",
        ]
        body = Group(
            *(
                Text.assemble(
                    (f"{i:>2}. ", "dim"),
                    (label, "body"),
                )
                for i, label in enumerate(steps, start=1)
            )
        )
        console.print(tab_breadcrumb(active="agents"))
        console.print()
        console.print(
            card(
                body,
                title="FULL PIPELINE · DRY RUN",
                meta=(f"start: {from_stage}" if from_stage else "start: research"),
                footer="run it:  recon run",
            )
        )
        return

    client, error = _try_create_client()
    if error:
        raise click.ClickException(f"ANTHROPIC_API_KEY not set. {error}")

    from recon.pipeline import Pipeline, PipelineConfig, PipelineStage
    from recon.state import StateStore

    ws = _open_cwd_workspace(path)
    state = StateStore(db_path=ws.root / ".recon" / "state.db")
    _run_async(state.initialize())

    stage_map = {
        "research": PipelineStage.RESEARCH,
        "enrich": PipelineStage.ENRICH,
        "index": PipelineStage.INDEX,
        "synthesize": PipelineStage.SYNTHESIZE,
    }

    config = PipelineConfig(
        deep_synthesis=deep,
        start_from=stage_map.get(from_stage, PipelineStage.RESEARCH),
        verification_enabled=False,
    )

    pipeline = Pipeline(
        workspace=ws,
        state_store=state,
        llm_client=client,
        config=config,
    )

    with LiveRunMonitor(console, title="FULL PIPELINE") as monitor:
        run_id = _run_async(pipeline.plan())
        _run_async(pipeline.execute(run_id))
    monitor.flush_summary()

    if pipeline.discovered_themes:
        success(console, f"{len(pipeline.discovered_themes)} themes discovered")
        for t in pipeline.discovered_themes:
            info(console, t.label, detail=t.evidence_strength)
    if pipeline.syntheses:
        success(console, f"wrote {len(pipeline.syntheses)} theme syntheses")

    summary_path = ws.root / "executive_summary.md"
    if summary_path.exists():
        success(console, "executive summary", detail=str(summary_path))


def _launch_tui(workspace: str) -> None:
    """Shared entry point for ``recon tui`` and its alias ``recon cli``.

    Extracted so the two commands stay byte-identical — the only
    difference is the command name the user types.
    """
    from recon.tui.app import ReconApp

    ws_path = Path(workspace)
    app = ReconApp(workspace_path=ws_path if (ws_path / "recon.yaml").exists() else None)
    app.run()


@main.command()
@click.option("--workspace", default=".", help="Workspace directory")
def tui(workspace):
    """Launch the interactive TUI."""
    _launch_tui(workspace)


@main.command(name="cli")
@click.option("--workspace", default=".", help="Workspace directory")
def cli_tui_alias(workspace):
    """Launch the interactive TUI (alias for ``recon tui``).

    Kept as a separate subcommand because "CLI" is the word users
    reach for when they mean "the interactive recon interface in a
    terminal." Functionally identical to ``recon tui``.
    """
    _launch_tui(workspace)


@main.command(name="repl")
@click.option(
    "--workspace",
    default=None,
    type=click.Path(file_okay=False),
    help="Pre-load this workspace so commands inherit it without --workspace.",
)
@click.pass_context
def cli_repl(ctx, workspace):
    """Launch the typed REPL — every ``recon <sub>`` in a warm shell.

    Drops into a prompt where you type the same subcommands you'd
    type at zsh (``plan``, ``schema``, ``comps``, ``research``, …)
    but in a warm Python process with tab-completion, history, and
    a shared workspace. Exit with ``exit``, ``quit``, or Ctrl+D.

    For the full-screen interactive experience, use ``recon cli`` or
    ``recon tui`` instead.
    """
    from recon.cli_ui.shell import run_shell

    run_shell(workspace_path=workspace, console=ctx.obj["console"])


@main.command()
@click.option(
    "--host",
    default="127.0.0.1",
    show_default=True,
    help="Bind interface. Non-loopback values require --unsafe-bind-all.",
)
@click.option(
    "--port",
    default=8787,
    show_default=True,
    type=int,
    help="Bind port.",
)
@click.option(
    "--workspace",
    "workspace_path",
    default=None,
    type=click.Path(exists=True, file_okay=False),
    help="Pre-open this workspace on launch (currently advisory; full wiring lands in Phase 2).",
)
@click.option(
    "--unsafe-bind-all",
    is_flag=True,
    default=False,
    help="Required to bind a non-loopback host. The web UI has no auth; only do this on trusted networks.",
)
@click.option(
    "--no-open",
    "no_open",
    is_flag=True,
    default=False,
    help="Do not auto-open the browser after the server starts.",
)
@click.option(
    "--web-log-level",
    default="info",
    show_default=True,
    type=click.Choice(["critical", "error", "warning", "info", "debug", "trace"], case_sensitive=False),
    help="uvicorn log level (independent of the global --log-level).",
)
def serve(host, port, workspace_path, unsafe_bind_all, no_open, web_log_level):
    """Launch the recon web UI on http://127.0.0.1:8787 by default.

    The web UI mirrors the TUI flow (Welcome -> Describe -> Discovery
    -> Template -> Confirm -> Run -> Results) in a browser. It is
    intentionally local-only; binding to a public interface requires
    the explicit --unsafe-bind-all flag.
    """
    from recon.web.server import is_loopback_host, run_server

    if not is_loopback_host(host) and not unsafe_bind_all:
        raise click.UsageError(
            f"Refusing to bind {host}: pass --unsafe-bind-all to opt in. "
            "The web UI has no authentication; only enable this on trusted networks.",
        )

    if workspace_path is not None:
        # Phase 1 records the path for later phases to consume; the
        # full pre-open behavior lands when /api/workspace is wired.
        click.echo(f"workspace pre-open requested: {workspace_path}")

    click.echo(f"recon web UI: http://{host}:{port}")
    run_server(
        host=host,
        port=port,
        open_browser=not no_open,
        log_level=web_log_level,
    )


@main.command(hidden=True)
@click.pass_context
def ping(ctx):
    """Smoke-test the CLI rendering layer (hidden).

    Prints a card that exercises every primitive — theme palette, the
    numbered-tab breadcrumb, shaded-block progress bar, and a rule
    divider — so a visual regression in ``cli_ui`` shows up on one
    command. Remove in phase 5 once real views cover this.
    """
    from rich.console import Group
    from rich.rule import Rule
    from rich.text import Text

    from recon.cli_ui.renderables import card, shaded_bar, tab_breadcrumb

    console = ctx.obj["console"]

    console.print(tab_breadcrumb(active="plan"))
    console.print()

    body = Group(
        Text.from_markup("[body]Pure-CLI rendering layer — phase 1 smoke test.[/body]"),
        Text(""),
        Text.from_markup("[card.title]PALETTE[/]"),
        Text.from_markup(
            "  [active]▌ active[/]   [accent]accent[/]   [body]body[/]   "
            "[dim]dim[/]   [muted]muted[/]   [subdued]subdued[/]   [error]error[/]"
        ),
        Text(""),
        Text.from_markup("[card.title]PROGRESS[/]"),
        Text.assemble(
            Text("  "),
            shaded_bar(0, 24),
            Text("   0%", style="bar.pct"),
        ),
        Text.assemble(
            Text("  "),
            shaded_bar(25, 24),
            Text("  25%", style="bar.pct"),
        ),
        Text.assemble(
            Text("  "),
            shaded_bar(65, 24),
            Text("  65%", style="bar.pct"),
        ),
        Text.assemble(
            Text("  "),
            shaded_bar(100, 24),
            Text(" 100%", style="bar.pct"),
        ),
        Text(""),
        Rule(style="border"),
    )
    console.print(
        card(
            body,
            title="RECON CLI · PING",
            meta="phase 1",
            footer="next:  recon plan   ·   docs:  recon --help",
        )
    )


if __name__ == "__main__":
    main()
