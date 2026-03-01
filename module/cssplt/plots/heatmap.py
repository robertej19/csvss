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

# Viridis colormap (matplotlib): key RGB samples for interpolation.
_VIRIDIS_RGB = [
    [0.267004, 0.004874, 0.329415],  # 0
    [0.278791, 0.062145, 0.386592],  # 32
    [0.282884, 0.135920, 0.453427],  # 64
    [0.260571, 0.246922, 0.522828],  # 96
    [0.188923, 0.410910, 0.556326],  # 128
    [0.119738, 0.603785, 0.541400],  # 160
    [0.404001, 0.800275, 0.362552],  # 192
    [0.751884, 0.874951, 0.143228],  # 224
    [0.993248, 0.906157, 0.143936],  # 255
]


def _viridis(t: float) -> str:
    """Map t in [0, 1] to viridis hex color."""
    t = max(0.0, min(1.0, t))
    n = len(_VIRIDIS_RGB) - 1
    i = t * n
    lo = int(i)
    hi = min(lo + 1, n)
    frac = i - lo
    r = _VIRIDIS_RGB[lo][0] * (1 - frac) + _VIRIDIS_RGB[hi][0] * frac
    g = _VIRIDIS_RGB[lo][1] * (1 - frac) + _VIRIDIS_RGB[hi][1] * frac
    b = _VIRIDIS_RGB[lo][2] * (1 - frac) + _VIRIDIS_RGB[hi][2] * frac
    return f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"


def _is_dark_bg(hex_color: str) -> bool:
    """Return True if background is dark enough to need white text."""
    if not hex_color or hex_color == "transparent":
        return False
    hex_color = hex_color.lstrip("#")
    if len(hex_color) != 6:
        return False
    r = int(hex_color[0:2], 16) / 255
    g = int(hex_color[2:4], 16) / 255
    b = int(hex_color[4:6], 16) / 255
    lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
    return lum < 0.45


def _viridis_gradient_stops(n: int = 9) -> str:
    """Return CSS linear-gradient color stops for viridis (bottom=min, top=max)."""
    stops = []
    for i in range(n):
        t = i / (n - 1) if n > 1 else 1.0
        pct = int(t * 100)
        stops.append(f"{_viridis(t)} {pct}%")
    return ", ".join(stops)


