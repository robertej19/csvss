#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate a small dummy dataset for cssplt demo plots.

Writes CSV files under examples/data/ that can be loaded by demo_linked.py
and the heatmap/KDE/radar artists. Column semantics:

- demo_heatmap.csv: model, dataset, accuracy, latency, cost, tag, notes
  Rows = (model × dataset); one row per cell. Metrics are columns so the
  heatmap can switch views by selected metric. notes = random text shown on hover.

- demo_kde.csv: tag, metric, value
  Sample values for KDE (one value per row). Many rows per (tag, metric)
  so density can be estimated. Tags: none, fast, robust. Metrics: accuracy,
  latency, cost.

- demo_radar.csv: series, accuracy, latency, cost
  One row per series (e.g. per tag). Values in [0,1] for radar axes.

Run from repo root with PYTHONPATH including module/:
  PYTHONPATH=. python examples/generate_demo_data.py
"""

import random
from pathlib import Path

import pandas as pd

# Gibberish word list for random notes
_WORDS = (
    "lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod "
    "tempor incididunt ut labore et dolore magna aliqua ut enim ad minim "
    "veniam quis nostrud exercitation ullamco laboris nisi aliquip ex ea "
    "commodo consequat duis aute irure dolor in reprehenderit voluptate "
    "velit esse cillum dolore eu fugiat nulla pariatur excepteur sint occaecat "
    "cupidatat non proident sunt in culpa qui officia deserunt mollit anim "
    "id est laborum praesent tristique magna sit amet purus gravida quis "
    "blandit turpis cursus in hac habitasse platea dictumst vestibulum "
    "rhoncus est pellentesque elit ullamcorper dignissim cras tincidunt "
    "lobortis feugiat vivamus at augue eget arcu dictum varius duis at "
    "consectetur lorem donec massa sapien faucibus et molestie ac feugiat "
    "sed lectus vestibulum mattis ullamcorper velit sed ullamcorper morbi "
    "tincidunt ornare massa eget egestas purus viverra accumsan in nisl nisi "
    "scelerisque eu ultrices vitae auctor eu augue ut lectus arcu bibendum "
    "at varius vel pharetra vel turpis nunc eget lorem dolor sed viverra"
).split()

# Default seed for reproducible dummy data
DEFAULT_SEED = 42
# Number of sample points per (tag, metric) for KDE
KDE_POINTS_PER_GROUP = 80


def _data_dir() -> Path:
    return Path(__file__).resolve().parent / "data"


def _gauss_clip(mu: float, sigma: float, low: float, high: float) -> float:
    x = random.gauss(mu, sigma)
    return max(low, min(high, x))


def _random_paragraph(min_words: int = 8, max_words: int = 25) -> str:
    """One paragraph of random gibberish."""
    n = random.randint(min_words, max_words)
    return " ".join(random.choices(_WORDS, k=n)).capitalize() + "."


def _random_notes(min_paragraphs: int = 1, max_paragraphs: int = 5) -> str:
    """Random notes: 1–5 paragraphs of gibberish."""
    n = random.randint(min_paragraphs, max_paragraphs)
    return "\n\n".join(_random_paragraph() for _ in range(n))


# Tag per model for heatmap row filtering (Option A)
HEATMAP_MODEL_TAG = {"M1": "fast", "M2": "none", "M3": "robust", "M4": "accurate", "M5": "cheap", "M6": "balanced"}


def make_heatmap_df(seed: int = DEFAULT_SEED) -> pd.DataFrame:
    """Heatmap: one row per (model, dataset) with accuracy, latency, cost, tag, and notes."""
    random.seed(seed)
    models = ["M1", "M2", "M3", "M4", "M5", "M6"]
    datasets = ["D1", "D2", "D3", "D4", "D5", "D6"]
    rows = []
    for m in models:
        for d in datasets:
            rows.append({
                "model": m,
                "dataset": d,
                "accuracy": round(random.uniform(0.5, 0.98), 4),
                "latency": round(random.uniform(5, 95), 2),
                "cost": round(random.uniform(0.5, 9.5), 2),
                "tag": HEATMAP_MODEL_TAG.get(m, "none"),
                "notes": _random_notes(),
            })
    return pd.DataFrame(rows)


def make_kde_df(seed: int = DEFAULT_SEED) -> pd.DataFrame:
    """KDE: long-format sample values per (tag, metric)."""
    random.seed(seed)
    tags = ["none", "fast", "robust", "accurate", "cheap", "balanced"]
    metrics = ["accuracy", "latency", "cost"]
    rows = []
    for tag in tags:
        for metric in metrics:
            for _ in range(KDE_POINTS_PER_GROUP):
                if metric == "accuracy":
                    mu = 0.7 + 0.1 * (tags.index(tag) - 1)
                    v = _gauss_clip(mu, 0.12, 0, 1)
                elif metric == "latency":
                    mu = 30 + 20 * tags.index(tag)
                    v = _gauss_clip(mu, 12, 1, 150)
                else:
                    mu = 3 + 2 * tags.index(tag)
                    v = _gauss_clip(mu, 1.2, 0.1, 15)
                rows.append({"tag": tag, "metric": metric, "value": round(v, 4)})
    return pd.DataFrame(rows)


def make_radar_df(seed: int = DEFAULT_SEED) -> pd.DataFrame:
    """Radar: one row per series with accuracy, latency, cost in [0,1] scale."""
    random.seed(seed)
    series = ["none", "fast", "robust", "accurate", "cheap", "balanced"]
    rows = []
    for s in series:
        a = round(random.uniform(0.55, 0.95), 4)
        l_raw = random.uniform(10, 90)
        l_norm = round(1 - (l_raw - 10) / 80, 4)
        c_raw = random.uniform(0.5, 9.5)
        c_norm = round(1 - (c_raw - 0.5) / 9, 4)
        rows.append({"series": s, "accuracy": a, "latency": l_norm, "cost": c_norm})
    return pd.DataFrame(rows)


def get_demo_data(seed: int = DEFAULT_SEED) -> dict[str, pd.DataFrame]:
    """Return dict of heatmap_df, kde_df, radar_df for programmatic use."""
    return {
        "heatmap": make_heatmap_df(seed=seed),
        "kde": make_kde_df(seed=seed),
        "radar": make_radar_df(seed=seed),
    }


def main() -> None:
    out_dir = _data_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    data = get_demo_data()
    for name, df in data.items():
        path = out_dir / f"demo_{name}.csv"
        df.to_csv(path, index=False)
        print(f"Wrote {path} ({len(df)} rows)")
    readme = out_dir / "README.txt"
    readme.write_text(
        "Generated by examples/generate_demo_data.py\n"
        "demo_heatmap.csv: model, dataset, accuracy, latency, cost, tag, notes\n"
        "demo_kde.csv: tag, metric, value (sample points for density)\n"
        "demo_radar.csv: series, accuracy, latency, cost (0-1 scale)\n",
        encoding="utf-8",
    )
    print(f"Wrote {readme}")


if __name__ == "__main__":
    main()
