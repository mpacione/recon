"""``recon plan`` — research brief + model selector + worker count."""

from __future__ import annotations

from pathlib import Path

from rich.console import Console, Group
from rich.table import Table
from rich.text import Text

from recon.cli_ui.renderables import card, shaded_bar, tab_breadcrumb
from recon.web.api import _BASELINE_MODEL_ID, _MODEL_CATALOG, _estimate_cost_by_stage
from recon.web.schemas import ConfirmResponse, ModelOption
from recon.workspace import Workspace


def _humanize_path(p: Path) -> str:
    """Replace $HOME prefix with ``~`` for display."""
    try:
        rel = p.relative_to(Path.home())
        return "~/" + str(rel)
    except ValueError:
        return str(p)


def plan_data(ws: Workspace) -> ConfirmResponse:
    """Assemble the plan-tab DTO. Duplicates the /api/confirm logic.

    Kept here (rather than imported from api.py) because api.py's
    version is a FastAPI endpoint body, not a pure function. If that
    ever gets refactored into a shared helper, swap this for a call.
    """
    profiles = ws.list_profiles()
    competitor_count = len(profiles)
    sections = ws.schema.sections if ws.schema else []
    section_keys = [s.key for s in sections]
    section_names = [s.title for s in sections]
    section_count = len(sections)

    cost_by_stage = _estimate_cost_by_stage(competitor_count, section_count)
    estimated_total = sum(cost_by_stage.values())

    baseline = next(m for m in _MODEL_CATALOG if m["id"] == _BASELINE_MODEL_ID)
    baseline_blended = baseline["input_price_per_million"] + baseline["output_price_per_million"]

    options: list[ModelOption] = []
    for entry in _MODEL_CATALOG:
        blended = entry["input_price_per_million"] + entry["output_price_per_million"]
        scale = blended / baseline_blended if baseline_blended else 1.0
        options.append(
            ModelOption(
                id=entry["id"],
                label=entry["label"],
                input_price_per_million=entry["input_price_per_million"],
                output_price_per_million=entry["output_price_per_million"],
                description=entry["description"],
                estimated_total=round(estimated_total * scale, 2),
                recommended=entry["recommended"],
            ),
        )

    return ConfirmResponse(
        competitor_count=competitor_count,
        section_keys=section_keys,
        section_names=section_names,
        cost_by_stage=cost_by_stage,
        estimated_total=round(estimated_total, 2),
        eta_seconds=0,
        model_options=options,
        default_model=_BASELINE_MODEL_ID,
        default_workers=5,
    )


def render_plan(ws: Workspace, console: Console) -> ConfirmResponse:
    """Print the PLAN card and return the DTO."""
    data = plan_data(ws)

    company = ws.schema.identity.company_name if ws.schema and ws.schema.identity else ""
    brief = ws.schema.domain if ws.schema else ""

    console.print(tab_breadcrumb(active="plan"))
    console.print()

    # Path line above the card — mirrors the web UI's path-pill.
    path_text = Text.assemble(
        ("  ", "body"),
        ("⌂ ", "accent"),
        (_humanize_path(ws.root), "body"),
        ("    ", "body"),
        ("local dir: ", "dim"),
        (str(ws.root), "subdued"),
    )
    console.print(path_text)
    console.print()

    # Research Brief card
    brief_body = Text(
        brief or "(no brief yet — run `recon init` or edit recon.yaml)",
        style="body" if brief else "subdued",
    )
    console.print(
        card(
            brief_body,
            title="RESEARCH BRIEF" + (f"  ·  {company.upper()}" if company else ""),
            meta=f"{data.competitor_count} comp's · {len(data.section_keys)} sections",
        )
    )
    console.print()

    # Models card with shaded-bar cost indicator
    models_table = Table.grid(padding=(0, 2), pad_edge=False, expand=False)
    models_table.add_column(width=3)   # marker
    models_table.add_column(min_width=14, no_wrap=True)  # label
    models_table.add_column(width=1)                       # em-dash
    models_table.add_column(min_width=22)                  # description
    models_table.add_column(justify="right", min_width=8, no_wrap=True)  # cost

    for m in data.model_options:
        is_rec = m.recommended
        marker = "▣" if is_rec else "▢"
        marker_style = "accent" if is_rec else "subdued"
        label_style = "accent" if is_rec else "body"
        desc_style = "body" if is_rec else "dim"
        cost_style = "accent" if is_rec else "body"
        models_table.add_row(
            Text(marker, style=marker_style),
            Text(m.label, style=label_style),
            Text("—", style="subdued"),
            Text(m.description, style=desc_style),
            Text(f"${m.estimated_total:>5.2f}", style=cost_style),
        )

    # Worker count visual — fixed 5 default, shaded bar out of 10
    workers = data.default_workers
    workers_line = Text.assemble(
        ("WORKERS  ", "card.title"),
        shaded_bar((workers / 10.0) * 100, 10, style="bar"),
        (f"  {workers}", "accent"),
        ("  parallel", "dim"),
    )

    models_body = Group(models_table, Text(""), workers_line)
    meta_text = f"EST COST · base ${data.estimated_total:.2f}"
    console.print(
        card(
            models_body,
            title="AI MODELS",
            meta=meta_text,
            footer="next:  recon schema   ·   json:  recon plan --json",
        )
    )

    return data
