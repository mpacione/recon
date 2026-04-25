"""``recon output`` — file tree + exec summary preview."""

from __future__ import annotations

from pathlib import Path

from rich.console import Console, Group
from rich.markdown import Markdown
from rich.text import Text
from rich.tree import Tree

from recon.cli_ui.renderables import card, tab_breadcrumb
from recon.web.schemas import ResultsResponse
from recon.workspace import Workspace


def output_data(ws: Workspace) -> ResultsResponse:
    """Assemble the output-tab DTO via the existing web helper."""
    # Reuse the endpoint's shared builder so CLI and web stay aligned.
    from recon.web.api import _build_results_response

    return _build_results_response(ws.root)


def render_output(ws: Workspace, console: Console) -> ResultsResponse:
    """Print the OUTPUT card (tree + exec summary) and return the DTO."""
    data = output_data(ws)

    console.print(tab_breadcrumb(active="output"))
    console.print()

    if not data.executive_summary_path and not data.theme_files and not data.output_files:
        console.print(
            card(
                Text(
                    "No outputs yet. Run research first:  recon research --all  then  recon summarize",
                    style="subdued",
                ),
                title="OUTPUT",
                meta="0 files",
                footer="json:  recon output --json",
            )
        )
        return data

    # File tree (left half)
    ws_name = ws.root.name
    tree = Tree(Text(ws_name + "/", style="accent"), guide_style="tree")

    if data.output_files or data.executive_summary_path:
        output_branch = tree.add(Text("output/", style="card.title"))
        seen_paths: set[str] = set()
        if data.executive_summary_path:
            p = Path(data.executive_summary_path)
            output_branch.add(Text(p.name, style="accent"))
            seen_paths.add(str(p))
        for of in data.output_files:
            if of.kind == "exec_summary" or of.path in seen_paths:
                continue
            output_branch.add(Text(Path(of.path).name, style="body"))

    if data.theme_files:
        themes_branch = tree.add(Text("themes/", style="card.title"))
        distilled_branch = None
        for tf in data.theme_files:
            themes_branch.add(Text(Path(tf.path).name, style="body"))
            if tf.distilled_path:
                if distilled_branch is None:
                    distilled_branch = tree.add(Text("themes/distilled/", style="card.title"))
                distilled_branch.add(Text(Path(tf.distilled_path).name, style="body"))

    # Exec summary preview (right half — rendered below the tree here
    # since stacking vertically reads better than side-by-side in a
    # terminal that might be < 120 cols)
    preview_renderable = None
    if data.executive_summary_preview:
        preview_renderable = Group(
            Text("—" * 60, style="subdued"),
            Text(""),
            Text(Path(data.executive_summary_path).name if data.executive_summary_path else "executive_summary.md", style="card.title"),
            Text(""),
            Markdown(data.executive_summary_preview),
        )

    body = Group(tree, preview_renderable) if preview_renderable is not None else tree

    total_files = (
        (1 if data.executive_summary_path else 0)
        + len(data.output_files)
        + len(data.theme_files)
        + sum(1 for t in data.theme_files if t.distilled_path)
    )
    console.print(
        card(
            body,
            title="OUTPUT",
            meta=f"{total_files} file{'s' if total_files != 1 else ''}",
            footer=f"local:  {ws.root}   ·   json:  recon output --json",
        )
    )
    return data
