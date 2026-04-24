"""v4 parchment theme for the recon TUI.

Aesthetic mirror of the web UI (``src/recon/web/static/primitives.css``)
and the pure CLI (``src/recon/cli_ui/theme.py``): cream ``#DDEDC4`` on
black, tan body, 1-cell hairlines, no background fills on content.

The previous theme was the amber cyberspace.online look with
``#DDEDC4`` as the accent. The swap here mirrors what ``RECON_STYLES``
does on the CLI side — foreground colors only, same semantic slot
names, same palette.
"""

RECON_THEME: dict[str, str] = {
    # Core palette — 1:1 with cli_ui/theme.py and web primitives.css.
    "background":   "#000000",
    "foreground":   "#DDEDC4",  # cream — primary accent (was #DDEDC4)
    "body":         "#a59a86",  # tan — normal prose, NEW slot
    "dim":          "#787266",  # dim tan (was #a59a86)
    "muted":        "#7f776a",  # placeholders, inputs
    "subdued":      "#686359",  # very dim — ghost rails
    "active":       "#ffffff",  # the one-up-from-fg highlight
    "accent":       "#DDEDC4",  # alias — used widely; kept === foreground
    "border":       "#3a3a3a",
    "border_sm":    "#353535",
    "nav_bg":       "#2e2b27",  # translucent nav wash (opaque here; Textual can't alpha)
    "error":        "#fb4b4b",  # was #fb4b4b
    "success":      "#DDEDC4",  # cream — "saved"/"done"
    "warning":      "#a59a86",  # tan — non-fatal warnings
    "surface":      "#000000",
    "panel":        "#000000",
}

