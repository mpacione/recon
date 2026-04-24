"""``recon status`` — the full-dashboard snapshot, all tabs stacked."""

from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.rule import Rule
from rich.text import Text

from recon.cli_ui.renderables import tab_breadcrumb
from recon.cli_ui.views.agents import render_agents_body
from recon.cli_ui.views.comps import render_comps_body
from recon.cli_ui.views.output import output_data
from recon.cli_ui.views.plan import plan_data
from recon.cli_ui.views.schema import schema_data
from recon.workspace import Workspace


def render_status(ws: Workspace, console: Console) -> dict:
    """Print the full dashboard (summary tiles for each tab).

    Returns a ``dict`` with the assembled DTOs under per-tab keys so
    callers (``--json``) can serialize the full snapshot.
    """
    plan = plan_data(ws)
    schema = schema_data(ws)
    comps = _comps_as_data(ws)
    outputs = output_data(ws)

    console.print(tab_breadcrumb(active=None))  # no tab highlighted — status is cross-cutting
    console.print()

    # Top-line summary bar — one row of meta-tiles for the workspace.
    brief = (ws.schema.domain or "") if ws.schema else ""
    brief_short = (brief[:50] + "…") if len(brief) > 51 else (brief or "(no brief)")
    company = ws.schema.identity.company_name if ws.schema and ws.schema.identity else ""

    header = Text.assemble(
        ("⌂ ", "accent"),
        (ws.root.name, "accent"),
        ((f"  ·  {company}" if company else ""), "dim"),
    )
    console.print(header)
    console.print(Text(f"  {brief_short}", style="body"))
    console.print()
    console.print(
        Text.assemble(
            ("  sections: ", "dim"),
            (f"{len(schema.sections)}", "accent"),
            ("    comp's: ", "dim"),
            (f"{len(comps.competitors)}", "accent"),
            ("    est cost: ", "dim"),
            (f"${plan.estimated_total:.2f}", "accent"),
            ("    runs: ", "dim"),
            (f"{len(agents_count_runs(ws))}", "accent"),
        )
    )
    console.print()

    # The big sections, rendered through the per-tab body helpers so
    # each card is identical to the focused command's output.
    render_comps_body(
        ws,
        console,
        show_breadcrumb=False,
        footer="focus:  recon comps   ·   json:  recon status --json",
    )
    console.print()
    render_agents_body(
        ws,
        console,
        show_breadcrumb=False,
        footer="focus:  recon agents",
        limit=5,
    )

    # Outputs (if present) — just a one-liner pointer rather than the
    # full preview; `recon output` is the focused view.
    if outputs.executive_summary_path or outputs.theme_files or outputs.output_files:
        console.print()
        console.print(
            Text.assemble(
                ("⌂ outputs: ", "dim"),
                (f"{Path(outputs.executive_summary_path).name if outputs.executive_summary_path else '—'}", "accent"),
                (f"   themes: {len(outputs.theme_files)}", "body"),
                ("   (recon output for preview)", "dim"),
            )
        )

    console.print()
    console.print(Rule(style="border"))
    console.print(
        Text.assemble(
            ("focus tabs:  ", "dim"),
            ("recon plan", "accent"),
            ("  ·  ", "subdued"),
            ("recon schema", "accent"),
            ("  ·  ", "subdued"),
            ("recon comps", "accent"),
            ("  ·  ", "subdued"),
            ("recon agents", "accent"),
            ("  ·  ", "subdued"),
            ("recon output", "accent"),
        )
    )

    return {
        "plan": plan.model_dump(mode="json"),
        "schema": schema.model_dump(mode="json"),
        "comps": comps.model_dump(mode="json"),
        "outputs": outputs.model_dump(mode="json"),
    }


def _comps_as_data(ws: Workspace):
    # Thin proxy so we only import comps.py at callsite (avoids a
    # circular-import pitfall if views grow).
    from recon.cli_ui.views.comps import comps_data

    return comps_data(ws)


def agents_count_runs(ws: Workspace) -> list:
    """Count-only helper so the top banner doesn't double-render runs."""
    from recon.cli_ui.views.agents import agents_data

    return agents_data(ws).runs
