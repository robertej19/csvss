"""KDEArtist: SVG density curves with hover via <title> and hit-target.

v0 renders only: subset=empty (no tag selected) + each single tag.
Multiple tags selected is treated as empty (documented). No JavaScript.
"""

from __future__ import annotations

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
    from cssplt.core.state import MultiCheckVar, RadioVar

# SVG size for one KDE plot
KDE_WIDTH = 360
KDE_HEIGHT = 160
KDE_PADDING = 24
KDE_BINS = 50
# Hit target: wider stroke for easier hover, stroke-opacity 0.001 (not 0)
KDE_HIT_STROKE_WIDTH = 12


def _histogram_density(values: List[float], n_bins: int) -> Tuple[List[float], List[float]]:
    """Return (bin_centers, densities). Pure Python, no numpy."""
    if not values:
        return [], []
    lo, hi = min(values), max(values)
    if hi <= lo:
        lo, hi = lo - 0.5, hi + 0.5
    bin_width = (hi - lo) / n_bins
    counts = [0] * n_bins
    for v in values:
        i = int((v - lo) / bin_width)
        if i >= n_bins:
            i = n_bins - 1
        counts[i] += 1
    n = len(values)
    densities = [c / (n * bin_width) if n and bin_width else 0 for c in counts]
    centers = [lo + (i + 0.5) * bin_width for i in range(n_bins)]
    return centers, densities


def _path_from_curve(
    xs: List[float],
    ys: List[float],
    x_min: float,
    x_max: float,
    y_max: float,
    width: int,
    height: int,
    padding: int,
) -> str:
    """Convert (x, density) points to SVG path d attribute (polyline)."""
    if not xs or not y_max:
        return ""
    w = width - 2 * padding
    h = height - 2 * padding
    x_scale = w / (x_max - x_min) if x_max > x_min else 1
    pts: List[str] = []
    for x, y in zip(xs, ys):
        sx = padding + (x - x_min) * x_scale
        sy = height - padding - (y / y_max * h) if y_max else height - padding
        pts.append(f"{sx:.2f},{sy:.2f}")
    return "M " + " L ".join(pts)


