"""``recon comps`` — competitor list with status + research progress."""

from __future__ import annotations

from rich.console import Console
from rich.table import Table
from rich.text import Text

from recon.cli_ui.renderables import card, tab_breadcrumb
from recon.web.schemas import CompetitorListResponse, CompetitorModel
from recon.workspace import Workspace

_STATUS_STYLE = {
    "scaffold":   "subdued",
    "researched": "accent",
    "enriched":   "accent",
    "verified":   "accent",
    "failed":     "error",
}


def comps_data(ws: Workspace) -> CompetitorListResponse:
    """Assemble the comps-tab DTO from workspace profiles."""
    profiles = ws.list_profiles()
    models: list[CompetitorModel] = []
    for p in profiles:
        models.append(
            CompetitorModel(
                name=p.get("name", p.get("_slug", "?")),
                slug=p.get("_slug", ""),
                type=p.get("type", "competitor"),
                status=p.get("research_status", "scaffold"),
                url=p.get("url"),
                blurb=p.get("blurb"),
            ),
        )
    return CompetitorListResponse(competitors=models)


def render_comps(ws: Workspace, console: Console) -> CompetitorListResponse:
    """Print the COMP'S card and return the DTO."""
    data = render_comps_body(ws, console, show_breadcrumb=True)
    return data


def render_comps_body(
    ws: Workspace,
    console: Console,
    *,
    show_breadcrumb: bool = True,
    footer: str | None = None,
) -> CompetitorListResponse:
    """Render the card; optionally skip the tab breadcrumb (used by ``status``)."""
    data = comps_data(ws)

    if show_breadcrumb:
        console.print(tab_breadcrumb(active="comps"))
        console.print()

    if not data.competitors:
        body = Text(
            "No competitors yet. Kick off discovery: recon discover --seed <name>",
            style="subdued",
        )
        console.print(
            card(
                body,
                title="COMPETITORS",
                meta="0 targets",
                footer=footer or "back:  recon schema   ·   json:  recon comps --json",
            )
        )
        return data

    rows = Table.grid(padding=(0, 2), pad_edge=False, expand=True)
    rows.add_column(width=3, no_wrap=True)   # idx
    rows.add_column(min_width=14, no_wrap=True)  # name
    rows.add_column(min_width=10, no_wrap=True)  # status
    rows.add_column(min_width=18)            # blurb
    rows.add_column(justify="right", no_wrap=True)  # url

    for i, c in enumerate(data.competitors, start=1):
        style = _STATUS_STYLE.get(c.status, "body")
        blurb = (c.blurb or "").split("\n")[0]
        if len(blurb) > 48:
            blurb = blurb[:45] + "…"
        url = c.url or ""
        if url:
            url = url.replace("https://", "").replace("http://", "").rstrip("/")
        rows.add_row(
            Text(f"{i:>2}.", style="dim"),
            Text(c.name, style="accent"),
            Text(c.status.upper(), style=style),
            Text(blurb, style="body"),
            Text(url, style="subdued"),
        )

    meta = f"{len(data.competitors)} target{'s' if len(data.competitors) != 1 else ''}"
    console.print(
        card(
            rows,
            title="COMPETITORS",
            meta=meta,
            footer=footer or "back:  recon schema   ·   next:  recon agents   ·   json:  recon comps --json",
        )
    )
    return data
