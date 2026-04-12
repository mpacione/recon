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

/* -------------------------------------------------------------------
 * Global interactive element overhaul — cyberspace.online aesthetic
 *
 * cyberspace.online buttons are THIN: transparent bg, 1px border,
 * monospace text, border brightens on hover/focus. Textual's default
 * Button has a blue primary fill and 3-line-tall block borders that
 * look completely wrong against the Gruvbox palette. These overrides
 * make every Button in the app match the cyberspace aesthetic by
 * default — no per-screen CSS needed.
 * ------------------------------------------------------------------- */

/* Base button — ghost style (transparent bg, dim border) */
Button {
    background: transparent;
    color: #efe5c0;
    border: solid #3a3a3a;
    height: 3;
    min-width: 8;
    padding: 0 1;
    text-style: none;
}

Button:hover {
    background: #1a1510;
    color: #efe5c0;
    border: solid #a89984;
    text-style: none;
}

Button:focus {
    background: transparent;
    color: #efe5c0;
    border: solid #e0a044;
    text-style: none;
}

/* Primary variant — inverted for emphasis (cream border, stands out) */
Button.-primary {
    background: transparent;
    color: #e0a044;
    border: solid #e0a044;
    text-style: bold;
}

Button.-primary:hover {
    background: #2a1f10;
    color: #e0a044;
    border: solid #e0a044;
    text-style: bold;
}

Button.-primary:focus {
    background: #2a1f10;
    color: #e0a044;
    border: solid #e0a044;
    text-style: bold;
}

/* Error variant — red border, red text */
Button.-error {
    background: transparent;
    color: #cc241d;
    border: solid #cc241d;
    text-style: none;
}

Button.-error:hover {
    background: #1a0505;
    color: #cc241d;
    border: solid #cc241d;
}

/* Warning variant */
Button.-warning {
    background: transparent;
    color: #d79921;
    border: solid #d79921;
}

/* Input fields — transparent bg, dim border, amber on focus */
Input {
    background: #0d0d0d;
    color: #efe5c0;
    border: solid #3a3a3a;
}

Input:focus {
    border: solid #e0a044;
}

Input > .input--placeholder {
    color: #a89984;
}

/* SelectionList items (wizard checkboxes, etc) */
SelectionList {
    background: #0d0d0d;
    color: #efe5c0;
    border: solid #3a3a3a;
}

SelectionList:focus {
    border: solid #e0a044;
}

SelectionList > .selection-list--button {
    color: #e0a044;
}
"""
