"""PlanScreen for recon TUI.

PLAN owns the project brief, run settings, and a lightweight cost / run summary.
"""

from __future__ import annotations

import contextlib
from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Static

from recon.cost import (
    SectionCostSpec,
    estimate_run_breakdown,
    estimate_run_duration_minutes,
    get_model_pricing,
    list_available_models,
)
from recon.tui.shell import ReconScreen
from recon.tui.primitives import TerminalBox
from recon.tui.widgets import action_button


class PlanScreen(ReconScreen):
    """Project brief + settings summary."""

    tab_key = "plan"
    show_log_pane = False
    show_activity_feed = False
    show_run_status_bar = False

    BINDINGS = [
        Binding("enter", "edit_brief", "edit brief", show=False),
        Binding("space", "next", "next", show=False),
        Binding("e", "edit_brief", "edit brief", show=False),
        Binding("m", "cycle_model", "model", show=False),
        Binding("v", "cycle_verification", "verification", show=False),
        Binding("plus", "more_workers", "more workers", show=False),
        Binding("equals_sign", "more_workers", "more workers", show=False),
        Binding("minus", "fewer_workers", "fewer workers", show=False),
        Binding("escape", "back", "back", show=False),
    ]

    keybind_hints = (
        "[#DDEDC4]↲[/] edit brief · "
        "[#DDEDC4]space[/] next · "
        "[#DDEDC4]m[/] model · "
        "[#DDEDC4]v[/] verification · "
        "[#DDEDC4]+/-[/] workers · "
        "[#DDEDC4]esc[/] back"
    )

    DEFAULT_CSS = """
    PlanScreen {
        background: #000000;
    }
    #plan-container {
        width: 100%;
        height: auto;
        padding: 0;
        overflow-y: auto;
    }
    #plan-run-card {
        margin-top: 1;
    }
    #plan-actions {
        dock: bottom;
        height: 3;
        padding: 0 2;
        layout: horizontal;
        background: #000000;
    }
    #plan-actions Button {
        margin: 0 1 0 0;
    }
    """

    def __init__(
        self,
        workspace_root: Path,
        project_brief: str,
        competitor_count: int,
        section_count: int,
        plan_settings: dict[str, object],
        total_cost: float,
        run_count: int,
    ) -> None:
        super().__init__()
        self._workspace_root = workspace_root
        self._project_brief = project_brief
        self._competitor_count = competitor_count
        self._section_count = section_count
        self._plan_settings = plan_settings
        self._total_cost = total_cost
        self._run_count = run_count

    def compose_body(self) -> ComposeResult:
        from recon.tui.primitives import Card

        with Vertical(id="plan-container"):
            with Card(
                title="PROJECT BRIEF",
                meta=self._workspace_root.name,
                id="plan-brief-card",
            ):
                yield Static(self._render_brief(), id="plan-brief")

            with Card(
                title="RUN SETTINGS",
                meta=self._settings_meta(),
                id="plan-settings-card",
            ):
                yield Static(self._render_settings(), id="plan-settings")

            with Card(
                title="COST ESTIMATE",
                meta=f"{self._competitor_count} companies · {self._section_count} sections",
                id="plan-cost-card",
            ):
                yield Static(self._render_cost(), id="plan-cost")

            with Card(
                title="LAST RUN",
                meta=f"{self._run_count} run{'s' if self._run_count != 1 else ''}",
                id="plan-run-card",
            ):
                yield Static(self._render_run_summary(), id="plan-run-summary")

        with Horizontal(id="plan-actions"):
            yield action_button("BACK", "Esc", button_id="btn-back")
            yield action_button("EDIT BRIEF", "Enter", button_id="btn-edit-brief", variant="primary")
            yield action_button("MODEL", "M", button_id="btn-model")
            yield action_button("VERIF.", "V", button_id="btn-verify")
            yield action_button("WORKERS", "+/-", button_id="btn-workers")
            yield Static("", classes="action-spacer")
            yield action_button("NEXT", "Space", button_id="btn-next")

    def _render_brief(self) -> str:
        if self._project_brief.strip():
            return (
                f"[#DDEDC4]{self._project_brief.strip()}[/]\n\n"
                "[#787266]Use this section to keep the project description, keys, and run assumptions aligned.[/]"
            )
        return (
            "[#787266]No project brief saved yet.[/]\n"
            "[#a59a86]Press[/] [#DDEDC4]E[/] [#a59a86]to add one before discovery.[/]"
        )

    def _settings_meta(self) -> str:
        model_name = str(self._plan_settings.get("model_name", "sonnet"))
        workers = int(self._plan_settings.get("workers", 5))
        verification = str(self._plan_settings.get("verification_mode", "standard"))
        return f"{model_name} · {workers} workers · {verification}"

    def _render_settings(self) -> str:
        model_name = str(self._plan_settings.get("model_name", "sonnet"))
        workers = int(self._plan_settings.get("workers", 5))
        verification = str(self._plan_settings.get("verification_mode", "standard"))
        return (
            f"[#a59a86]Model:[/] [#DDEDC4]{model_name}[/]  [#787266](press M to cycle)[/]\n"
            f"[#a59a86]Parallel workers:[/] [#DDEDC4]{workers}[/]  [#787266](press +/- to change)[/]\n"
            f"[#a59a86]Verification:[/] [#DDEDC4]{verification}[/]  [#787266](press V to cycle)[/]\n\n"
            "[#787266]These settings update the estimate and the AGENTS run path directly.[/]"
        )

    def _render_cost(self) -> str:
        model_name = str(self._plan_settings.get("model_name", "sonnet"))
        verification = str(self._plan_settings.get("verification_mode", "standard"))
        workers = int(self._plan_settings.get("workers", 5))
        pricing = get_model_pricing(model_name)
        section_specs = self._section_specs()
        standard_breakdown = estimate_run_breakdown(
            pricing=pricing,
            competitor_count=1,
            sections=section_specs,
            section_count=self._section_count,
            verification_mode="standard",
        )
        per_company_breakdown = estimate_run_breakdown(
            pricing=pricing,
            competitor_count=1,
            sections=section_specs,
            section_count=self._section_count,
            verification_mode=verification,
        )
        projection_companies = self._competitor_count if self._competitor_count > 0 else 10
        projected_breakdown = estimate_run_breakdown(
            pricing=pricing,
            competitor_count=projection_companies,
            sections=section_specs,
            section_count=self._section_count,
            verification_mode=verification,
        )
        est_minutes = estimate_run_duration_minutes(
            section_count=self._section_count,
            competitor_count=projection_companies,
            worker_count=workers,
            verification_mode=verification,
        )
        per_company_minutes = est_minutes / projection_companies if projection_companies > 0 else 0.0
        verification_uplift = max(
            0.0,
            per_company_breakdown.variable_per_company - standard_breakdown.variable_per_company,
        )
        projection_label = (
            f"{projection_companies} accepted companies"
            if self._competitor_count > 0
            else f"nominal {projection_companies}-company run"
        )
        return (
            f"[#a59a86]Total cost per company:[/] "
            f"[bold #DDEDC4]~${projected_breakdown.blended_per_company:.2f}[/] "
            f"[#787266](includes {verification} verification)[/]\n"
            f"[#a59a86]Includes research:[/] [#DDEDC4]~${per_company_breakdown.research_per_company:.2f}[/]  "
            f"[#a59a86]enrichment:[/] [#DDEDC4]~${per_company_breakdown.enrichment_per_company:.2f}[/]\n"
            f"[#a59a86]Verification cost uplift:[/] [#DDEDC4]+~${verification_uplift:.2f}/company[/]\n"
            f"[#a59a86]Fixed overhead (shared once per run):[/] [#DDEDC4]~${projected_breakdown.fixed_total:.2f}[/]\n"
            f"[#787266]themes ~${projected_breakdown.fixed_themes:.2f} + executive summary ~${projected_breakdown.fixed_summary:.2f}[/]\n"
            f"[#a59a86]Projected full run ({projection_label}):[/] "
            f"[bold #DDEDC4]~${projected_breakdown.total_run_cost:.2f}[/]\n"
            f"[#a59a86]Estimated time:[/] [#DDEDC4]~{est_minutes:.0f}m[/] "
            f"[#787266]@ {projection_companies} competitors · {per_company_minutes:.1f}m/competitor est[/]\n"
            f"[#a59a86]Current tracked spend:[/] [#DDEDC4]${self._total_cost:.2f}[/]\n\n"
            "[#787266]Variable cost scales with companies; themes and executive summary stay fixed.[/]"
        )

    def _section_specs(self) -> list[SectionCostSpec]:
        try:
            from recon.workspace import Workspace

            ws = Workspace.open(self._workspace_root)
            schema = ws.schema
            if schema is None or not schema.sections:
                return []
            return [
                SectionCostSpec(
                    format_type=section.preferred_format,
                    verification_tier=section.verification_tier.value,
                )
                for section in schema.sections
            ]
        except Exception:
            return []

    def _render_run_summary(self) -> str:
        if self._run_count <= 0:
            return (
                "[#787266]No runs yet.[/]\n"
                "[#a59a86]Go to[/] [#DDEDC4]COMPANIES[/] [#a59a86]and[/] [#DDEDC4]SCHEMA[/] "
                "[#a59a86]to prepare, then launch from[/] [#DDEDC4]AGENTS[/][#a59a86].[/]"
            )
        return (
            f"[#a59a86]Total tracked spend:[/] [#DDEDC4]${self._total_cost:.2f}[/]\n"
            f"[#a59a86]Completed runs:[/] [#DDEDC4]{self._run_count}[/]"
        )

    def reload(
        self,
        *,
        project_brief: str,
        competitor_count: int,
        section_count: int,
        plan_settings: dict[str, object],
        total_cost: float,
        run_count: int,
    ) -> None:
        """Refresh the visible PLAN screen in place from saved workspace state."""
        self._project_brief = project_brief
        self._competitor_count = competitor_count
        self._section_count = section_count
        self._plan_settings = plan_settings
        self._total_cost = total_cost
        self._run_count = run_count

        self._update_card_header("plan-brief-card", "PROJECT BRIEF", self._workspace_root.name)
        self._update_card_header("plan-settings-card", "RUN SETTINGS", self._settings_meta())
        self._update_card_header(
            "plan-cost-card",
            "COST ESTIMATE",
            f"{self._competitor_count} companies · {self._section_count} sections",
        )
        self._update_card_header(
            "plan-run-card",
            "LAST RUN",
            f"{self._run_count} run{'s' if self._run_count != 1 else ''}",
        )

        self.query_one("#plan-brief", Static).update(self._render_brief())
        self.query_one("#plan-settings", Static).update(self._render_settings())
        self.query_one("#plan-cost", Static).update(self._render_cost())
        self.query_one("#plan-run-summary", Static).update(self._render_run_summary())

    def _update_card_header(self, card_id: str, title: str, meta: str) -> None:
        """Keep card header meta in sync after edits without remounting the screen."""
        card = self.query_one(f"#{card_id}")
        header = next(
            (child for child in card.children if isinstance(child, Static)),
            None,
        )
        if header is None:
            return
        rebuilt = TerminalBox._build_header(title, meta)
        if rebuilt is None:
            return
        header.update(rebuilt.render())

    def action_back(self) -> None:
        self.dismiss(None)

    def action_next(self) -> None:
        with contextlib.suppress(Exception):
            self.app.action_goto_tab("schema")

    def action_edit_brief(self) -> None:
        from recon.tui.screens.describe import DescribeScreen

        self.app.push_screen(
            DescribeScreen(
                output_dir=self._workspace_root,
                initial_description=self._project_brief,
            ),
            self.app._handle_plan_describe_result,  # type: ignore[attr-defined]
        )

    def _apply_settings(self, *, model_name: str | None = None, workers: int | None = None, verification_mode: str | None = None) -> None:
        next_model = str(model_name or self._plan_settings.get("model_name", "sonnet"))
        next_workers = int(workers if workers is not None else self._plan_settings.get("workers", 5))
        next_verification = str(verification_mode or self._plan_settings.get("verification_mode", "standard"))
        self.app._save_plan_settings(  # type: ignore[attr-defined]
            model_name=next_model,
            workers=next_workers,
            verification_mode=next_verification,
        )
        self.app._refresh_plan_screen()  # type: ignore[attr-defined]

    def action_cycle_model(self) -> None:
        models = [str(model["name"]) for model in list_available_models()]
        current = str(self._plan_settings.get("model_name", "sonnet"))
        if current not in models:
            next_model = models[0]
        else:
            next_model = models[(models.index(current) + 1) % len(models)]
        self._apply_settings(model_name=next_model)

    def action_cycle_verification(self) -> None:
        modes = ["standard", "verified", "deep"]
        current = str(self._plan_settings.get("verification_mode", "standard"))
        if current not in modes:
            next_mode = modes[0]
        else:
            next_mode = modes[(modes.index(current) + 1) % len(modes)]
        self._apply_settings(verification_mode=next_mode)

    def action_more_workers(self) -> None:
        workers = int(self._plan_settings.get("workers", 5))
        self._apply_settings(workers=min(20, workers + 1))

    def action_fewer_workers(self) -> None:
        workers = int(self._plan_settings.get("workers", 5))
        self._apply_settings(workers=max(1, workers - 1))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        match event.button.id:
            case "btn-edit-brief":
                self.action_edit_brief()
            case "btn-model":
                self.action_cycle_model()
            case "btn-verify":
                self.action_cycle_verification()
            case "btn-workers":
                self.action_more_workers()
            case "btn-back":
                self.action_back()
            case "btn-next":
                self.action_next()
