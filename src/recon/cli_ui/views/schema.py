"""``recon schema`` — dossier sections with toggle state + preferred format."""

from __future__ import annotations

from rich.console import Console
from rich.table import Table
from rich.text import Text

from recon.cli_ui.renderables import card, tab_breadcrumb
from recon.web.schemas import TemplateResponse, TemplateSectionModel
from recon.workspace import Workspace


def schema_data(ws: Workspace) -> TemplateResponse:
    """Assemble the schema-tab DTO."""
    sections = ws.schema.sections if ws.schema else []
    return TemplateResponse(
        sections=[
            TemplateSectionModel(
                key=s.key,
                title=s.title,
                description=s.description,
                selected=True,  # every section in the yaml is selected
                allowed_formats=s.allowed_formats,
                preferred_format=s.preferred_format,
            )
            for s in sections
        ]
    )


def render_schema(ws: Workspace, console: Console) -> TemplateResponse:
    """Print the SCHEMA card and return the DTO."""
    data = schema_data(ws)

    console.print(tab_breadcrumb(active="schema"))
    console.print()

    rows = Table.grid(padding=(0, 2), pad_edge=False, expand=True)
    rows.add_column(width=2, no_wrap=True)            # check mark
    rows.add_column(min_width=14, no_wrap=True)       # title
    rows.add_column(width=1)                           # em-dash
    rows.add_column(min_width=16)                      # description
    rows.add_column(justify="right", no_wrap=True)     # format tag

    for s in data.sections:
        rows.add_row(
            Text("▣" if s.selected else "▢", style="accent" if s.selected else "subdued"),
            Text(s.title, style="accent"),
            Text("—", style="subdued"),
            Text(s.description, style="body"),
            Text(f"[{s.preferred_format}]", style="dim"),
        )

    meta = f"{sum(1 for s in data.sections if s.selected)} / {len(data.sections)} selected"
    console.print(
        card(
            rows,
            title="DOSSIER SCHEMA",
            meta=meta,
            footer="back:  recon plan   ·   next:  recon comps   ·   json:  recon schema --json",
        )
    )
    return data
