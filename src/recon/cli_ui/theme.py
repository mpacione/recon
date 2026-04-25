"""Recon CLI theme — the parchment palette from the v4 web UI.

Colors are **foreground-only**: we never set a background. The user's
terminal owns the background, and fg-only painting means the same
palette reads well on both dark and light themes, and degrades
gracefully in 256-color terminals where truecolor isn't available.

Palette lifted 1:1 from ``src/recon/web/static/primitives.css`` ``:root``:

    --recon-fg        #ede5c4   cream primary
    --recon-body      #a59a86   tan body text
    --recon-dim       #787266   dim tan
    --recon-muted     #7f776a   muted (input hints)
    --recon-subdued   #686359   very dim
    --recon-active    #ffffff   the one-up-from-fg accent
    --recon-border    #3a3a3a   hairline
    --recon-error     #fb4b4b   validation red

Reference markup anywhere via Rich style names, e.g.
``console.print("[accent]saved[/accent]")`` or
``Panel(body, border_style="border")``.
"""

from __future__ import annotations

from rich.theme import Theme

# Semantic style names — prefer these in view code over hex values.
RECON_STYLES: dict[str, str] = {
    # Foreground primitives
    "accent":   "#ede5c4",          # cream — titles, primary buttons, active values
    "active":   "bold #ffffff",     # the one-up-from-fg highlight (active tab)
    "body":     "#a59a86",          # normal prose / tables / lists
    "dim":      "#787266",          # meta text, secondary timestamps
    "muted":    "#7f776a",          # placeholders, disabled hints
    "subdued":  "#686359",          # very dim — empty checkboxes, ghost rails
    "border":   "#3a3a3a",          # 1-cell hairlines
    "error":    "#fb4b4b",          # red validation / failure
    "ok":       "#ede5c4",          # "saved", "done" — same cream as accent
    # Semantic aliases — map status vocabulary to palette roles.
    "status.new":      "#ede5c4",
    "status.running":  "#ede5c4",
    "status.paused":   "#a59a86",
    "status.complete": "#ede5c4",
    "status.failed":   "#fb4b4b",
    "status.missing":  "#787266",
    "status.cancelled":"#787266",
    # Role aliases reused across cards.
    "card.title":     "bold #a59a86",
    "card.meta":      "#a59a86",
    "card.footer":    "#787266",
    "card.key":       "#ede5c4",     # [key] bracket contents in footers
    # Key hint chips: the `[N]` part of button labels.
    "kbd":            "#ede5c4",
    # Shaded-block progress bar.
    "bar":            "#ede5c4",
    "bar.empty":      "#3a3a3a",
    "bar.pct":        "#a59a86",
    # Markdown rendering (rich.markdown).
    "markdown.h1":    "bold #ffffff",
    "markdown.h2":    "bold #ede5c4",
    "markdown.h3":    "#ede5c4",
    "markdown.h4":    "#a59a86",
    "markdown.code":  "#ede5c4 on default",
    "markdown.link":  "underline #ede5c4",
    "markdown.block_quote": "italic #a59a86",
    "markdown.list":  "#a59a86",
    "markdown.item":  "#a59a86",
    "markdown.hr":    "#3a3a3a",
    "markdown.strong":"bold #ede5c4",
    "markdown.emph":  "italic #a59a86",
    "markdown.table_header": "bold #ede5c4",
    # Tree (rich.tree) guide lines — the `├── └── │`.
    "tree":           "#3a3a3a",
    "tree.line":      "#3a3a3a",
}

RECON_THEME = Theme(RECON_STYLES, inherit=True)
