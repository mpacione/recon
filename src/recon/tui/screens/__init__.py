"""Textual Screen subclasses for the recon TUI.

Also re-exports DashboardData and build_dashboard_data for backward
compatibility with code that imports from recon.tui.screens.
"""

from recon.tui.models.dashboard import DashboardData, build_dashboard_data

__all__ = ["DashboardData", "build_dashboard_data"]
