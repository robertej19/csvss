from __future__ import annotations

import json
from pathlib import Path
import pandas as pd


# -----------------------------
# Hard-coded schema templates
# -----------------------------
SCHEMAS = {
    "rwb": {
        "run_name": "Run (R/W/B) plan→search→generate",
        "type_style": [
            # type, label, bg, fg, border, component
            ("plan", "Plan", "#e74c3c", "#ffffff", "#b33a2f", "markdown"),
            ("search", "Search", "#f7f7f7", "#111111", "#aaaaaa", "tool_search"),
            ("generate", "Generate", "#1f5fff", "#ffffff", "#163fbf", "markdown"),
        ],
        "default": ("#888888", "#ffffff", "#666666", "json"),
        "sequence": ["plan", "search", "generate"],
    },
    "rgbv": {
        "run_name": "Run (R/G/B/V) plan→search→evaluate→search→evaluate→synthesize",
        "type_style": [
            ("plan", "Plan", "#e74c3c", "#ffffff", "#b33a2f", "markdown"),      # R
            ("search", "Search", "#3498db", "#ffffff", "#2b79ad", "tool_search"), # B
            ("evaluate", "Evaluate", "#9b59b6", "#ffffff", "#7b3f97", "eval"),    # V
            ("synthesize", "Synthesize", "#2ecc71", "#0b2a12", "#1f9a52", "markdown"), # G-ish
        ],
        "default": ("#888888", "#ffffff", "#666666", "json"),
        "sequence": ["plan", "search", "evaluate", "search", "evaluate", "synthesize"],
    },
}


def make_schema_csv(schema_key: str) -> pd.DataFrame:
    s = SCHEMAS[schema_key]
    default_bg, default_fg, default_border, default_component = s["default"]

    rows = []
    # meta section
    rows.append({"section": "meta", "key": "schema_version", "value": "1"})
    rows.append({"section": "meta", "key": "run_name", "value": s["run_name"]})
    rows.append({"section": "meta", "key": "reasoning_format", "value": "json"})
    rows.append({"section": "meta", "key": "default_bg", "value": default_bg})
    rows.append({"section": "meta", "key": "default_fg", "value": default_fg})
    rows.append({"section": "meta", "key": "default_border", "value": default_border})
    rows.append({"section": "meta", "key": "default_component", "value": default_component})

    # columns section (optional but nice)
    rows.append({"section": "columns", "key": "question_id", "value": "question_id"})
    rows.append({"section": "columns", "key": "question", "value": "question"})
    rows.append({"section": "columns", "key": "reasoning", "value": "reasoning"})
    rows.append({"section": "columns", "key": "final", "value": "final"})

    # type_style section
    for (t, label, bg, fg, border, component) in s["type_style"]:
        rows.append(
            {
                "section": "type_style",
                "type": t,
                "label": label,
                "bg": bg,
                "fg": fg,
                "border": border,
                "component": component,
            }
        )

    return pd.DataFrame(rows)


def make_reasoning(sequence: list[str]) -> list[dict]:
    # Minimal step payload; you can extend later.
    steps = []
    for i, t in enumerate(sequence, start=1):
        steps.append(
            {
                "type": t,
                "summary": f"{t.title()} step {i}",
                "data": {"note": f"dummy payload for {t}"},
            }
        )
    return steps


def make_qra_df(schema_key: str, include_q2: bool) -> pd.DataFrame:
    seq = SCHEMAS[schema_key]["sequence"]

    rows = [
        {
            "question_id": 1,
            "question": "What is 2 + 2?",
            "reasoning": json.dumps(make_reasoning(seq), ensure_ascii=False),
            "final": "2 + 2 = 4.",
        }
    ]
    if include_q2:
        rows.append(
            {
                "question_id": 2,
                "question": "Name a prime number greater than 10.",
                "reasoning": json.dumps(make_reasoning(seq[:-1]), ensure_ascii=False),
                "final": "11 is a prime number greater than 10.",
            }
        )
    return pd.DataFrame(rows)


def generate_runs(out_dir: Path, n_runs: int) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    schema_keys = ["rwb", "rgbv"]  # cycle between these

    for i in range(1, n_runs + 1):
        run_dir = out_dir / f"run_{i:02d}"
        run_dir.mkdir(parents=True, exist_ok=True)

        schema_key = schema_keys[(i - 1) % len(schema_keys)]

        # Make Q2 appear only in some runs (e.g. every 2nd run)
        include_q2 = (i % 2 == 0)

        schema_df = make_schema_csv(schema_key)
        qra_df = make_qra_df(schema_key, include_q2=include_q2)

        schema_df.to_csv(run_dir / "schema.csv", index=False)
        qra_df.to_csv(run_dir / "qra.csv", index=False)

    print(f"Generated {n_runs} runs in: {out_dir.resolve()}")


if __name__ == "__main__":
    # Change these as desired
    generate_runs(Path("sample_runs"), n_runs=4)
