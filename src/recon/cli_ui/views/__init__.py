"""One ``render_*`` function per v4 tab — the pure-CLI analogue of the
``<template id="screen-*">`` blocks in ``static/index.html``.

Each view takes a :class:`recon.workspace.Workspace` and a
:class:`rich.console.Console`, prints styled output, and optionally
returns a Pydantic DTO so callers can emit ``--json`` without
re-assembling data. The DTOs match the web API responses so a skill
can parse the same shape from either layer.
"""
from __future__ import annotations

from recon.cli_ui.views.agents import render_agents
from recon.cli_ui.views.comps import render_comps
from recon.cli_ui.views.home import render_home
from recon.cli_ui.views.output import render_output
from recon.cli_ui.views.plan import render_plan
from recon.cli_ui.views.schema import render_schema
from recon.cli_ui.views.status import render_status

__all__ = [
    "render_home",
    "render_plan",
    "render_schema",
    "render_comps",
    "render_agents",
    "render_output",
    "render_status",
]
