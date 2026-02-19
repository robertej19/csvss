from __future__ import annotations

import random
import math
import csv
from pathlib import Path

DATA_DIR = Path("data/")
DATA_DIR.mkdir(parents=True, exist_ok=True)

spec_path = DATA_DIR / "spec.csv"
data_path = DATA_DIR / "data.csv"

random.seed(7)

# --- Define demo dimensions ---
x_items = [
    ("q1", "Question 1"),
    ("q2", "Question 2"),
    ("q3", "Question 3"),
    ("q4", "Question 4"),
    ("q5", "Question 5"),
]

y_items = [
    ("a1", "Answer 1"),
    ("a2", "Answer 2"),
    ("a3", "Answer 3"),
]

# --- Tag universe (C) ---
tags = [
    ("easy", "Easy"),
    ("medium", "Medium"),
    ("hard", "Hard"),
    ("sports", "Sports"),
    ("cooking", "Cooking"),
]

# Assign tags per question (x)
x_tags = {
    "q1": {"easy", "cooking"},
    "q2": {"medium"},
    "q3": {"hard", "sports"},
    "q4": {"easy", "sports"},
    "q5": {"medium", "cooking"},
}

# --- Metrics (M) ---
metrics = [
    # m_id, label, fmt, palette, min, max, bins
    ("m_accuracy", "Accuracy", "0.000", "viridis", 0.0, 1.0, 11),
    ("m_latency", "Latency (s)", "0.00", "magma", 0.0, 3.0, 11),
    ("m_helpfulness", "Helpfulness", "0.0", "plasma", 0.0, 5.0, 11),
]

# --- Write spec.csv (sectioned) ---
spec_rows = []

# meta
spec_rows += [
    {"section": "meta", "key": "title", "value": "QA Heatmap Demo (metrics + tag filtering)"},
    {"section": "meta", "key": "x_label", "value": "Questions"},
    {"section": "meta", "key": "y_label", "value": "Answers"},
    {"section": "meta", "key": "value_label", "value": "Metric value"},
    {"section": "meta", "key": "tooltip_html_field", "value": "note_html"},
    {"section": "meta", "key": "tags_separator", "value": "|"},
]

# layout
spec_rows += [
    {"section": "layout", "key": "cell_px", "value": "28"},
    {"section": "layout", "key": "font_px", "value": "16"},
    {"section": "layout", "key": "show_values", "value": "false"},
]

# tooltip fields: text vs html
spec_rows += [
    {"section": "tooltip_fields", "key": "x_label", "value": "text"},
    {"section": "tooltip_fields", "key": "y_label", "value": "text"},
    {"section": "tooltip_fields", "key": "metric", "value": "text"},
    {"section": "tooltip_fields", "key": "value", "value": "text"},
    {"section": "tooltip_fields", "key": "tags", "value": "text"},
    {"section": "tooltip_fields", "key": "note_html", "value": "html_sanitized"},
]

# metrics registry
for m_id, label, fmt, palette, vmin, vmax, bins in metrics:
    spec_rows.append(
        {
            "section": "metrics",
            "m_id": m_id,
            "label": label,
            "fmt": fmt,
            "palette": palette,
            "min": vmin,
            "max": vmax,
            "bins": bins,
        }
    )

# tags registry
for tag_id, tag_label in tags:
    spec_rows.append(
        {
            "section": "tags",
            "tag_id": tag_id,
            "tag_label": tag_label,
        }
    )

# write CSV with a union of keys
spec_fieldnames = sorted({k for r in spec_rows for k in r.keys()})
with spec_path.open("w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=spec_fieldnames)
    w.writeheader()
    for r in spec_rows:
        w.writerow(r)

# --- Helper: rich html note (intentionally includes some tags we will sanitize later) ---
def rich_note_html(x_id: str, y_id: str, metric_values: dict[str, float], tags_str: str) -> str:
    acc = metric_values["m_accuracy"]
    lat = metric_values["m_latency"]
    helpf = metric_values["m_helpfulness"]
    badge = "✅" if acc > 0.75 else ("⚠️" if acc > 0.45 else "🧊")
    return f"""
    <div class="note">
      <div class="note-top">
        <span class="flag">{badge}</span>
        <strong>Cell report</strong>
      </div>
      <ul class="note-list">
        <li><span class="k">qid</span> <code>{x_id}</code></li>
        <li><span class="k">aid</span> <code>{y_id}</code></li>
        <li><span class="k">acc</span> <span class="pill">{acc:.3f}</span></li>
        <li><span class="k">lat</span> <span class="pill">{lat:.2f}s</span></li>
        <li><span class="k">help</span> <span class="pill">{helpf:.1f}</span></li>
        <li><span class="k">tags</span> <em>{tags_str}</em></li>
      </ul>
      <div class="note-foot">safe tooltip HTML (sanitized)</div>
    </div>
    """.strip()

# --- Generate cell metrics with some spatial structure (so it looks like a heatmap) ---
def gen_metrics(ix: int, iy: int, nx: int, ny: int) -> dict[str, float]:
    # accuracy: gaussian bump + mild noise
    cx, cy = (nx - 1) / 2, (ny - 1) / 2
    g = math.exp(-(((ix - cx) ** 2) / (nx * 0.9) + ((iy - cy) ** 2) / (ny * 0.7)))
    acc = max(0.0, min(1.0, 0.25 + 0.70 * g + random.uniform(-0.05, 0.05)))

    # latency: higher near edges
    edge = max(abs(ix - cx) / (cx + 1e-9), abs(iy - cy) / (cy + 1e-9))
    lat = max(0.0, min(3.0, 0.5 + 2.2 * edge + random.uniform(-0.10, 0.10)))

    # helpfulness: correlate with accuracy, add discrete-ish effect
    helpf = max(0.0, min(5.0, 1.0 + 4.0 * acc + random.uniform(-0.35, 0.35)))

    return {
        "m_accuracy": round(acc, 4),
        "m_latency": round(lat, 4),
        "m_helpfulness": round(helpf, 4),
    }

# --- Write data.csv ---
data_rows = []
nx, ny = len(x_items), len(y_items)
for ix, (x_id, x_label) in enumerate(x_items):
    tagset = x_tags.get(x_id, set())
    tags_str = "|".join(sorted(tagset))
    for iy, (y_id, y_label) in enumerate(y_items):
        mvals = gen_metrics(ix, iy, nx, ny)
        note_html = rich_note_html(x_id, y_id, mvals, tags_str)

        row = {
            "x_id": x_id,
            "x_label": x_label,
            "y_id": y_id,
            "y_label": y_label,
            "tags": tags_str,
            "note_html": note_html,
        }
        row.update(mvals)
        data_rows.append(row)

data_fieldnames = ["x_id", "x_label", "y_id", "y_label", "tags"] + [m[0] for m in metrics] + ["note_html"]
with data_path.open("w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=data_fieldnames)
    w.writeheader()
    for r in data_rows:
        w.writerow(r)

(spec_path.as_posix(), data_path.as_posix(), len(spec_rows), len(data_rows))
