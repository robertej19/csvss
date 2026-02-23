"""HeatmapArtist: render a single-metric heatmap with CSS tooltips.

For now this is a purely local HTML generator that turns a pandas
DataFrame into a small grid of DIVs. Interactivity is limited to CSS
hover tooltips; linking to global controls happens in later steps.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

import pandas as pd

from cssplt.core.utils import esc


@dataclass
class HeatmapArtist:
    """Single-metric heatmap from a tidy DataFrame.

    The input ``df`` is expected to contain at least three columns:
    - ``row``: row key (e.g. model)
    - ``col``: column key (e.g. dataset)
    - ``metric``: chosen metric column name (e.g. accuracy, latency, cost)
    """

    df: pd.DataFrame
    row: str = "model"
    col: str = "dataset"
    metric: str = "accuracy"
    heatmap_id: str = "heatmap"

    def render_html(self) -> str:
        """Return HTML for the heatmap grid."""
        if self.row not in self.df or self.col not in self.df or self.metric not in self.df:
            raise ValueError(
                f"DataFrame must contain '{self.row}', '{self.col}', and '{self.metric}' columns"
            )

        pivot = self.df.pivot(index=self.row, columns=self.col, values=self.metric)
        if pivot.empty:
            return '<div class="cssplt-heatmap cssplt-heatmap--empty">No data</div>'

        row_labels = [str(r) for r in pivot.index]
        col_labels = [str(c) for c in pivot.columns]

        vmin = float(pivot.min().min())
        vmax = float(pivot.max().max())
        if not (vmax > vmin):
            # Avoid divide-by-zero; fall back to mid-level.
            vmax = vmin + 1.0

        def color_for(value: float) -> str:
            """Return an HSL color string for the cell value."""
            if pd.isna(value):
                return "transparent"
            t = (float(value) - vmin) / (vmax - vmin)
            t = max(0.0, min(1.0, t))
            # Simple viridis-ish: hue 260 -> 60, lightness 25 -> 85
            hue = 260 - 200 * t
            light = 25 + 60 * t
            return f"hsl({hue:.0f}, 80%, {light:.0f}%)"

        n_cols = len(col_labels) + 1  # plus row-header column
        lines: list[str] = []
        lines.append(
            f'<div class="cssplt-heatmap" data-heatmap-id="{esc(self.heatmap_id)}" '
            f'data-metric="{esc(self.metric)}">'
        )

        # Header row: empty corner + column headers.
        lines.append(
            f'  <div class="cssplt-heatmap-row cssplt-heatmap-row--header" '
            f'style="grid-template-columns: repeat({n_cols}, minmax(48px, 1fr));">'
        )
        lines.append('    <div class="cssplt-heatmap-cell cssplt-heatmap-cell--corner"></div>')
        for col_label in col_labels:
            lines.append(
                '    <div class="cssplt-heatmap-cell cssplt-heatmap-cell--col-header">'
                f"{esc(col_label)}</div>"
            )
        lines.append("  </div>")

        # Body rows.
        for r_label in row_labels:
            row_values = pivot.loc[r_label]
            lines.append(
                f'  <div class="cssplt-heatmap-row" '
                f'style="grid-template-columns: repeat({n_cols}, minmax(48px, 1fr));">'
            )
            # Row header.
            lines.append(
                '    <div class="cssplt-heatmap-cell cssplt-heatmap-cell--row-header">'
                f"{esc(r_label)}</div>"
            )
            # Value cells.
            for c_label in col_labels:
                value = float(row_values[c_label])
                color = color_for(value)
                tooltip = f"{r_label} / {c_label}: {value:.3f}"
                lines.append(
                    '    <div class="cssplt-heatmap-cell cssplt-heatmap-cell--value"'
                    f' data-row="{esc(r_label)}"'
                    f' data-col="{esc(c_label)}"'
                    f' data-value="{value:.4f}"'
                    f' style="background-color: {color};">'
                    f'<div class="cssplt-heatmap-cell-inner">{value:.3f}</div>'
                    f'<div class="cssplt-heatmap-tooltip">{esc(tooltip)}</div>'
                    "</div>"
                )
            lines.append("  </div>")

        lines.append("</div>")
        return "\n".join(lines)

    def render_html_views(
        self,
        metric_var_key: str,
        metric_values: List[str],
    ) -> Tuple[str, str]:
        """Render one heatmap per metric and CSS to show only the selected view (Option B).

        Returns (html_fragment, css_fragment). Use the CSS in the figure's
        main <style> so :has() on the metric radio shows the matching view.
        """
        html_parts: List[str] = []
        for m in metric_values:
            if m not in self.df.columns:
                raise ValueError(
                    f"Metric '{m}' is not a column of the heatmap DataFrame"
                )
            one = HeatmapArtist(
                df=self.df,
                row=self.row,
                col=self.col,
                metric=m,
                heatmap_id=f"{self.heatmap_id}-{m}",
            )
            view_html = one.render_html()
            html_parts.append(
                f'<div class="cssplt-heatmap-view" data-metric-view="{esc(m)}">'
                f"{view_html}</div>"
            )
        html_fragment = "\n".join(html_parts)

        css_lines: List[str] = [
            ".cssplt-heatmap-view { display: none; }",
        ]
        for m in metric_values:
            sel = (
                f'.cssplt-fig:has(input[type="radio"][data-var-key="{esc(metric_var_key)}"]'
                f'[data-var-value="{esc(m)}"]:checked) '
                f'.cssplt-heatmap-view[data-metric-view="{esc(m)}"]'
            )
            css_lines.append(f"{sel} {{ display: block; }}")
        css_fragment = "\n".join(css_lines)
        return (html_fragment, css_fragment)

