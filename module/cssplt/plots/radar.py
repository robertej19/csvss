"""RadarArtist: SVG polygon + vertices, hover via <title> and hit-target.

Tag variants are combinatorial (all subsets) when 2^T <= MAX_TAG_COMBINATIONS,
else single-tag only. No JavaScript.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, List, Tuple

import pandas as pd

from cssplt.core.state import (
    MAX_TAG_COMBINATIONS,
    TagFilterMode,
    iter_tag_subsets,
)
from cssplt.core.utils import esc

if TYPE_CHECKING:
    from cssplt.core.state import MultiCheckVar

RADAR_SIZE = 160
RADAR_CX = RADAR_SIZE / 2
RADAR_CY = RADAR_SIZE / 2
RADAR_R = (RADAR_SIZE / 2) - 16
RADAR_HIT_STROKE_WIDTH = 10


def _polygon_path(
    values: List[float],
    angles_rad: List[float],
    cx: float,
    cy: float,
    r_scale: float,
) -> str:
    """SVG path d for closed polygon. values[i] maps to radius at angles_rad[i]."""
    if not values or len(values) != len(angles_rad):
        return ""
    pts: List[str] = []
    for v, theta in zip(values, angles_rad):
        r = max(0, min(1, float(v))) * r_scale
        x = cx + r * math.sin(theta)
        y = cy - r * math.cos(theta)
        pts.append(f"{x:.2f},{y:.2f}")
    if not pts:
        return ""
    return "M " + " L ".join(pts) + " Z"


@dataclass
class RadarArtist:
    """Radar chart from a DataFrame: one row per series, columns = axis values (0-1)."""

    df: pd.DataFrame
    series_col: str = "series"
    axis_columns: List[str] | None = None  # default: all numeric except series_col
    radar_id: str = "radar"

    def _axis_cols(self) -> List[str]:
        if self.axis_columns is not None:
            return self.axis_columns
        return [
            c for c in self.df.columns
            if c != self.series_col and pd.api.types.is_numeric_dtype(self.df[c])
        ]

    def _rows_for_subset(
        self,
        subset: Tuple[str, ...],
        tag_var: "MultiCheckVar",
    ) -> pd.DataFrame:
        """Rows for this tag subset. Empty subset = all rows."""
        if not subset:
            return self.df
        if tag_var.filter_mode == TagFilterMode.ANY:
            return self.df[self.df[self.series_col].isin(set(subset))]
        if len(subset) == 1:
            return self.df[self.df[self.series_col] == subset[0]]
        return self.df.iloc[0:0]

    def render_html_views(self, tag_var: "MultiCheckVar") -> Tuple[str, str]:
        """Pre-render one variant per tag subset (combinatorial or single-tag only)."""
        tag_values = [opt.value for opt in tag_var.options]
        n_combos = 2 ** len(tag_values)
        use_combinatorial = n_combos <= MAX_TAG_COMBINATIONS

        if use_combinatorial:
            variants = iter_tag_subsets(tag_values)
        else:
            variants = [("empty", ())] + [(t, (t,)) for t in tag_values]

        axes = self._axis_cols()
        if not axes:
            return ("<!-- radar: no axis columns -->", "")
        n_axes = len(axes)
        angles_rad = [2 * math.pi * i / n_axes - math.pi / 2 for i in range(n_axes)]

        html_parts: List[str] = []
        css_parts: List[str] = [
            ".cssplt-radar-svg { width: 100%; height: auto; max-height: 28vh; }",
        ]

        variant_groups: List[str] = []
        for key, subset in variants:
            rows = self._rows_for_subset(subset, tag_var)
            group_parts: List[str] = []
            for _, row in rows.iterrows():
                series_name = str(row[self.series_col])
                vals = [float(row[c]) for c in axes]
                path_d = _polygon_path(
                    vals, angles_rad, RADAR_CX, RADAR_CY, RADAR_R
                )
                if not path_d:
                    continue
                title_esc = esc(f"Radar ({series_name})")
                group_parts.append(
                    f'<path class="cssplt-radar-polygon" fill="none" stroke="currentColor" '
                    f'stroke-width="1.5" d="{path_d}"/>'
                    f'<path class="cssplt-radar-hit" fill="none" stroke="currentColor" '
                    f'stroke-width="{RADAR_HIT_STROKE_WIDTH}" stroke-opacity="0.001" d="{path_d}">'
                    f"<title>{title_esc}</title></path>"
                )
            if group_parts:
                variant_groups.append(
                    f'<g class="cssplt-radar-variant" data-tag-subset="{esc(key)}">'
                    + "\n    ".join(group_parts) +
                    "</g>"
                )
            else:
                variant_groups.append(
                    f'<g class="cssplt-radar-variant" data-tag-subset="{esc(key)}"></g>'
                )

        svg_inner = "\n    ".join(variant_groups)
        svg = (
            f'<svg class="cssplt-radar-svg" viewBox="0 0 {RADAR_SIZE} {RADAR_SIZE}" '
            f'preserveAspectRatio="xMidYMid meet">'
            f"\n    {svg_inner}\n"
            "</svg>"
        )
        html_parts.append(svg)

        css_parts.append(".cssplt-radar-variant { display: none; }")
        for key, subset in variants:
            sel = tag_var.subset_selector(list(subset))
            css_parts.append(
                f'{sel} .cssplt-radar-variant[data-tag-subset="{esc(key)}"] '
                "{ display: block; }"
            )
        if not use_combinatorial and tag_var.filter_mode == TagFilterMode.ALL:
            for sel in tag_var.at_least_n_checked_selectors(2):
                css_parts.append(
                    f'{sel} .cssplt-radar-variant[data-tag-subset="empty"] '
                    "{ display: block; }"
                )

        return ("\n".join(html_parts), "\n".join(css_parts))