@dataclass
class HeatmapArtist:
    """Single-metric heatmap from a tidy DataFrame.

    The input ``df`` is expected to contain at least three columns:
    - ``row``: row key (e.g. model)
    - ``col``: column key (e.g. dataset)
    - ``metric``: chosen metric column name (e.g. accuracy, latency, cost)

    Optional ``tag_col``: when set, each body row gets data-tag from that column
    so tag checkboxes can filter rows via CSS (Option A).

    Optional ``decimals``: number of decimal places for cell values (default 3).
    Optional ``show_values``: if False, cell values are hidden (tooltips still show).
    Optional ``notes_col``: when set and present in ``df``, per-cell notes are shown in the tooltip.
    Optional ``show_legend``: if False, the colorbar legend (min/max bar) is hidden.
    """

    df: pd.DataFrame
    row: str = "model"
    col: str = "dataset"
    metric: str = "accuracy"
    heatmap_id: str = "heatmap"
    tag_col: str | None = None
    notes_col: str | None = "notes"
    decimals: int | None = 3
    show_values: bool = True
    show_legend: bool = True

    def render_html(self) -> str:
        """Return HTML for the heatmap grid."""
        if self.row not in self.df or self.col not in self.df or self.metric not in self.df:
            raise ValueError(
                f"DataFrame must contain '{self.row}', '{self.col}', and '{self.metric}' columns"
            )

        pivot = self.df.pivot(index=self.row, columns=self.col, values=self.metric)
        if pivot.empty:
            return '<div class="cssplt-heatmap-wrapper"><div class="cssplt-heatmap cssplt-heatmap--empty">No data</div></div>'

        row_labels = [str(r) for r in pivot.index]
        col_labels = [str(c) for c in pivot.columns]
        row_to_tag: dict[str, str] = {}
        if self.tag_col and self.tag_col in self.df.columns:
            for r in row_labels:
                match = self.df[self.df[self.row].astype(str) == r]
                if not match.empty:
                    row_to_tag[r] = str(match[self.tag_col].iloc[0])

        # (row_key, col_key) -> notes for tooltip
        notes_map: dict[Tuple[str, str], str] = {}
        if self.notes_col and self.notes_col in self.df.columns:
            for _, r in self.df.iterrows():
                rk, ck = str(r[self.row]), str(r[self.col])
                val = r[self.notes_col]
                notes_map[(rk, ck)] = "" if pd.isna(val) else str(val).strip()

        vmin = float(pivot.min().min())
        vmax = float(pivot.max().max())
        if not (vmax > vmin):
            # Avoid divide-by-zero; fall back to mid-level.
            vmax = vmin + 1.0

        decimals = self.decimals if self.decimals is not None else 3

        def color_for(value: float) -> str:
            """Return viridis hex color for the cell value."""
            if pd.isna(value):
                return "transparent"
            t = (float(value) - vmin) / (vmax - vmin)
            t = max(0.0, min(1.0, t))
            return _viridis(t)

        def fmt_cell(v: float) -> str:
            """Format value for cell display."""
            if pd.isna(v):
                return ""
            if decimals == 0:
                return str(int(round(v)))
            return f"{v:.{decimals}f}"

        def fmt_val(v: float) -> str:
            """Format value for legend display."""
            if abs(v) >= 1000 or (abs(v) < 0.01 and v != 0):
                return f"{v:.2g}"
            return f"{v:.3f}".rstrip("0").rstrip(".")

        n_cols = len(col_labels) + 1  # plus row-header column
        gradient_stops = _viridis_gradient_stops()
        lock_name = f"heatmap-lock-{esc(self.heatmap_id)}"
        lock_none_id = f"{lock_name}-none".replace(" ", "_")
        lines: list[str] = []
        lines.append('<div class="cssplt-heatmap-wrapper">')
        lines.append(
            f'  <input type="radio" name="{lock_name}" value="none" '
            f'id="{lock_none_id}" checked class="cssplt-input cssplt-heatmap-lock-none">'
        )
        lines.append(
            f'  <div class="cssplt-heatmap" data-heatmap-id="{esc(self.heatmap_id)}" '
            f'data-metric="{esc(self.metric)}">'
        )

        # Header row: empty corner + column headers.
        lines.append(
            f'    <div class="cssplt-heatmap-row cssplt-heatmap-row--header" '
            f'style="grid-template-columns: repeat({n_cols}, minmax(0, 1fr));">'
        )
        lines.append('      <div class="cssplt-heatmap-cell cssplt-heatmap-cell--corner"></div>')
        for col_label in col_labels:
            lines.append(
                '      <div class="cssplt-heatmap-cell cssplt-heatmap-cell--col-header">'
                f"{esc(col_label)}</div>"
            )
        lines.append("    </div>")

        # Body rows.
        for r_label in row_labels:
            row_values = pivot.loc[r_label]
            data_tag = f' data-tag="{esc(row_to_tag[r_label])}"' if r_label in row_to_tag else ""
            lines.append(
                f'    <div class="cssplt-heatmap-row"'
                f'{data_tag} '
                f'style="grid-template-columns: repeat({n_cols}, minmax(0, 1fr));">'
            )
            # Row header.
            lines.append(
                '      <div class="cssplt-heatmap-cell cssplt-heatmap-cell--row-header">'
                f"{esc(r_label)}</div>"
            )
            # Value cells: label + hidden radio for click-to-lock; tooltip shows when locked.
            for c_label in col_labels:
                value = float(row_values[c_label])
                color = color_for(value)
                value_line = f"{r_label} / {c_label}: {value:.3f}"
                notes = notes_map.get((r_label, c_label), "").strip()
                tooltip_inner = f'<span class="cssplt-heatmap-tooltip-value">{esc(value_line)}</span>'
                if notes:
                    tooltip_inner += f'<div class="cssplt-heatmap-tooltip-notes">{esc(notes)}</div>'
                cell_text = fmt_cell(value) if self.show_values else ""
                style_parts = [f"background-color: {color}"]
                if _is_dark_bg(color):
                    style_parts.append("color: #ffffff")
                style_str = "; ".join(style_parts)
                cell_value = f"{r_label}_{c_label}".replace(" ", "_")
                cell_id = f"{lock_name}-{cell_value}".replace(" ", "_")
                lines.append(
                    f'      <label class="cssplt-heatmap-cell cssplt-heatmap-cell--value"'
                    f' for="{esc(cell_id)}"'
                    f' data-row="{esc(r_label)}"'
                    f' data-col="{esc(c_label)}"'
                    f' data-value="{value:.4f}"'
                    f' style="{style_str}">'
                    f'<input type="radio" class="cssplt-input cssplt-heatmap-lock-cell" '
                    f'name="{lock_name}" value="{esc(cell_value)}" id="{esc(cell_id)}">'
                    f'<div class="cssplt-heatmap-cell-inner">{esc(cell_text)}</div>'
                    f'<div class="cssplt-heatmap-tooltip">{tooltip_inner}</div>'
                    "</label>"
                )
            lines.append("    </div>")

        lines.append("  </div>")
        # Legend on the right: bar with max/min labels (optional).
        if self.show_legend:
            lines.append(
                f'  <div class="cssplt-heatmap-legend">'
                f'<span class="cssplt-heatmap-legend-max">{esc(fmt_val(vmax))}</span>'
                f'<div class="cssplt-heatmap-legend-bar" '
                f'style="background: linear-gradient(to top, {gradient_stops});"></div>'
                f'<span class="cssplt-heatmap-legend-min">{esc(fmt_val(vmin))}</span>'
                f"</div>"
            )
        # Overlay: click to unlock (selects "none" radio).
        lines.append(
            f'  <label for="{esc(lock_none_id)}" class="cssplt-heatmap-overlay" '
            f'aria-label="Close tooltip"></label>'
        )
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
                decimals=self.decimals,
                show_values=self.show_values,
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

