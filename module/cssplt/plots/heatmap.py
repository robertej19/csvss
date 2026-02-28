"""HeatmapArtist: render a single-metric heatmap with CSS tooltips.

For now this is a purely local HTML generator that turns a pandas
DataFrame into a small grid of DIVs. Interactivity is limited to CSS
hover tooltips; linking to global controls happens in later steps.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple, TYPE_CHECKING

import pandas as pd

from cssplt.core.utils import esc

if TYPE_CHECKING:
    from cssplt.core.state import MultiCheckVar


@dataclass
class HeatmapArtist:
    """Single-metric heatmap from a tidy DataFrame.

    The input ``df`` is expected to contain at least three columns:
    - ``row``: row key (e.g. model)
    - ``col``: column key (e.g. dataset)
    - ``metric``: chosen metric column name (e.g. accuracy, latency, cost)

    Optional ``tag_col``: when set, each body row gets data-tag from that column
    so tag checkboxes can filter rows via CSS (Option A).
    """

    df: pd.DataFrame
    row: str = "model"
    col: str = "dataset"
    metric: str = "accuracy"
    heatmap_id: str = "heatmap"
    tag_col: str | None = None

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
        row_to_tag: dict[str, str] = {}
        if self.tag_col and self.tag_col in self.df.columns:
            for r in row_labels:
                match = self.df[self.df[self.row].astype(str) == r]
                if not match.empty:
                    row_to_tag[r] = str(match[self.tag_col].iloc[0])

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
            f'style="grid-template-columns: repeat({n_cols}, minmax(0, 1fr));">'
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
            data_tag = f' data-tag="{esc(row_to_tag[r_label])}"' if r_label in row_to_tag else ""
            lines.append(
                f'  <div class="cssplt-heatmap-row"'
                f'{data_tag} '
                f'style="grid-template-columns: repeat({n_cols}, minmax(0, 1fr));">'
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
        tag_var: "MultiCheckVar | None" = None,
        tag_col: str | None = None,
    ) -> Tuple[str, str]:
        """Render one heatmap per metric (Option B) and optional tag row filter (Option A).

        When tag_var and tag_col are provided, body rows get data-tag and CSS
        filters visibility by selected tag(s): no selection = show all; selection = show
        rows whose tag is in the selected set (ANY).
        """
        use_tag_filter = tag_var is not None and tag_col and tag_col in self.df.columns
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
                tag_col=tag_col if use_tag_filter else None,
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

        if use_tag_filter and tag_var is not None:
            # Option A: tag filter rows. Hide tagged rows by default; when no tag
            # selected show all; when tag t selected show rows with data-tag="t".
            css_lines.append(".cssplt-heatmap-row[data-tag] { display: none; }")
            key = esc(tag_var.key)
            css_lines.append(
                f'.cssplt-fig:not(:has(input[type="checkbox"][data-var-key="{key}"]:checked)) '
                '.cssplt-heatmap-row[data-tag] { display: grid; }'
            )
            for opt in tag_var.options:
                t = esc(opt.value)
                css_lines.append(
                    f'.cssplt-fig:has(input[type="checkbox"][data-var-key="{key}"][data-var-value="{t}"]:checked) '
                    f'.cssplt-heatmap-row[data-tag="{t}"] {{ display: grid; }}'
                )
        css_fragment = "\n".join(css_lines)
        return (html_fragment, css_fragment)

