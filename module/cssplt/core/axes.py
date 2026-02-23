"""Axes: subplot container for artists.

For Step 3 this is still a lightweight placeholder, but it now carries a
reference back to its parent Figure and an index so we can render a grid
of empty axes boxes in the HTML shell.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Axes:
    """Minimal axes placeholder for the HTML shell."""

    figure: "Figure"  # string annotation; Figure lives in figure.py
    index: int
    _inner_html: str = field(default="", repr=False)
    _extra_css: str = field(default="", repr=False)

    def set_html(self, html: str) -> None:
        """Set raw HTML content to be rendered inside this axes box."""
        self._inner_html = html

    def set_extra_css(self, css: str) -> None:
        """Set CSS to be merged into the figure's main <style> (e.g. for :has() view switching)."""
        self._extra_css = css

    def _render_box(self) -> str:
        """Return a single box for this axes, including inner HTML if any."""
        inner = self._inner_html or ""
        return (
            f'<div class="cssplt-axes-box" data-axes-index="{self.index}">{inner}</div>'
        )

