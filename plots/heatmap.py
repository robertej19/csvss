from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pandas as pd


# -----------------------------
# Paths
# -----------------------------
SPEC_PATH = Path("data/spec.csv")
DATA_PATH = Path("data/data.sanitized.csv")
OUT_PATH = Path("out/heatmap.html")
OUT_PATH.parent.mkdir(parents=True, exist_ok=True)


# -----------------------------
# Palettes (11-bin, UI-friendly)
# -----------------------------
PALETTES_11 = {
    "viridis": [
        "#440154", "#482878", "#3E4989", "#31688E", "#26828E",
        "#1F9E89", "#35B779", "#6DCD59", "#B4DE2C", "#FDE725",
        "#FFF7B2",
    ],
    "plasma": [
        "#0D0887", "#41049D", "#6A00A8", "#8F0DA4", "#B12A90",
        "#CC4778", "#E16462", "#F2844B", "#FCA636", "#FCCE25",
        "#F0F921",
    ],
    "magma": [
        "#000004", "#1B0C41", "#4F0C6B", "#781C6D", "#A52C60",
        "#CF4446", "#ED6925", "#FB9B06", "#F7D13D", "#FCFDBF",
        "#FFFFFF",
    ],
}


# -----------------------------
# Helpers
# -----------------------------
def esc(s: Any) -> str:
    s = "" if s is None else str(s)
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def sample_palette(base: List[str], bins: int) -> List[str]:
    if bins <= 1:
        return [base[0]]
    out = []
    for k in range(bins):
        t = k / (bins - 1)
        idx = int(round(t * (len(base) - 1)))
        out.append(base[idx])
    return out


def value_to_color(v: float, vmin: float, vmax: float, palette: List[str]) -> str:
    if vmax <= vmin:
        return palette[0]
    t = clamp01((v - vmin) / (vmax - vmin))
    idx = int(math.floor(t * (len(palette) - 1) + 1e-12))
    return palette[idx]


def fmt_value(v: float, fmt: str) -> str:
    if fmt and fmt.startswith("0.") and "." in fmt:
        decimals = len(fmt.split(".", 1)[1])
        return f"{v:.{decimals}f}"
    if fmt == "0":
        return str(int(round(v)))
    return f"{v}"


def mean(xs: List[float]) -> float:
    return sum(xs) / len(xs) if xs else float("nan")


def stddev(xs: List[float]) -> float:
    if len(xs) < 2:
        return 0.0
    m = mean(xs)
    v = sum((x - m) ** 2 for x in xs) / (len(xs) - 1)
    return math.sqrt(max(0.0, v))


def series_colors_from_viridis(k: int) -> List[str]:
    """
    Choose k series colors derived from viridis, avoiding extreme endpoints
    for better contrast on white.
    """
    base = PALETTES_11["viridis"]
    pool = base[1:-1] or base  # drop darkest + lightest if possible
    cols = sample_palette(pool, max(3, k))
    while len(cols) < k:
        cols += cols
    return cols[:k]


# -----------------------------
# Spec parsing
# -----------------------------
def read_spec(spec_path: Path) -> Dict[str, Any]:
    df = pd.read_csv(spec_path).fillna("")
    meta: Dict[str, str] = {}
    layout: Dict[str, str] = {}
    tooltip_fields: Dict[str, str] = {}
    metrics: List[Dict[str, Any]] = []
    tags: List[Dict[str, str]] = []

    for _, r in df.iterrows():
        section = str(r.get("section", "")).strip().lower()
        if not section:
            continue

        if section in ("meta", "layout", "tooltip_fields"):
            key = str(r.get("key", "")).strip()
            val = r.get("value", "")
            if not key:
                continue
            if section == "meta":
                meta[key] = str(val)
            elif section == "layout":
                layout[key] = str(val)
            else:
                tooltip_fields[key] = str(val).strip().lower()
            continue

        if section == "metrics":
            m_id = str(r.get("m_id", "")).strip()
            if not m_id:
                continue
            metrics.append(
                dict(
                    m_id=m_id,
                    label=str(r.get("label", "")).strip() or m_id,
                    fmt=str(r.get("fmt", "")).strip() or "0.000",
                    palette=str(r.get("palette", "")).strip().lower() or "viridis",
                    vmin=float(r.get("min", 0.0) or 0.0),
                    vmax=float(r.get("max", 1.0) or 1.0),
                    bins=int(float(r.get("bins", 11) or 11)),
                )
            )
            continue

        if section == "tags":
            tag_id = str(r.get("tag_id", "")).strip()
            if not tag_id:
                continue
            tags.append(dict(tag_id=tag_id, tag_label=str(r.get("tag_label", "")).strip() or tag_id))
            continue

    if not metrics:
        raise SystemExit("spec.csv missing section=metrics rows (need at least 1 metric).")

    return {"meta": meta, "layout": layout, "tooltip_fields": tooltip_fields, "metrics": metrics, "tags": tags}


