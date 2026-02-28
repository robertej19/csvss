# cssplt

Single-file HTML+CSS-only interactive plots (no JavaScript). Uses radio/checkbox inputs and CSS `:has()` to switch between pre-rendered views. Targets modern Chromium.

## Quick start

```bash
# From the module directory
pip install -e .
python examples/generate_demo_data.py   # optional: create sample data
PYTHONPATH=. python examples/demo_linked.py
# Open examples/demo_linked.html in a browser
```

## Usage

- **Figure + controls:** Create a `StateRegistry`, add a metric radio and tag checkboxes, then `fig = plt.figure(state=state)` and `fig.add_subplot()` for each subplot.
- **Heatmap:** `HeatmapArtist(df, row="model", col="dataset", metric="accuracy")`. Use `render_html_views(metric_var_key, metric_values)` to get HTML + CSS for metric switching; pass the CSS to the figure via `ax.set_extra_css(css)`.
- **KDE:** `KDEArtist(df, tag_col="tag", metric_col="metric", value_col="value")`. Call `render_html_views(metric_var, tag_var)`; tag variants are combinatorial (all subsets) when `2^num_tags <= 256`, else single-tag only.
- **Radar:** `RadarArtist(df, series_col="series", axis_columns=["accuracy", "latency", "cost"])`. Call `render_html_views(tag_var)` for the same tag-subset behavior.
- **Tag semantics:** `StateRegistry(tag_filter_mode=TagFilterMode.ANY)` for OR (show data with any selected tag); `TagFilterMode.ALL` for AND. When over 256 tag combinations, only empty + single-tag variants are rendered.

## Demo data

Run `python examples/generate_demo_data.py` to create `examples/data/demo_heatmap.csv`, `demo_kde.csv`, and `demo_radar.csv`.

## Requirements

- Python 3.9+
- pandas
- Modern browser with `:has()` support (e.g. Chromium)
