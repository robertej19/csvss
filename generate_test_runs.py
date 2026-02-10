from __future__ import annotations

import json
from pathlib import Path
import pandas as pd


# -----------------------------
# Rainbow step definitions
# -----------------------------
RAINBOW_STEPS = [
    ("understand", "Understand", "#E53935", "#ffffff", "#B71C1C", "markdown"),   # red
    ("plan",       "Plan",       "#FB8C00", "#111111", "#EF6C00", "markdown"),   # orange
    ("question",   "Question",   "#FDD835", "#111111", "#F9A825", "markdown"),   # yellow
    ("search",     "Search",     "#43A047", "#ffffff", "#2E7D32", "tool_search"),# green
    ("evaluate",   "Evaluate",   "#1E88E5", "#ffffff", "#1565C0", "eval"),       # blue
    ("generate",   "Generate",   "#5E35B1", "#ffffff", "#4527A0", "markdown"),   # indigo
    ("judge",      "Judge",      "#8E24AA", "#ffffff", "#6A1B9A", "judge"),      # violet
]
RAINBOW_SEQUENCE = [t for (t, *_rest) in RAINBOW_STEPS]


# -----------------------------
# Hard-coded schema templates
# (Same rainbow steps, different run names)
# -----------------------------
SCHEMAS = {
    "rainbow_v1": {
        "run_name": "Rainbow v1 (Understand→Plan→Question→Search→Evaluate→Generate→Judge)",
        "type_style": RAINBOW_STEPS,
        "default": ("#888888", "#ffffff", "#666666", "json"),
        "sequence": RAINBOW_SEQUENCE,
    },
    "rainbow_v2": {
        "run_name": "Rainbow v2 (same steps, different label)",
        "type_style": RAINBOW_STEPS,
        "default": ("#888888", "#ffffff", "#666666", "json"),
        "sequence": RAINBOW_SEQUENCE,
    },
}


def make_schema_csv(schema_key: str) -> pd.DataFrame:
    s = SCHEMAS[schema_key]
    default_bg, default_fg, default_border, default_component = s["default"]

    rows: list[dict] = []

    # meta section
    rows.append({"section": "meta", "key": "schema_version", "value": "1"})
    rows.append({"section": "meta", "key": "run_name", "value": s["run_name"]})
    rows.append({"section": "meta", "key": "reasoning_format", "value": "json"})
    rows.append({"section": "meta", "key": "default_bg", "value": default_bg})
    rows.append({"section": "meta", "key": "default_fg", "value": default_fg})
    rows.append({"section": "meta", "key": "default_border", "value": default_border})
    rows.append({"section": "meta", "key": "default_component", "value": default_component})

    # columns section (optional)
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


def make_reasoning(sequence: list[str], qid: int) -> list[dict]:
    # A tiny bit of qid-specific flavor so you can tell rows apart
    steps = []
    for i, t in enumerate(sequence, start=1):
        steps.append(
            {
                "type": t,
                "summary": f"{t.title()} step {i} (Q{qid})",
                "data": {"note": f"dummy payload for {t}", "question_id": qid},
            }
        )
    return steps


def make_qra_rows(schema_key: str, run_index: int) -> list[dict]:
    seq = SCHEMAS[schema_key]["sequence"]

    # Q1: always present
    rows = [
        {
            "question_id": 1,
            "question": "What is 2 + 2?",
            "reasoning": json.dumps(make_reasoning(seq, qid=1), ensure_ascii=False),
            "final": f"2 + 2 = 4. (run {run_index:02d})",
        }
    ]

    # Q2: present on even runs
    if run_index % 2 == 0:
        rows.append(
            {
                "question_id": 2,
                "question": "Name a prime number greater than 10.",
                "reasoning": json.dumps(make_reasoning(seq, qid=2), ensure_ascii=False),
                "final": f"11 is a prime number greater than 10. (run {run_index:02d})",
            }
        )

    # Q3: present on runs divisible by 3
    if run_index % 3 == 0:
        rows.append(
            {
                "question_id": 3,
                "question": "What is the capital of Massachusetts?",
                "reasoning": json.dumps(make_reasoning(seq, qid=3), ensure_ascii=False),
                "final": f"Boston. (run {run_index:02d})",
            }
        )

    return rows


def generate_runs(out_dir: Path, n_runs: int) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    schema_keys = ["rainbow_v1", "rainbow_v2"]  # cycle between these

    for i in range(1, n_runs + 1):
        run_dir = out_dir / f"run_{i:02d}"
        run_dir.mkdir(parents=True, exist_ok=True)

        schema_key = schema_keys[(i - 1) % len(schema_keys)]

        schema_df = make_schema_csv(schema_key)
        qra_df = pd.DataFrame(make_qra_rows(schema_key, run_index=i))

        schema_df.to_csv(run_dir / "schema.csv", index=False)
        qra_df.to_csv(run_dir / "qra.csv", index=False)

    print(f"Generated {n_runs} runs in: {out_dir.resolve()}")


if __name__ == "__main__":
    generate_runs(Path("sample_runs"), n_runs=4)  # 3+ runs recommended