# -----------------------------
# Data loading
# -----------------------------
def load_data(data_path: Path, metrics: List[Dict[str, Any]], tags_sep: str) -> Dict[str, Any]:
    df = pd.read_csv(data_path).fillna("")

    required = {"x_id", "x_label", "y_id", "y_label", "tags", "note_html"}
    missing = sorted(required - set(df.columns))
    if missing:
        raise SystemExit(f"data.csv missing required columns: {missing}")

    metric_cols = [m["m_id"] for m in metrics]
    for c in metric_cols:
        if c not in df.columns:
            raise SystemExit(f"data.csv missing metric column: {c}")

    x_order: List[str] = []
    x_label: Dict[str, str] = {}
    x_tags: Dict[str, List[str]] = {}

    for _, r in df.iterrows():
        xid = str(r["x_id"])
        if xid not in x_label:
            x_order.append(xid)
            x_label[xid] = str(r["x_label"])
        if xid not in x_tags:
            raw = str(r.get("tags", ""))
            ts = [t for t in raw.split(tags_sep) if t]
            x_tags[xid] = sorted(set(ts))

    y_order: List[str] = []
    y_label: Dict[str, str] = {}
    for _, r in df.iterrows():
        yid = str(r["y_id"])
        if yid not in y_label:
            y_order.append(yid)
            y_label[yid] = str(r["y_label"])

    cell: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for _, r in df.iterrows():
        xid = str(r["x_id"])
        yid = str(r["y_id"])
        d = {c: float(r[c]) for c in metric_cols}
        d["note_html"] = str(r.get("note_html", ""))
        cell[(xid, yid)] = d

    return {"x_order": x_order, "y_order": y_order, "x_label": x_label, "y_label": y_label, "x_tags": x_tags, "cell": cell}


# -----------------------------
# KDE + Radar SVG (multi-series) with hover (no JS)
# NOTE: hover targets must have nonzero opacity in many browsers
# -----------------------------
def kde_density(values: List[float], xmin: float, xmax: float, n_grid: int = 240) -> Tuple[List[float], List[float]]:
    xs = [xmin + (xmax - xmin) * i / (n_grid - 1) for i in range(n_grid)]
    if not values:
        return xs, [0.0 for _ in xs]

    n = len(values)
    s = stddev(values)
    if s <= 1e-12:
        s = max(1e-6, (xmax - xmin) / 1000.0)

    h = 1.06 * s * (n ** (-1 / 5))
    h = max(h, 1e-6)

    inv = 1.0 / (h * math.sqrt(2 * math.pi) * n)

    ys: List[float] = []
    for x in xs:
        acc = 0.0
        for v in values:
            t = (x - v) / h
            acc += math.exp(-0.5 * t * t)
        ys.append(inv * acc)
    return xs, ys