# Textual CSS for the v4 aesthetic. Kept inline (rather than a .tcss
# file) to match how the rest of the project composes CSS.
RECON_CSS = """
/* ------------------------------------------------------------------ *
 * Base screen
 * ------------------------------------------------------------------ */

Screen {
    background: #000000;
    color: #a59a86;
    scrollbar-background: #000000;
    scrollbar-color: #3a3a3a;
    scrollbar-color-hover: #DDEDC4;
    scrollbar-color-active: #DDEDC4;
    scrollbar-size-vertical: 1;
}

/* ------------------------------------------------------------------ *
 * Chrome — top nav + bottom keybar
 *
 * Header/Footer are the canonical Textual widgets; we override their
 * colors and let screens slot in our own TabStrip / KeyBar widgets as
 * DOM siblings for the fancier v4 treatment.
 * ------------------------------------------------------------------ */

Header {
    display: none;
}

Footer {
    display: none;
}

Footer > .footer--key {
    color: #DDEDC4;
    background: transparent;
}
Footer > .footer--description {
    color: #a59a86;
    background: transparent;
}
Footer > .footer--highlight {
    background: transparent;
    color: #ffffff;
}

/* ------------------------------------------------------------------ *
 * Utility classes — referenced by screens for semantic styling
 * ------------------------------------------------------------------ */

.title {
    color: #DDEDC4;
    text-style: bold;
}

.meta {
    color: #a59a86;
}

.dim {
    color: #787266;
}

.muted {
    color: #7f776a;
}

.subdued {
    color: #686359;
}

.accent {
    color: #DDEDC4;
}

.active {
    color: #ffffff;
    text-style: bold;
}

.body {
    color: #a59a86;
}

.border {
    border: solid #3a3a3a;
}

.success {
    color: #DDEDC4;
}

.error {
    color: #fb4b4b;
}

.warning {
    color: #a59a86;
}

/* ------------------------------------------------------------------ *
 * DataTable — used by the competitor roster + run history views
 * ------------------------------------------------------------------ */

DataTable {
    background: #000000;
    color: #a59a86;
}

DataTable > .datatable--header {
    background: #000000;
    color: #DDEDC4;
    text-style: bold;
}

DataTable > .datatable--cursor {
    background: #DDEDC4;
    color: #000000;
    text-style: bold;
}

DataTable > .datatable--hover {
    background: #000000;
    color: #DDEDC4;
}

/* ------------------------------------------------------------------ *
 * Interactive elements — v4 "ghost" look matches the web UI
 * `.btn` class: transparent bg, 1-cell hairline, primary variant has
 * the cream fill (inverted).
 * ------------------------------------------------------------------ */

Button {
    background: transparent;
    color: #DDEDC4;
    border: solid #3a3a3a;
    height: 3;
    min-height: 3;
    max-height: 3;
    min-width: 8;
    padding: 0 1;
    content-align: center middle;
    text-style: none;
}

Button:hover {
    background: transparent;
    color: #ffffff;
    border: solid #DDEDC4;
    text-style: none;
}

Button:focus {
    background: transparent;
    color: #ffffff;
    border: solid #DDEDC4;
    text-style: none;
}

/* Primary variant — cream fill, black text (matches the web UI's
 * .btn--primary). Used for NEW / NEXT / primary confirms. */
Button.-primary {
    background: transparent;
    color: #DDEDC4;
    border: solid #3a3a3a;
    height: 3;
    min-height: 3;
    max-height: 3;
    padding: 0 1;
    content-align: center middle;
    text-style: none;
}

Button.-primary:hover {
    background: transparent;
    color: #ffffff;
    border: solid #DDEDC4;
    text-style: none;
}

Button.-primary:focus {
    background: transparent;
    color: #ffffff;
    border: solid #DDEDC4;
    text-style: none;
}

Button.-error {
    background: transparent;
    color: #fb4b4b;
    border: solid #fb4b4b;
    text-style: none;
}

Button.-error:hover {
    background: transparent;
    color: #fb4b4b;
    border: solid #fb4b4b;
    text-style: bold;
}

Button.-warning {
    background: transparent;
    color: #a59a86;
    border: solid #a59a86;
}

/* Ghost — borderless for footer actions / inline hints. */
Button.-ghost {
    background: transparent;
    color: #a59a86;
    border: none;
    text-style: none;
}
Button.-ghost:hover {
    color: #DDEDC4;
    border: none;
}

/* ------------------------------------------------------------------ *
 * Input / SelectionList
 * ------------------------------------------------------------------ */

Input {
    background: #000000;
    color: #DDEDC4;
    border: solid #353535;
}

Input:focus {
    border: solid #DDEDC4;
}

Input > .input--placeholder {
    color: #7f776a;
}

SelectionList {
    background: #000000;
    color: #a59a86;
    border: solid #3a3a3a;
}

SelectionList:focus {
    border: solid #DDEDC4;
}

SelectionList > .selection-list--button {
    color: #DDEDC4;
}

SelectionList > .selection-list--button-selected {
    color: #ffffff;
    text-style: bold;
}

/* ------------------------------------------------------------------ *
 * Static + Label defaults — prevent Textual auto-styling them bright
 * ------------------------------------------------------------------ */

Label {
    color: #a59a86;
}

Static {
    color: #a59a86;
}

/* ------------------------------------------------------------------ *
 * v4 primitives — TabStrip, CardContainer, ShadedBar widget classes
 * ------------------------------------------------------------------ */

TabStrip {
    /* Intentionally NOT docked — ReconScreen.compose yields TabStrip
     * first so it appears at the top naturally. Two dock:top siblings
     * overlap at y=0 in Textual. */
    height: 1;
    background: #2e2b27;
    color: #a59a86;
    padding: 0 1;
    border-bottom: solid #2e2b27;
}

TabStrip > .tab-strip--brand {
    color: #DDEDC4;
    text-style: bold;
}

TabStrip > .tab-strip--tab {
    color: #a59a86;
    padding: 0 1;
}

TabStrip > .tab-strip--tab-active {
    color: #ffffff;
    text-style: bold;
}

TabStrip > .tab-strip--separator {
    color: #686359;
}

KeyBar {
    height: 1;
    background: #2e2b27;
    color: #787266;
    padding: 0 1;
    border-top: solid #2e2b27;
}

KeyBar > .key-bar--key {
    color: #DDEDC4;
    text-style: bold;
}

KeyBar > .key-bar--label {
    color: #787266;
}

/* Card container — a .card with optional title band (upper border) and
 * subtitle (lower border). Textual's Border component supports a label
 * line via border_title / border_subtitle attributes. */

.card {
    border: solid #3a3a3a;
    padding: 0 1;
    background: transparent;
    color: #a59a86;
}

.card-filled {
    background: #DDEDC4;
    color: #000000;
    border: solid #DDEDC4;
}

.card-highlight {
    border: thick #DDEDC4;
}
"""
