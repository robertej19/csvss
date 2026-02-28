"""Figure: top-level container; writes self-contained HTML.

Step 3: the Figure now owns a collection of Axes and an optional
StateRegistry. ``write_html()`` emits a basic HTML shell with:

- a controls area (rendered from the registry), and
- a responsive grid of empty axes boxes.
"""

from __future__ import annotations

from typing import List, Optional

from .axes import Axes
from .state import StateRegistry
from .theme import THEME


class Figure:
    """Figure with a shared StateRegistry and one or more Axes."""

    def __init__(self, state: Optional[StateRegistry] = None) -> None:
        # If no registry is supplied we create an empty one so that
        # write_html() can always rely on ``self.state``.
        self.state: StateRegistry = state or StateRegistry()
        self._axes: List[Axes] = []

    # Public API -----------------------------------------------------
    def add_subplot(self, *args, **kwargs) -> Axes:
        """Create a new Axes and attach it to this figure.

        Arguments are currently ignored but reserved for a future
        Matplotlib-like indexing API.
        """
        index = len(self._axes) + 1
        ax = Axes(figure=self, index=index)
        self._axes.append(ax)
        return ax

    @property
    def axes(self) -> List[Axes]:
        """Return a shallow copy of the axes list."""
        return list(self._axes)

    def write_html(self, path: str) -> None:
        """Write one self-contained HTML file (no JS)."""
        html = self._build_html()
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)

    # Internal helpers -----------------------------------------------
    def _build_html(self) -> str:
        controls_html = self.state.render_html()
        if controls_html:
            controls_block = "\n".join(
                "      " + line for line in controls_html.splitlines()
            )
        else:
            controls_block = "      <!-- no controls -->"

        axes_boxes = [
            ax._render_box() for ax in self._axes  # type: ignore[attr-defined]
        ]
        if axes_boxes:
            axes_block = "\n".join("      " + box for box in axes_boxes)
        else:
            axes_block = "      <!-- no axes -->"

        extra_css_parts = [
            getattr(ax, "_extra_css", "") for ax in self._axes
        ]
        extra_css_block = "\n".join(p for p in extra_css_parts if p).strip()
        if extra_css_block:
            extra_css_block = "\n\n" + extra_css_block
        else:
            extra_css_block = ""

        bg = THEME["background"]
        surface = THEME.get("surface", "#ffffff")
        fg = THEME["foreground"]
        border = THEME["border"]
        pill_bg = THEME["pill_bg"]
        pill_bg_checked = THEME["pill_bg_checked"]
        accent = THEME.get("accent", pill_bg_checked)
        accent_soft = THEME.get("accent_soft", pill_bg)
        muted = THEME.get("muted", "#6b7280")

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>cssplt</title>
<style>
*, *::before, *::after {{
  box-sizing: border-box;
}}

html {{
  width: 100%;
}}

body {{
  margin: 0;
  padding: clamp(2vw, 1rem, 5vw);
  width: 100%;
  max-width: 100%;
  font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  background: {bg};
  color: {fg};
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
}}

.cssplt-fig {{
  width: 100%;
  max-width: min(1120px, 100%);
  min-width: 0;
  margin: 0 auto;
  display: grid;
  gap: clamp(1rem, 2.5vw, 1.5rem);
  padding: clamp(1rem, 2.5vw, 1.5rem);
  border-radius: clamp(12px, 2vw, 16px);
  border: 1px solid {border};
  background: {surface};
  box-shadow: 0 18px 45px rgba(15, 23, 42, 0.08);
}}

.cssplt-controls {{
  display: flex;
  flex-direction: column;
  gap: clamp(0.5rem, 1.5vw, 0.75rem);
  padding-bottom: clamp(0.5rem, 1.5vw, 0.75rem);
  border-bottom: 1px solid {border};
  min-width: 0;
}}

.cssplt-control {{
  display: flex;
  flex-wrap: wrap;
  gap: clamp(0.35rem, 1vw, 0.5rem);
  align-items: center;
  min-width: 0;
}}

.cssplt-input {{
  position: absolute;
  opacity: 0;
  pointer-events: none;
}}

.cssplt-pill {{
  display: inline-block;
  padding: 0.25rem 0.8rem;
  border-radius: 999px;
  border: 1px solid {border};
  background: {pill_bg};
  font-size: 0.85rem;
  cursor: pointer;
  user-select: none;
  color: {muted};
  letter-spacing: 0.01em;
  transition: background-color 140ms ease-out, color 140ms ease-out,
              border-color 140ms ease-out, box-shadow 140ms ease-out;
}}

.cssplt-pill:hover {{
  background: {accent_soft};
  border-color: {accent};
  color: {accent};
  box-shadow: 0 0 0 1px rgba(99, 102, 241, 0.15);
}}

.cssplt-input:checked + .cssplt-pill {{
  background: {accent};
  color: #ffffff;
  border-color: {accent};
  box-shadow: 0 0 0 1px rgba(15, 23, 42, 0.06);
}}

.cssplt-axes-grid {{
  display: grid;
  gap: clamp(1rem, 2.5vw, 1.25rem);
  grid-template-columns: repeat(auto-fit, minmax(min(280px, 100%), 1fr));
  min-width: 0;
}}

.cssplt-axes-box {{
  width: 100%;
  min-width: 0;
  min-height: 22vh;
  border-radius: clamp(8px, 1.5vw, 12px);
  border: 1px solid {border};
  background: {surface};
  box-shadow: 0 12px 30px rgba(15, 23, 42, 0.06);
  padding: clamp(0.75rem, 2vw, 1.25rem);
  display: flex;
  align-items: stretch;
}}

.cssplt-heatmap {{
  display: block;
  width: 100%;
  max-width: 100%;
  min-width: 0;
  border-radius: clamp(8px, 1.5vw, 10px);
  overflow: hidden;
  background: {surface};
  border: 1px solid {border};
  font-size: clamp(0.7rem, 1.1vw, 0.9rem);
}}

.cssplt-heatmap-row {{
  display: grid;
}}

.cssplt-heatmap-cell {{
  padding: 0.2rem 0.35rem;
  box-sizing: border-box;
  border: 1px solid rgba(255, 255, 255, 0.6);
  min-width: 0;
  min-height: 2.5vh;
  display: flex;
  align-items: center;
  justify-content: center;
}}

.cssplt-heatmap-cell--corner {{
  background: {pill_bg};
}}

.cssplt-heatmap-cell--row-header,
.cssplt-heatmap-cell--col-header {{
  background: {pill_bg};
  font-weight: 600;
  color: {muted};
}}

.cssplt-heatmap-cell--value {{
  position: relative;
  cursor: default;
  color: #111;
}}

.cssplt-heatmap-cell-inner {{
  position: relative;
  z-index: 1;
}}

.cssplt-heatmap-tooltip {{
  position: absolute;
  left: 50%;
  bottom: 100%;
  transform: translate(-50%, -0.5rem);
  padding: 0.5rem 0.85rem;
  border-radius: 6px;
  background: #111827;
  color: #ffffff;
  font-size: 0.9rem;
  font-weight: 500;
  white-space: nowrap;
  opacity: 0;
  pointer-events: none;
  transition: opacity 120ms ease-out;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}}

.cssplt-heatmap-cell--value:hover .cssplt-heatmap-tooltip {{
  opacity: 1;
}}{extra_css_block}
</style>
</head>
<body>
<div class="cssplt-fig">
  <div class="cssplt-controls">
{controls_block}
  </div>
  <div class="cssplt-axes-grid">
{axes_block}
  </div>
</div>
</body>
</html>
"""