def svg_kde_multi(
    series: List[Tuple[str, List[float], str]],  # (series_label, values, color)
    xmin: float,
    xmax: float,
    title: str,
    xlabel: str,
    trace_toggle_prefix: str = "",  # e.g. "kde-t-none-m_accuracy" for checkbox ids
) -> str:
    W, H = 520, 360
    pad_l, pad_r, pad_t, pad_b = 46, 18, 44, 34
    plot_w = W - pad_l - pad_r
    plot_h = H - pad_t - pad_b

    density_series = []
    ymax = 1e-12
    total_n = 0
    for lab, vals, col in series:
        xs, ys = kde_density(vals, xmin, xmax, n_grid=240)
        total_n += len(vals)
        ymax = max(ymax, max(ys) if ys else 0.0)
        density_series.append((lab, vals, col, xs, ys))

    def x2px(x: float) -> float:
        return pad_l + (x - xmin) / (xmax - xmin + 1e-12) * plot_w

    def y2px(y: float) -> float:
        return pad_t + (1.0 - (y / ymax)) * plot_h

    base_y = pad_t + plot_h
    parts: List[str] = []

    for idx, (lab, vals, col, xs, ys) in enumerate(density_series):
        pts = " ".join(f"{x2px(x):.2f},{y2px(y):.2f}" for x, y in zip(xs, ys))
        fill = f"M {pad_l:.2f},{base_y:.2f} L {pts} L {pad_l + plot_w:.2f},{base_y:.2f} Z"

        n = len(vals)
        mu = mean(vals) if vals else float("nan")
        sd = stddev(vals) if vals else float("nan")
        title_text = f"{lab}\n" f"n={n}\n" f"mean={mu:.4g}\n" f"std={sd:.4g}"

        # Wrap in <g> with data-trace for toggle visibility (when trace_toggle_prefix set)
        trace_attr = f' data-trace="{idx}"' if trace_toggle_prefix else ""
        parts.append(f'<g class="kde-trace"{trace_attr}>')
        parts.append(f'<title>{esc(title_text)}</title>')
        # Visible fill + curve (no pointer events so hover target receives them)
        parts.append(
            f'<path d="{fill}" fill="{col}" fill-opacity="0.12" stroke="none" pointer-events="none"/>'
            f'<polyline points="{pts}" fill="none" stroke="{col}" stroke-width="2.2" '
            f'stroke-opacity="0.95" vector-effect="non-scaling-stroke" pointer-events="none"/>'
        )
        # Hover hit target: wide stroke, opacity high enough for reliable hit-testing (0.05)
        parts.append(
            f'<polyline points="{pts}" fill="none" stroke="{col}" stroke-width="24" '
            f'stroke-opacity="0.05" pointer-events="stroke" vector-effect="non-scaling-stroke">'
            f'<title>{esc(title_text)}</title>'
            f"</polyline>"
        )
        # CSS-only tooltip fallback (for environments where native title is disabled)
        tt_safe = esc(title_text).replace("\n", "&#10;")
        parts.append(
            f'<foreignObject x="330" y="26" width="178" height="88" class="kde-svg-tt">'
            f'<div xmlns="http://www.w3.org/1999/xhtml" class="kde-tt-inner">{tt_safe}</div>'
            f"</foreignObject>"
        )
        parts.append("</g>")

    # Legend at bottom (below x-axis): with trace toggles if trace_toggle_prefix set
    legend_y = 328
    legend_fh = 32
    if trace_toggle_prefix:
        legend_parts: List[str] = []
        for i, (lab, vals, col, _, _) in enumerate(density_series):
            cid = f"{trace_toggle_prefix}-{i}"
            legend_parts.append(
                f'<label class="kde-legend-item">'
                f'<input type="checkbox" class="kde-trace-cb" id="{esc(cid)}" checked>'
                f'<span class="kde-legend-swatch" style="background:{col}"></span>'
                f'<span class="kde-legend-txt">{esc(lab)}</span>'
                f'</label>'
            )
        legend_html = "\n".join(legend_parts)
        legend_block = (
            f'<foreignObject x="{pad_l}" y="{legend_y}" width="{plot_w}" height="{legend_fh}" class="kde-legend-fo">'
            f'<div xmlns="http://www.w3.org/1999/xhtml" class="kde-legend-row">{legend_html}</div>'
            f'</foreignObject>'
        )
    else:
        # fallback: simple text legend row at bottom
        legend_block = ""
        for i, (lab, vals, col, _, _) in enumerate(density_series):
            lx = pad_l + i * (plot_w // max(1, len(density_series))) + 8
            legend_block += (
                f'<g transform="translate({lx},{legend_y + 12})">'
                f'<rect x="0" y="-9" width="10" height="10" fill="{col}" fill-opacity="0.95"/>'
                f'<text x="14" y="0" font-size="15" fill="#000000">{esc(lab)}</text>'
                f"</g>"
            )

    svg = f"""
    <svg viewBox="0 0 {W} {H}" width="100%" height="100%" role="img" aria-label="{esc(title)}" style="pointer-events:all">
      <text x="{W/2}" y="18" font-size="19" fill="#000000" font-weight="800" text-anchor="middle">{esc(title)}</text>

      <line x1="{pad_l}" y1="{pad_t+plot_h}" x2="{pad_l+plot_w}" y2="{pad_t+plot_h}" stroke="rgba(17,24,39,.25)"/>
      <line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t+plot_h}" stroke="rgba(17,24,39,.25)"/>

      <text x="{pad_l}" y="{pad_t+plot_h+18}" font-size="15" fill="#333333">{xmin:g}</text>
      <text x="{pad_l+plot_w/2}" y="{pad_t+plot_h+18}" font-size="15" fill="#333333" text-anchor="middle">{(xmin+xmax)/2:g}</text>
      <text x="{pad_l+plot_w}" y="{pad_t+plot_h+18}" font-size="15" fill="#333333" text-anchor="end">{xmax:g}</text>

      {"".join(parts)}
      {legend_block}
    </svg>
    """.strip()
    return svg


def svg_radar_multi(
    metric_defs: List[Dict[str, Any]],
    series_means: List[Tuple[str, Dict[str, float], str]],  # (series_label, means_by_metric, color)
    title: str,
    trace_toggle_prefix: str = "",
) -> str:
    W, H = 520, 400
    cx, cy = 260, 188
    R = 92
    label_r = 118

    k = len(metric_defs) or 1

    spokes = []
    label_pts = []
    for i in range(k):
        ang = -math.pi / 2 + 2 * math.pi * i / k
        spokes.append((cx + R * math.cos(ang), cy + R * math.sin(ang), ang))
        label_pts.append((cx + label_r * math.cos(ang), cy + label_r * math.sin(ang), ang))

    rings = []
    for rr in [0.25, 0.5, 0.75, 1.0]:
        ring_pts = []
        for i in range(k):
            ang = -math.pi / 2 + 2 * math.pi * i / k
            ring_pts.append((cx + R * rr * math.cos(ang), cy + R * rr * math.sin(ang)))
        rings.append(" ".join(f"{x:.2f},{y:.2f}" for x, y in ring_pts))

    def anchor_for_ang(a: float) -> str:
        c = math.cos(a)
        if c > 0.35:
            return "start"
        if c < -0.35:
            return "end"
        return "middle"

    polys: List[str] = []

    for idx, (lab, means_by_metric, col) in enumerate(series_means):
        pts: List[Tuple[float, float]] = []
        vals_for_title: List[str] = []

        for i, m in enumerate(metric_defs):
            ang = -math.pi / 2 + 2 * math.pi * i / k
            mid = m["m_id"]
            v = means_by_metric.get(mid, float("nan"))
            vmin, vmax = float(m["vmin"]), float(m["vmax"])
            if math.isnan(v) or vmax <= vmin:
                t = 0.0
            else:
                t = clamp01((v - vmin) / (vmax - vmin))
            r_i = R * t
            pts.append((cx + r_i * math.cos(ang), cy + r_i * math.sin(ang)))
            vals_for_title.append(f"{m['label']}={v:.4g}")

        poly = " ".join(f"{x:.2f},{y:.2f}" for x, y in pts)
        poly_title = esc(lab + "\n" + "\n".join(vals_for_title))

        trace_attr = f' data-trace="{idx}"' if trace_toggle_prefix else ""
        polys.append(f'<g class="radar-trace"{trace_attr}>')
        polys.append(f"<title>{poly_title}</title>")
        # visible polygon (no pointer events so hover target receives them)
        polys.append(
            f'<polygon points="{poly}" fill="{col}" fill-opacity="0.14" '
            f'stroke="{col}" stroke-width="2.2" stroke-opacity="0.95" '
            f'vector-effect="non-scaling-stroke" pointer-events="none"/>'
        )
        # hover: stroke (edge) and fill (interior), opacity 0.05 for reliable hit-testing
        polys.append(
            f'<polygon points="{poly}" fill="none" stroke="{col}" stroke-width="24" '
            f'stroke-opacity="0.05" pointer-events="stroke" vector-effect="non-scaling-stroke">'
            f"<title>{poly_title}</title>"
            f"</polygon>"
        )
        polys.append(
            f'<polygon points="{poly}" fill="{col}" fill-opacity="0.05" stroke="none" pointer-events="all">'
            f"<title>{poly_title}</title>"
            f"</polygon>"
        )
        # CSS-only tooltip fallback
        poly_tt_safe = poly_title.replace("\n", "&#10;")
        polys.append(
            f'<foreignObject x="320" y="26" width="188" height="120" class="radar-svg-tt">'
            f'<div xmlns="http://www.w3.org/1999/xhtml" class="radar-tt-inner">{poly_tt_safe}</div>'
            f"</foreignObject>"
        )

        # vertices: use tiny nonzero fill-opacity so hover works reliably
        for (vx, vy), m in zip(pts, metric_defs):
            mid = m["m_id"]
            v = means_by_metric.get(mid, float("nan"))
            title_text = esc(f"{lab}\n{m['label']}={v:.4g}")
            polys.append(
                f'<circle cx="{vx:.2f}" cy="{vy:.2f}" r="7" fill="transparent" fill-opacity="0.001" '
                f'pointer-events="all"><title>{title_text}</title></circle>'
            )
        polys.append("</g>")

    # Legend at bottom (below chart)
    legend_y = 358
    legend_fh = 40
    if trace_toggle_prefix:
        legend_parts = []
        for i, (lab, _, col) in enumerate(series_means):
            cid = f"{trace_toggle_prefix}-{i}"
            legend_parts.append(
                f'<label class="radar-legend-item">'
                f'<input type="checkbox" class="radar-trace-cb" id="{esc(cid)}" checked>'
                f'<span class="radar-legend-swatch" style="background:{col}"></span>'
                f'<span class="radar-legend-txt">{esc(lab)}</span>'
                f'</label>'
            )
        legend_html = "\n".join(legend_parts)
        legend_block = (
            f'<foreignObject x="0" y="{legend_y}" width="{W}" height="{legend_fh}" class="radar-legend-fo">'
            f'<div xmlns="http://www.w3.org/1999/xhtml" class="radar-legend-row">{legend_html}</div>'
            f'</foreignObject>'
        )
    else:
        legend_block = ""

    svg = f"""
    <svg viewBox="0 0 {W} {H}" width="100%" height="100%" role="img" aria-label="{esc(title)}" style="pointer-events:all">
      <text x="{W/2}" y="18" font-size="19" fill="#000000" font-weight="800" text-anchor="middle">{esc(title)}</text>

      {"".join(f'<polygon points="{rp}" fill="none" stroke="rgba(17,24,39,.12)" stroke-width="1"/>' for rp in rings)}
      {"".join(f'<line x1="{cx}" y1="{cy}" x2="{x:.2f}" y2="{y:.2f}" stroke="rgba(17,24,39,.14)" />'
               for (x, y, _) in spokes)}

      {"".join(polys)}

      <circle cx="{cx}" cy="{cy}" r="2.6" fill="rgba(17,24,39,.75)"/>

      {"".join(
        f'<text x="{x:.2f}" y="{y:.2f}" font-size="15" fill="#000000" text-anchor="{anchor_for_ang(a)}">'
        f'{esc(str(m["label"]))}</text>'
        for (x, y, a), m in zip(label_pts, metric_defs)
      )}

      {legend_block}
    </svg>
    """.strip()
    return svg


# -----------------------------
# Tag-subset precomputation
# -----------------------------
@dataclass(frozen=True)
class TagSubset:
    mask: int
    key: str
    selected_tags: Tuple[str, ...]


def all_tag_subsets(tag_ids: List[str]) -> List[TagSubset]:
    out: List[TagSubset] = []
    T = len(tag_ids)
    for mask in range(1 << T):
        sel = tuple(tag_ids[i] for i in range(T) if (mask >> i) & 1)
        key = "none" if mask == 0 else "|".join(sel)
        out.append(TagSubset(mask=mask, key=key, selected_tags=sel))
    return out


def included_questions_or(x_order: List[str], x_tags: Dict[str, List[str]], selected: Tuple[str, ...]) -> List[str]:
    if not selected:
        return list(x_order)
    sel = set(selected)
    keep = []
    for xid in x_order:
        if sel.intersection(x_tags.get(xid, [])):
            keep.append(xid)
    return keep


def collect_metric_values_for_y(
    xids: List[str],
    yid: str,
    cell: Dict[Tuple[str, str], Dict[str, Any]],
    metric_id: str,
) -> List[float]:
    vals: List[float] = []
    for xid in xids:
        d = cell.get((xid, yid))
        if d is None:
            continue
        vals.append(float(d[metric_id]))
    return vals


def aggregate_means_for_y(
    xids: List[str],
    yid: str,
    cell: Dict[Tuple[str, str], Dict[str, Any]],
    metric_defs: List[Dict[str, Any]],
) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for m in metric_defs:
        mid = m["m_id"]
        vals = collect_metric_values_for_y(xids, yid, cell, mid)
        out[mid] = mean(vals) if vals else float("nan")
    return out


# -----------------------------
# HTML render
# -----------------------------
def render(spec: Dict[str, Any], data: Dict[str, Any]) -> str:
    meta = spec["meta"]
    layout = spec["layout"]
    tooltip_fields = spec["tooltip_fields"]
    metrics = spec["metrics"]
    tags = spec["tags"]

    title = meta.get("title", "Heatmap")
    description = meta.get("description", "").strip()
    if not description:
        description = (
            "Lorem ipsum dolor sit amet, consectetur adipiscing elit. "
            "Select a metric and optional tags to explore the heatmap, KDE, and radar views below."
        )
    x_axis_label = meta.get("x_label", "X")
    y_axis_label = meta.get("y_label", "Y")
    tags_sep = meta.get("tags_separator", "|")

    cell_px = int(float(layout.get("cell_px", "28") or 28))
    font_px = int(float(layout.get("font_px", "19") or 19))

    x_order = data["x_order"]
    y_order = data["y_order"]
    x_label = data["x_label"]
    y_label = data["y_label"]
    x_tags = data["x_tags"]
    cell = data["cell"]

    tag_ids = [t["tag_id"] for t in tags]
    subsets = all_tag_subsets(tag_ids)

    y_series_cols = series_colors_from_viridis(len(y_order))

    # Controls: metric radios
    metric_controls = []
    metric_label_controls = []
    for i, m in enumerate(metrics):
        mid = m["m_id"]
        rid = f"metric-{mid}"
        checked = "checked" if i == 0 else ""
        metric_controls.append(f'<input class="metricRadio" type="radio" name="metric" id="{esc(rid)}" {checked}>')
        metric_label_controls.append(f'<label class="pill metricPill" for="{esc(rid)}">{esc(m["label"])}</label>')

    # Controls: tag checkboxes
    tag_controls = []
    tag_label_controls = []
    for t in tags:
        tid = t["tag_id"]
        cid = f"tag-{tid}"
        tag_controls.append(f'<input class="tagCheck" type="checkbox" id="{esc(cid)}">')
        tag_label_controls.append(f'<label class="pill tagPill" for="{esc(cid)}">{esc(t["tag_label"])}</label>')

    # Y-axis column (shared)
    ycol_html = []
    for yid in y_order:
        ycol_html.append(f'<div class="ytick">{esc(y_label[yid])}</div>')
    ycol_html = "".join(ycol_html)

    # CSS blocks (using :has())
    metric_view_css: List[str] = []
    metric_selected_pill_css: List[str] = []
    tag_selected_pill_css: List[str] = []
    tag_filter_css: List[str] = []
    kde_show_css: List[str] = []
    radar_show_css: List[str] = []

    for m in metrics:
        rid = f"metric-{m['m_id']}"
        view_id = f"view-{m['m_id']}"
        metric_view_css.append(f'.state:has(#{rid}:checked) ~ .plot #{view_id} {{ display: block; }}')
        metric_selected_pill_css.append(
            f'.state:has(#{rid}:checked) ~ .plot .metricPills label[for="{rid}"] '
            f'{{ outline: 2px solid #0066FF; background: rgba(0,102,255,.18); }}'
        )

    for t in tags:
        cid = f"tag-{t['tag_id']}"
        tag_selected_pill_css.append(
            f'.state:has(#{cid}:checked) ~ .plot .tagPills label[for="{cid}"] '
            f'{{ outline: 2px solid #0066FF; background: rgba(0,102,255,.18); }}'
        )

    # OR tag filter for heatmap columns
    tag_filter_css.append(".state:has(input.tagCheck:checked) ~ .plot .xcol { display: none; }")
    for t in tags:
        tid = t["tag_id"]
        cid = f"tag-{tid}"
        tag_filter_css.append(f'.state:has(#{cid}:checked) ~ .plot .xcol.tag-{tid} {{ display: flex; }}')

    # Heatmap views
    views_html = []
    for m in metrics:
        mid = m["m_id"]
        view_id = f"view-{mid}"

        pal_name = "viridis"
        base_pal = PALETTES_11["viridis"]
        palette = sample_palette(base_pal, int(m["bins"]))
        vmin, vmax = float(m["vmin"]), float(m["vmax"])
        fmt = m["fmt"]

        cb_blocks = []
        for i, c in enumerate(palette):
            t = i / (len(palette) - 1) if len(palette) > 1 else 0.0
            vv = vmin + t * (vmax - vmin)
            cb_blocks.append(f'<div class="cbBlock" style="background:{c}" title="{vv:.4f}"></div>')
        cb_html = "".join(reversed(cb_blocks))

        xcols_parts = []
        for xid in x_order:
            tagset = x_tags.get(xid, [])
            tag_classes = " ".join([f"tag-{t}" for t in tagset])
            tag_str = tags_sep.join(tagset)

            col_parts = []
            for yid in y_order:
                d = cell.get((xid, yid))
                if d is None:
                    bg = "#f3f4f6"
                    classes = "cell missing"
                    tip_note = ""
                    val_str = "NA"
                else:
                    v = float(d[mid])
                    bg = value_to_color(v, vmin, vmax, palette)
                    classes = "cell"
                    val_str = fmt_value(v, fmt)
                    tip_note = d.get("note_html", "")

                # Tooltip format: "X, Y" \n Metric: Z \n Tags: ... \n Note: ...
                tip_first = f"{esc(x_label[xid])}, {esc(y_label[yid])}"
                tip_metric = f"{esc(m['label'])}: {esc(val_str)}"
                tip_tags = f"Tags: {esc(tag_str) if tag_str else '—'}"
                note_mode = tooltip_fields.get("note_html", "off")
                note_content = tip_note if (note_mode in ("html", "html_sanitized") and tip_note) else ""
                note_block = f'<div class="tipNote">Note: {note_content}</div>' if note_content else ""

                tip_html = (
                    f'<div class="tip">'
                    f'<div class="tipTitle">{tip_first}</div>'
                    f'<div class="tipRow"><span class="v">{tip_metric}</span></div>'
                    f'<div class="tipRow"><span class="v">{tip_tags}</span></div>'
                    f'{note_block}'
                    f'</div>'
                )
                col_parts.append(f'<div class="{classes}" style="background:{bg}">{tip_html}</div>')

            xcols_parts.append(f'<div class="xcol {esc(tag_classes)}" data-xid="{esc(xid)}">{"".join(col_parts)}</div>')

        views_html.append(
            f"""
            <section class="metricView" id="{esc(view_id)}">
              <div class="plotRow">
                <div class="plotSegment tagsColumn">
                  <div class="controlTitle">Tags</div>
                  <div class="pillRow tagPills">
                    {''.join(tag_label_controls)}
                  </div>
                </div>
                <div class="plotSegment heatmapLegendBox" style="--n-cols: {len(x_order)}; --n-rows: {len(y_order)}">
                  <div class="heatwrap">
                    <div class="ycol">{ycol_html}</div>
                    <div class="xwrap">
                      <div class="xcols">{''.join(xcols_parts)}</div>
                      <div class="xAxisTitle">{esc(x_axis_label)}</div>
                    </div>
                  </div>
                  <aside class="legend">
                    <div class="legendTitle">{esc(m["label"])}</div>
                    <div class="cbWrap">
                      <div class="cb">{cb_html}</div>
                      <div class="cbLabelsRight">
                        <span class="cbVal cbMax">{esc(vmax)}</span>
                        <span class="cbVal cbMin">{esc(vmin)}</span>
                      </div>
                    </div>
                  </aside>
                </div>
                <div class="plotSegment metricColumn">
                  <div class="controlTitle">Metric</div>
                  <div class="pillRow metricPills">
                    {''.join(metric_label_controls)}
                  </div>
                </div>
              </div>
            </section>
            """.strip()
        )

    # Bottom plots: KDE + Radar (pre-render per tag-subset; KDE also per metric)
    kde_blocks: List[str] = []
    radar_blocks: List[str] = []
    kde_trace_toggle_css: List[str] = []
    radar_trace_toggle_css: List[str] = []

    def subset_selector(selected: Tuple[str, ...]) -> str:
        parts = [".state"]
        for tid in selected:
            parts.append(f":has(#tag-{tid}:checked)")
        for tid in tag_ids:
            if tid not in selected:
                parts.append(f":not(:has(#tag-{tid}:checked))")
        return "".join(parts)

    for subset in subsets:
        included_x = included_questions_or(x_order, x_tags, subset.selected_tags)

        radar_series = []
        for i, yid in enumerate(y_order):
            col = y_series_cols[i]
            means = aggregate_means_for_y(included_x, yid, cell, metrics)
            radar_series.append((y_label[yid], means, col))
        safe_radar = (subset.key or "none").replace("|", "_").replace(" ", "_")
        radar_toggle_prefix = f"radar-t-{safe_radar}"
        radar_svg = svg_radar_multi(
            metrics, radar_series, title="Radar Plot",
            trace_toggle_prefix=radar_toggle_prefix,
        )
        radar_blocks.append(f'<div class="radarPlot" data-subset="{esc(subset.key)}">{radar_svg}</div>')
        for i in range(len(radar_series)):
            radar_trace_toggle_css.append(
                f'.radarPlot[data-subset="{esc(subset.key)}"] svg:has(#{esc(radar_toggle_prefix)}-{i}:not(:checked)) '
                f'.radar-trace[data-trace="{i}"] {{ display: none; pointer-events: none; }}'
            )

        for m in metrics:
            kde_series = []
            for i, yid in enumerate(y_order):
                col = y_series_cols[i]
                vals = collect_metric_values_for_y(included_x, yid, cell, m["m_id"])
                kde_series.append((y_label[yid], vals, col))
            safe_kde = ((subset.key or "none") + "-" + m["m_id"]).replace("|", "_").replace(" ", "_")
            kde_toggle_prefix = f"kde-t-{safe_kde}"
            kde_svg = svg_kde_multi(
                kde_series,
                xmin=float(m["vmin"]),
                xmax=float(m["vmax"]),
                title=f'{m["label"]} KDE',
                xlabel=m["label"],
                trace_toggle_prefix=kde_toggle_prefix,
            )
            kde_blocks.append(
                f'<div class="kdePlot" data-subset="{esc(subset.key)}" data-metric="{esc(m["m_id"])}">{kde_svg}</div>'
            )
            for i in range(len(kde_series)):
                kde_trace_toggle_css.append(
                    f'.kdePlot[data-subset="{esc(subset.key)}"][data-metric="{esc(m["m_id"])}"] '
                    f'svg:has(#{esc(kde_toggle_prefix)}-{i}:not(:checked)) .kde-trace[data-trace="{i}"] '
                    f'{{ display: none; pointer-events: none; }}'
                )

    for subset in subsets:
        sel = subset_selector(subset.selected_tags)
        radar_show_css.append(f'{sel} ~ .below .radarPlot[data-subset="{subset.key}"] {{ display: block; }}')
        for m in metrics:
            mid = m["m_id"]
            kde_show_css.append(
                f'{sel}:has(#metric-{mid}:checked) ~ .below .kdePlot[data-subset="{subset.key}"][data-metric="{mid}"] {{ display: block; }}'
            )

    max_legend_title_ch = max((len(m["label"]) for m in metrics), default=1)

    # White theme + viridis accents
    css = f"""
    :root {{
      --legend-title-ch: {max_legend_title_ch};
      --bg: #ffffff;
      --panel: #ffffff;
      --border: #d9dde7;
      --text: #000000;
      --muted: #333333;
      --shadow: 0 10px 26px rgba(17,24,39,.10);
      --radius: 14px;
      --cell: {cell_px}px;
      --font: {font_px}px;

      --accent: #26828E;
      --accent2: #35B779;

      --tip-bg: #ffffff;
      --tip-border: rgba(17,24,39,.18);
    }}

    html, body {{ height: 100%; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial;
      font-size: var(--font);
      overflow-x: auto;
    }}

    .wrap {{
      width: calc(100vw - 24px);
      margin: 16px auto;
      padding: 0 12px;
    }}

    .card {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      overflow: visible;
    }}

    .header {{
      padding: 12px 14px;
      border-bottom: 1px solid var(--border);
      background: #f6f8fb;
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 14px;
      flex-wrap: wrap;
      border-top-left-radius: var(--radius);
      border-top-right-radius: var(--radius);
    }}

    .title {{
      margin: 0;
      font-size: 26px;
      font-weight: 850;
      letter-spacing: .2px;
    }}

    .description {{
      margin: 8px 0 0;
      font-size: 18px;
      line-height: 1.5;
      color: var(--muted);
      max-width: 60em;
    }}

    .sub {{
      color: var(--muted);
      font-size: 18px;
      margin: 0;
      white-space: nowrap;
    }}

    .state {{
      position: absolute;
      left: -9999px;
      top: -9999px;
    }}

    .controlTitle {{
      font-size: 18px;
      font-weight: 700;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: .12em;
      margin-bottom: 6px;
    }}

    .pillRow {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }}

    .pill {{
      display: inline-block;
      padding: 5px 10px;
      border-radius: 999px;
      border: 1px solid rgba(17,24,39,.16);
      background: rgba(17,24,39,.03);
      color: var(--text);
      font-size: 17px;
      cursor: pointer;
      user-select: none;
    }}
    .pill:hover {{
      background: rgba(0,102,255,.08);
      border-color: rgba(0,102,255,.4);
    }}

    .plot {{
      padding: 12px;
    }}

    .metricView {{ display: none; }}

    .plotRow {{
      display: grid;
      grid-template-columns: 140px 1fr 140px;
      gap: 0;
      align-items: stretch;
    }}

    .plotSegment {{
      border: 1px solid var(--border);
      background: rgba(17,24,39,.02);
      padding: 10px;
    }}
    .plotSegment:first-child {{
      border-right: none;
      border-radius: 12px 0 0 12px;
    }}
    .plotSegment.heatmapLegendBox {{
      display: flex;
      flex-direction: row;
      gap: 12px;
      align-items: center;
      flex: 1;
      min-width: 0;
      padding-left: 2%;
    }}
    .plotSegment.heatmapLegendBox .heatwrap {{
      flex: 1;
      min-width: 0;
      container-type: inline-size;
    }}
    .plotSegment:last-child {{
      border-left: none;
      border-radius: 0 12px 12px 0;
    }}

    .tagsColumn {{
      display: flex;
      flex-direction: column;
    }}

    .metricColumn {{
      display: flex;
      flex-direction: column;
    }}

    .tagsColumn .pillRow,
    .metricColumn .pillRow {{
      flex-direction: column;
      flex-wrap: nowrap;
      gap: 6px;
    }}

    .heatwrap {{
      display: flex;
      gap: 6px;
      align-items: flex-start;
    }}

    .ycol {{
      flex: 0 0 auto;
      width: max-content;
      min-width: 60px;
      display: flex;
      flex-direction: column;
      gap: 0;
    }}

    .xwrap {{
      display: flex;
      flex-direction: column;
      align-items: flex-start;
      width: 90cqw;
    }}
    .xAxisTitle {{
      width: 100%;
      text-align: center;
      padding: 6px 0 0;
      font-size: 16px;
      color: var(--muted);
    }}

    .ytick {{
      height: var(--cell);
      display: flex;
      align-items: center;
      justify-content: flex-end;
      padding-right: 6px;
      color: var(--muted);
      font-size: 16px;
      user-select: none;
      white-space: nowrap;
    }}

    .xcols {{
      display: flex;
      gap: 0;
      align-items: flex-start;
    }}

    .xcol {{
      flex: 0 0 calc(90cqw / var(--n-cols));
      width: calc(90cqw / var(--n-cols));
      display: flex;
      flex-direction: column;
      gap: 0;
    }}

    .xtick {{
      height: var(--cell);
      width: calc(90cqw / var(--n-cols));
      min-width: calc(90cqw / var(--n-cols));
      max-width: calc(90cqw / var(--n-cols));
      display: flex;
      align-items: flex-end;
      justify-content: center;
      text-align: center;
      color: var(--muted);
      font-size: 16px;
      user-select: none;
      padding-bottom: 2px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      border-bottom: 1px solid rgba(17,24,39,.12);
    }}

    .cell {{
      width: 100%;
      height: var(--cell);
      border-radius: 0;
      border: 1px solid rgba(17,24,39,.08);
      box-shadow: none;
      position: relative;
    }}
    .cell.missing {{
      background: #f3f4f6;
      border: 1px solid rgba(17,24,39,.12);
      box-shadow: none;
    }}
    .cell:hover {{
      outline: 2px solid #0066FF;
      outline-offset: 0;
      z-index: 10;
    }}

    .tip {{
      position: absolute;
      left: calc(100% + 10px);
      top: 50%;
      transform: translateY(-50%) translateX(-4px);
      min-width: 200px;
      max-width: min(520px, 90vw);
      width: max-content;
      background: var(--tip-bg);
      border: 1px solid var(--tip-border);
      border-radius: 12px;
      box-shadow: 0 12px 24px rgba(17,24,39,.14);
      padding: 12px 14px;
      pointer-events: none;
      opacity: 0;
      transition: opacity .10s ease, transform .10s ease;
    }}
    .cell:hover .tip {{
      opacity: 1;
      transform: translateY(-50%) translateX(0);
    }}

    .tipTitle {{
      font-weight: 850;
      margin-bottom: 8px;
      font-size: 17px;
      color: var(--text);
      white-space: normal;
      word-break: break-word;
    }}
    .tipRow {{
      font-size: 16px;
      color: var(--text);
      padding: 3px 0;
      white-space: normal;
      word-break: break-word;
    }}
    .tipRow .v {{
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
      color: var(--text);
    }}
    .tipNote {{
      margin-top: 8px;
      padding-top: 8px;
      border-top: 1px solid rgba(17,24,39,.12);
      font-size: 15px;
      color: var(--muted);
      white-space: normal;
      word-break: break-word;
    }}

    .legend {{
      flex: 0 0 auto;
      min-width: calc(var(--legend-title-ch) * 1ch + 16px + 6px + 3.5em);
      border: none;
      border-radius: 0;
      padding: 8px 0 0 8px;
      background: transparent;
      position: sticky;
      top: 12px;
    }}
    .legendTitle {{
      margin: 0 0 6px;
      min-width: calc(var(--legend-title-ch) * 1ch);
      font-size: 13px;
      letter-spacing: .08em;
      text-transform: uppercase;
      color: var(--muted);
    }}
    .cbWrap {{
      display: flex;
      align-items: stretch;
      gap: 6px;
    }}
    .cb {{
      display: flex;
      flex-direction: column;
      width: 16px;
      min-height: 100px;
      overflow: hidden;
      border-radius: 2px;
    }}
    .cbBlock {{
      flex: 1;
      min-height: 4px;
      width: 100%;
    }}
    .cbLabelsRight {{
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      color: var(--muted);
      font-size: 12px;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
    }}

    .below {{
      padding: 0 16px 16px;
    }}
    .belowGrid {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 14px;
      margin-top: 14px;
    }}
    .miniCard {{
      border: 1px solid rgba(17,24,39,.10);
      border-radius: 12px;
      background: rgba(17,24,39,.02);
      padding: 10px;
      min-height: 420px;
      overflow: visible;
    }}
    .miniBody {{
      width: 100%;
      height: 380px;
      display: flex;
      justify-content: center;
      align-items: center;
      overflow: visible;
    }}
    .miniBody .kdePlot,
    .miniBody .radarPlot {{
      width: 520px;
      max-width: 100%;
      height: 380px;
      margin: 0 auto;
      overflow: visible;
    }}

    /* KDE/radar legend row at bottom (with trace toggles) */
    .kde-legend-row, .radar-legend-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 12px 20px;
      align-items: center;
      justify-content: center;
      padding-top: 14px;
    }}
    .kde-legend-item, .radar-legend-item {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      cursor: pointer;
      font-size: 15px;
      color: var(--text);
      user-select: none;
    }}
    .kde-legend-item:hover, .radar-legend-item:hover {{ opacity: 0.9; }}
    .kde-trace-cb, .radar-trace-cb {{
      position: absolute;
      opacity: 0;
      width: 0;
      height: 0;
      pointer-events: none;
    }}
    .kde-legend-swatch, .radar-legend-swatch {{
      width: 10px;
      height: 10px;
      border-radius: 2px;
      flex-shrink: 0;
    }}
    .kde-legend-txt, .radar-legend-txt {{ white-space: nowrap; }}

    /* SVG hover tooltips (KDE/radar) when native title is disabled */
    .kde-svg-tt, .radar-svg-tt {{
      opacity: 0;
      pointer-events: none;
      transition: opacity 0.12s ease;
    }}
    .kde-trace:hover .kde-svg-tt, .radar-trace:hover .radar-svg-tt {{
      opacity: 1;
    }}
    .kde-tt-inner, .radar-tt-inner {{
      font-size: 14px;
      line-height: 1.4;
      padding: 8px 10px;
      background: var(--tip-bg);
      border: 1px solid var(--tip-border);
      border-radius: 8px;
      color: var(--text);
      white-space: pre-line;
      box-shadow: 0 4px 12px rgba(0,0,0,.08);
    }}

    .kdePlot, .radarPlot {{ display: none; }}

    {" ".join(metric_view_css)}
    {" ".join(metric_selected_pill_css)}
    {" ".join(tag_selected_pill_css)}
    {" ".join(tag_filter_css)}
    {" ".join(kde_show_css)}
    {" ".join(radar_show_css)}
    {" ".join(kde_trace_toggle_css)}
    {" ".join(radar_trace_toggle_css)}

    @media (max-width: 980px) {{
      .plotRow {{ grid-template-columns: 1fr; }}
      .legend {{ position: relative; top: 0; }}
      .ycol {{ width: 180px; }}
      .belowGrid {{ grid-template-columns: 1fr; }}
    }}
    """.strip()

    html = f"""
    <!doctype html>
    <html lang="en">
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <title>{esc(title)}</title>
      <style>{css}</style>
    </head>
    <body>
      <div class="wrap">
        <div class="card">
          <div class="header">
            <h1 class="title">{esc(title)}</h1>
            <p class="sub">{esc(y_axis_label)} × {esc(x_axis_label)} • heatmap + KDE + radar (no JS)</p>
            <p class="description">{esc(description)}</p>
          </div>

          <div class="state">
            {''.join(metric_controls)}
            {''.join(tag_controls)}
          </div>

          <div class="plot">
            {''.join(views_html)}
          </div>

          <div class="below">
            <div class="belowGrid">
              <div class="miniCard">
                <div class="miniBody">
                  {''.join(kde_blocks)}
                </div>
              </div>

              <div class="miniCard">
                <div class="miniBody">
                  {''.join(radar_blocks)}
                </div>
              </div>
            </div>
          </div>

        </div>
      </div>
    </body>
    </html>
    """.strip()

    return html


def main() -> None:
    if not SPEC_PATH.exists():
        raise SystemExit(f"Missing spec: {SPEC_PATH}")
    if not DATA_PATH.exists():
        raise SystemExit(f"Missing data: {DATA_PATH}")

    spec = read_spec(SPEC_PATH)
    tags_sep = spec["meta"].get("tags_separator", "|")
    data = load_data(DATA_PATH, spec["metrics"], tags_sep=tags_sep)

    OUT_PATH.write_text(render(spec, data), encoding="utf-8")
    print(f"Wrote: {OUT_PATH.resolve()}")


if __name__ == "__main__":
    main()
