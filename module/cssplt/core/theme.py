"""Minimalist light theme + viridis-style gradients.

Used by the figure shell (soft gray background, white surfaces, dark text)
and by HeatmapArtist (HSL gradient from purple to yellow). No JavaScript;
all styling is inline CSS.
"""

# Light-mode defaults: subtle gray background, white cards, neutral borders.
THEME = {
    "background": "#f5f5f8",       # page background
    "surface": "#ffffff",          # cards / axes boxes / controls surface
    "foreground": "#111827",       # primary text
    "border": "#e5e7eb",           # low-contrast borders
    "pill_bg": "#f3f4f6",          # unselected pill background
    "pill_bg_checked": "#111827",  # selected pill background
    "accent": "#6366f1",           # primary accent (indigo)
    "accent_soft": "#eef2ff",      # soft accent background
    "muted": "#6b7280",            # secondary text
}
