"""Warm amber retro terminal theme for recon.

Aesthetic reference: cyberspace.online
Pure black background, warm parchment text, amber accents.
"""

RECON_THEME: dict[str, str] = {
    "background": "#000000",
    "foreground": "#efe5c0",
    "dim": "#a89984",
    "border": "#3a3a3a",
    "accent": "#e0a044",
    "error": "#cc241d",
    "success": "#98971a",
    "warning": "#d79921",
    "surface": "#1a1a1a",
    "panel": "#0d0d0d",
}

RECON_CSS = """
Screen {
    background: #000000;
    color: #efe5c0;
}

Header {
    background: #0d0d0d;
    color: #e0a044;
    dock: top;
    height: 3;
}

Footer {
    background: #0d0d0d;
    color: #a89984;
    dock: bottom;
}

.title {
    color: #e0a044;
    text-style: bold;
}

.dim {
    color: #a89984;
}

.border {
    border: solid #3a3a3a;
}

.success {
    color: #98971a;
}

.error {
    color: #cc241d;
}

.warning {
    color: #d79921;
}

DataTable {
    background: #000000;
    color: #efe5c0;
}

DataTable > .datatable--header {
    background: #1a1a1a;
    color: #e0a044;
    text-style: bold;
}

DataTable > .datatable--cursor {
    background: #3a3a3a;
    color: #efe5c0;
}
"""