@dataclass
class KDEArtist:
    """KDE curves from a long-format DataFrame (tag, metric, value)."""

    df: pd.DataFrame
    tag_col: str = "tag"
    metric_col: str = "metric"
    value_col: str = "value"
    kde_id: str = "kde"

    def _curve_for_subset(
        self,
        metric_value: str,
        tag_subset: str,
        values: List[float],
        x_min: float,
        x_max: float,
        global_max_density: float,
    ) -> str:
        """One variant: SVG <g> with visible path + hit-target path (stroke-opacity 0.001)."""
        if not values:
            return ""
        centers, densities = _histogram_density(values, KDE_BINS)
        path_d = _path_from_curve(
            centers,
            densities,
            x_min,
            x_max,
            global_max_density,
            KDE_WIDTH,
            KDE_HEIGHT,
            KDE_PADDING,
        )
        if not path_d:
            return ""
        label = "no tag" if tag_subset == "empty" else tag_subset
        title_esc = esc(f"KDE ({label})")
        g = (
            f'<g class="cssplt-kde-variant" data-tag-subset="{esc(tag_subset)}">'
            f'<path class="cssplt-kde-curve" fill="none" stroke="currentColor" '
            f'stroke-width="1.5" d="{path_d}"/>'
            f'<path class="cssplt-kde-hit" fill="none" stroke="currentColor" '
            f'stroke-width="{KDE_HIT_STROKE_WIDTH}" stroke-opacity="0.001" d="{path_d}">'
            f"<title>{title_esc}</title></path>"
            "</g>"
        )
        return g

    def _svg_for_metric(
        self,
        metric_value: str,
        variant_values: List[Tuple[str, List[float]]],
        x_min: float,
        x_max: float,
        global_max_density: float,
    ) -> str:
        """One SVG containing all tag variants for this metric."""
        curves = []
        for tag_subset, values in variant_values:
            curves.append(
                self._curve_for_subset(
                    metric_value,
                    tag_subset,
                    values,
                    x_min,
                    x_max,
                    global_max_density,
                )
            )
        curves_html = "\n    ".join(c for c in curves if c)
        return (
            f'<svg class="cssplt-kde-svg" viewBox="0 0 {KDE_WIDTH} {KDE_HEIGHT}" '
            f'preserveAspectRatio="xMidYMid meet">'
            f"\n    {curves_html}\n"
            "</svg>"
        )

    def _values_for_subset(
        self,
        sub: pd.DataFrame,
        subset: Tuple[str, ...],
        tag_var: "MultiCheckVar",
    ) -> List[float]:
        """Values for this metric filtered by tag subset. Empty subset = all data."""
        if not subset:
            return sub[self.value_col].dropna().astype(float).tolist()
        if tag_var.filter_mode == TagFilterMode.ANY:
            # OR: rows with any tag in subset
            mask = sub[self.tag_col].isin(set(subset))
        else:
            # ALL: with one tag per row, only non-empty when len(subset)==1
            if len(subset) == 1:
                mask = sub[self.tag_col] == subset[0]
            else:
                mask = pd.Series(False, index=sub.index)
        return sub.loc[mask, self.value_col].dropna().astype(float).tolist()

    def render_html_views(
        self,
        metric_var: "RadioVar",
        tag_var: "MultiCheckVar",
    ) -> Tuple[str, str]:
        """Pre-render one view per metric; tag variants are combinatorial when
        total combinations <= MAX_TAG_COMBINATIONS, else single-tag only.
        """
        metric_values = [opt.value for opt in metric_var.options]
        tag_values = [opt.value for opt in tag_var.options]
        n_combos = 2 ** len(tag_values)
        use_combinatorial = n_combos <= MAX_TAG_COMBINATIONS

        if use_combinatorial:
            variants = iter_tag_subsets(tag_values)  # [(key, subset), ...]
        else:
            # Single-tag-only fallback: empty + each single tag
            variants = [("empty", ())] + [(t, (t,)) for t in tag_values]

        html_parts: List[str] = []
        css_parts: List[str] = [
            ".cssplt-kde-svg { width: 100%; height: auto; max-height: 200px; }",
        ]

        for m in metric_values:
            if m not in self.df[self.metric_col].values:
                continue
            sub = self.df[self.df[self.metric_col] == m]
            variant_values: List[Tuple[str, List[float]]] = []
            max_density = 0.0
            for key, subset in variants:
                vals = self._values_for_subset(sub, subset, tag_var)
                variant_values.append((key, vals))
                if vals:
                    _, densities = _histogram_density(vals, KDE_BINS)
                    max_density = max(max_density, max(densities) if densities else 0)
            all_vals = sub[self.value_col].dropna().astype(float).tolist()
            x_min = min(all_vals) if all_vals else 0
            x_max = max(all_vals) if all_vals else 1
            if not max_density:
                max_density = 1.0
            svg = self._svg_for_metric(
                m, variant_values, x_min, x_max, max_density
            )
            html_parts.append(
                f'<div class="cssplt-kde-metric-view" data-metric="{esc(m)}">'
                f"{svg}</div>"
            )

        # CSS: metric view switching
        css_parts.append(".cssplt-kde-metric-view { display: none; }")
        for m in metric_values:
            sel = (
                f'.cssplt-fig:has(input[type="radio"][data-var-key="{esc(metric_var.key)}"]'
                f'[data-var-value="{esc(m)}"]:checked) '
                f'.cssplt-kde-metric-view[data-metric="{esc(m)}"]'
            )
            css_parts.append(f"{sel} {{ display: block; }}")

        # CSS: tag variant switching — one rule per variant (exact checkbox set).
        css_parts.append(".cssplt-kde-variant { display: none; }")
        for key, subset in variants:
            sel = tag_var.subset_selector(list(subset))
            css_parts.append(
                f'{sel} .cssplt-kde-variant[data-tag-subset="{esc(key)}"] '
                "{ display: block; }"
            )
        if not use_combinatorial:
            # When over cap, 2+ selected: show empty (ALL mode only; ANY already per-tag).
            if tag_var.filter_mode == TagFilterMode.ALL:
                for sel in tag_var.at_least_n_checked_selectors(2):
                    css_parts.append(
                        f'{sel} .cssplt-kde-variant[data-tag-subset="empty"] '
                        "{ display: block; }"
                    )

        html_fragment = "\n".join(html_parts)
        css_fragment = "\n".join(css_parts)
        return (html_fragment, css_fragment)
