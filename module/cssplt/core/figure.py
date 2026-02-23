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

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>cssplt</title>
<style>
body {{
  margin: 1rem;
  font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  background: #ffffff;
  color: #111111;
}}

.cssplt-fig {{
  max-width: 960px;
  margin: 0 auto;
  display: grid;
  gap: 1rem;
}}

.cssplt-controls {{
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}}

.cssplt-control {{
  display: flex;
  flex-wrap: wrap;
  gap: 0.25rem;
  align-items: center;
}}

.cssplt-input {{
  position: absolute;
  opacity: 0;
  pointer-events: none;
}}

.cssplt-pill {{
  display: inline-block;
  padding: 0.2rem 0.6rem;
  border-radius: 999px;
  border: 1px solid #d0d0d0;
  background: #f8f8f8;
  font-size: 0.85rem;
  cursor: pointer;
  user-select: none;
}}

.cssplt-input:checked + .cssplt-pill {{
  background: #111111;
  color: #ffffff;
  border-color: #111111;
}}

.cssplt-axes-grid {{
  display: grid;
  gap: 0.75rem;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
}}

.cssplt-axes-box {{
  min-height: 180px;
  border-radius: 8px;
  border: 1px solid #e0e0e0;
  background: #fafafa;
  box-shadow: inset 0 0 0 1px rgba(0, 0, 0, 0.02);
}}

.cssplt-heatmap {{
  display: inline-block;
  border-radius: 6px;
  overflow: hidden;
  background: #f5f5f5;
  font-size: 0.75rem;
}}

.cssplt-heatmap-row {{
  display: grid;
}}

.cssplt-heatmap-cell {{
  padding: 0.2rem 0.35rem;
  box-sizing: border-box;
  border: 1px solid rgba(255, 255, 255, 0.6);
  min-width: 2.4rem;
  min-height: 1.6rem;
  display: flex;
  align-items: center;
  justify-content: center;
}}

.cssplt-heatmap-cell--corner {{
  background: #ffffff;
}}

.cssplt-heatmap-cell--row-header,
.cssplt-heatmap-cell--col-header {{
  background: #ffffff;
  font-weight: 600;
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
  transform: translate(-50%, -0.2rem);
  padding: 0.15rem 0.4rem;
  border-radius: 4px;
  background: rgba(0, 0, 0, 0.8);
  color: #ffffff;
  font-size: 0.7rem;
  white-space: nowrap;
  opacity: 0;
  pointer-events: none;
  transition: opacity 120ms ease-out;
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
