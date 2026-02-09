from __future__ import annotations

import json
import html
from pathlib import Path
from dataclasses import dataclass
from typing import Any
import pandas as pd


def esc(x: Any) -> str:
    return html.escape(str(x), quote=True)


@dataclass
class RunSchema:
    run_name: str
    reasoning_format: str
    default_bg: str
    default_fg: str
    default_border: str
    default_component: str
    type_styles: dict[str, dict[str, str]]  # type -> {label,bg,fg,border,component}


@dataclass
class RunData:
    key: str          # directory name e.g. run_01
    schema: RunSchema
    df: pd.DataFrame  # qra rows


# -----------------------------
# Reading schema + run
# -----------------------------
def read_schema(schema_path: Path) -> RunSchema:
    df = pd.read_csv(schema_path)

    meta: dict[str, str] = {}
    type_styles: dict[str, dict[str, str]] = {}

    mdf = df[df["section"] == "meta"]
    for _, r in mdf.iterrows():
        k = str(r.get("key", "")).strip()
        v = r.get("value", "")
        if k:
            meta[k] = str(v)

    tdf = df[df["section"] == "type_style"]
    for _, r in tdf.iterrows():
        t = str(r.get("type", "")).strip()
        if not t:
            continue
        type_styles[t] = {
            "label": str(r.get("label", t)),
            "bg": str(r.get("bg", meta.get("default_bg", "#888888"))),
            "fg": str(r.get("fg", meta.get("default_fg", "#ffffff"))),
            "border": str(r.get("border", meta.get("default_border", "#666666"))),
            "component": str(r.get("component", meta.get("default_component", "json"))),
        }

    return RunSchema(
        run_name=meta.get("run_name", schema_path.parent.name),
        reasoning_format=meta.get("reasoning_format", "json"),
        default_bg=meta.get("default_bg", "#888888"),
        default_fg=meta.get("default_fg", "#ffffff"),
        default_border=meta.get("default_border", "#666666"),
        default_component=meta.get("default_component", "json"),
        type_styles=type_styles,
    )


def read_run(run_dir: Path) -> RunData | None:
    schema_path = run_dir / "schema.csv"
    qra_path = run_dir / "qra.csv"
    if not (schema_path.exists() and qra_path.exists()):
        return None

    schema = read_schema(schema_path)
    df = pd.read_csv(qra_path)

    for col in ["question_id", "question", "reasoning", "final"]:
        if col not in df.columns:
            raise ValueError(f"Missing column '{col}' in {qra_path}")

    return RunData(key=run_dir.name, schema=schema, df=df)


# -----------------------------
# Data helpers
# -----------------------------
def parse_reasoning(schema: RunSchema, reasoning_cell: Any) -> list[dict]:
    if pd.isna(reasoning_cell):
        return []
    s = str(reasoning_cell)
    if schema.reasoning_format == "json":
        try:
            v = json.loads(s)
            return v if isinstance(v, list) else []
        except json.JSONDecodeError:
            return [{"type": "parse_error", "summary": "Failed to parse reasoning JSON", "data": {"raw": s}}]
    return [{"type": "text", "summary": s, "data": {}}]


def lookup_row(run: RunData, qid: int) -> dict | None:
    sub = run.df[run.df["question_id"] == qid]
    if sub.empty:
        return None
    return sub.iloc[0].to_dict()


# -----------------------------
# Rendering
# -----------------------------
def render_data(component: str, data: dict) -> str:
    """Render the data field based on component type."""
    if not data:
        return ""
    
    if component == "json":
        # Format JSON data nicely
        try:
            json_str = json.dumps(data, indent=2, ensure_ascii=False)
            return f'<pre class="step-data json"><code>{esc(json_str)}</code></pre>'
        except (TypeError, ValueError):
            return f'<pre class="step-data json"><code>{esc(str(data))}</code></pre>'
    elif component == "markdown":
        # For markdown, just display as formatted text
        # Note: Without JS, we can't render markdown, so show as preformatted
        if "content" in data:
            content = data.get("content", "")
            return f'<div class="step-data markdown"><pre>{esc(str(content))}</pre></div>'
        else:
            # If no content key, show as JSON
            try:
                json_str = json.dumps(data, indent=2, ensure_ascii=False)
                return f'<div class="step-data markdown"><pre>{esc(json_str)}</pre></div>'
            except (TypeError, ValueError):
                return f'<div class="step-data markdown"><pre>{esc(str(data))}</pre></div>'
    elif component == "tool_search":
        # Format tool search results
        query = data.get("query", "")
        results = data.get("results", [])
        parts = []
        if query:
            parts.append(f'<div class="data-label">Query:</div><div class="data-value">{esc(query)}</div>')
        if results:
            parts.append(f'<div class="data-label">Results:</div><div class="data-value"><pre>{esc(json.dumps(results, indent=2, ensure_ascii=False))}</pre></div>')
        if not parts:
            parts.append(f'<pre>{esc(json.dumps(data, indent=2, ensure_ascii=False))}</pre>')
        return f'<div class="step-data tool-search">{"".join(parts)}</div>'
    elif component == "eval":
        # Format evaluation results
        result = data.get("result", "")
        score = data.get("score", "")
        parts = []
        if score:
            parts.append(f'<div class="data-label">Score:</div><div class="data-value">{esc(str(score))}</div>')
        if result:
            parts.append(f'<div class="data-label">Result:</div><div class="data-value">{esc(str(result))}</div>')
        if not parts:
            parts.append(f'<pre>{esc(json.dumps(data, indent=2, ensure_ascii=False))}</pre>')
        return f'<div class="step-data eval">{"".join(parts)}</div>'
    else:
        # Default: show as JSON
        try:
            json_str = json.dumps(data, indent=2, ensure_ascii=False)
            return f'<pre class="step-data json"><code>{esc(json_str)}</code></pre>'
        except (TypeError, ValueError):
            return f'<pre class="step-data"><code>{esc(str(data))}</code></pre>'


def render_steps(schema: RunSchema, steps: list[dict]) -> str:
    out = []
    for i, st in enumerate(steps, start=1):
        t = str(st.get("type", "unknown"))
        summary = st.get("summary", "")
        data = st.get("data", {})
        style = schema.type_styles.get(
            t,
            {
                "label": t,
                "bg": schema.default_bg,
                "fg": schema.default_fg,
                "border": schema.default_border,
                "component": schema.default_component,
            },
        )
        
        component = style.get("component", schema.default_component)
        data_html = render_data(component, data) if data else ""

        out.append(
            f"""
            <div class="step" style="--bg:{esc(style["bg"])}; --fg:{esc(style["fg"])}; --border:{esc(style["border"])};">
              <div class="step-head">
                <span class="pill">{esc(style.get("label", t))}</span>
                <span class="step-title">Step {i}</span>
              </div>
              <div class="step-body">
                <div class="step-summary">{esc(summary)}</div>
                {data_html}
              </div>
            </div>
            """.strip()
        )
    return "\n".join(out)


def render_run_panel(run: RunData, row: dict | None) -> str:
    if row is None:
        return f"""
        <div class="missing">
          <div class="missing-title">Missing</div>
          <div class="missing-body">No row for this question_id in <code>{esc(run.key)}/qra.csv</code>.</div>
        </div>
        """.strip()

    steps = parse_reasoning(run.schema, row.get("reasoning", ""))

    return f"""
    <div class="panel">
      <div class="panel-section">
        <div class="h">Question</div>
        <div class="question">{esc(row.get("question",""))}</div>
      </div>

      <div class="panel-section">
        <div class="h">Reasoning trace</div>
        <div class="steps">
          {render_steps(run.schema, steps)}
        </div>
      </div>

      <div class="panel-section">
        <div class="h">Final answer</div>
        <div class="final">{esc(row.get("final",""))}</div>
      </div>
    </div>
    """.strip()


# -----------------------------
# CSS generation (no JS)
# -----------------------------
def build_css(qids: list[int], run_keys: list[str]) -> str:
    base = """
    :root{
      --bg: #0b0d12;
      --text:#e9ecf1;
      --muted:#aab3c0;
      --border:#25304b;
      --shadow: 0 10px 30px rgba(0,0,0,.35);
      --radius: 14px;
      --pad: 14px;

      --leftHi: rgba(231, 76, 60, .18);   /* red highlight */
      --leftHiB: rgba(231, 76, 60, .40);
      --rightHi: rgba(52, 152, 219, .18); /* blue highlight */
      --rightHiB: rgba(52, 152, 219, .40);

      --mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
      --sans: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, "Apple Color Emoji","Segoe UI Emoji";
    }

    html,body{height:100%;}
    body{
      margin:0;
      background:
        radial-gradient(1200px 700px at 20% 10%, #1b2340 0%, rgba(27,35,64,0) 55%),
        radial-gradient(900px 600px at 85% 35%, #2a1240 0%, rgba(42,18,64,0) 55%),
        var(--bg);
      color: var(--text);
      font-family: var(--sans);
    }

    input[type="radio"]{ position:absolute; left:-9999px; }

    .wrap{max-width:1400px; margin:24px auto; padding: 0 16px;}
    .title{font-size:22px; font-weight:750; margin:0 0 6px;}
    .subtitle{color:var(--muted); margin:0 0 14px; font-size:14px;}

    .card{
      border:1px solid var(--border);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      overflow:hidden;
      background: linear-gradient(180deg, rgba(255,255,255,.03), rgba(255,255,255,.01));
    }

    .topbar{
      display:flex;
      gap:12px;
      align-items:center;
      justify-content:space-between;
      padding: 12px 14px;
      border-bottom:1px solid var(--border);
      background: rgba(255,255,255,.02);
      flex-wrap:wrap;
    }

    .chip{
      display:inline-flex;
      align-items:center;
      gap:8px;
      padding: 7px 10px;
      border-radius: 999px;
      border: 1px solid var(--border);
      background: rgba(255,255,255,.02);
      color: var(--muted);
      font-size: 13px;
      white-space:nowrap;
    }
    .chip strong{color: var(--text); font-weight:650;}

    .toggles{
      display:flex;
      gap:10px;
      align-items:center;
      flex-wrap:wrap;
    }
    .toggleGroup{
      display:flex;
      gap:8px;
      align-items:center;
      flex-wrap:wrap;
    }
    .groupLabel{
      color: var(--muted);
      font-size: 12px;
      letter-spacing:.10em;
      text-transform: uppercase;
      margin-right: 2px;
    }
    .rtab{
      cursor:pointer;
      user-select:none;
      padding: 8px 10px;
      border-radius: 999px;
      border: 1px solid var(--border);
      background: rgba(255,255,255,.02);
      color: var(--muted);
      font-size: 13px;
      max-width: 320px;
      overflow:hidden;
      text-overflow:ellipsis;
      white-space:nowrap;
    }
    .rtab code{font-family: var(--mono); font-size: 12px; color: var(--muted);}

    .layout{
      display:grid;
      grid-template-columns: 33% 33.5% 33.5%;
      min-height: 70vh;
    }

    .sidebar{
      border-right: 1px solid var(--border);
      background: rgba(255,255,255,.015);
    }
    .sidebarHeader{
      padding: 12px 14px;
      border-bottom: 1px solid var(--border);
      display:flex;
      align-items:center;
      justify-content:space-between;
      gap:10px;
    }
    .sidebarHeader .h2{
      font-size: 12px;
      letter-spacing:.12em;
      text-transform: uppercase;
      color: var(--muted);
    }

    .qList{
      padding: 10px;
      display:flex;
      flex-direction:column;
      gap:8px;
      max-height: calc(70vh - 50px);
      overflow:auto;
    }
    .qItem{
      cursor:pointer;
      user-select:none;
      padding: 10px 10px;
      border-radius: 12px;
      border: 1px solid var(--border);
      background: rgba(255,255,255,.02);
      color: var(--muted);
      font-size: 13px;
      line-height:1.25;
    }
    .qItem .qid{ font-family: var(--mono); color: var(--text); font-weight:700; }
    .qItem .qtxt{ display:block; margin-top: 6px; color: var(--muted); }

    .main{
      grid-column: 2 / 4;
      padding: 14px;
    }

    .compareGrid{
      display:grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
      align-items:start;
    }
    .colHeader{
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 10px 12px;
      background: rgba(255,255,255,.02);
      display:flex;
      align-items:center;
      justify-content:space-between;
      gap:10px;
      margin-bottom: 10px;
    }
    .colHeader .name{
      font-weight:750;
      font-size: 13px;
      overflow:hidden;
      text-overflow:ellipsis;
      white-space:nowrap;
    }
    .colHeader .badge{
      font-family: var(--mono);
      font-size: 12px;
      padding: 3px 8px;
      border-radius: 999px;
      border: 1px solid var(--border);
      color: var(--muted);
      white-space:nowrap;
    }
    .colHeader.left { border-color: var(--leftHiB); background: var(--leftHi); }
    .colHeader.right{ border-color: var(--rightHiB); background: var(--rightHi); }

    .qview{ display:none; }
    .leftPane .runpanel,
    .rightPane .runpanel{ display:none; }

    .panel{
      background: rgba(255,255,255,.02);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: var(--pad);
    }
    .panel-section + .panel-section{ margin-top: 12px; }
    .h{
      font-size: 12px;
      letter-spacing: .12em;
      text-transform: uppercase;
      color: var(--muted);
      margin-bottom: 6px;
    }
    .question{font-size: 16px; font-weight: 700; line-height: 1.35;}
    .final{
      background: rgba(78,161,255,.10);
      border: 1px solid rgba(78,161,255,.30);
      border-radius: 12px;
      padding: 12px;
      font-size: 15px;
      line-height: 1.45;
    }

    .steps{display:flex; flex-direction:column; gap:10px;}
    .step{
      background: rgba(255,255,255,.02);
      border: 1px solid color-mix(in srgb, var(--border), #000 10%);
      border-left: 6px solid var(--border);
      border-radius: 12px;
      overflow:hidden;
      box-shadow: 0 6px 18px rgba(0,0,0,.20);
    }
    .step-head{
      display:flex;
      align-items:center;
      gap:10px;
      padding: 10px 12px;
      background: var(--bg);
      color: var(--fg);
      border-bottom: 1px solid rgba(255,255,255,.10);
    }
    .pill{
      display:inline-flex;
      align-items:center;
      padding: 3px 8px;
      border-radius: 999px;
      font-size: 12px;
      font-family: var(--mono);
      background: rgba(0,0,0,.18);
      border: 1px solid rgba(255,255,255,.20);
    }
    .step-title{font-weight:800;}
    .step-body{
      padding: 10px 12px;
      color: var(--text);
      background: rgba(255,255,255,.02);
      font-size: 13px;
      line-height: 1.45;
    }
    .step-summary{
      margin-bottom: 8px;
      font-weight: 500;
    }
    .step-data{
      margin-top: 10px;
      padding-top: 10px;
      border-top: 1px solid rgba(255,255,255,.08);
    }
    .step-data pre,
    .step-data code{
      font-family: var(--mono);
      font-size: 12px;
      margin: 0;
      padding: 0;
    }
    .step-data.json{
      background: rgba(0,0,0,.20);
      border-radius: 8px;
      padding: 10px;
      overflow-x: auto;
    }
    .step-data.json code{
      color: var(--text);
      white-space: pre;
    }
    .step-data.markdown{
      background: rgba(0,0,0,.15);
      border-radius: 8px;
      padding: 10px;
    }
    .step-data.markdown pre{
      margin: 0;
      color: var(--text);
      white-space: pre-wrap;
      word-wrap: break-word;
    }
    .step-data.tool-search,
    .step-data.eval{
      background: rgba(0,0,0,.15);
      border-radius: 8px;
      padding: 10px;
    }
    .data-label{
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: .1em;
      color: var(--muted);
      margin-top: 8px;
      margin-bottom: 4px;
      font-weight: 600;
    }
    .data-label:first-child{
      margin-top: 0;
    }
    .data-value{
      color: var(--text);
      font-size: 12px;
      line-height: 1.5;
    }
    .data-value pre{
      margin: 4px 0 0 0;
      padding: 8px;
      background: rgba(0,0,0,.20);
      border-radius: 6px;
      overflow-x: auto;
      font-family: var(--mono);
      font-size: 11px;
      white-space: pre;
    }

    .missing{
      background: rgba(231,76,60,.10);
      border: 1px solid rgba(231,76,60,.30);
      border-radius: var(--radius);
      padding: 14px;
    }
    .missing-title{font-weight:800; margin-bottom: 6px;}
    .missing-body{color: var(--muted); font-size: 13px; line-height: 1.4;}
    .missing-body code{font-family: var(--mono);}

    /* Helpful on smaller screens */
    @media (max-width: 1100px){
      .layout{ grid-template-columns: 40% 60%; }
      .main{ grid-column: 2 / 3; }
      .compareGrid{ grid-template-columns: 1fr; }
    }
    """.strip()

    dyn: list[str] = []
    dyn.append("\n/* --- generated selectors (no JS) --- */")

    # Question: show only chosen qview, and highlight selected item in sidebar
    for qid in qids:
        dyn.append(f"#qsel-{qid}:checked ~ .card .main #qview-{qid}{{display:block;}}")
        dyn.append(
            f"#qsel-{qid}:checked ~ .card .sidebar .qList label[for='qsel-{qid}']"
            "{background: rgba(78,161,255,.12); border-color: rgba(78,161,255,.30); color: var(--text);}"
        )

    # Run toggles: highlight selected left (red) and right (blue) run chips in topbar
    for rk in run_keys:
        dyn.append(
            f"#left-{rk}:checked ~ .card .topbar .toggleGroup.left label[for='left-{rk}']"
            "{background: var(--leftHi); border-color: var(--leftHiB); color: var(--text);}"
        )
        dyn.append(
            f"#right-{rk}:checked ~ .card .topbar .toggleGroup.right label[for='right-{rk}']"
            "{background: var(--rightHi); border-color: var(--rightHiB); color: var(--text);}"
        )

    # For each question view, show correct run panel in left/right panes based on selected run
    # Fix: left/right radios are siblings of .card, not descendants
    # We need to check BOTH qsel-{qid} AND left-{rk} are checked
    # Since both are siblings before .card, we check from left radio and target the specific qview
    # The qview will only be visible if qsel-{qid} is checked (handled above), so this works correctly
    for qid in qids:
        for rk in run_keys:
            # When left-{rk} is checked, show run-{rk} in leftPane of qview-{qid}
            # This will only be visible if qview-{qid} is also visible (i.e., qsel-{qid} is checked)
            dyn.append(
                f"#left-{rk}:checked ~ .card .main #qview-{qid} .leftPane .run-{rk}{{display:block;}}"
            )
            dyn.append(
                f"#right-{rk}:checked ~ .card .main #qview-{qid} .rightPane .run-{rk}{{display:block;}}"
            )

    return base + "\n" + "\n".join(dyn)


def build_html(runs: list[RunData]) -> str:
    run_keys = [r.key for r in runs]

    all_qids = sorted(set().union(*[set(r.df["question_id"].tolist()) for r in runs]))
    if not all_qids:
        raise ValueError("No questions found in any run.")

    default_qid = all_qids[0]
    default_left = run_keys[0]
    default_right = run_keys[1] if len(run_keys) > 1 else run_keys[0]

    # Put ALL radios *before* the .card so CSS sibling selectors can reach everywhere
    q_radios = "\n".join(
        f"<input type='radio' name='qsel' id='qsel-{qid}' {'checked' if qid == default_qid else ''}>"
        for qid in all_qids
    )
    left_radios = "\n".join(
        f"<input type='radio' name='leftsel' id='left-{rk}' {'checked' if rk == default_left else ''}>"
        for rk in run_keys
    )
    right_radios = "\n".join(
        f"<input type='radio' name='rightsel' id='right-{rk}' {'checked' if rk == default_right else ''}>"
        for rk in run_keys
    )

    # Top bar run toggles
    left_tabs = "\n".join(
        f"<label class='rtab' for='left-{esc(r.key)}'>{esc(r.schema.run_name)} <code>{esc(r.key)}</code></label>"
        for r in runs
    )
    right_tabs = "\n".join(
        f"<label class='rtab' for='right-{esc(r.key)}'>{esc(r.schema.run_name)} <code>{esc(r.key)}</code></label>"
        for r in runs
    )

    # Sidebar question list
    # Grab a representative question text (first run that contains it)
    q_items = []
    for qid in all_qids:
        qtxt = ""
        for r in runs:
            row = lookup_row(r, qid)
            if row is not None:
                qtxt = str(row.get("question", ""))
                break
        q_items.append(
            f"""
            <label class="qItem" for="qsel-{qid}">
              <span class="qid">QID {qid}</span>
              <span class="qtxt">{esc(qtxt)[:140]}{("…" if len(esc(qtxt))>140 else "")}</span>
            </label>
            """.strip()
        )

    # For each question, build a view with *all* runpanels in each side,
    # then CSS chooses which is visible.
    qviews = []
    for qid in all_qids:
        left_runpanels = []
        right_runpanels = []
        for r in runs:
            row = lookup_row(r, qid)
            panel = render_run_panel(r, row)
            left_runpanels.append(f"<div class='runpanel run-{esc(r.key)}'>{panel}</div>")
            right_runpanels.append(f"<div class='runpanel run-{esc(r.key)}'>{panel}</div>")

        qviews.append(
            f"""
            <section class="qview" id="qview-{qid}">
              <div class="compareGrid">
                <div>
                  <div class="colHeader left">
                    <div class="name">Left (red)</div>
                    <div class="badge">selected via top bar</div>
                  </div>
                  <div class="leftPane">
                    {''.join(left_runpanels)}
                  </div>
                </div>

                <div>
                  <div class="colHeader right">
                    <div class="name">Right (blue)</div>
                    <div class="badge">selected via top bar</div>
                  </div>
                  <div class="rightPane">
                    {''.join(right_runpanels)}
                  </div>
                </div>
              </div>
            </section>
            """.strip()
        )

    css = build_css(all_qids, run_keys)

    html_doc = f"""
    <!doctype html>
    <html lang="en">
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <title>Run Comparator (No JS)</title>
      <style>{css}</style>
    </head>
    <body>
      <div class="wrap">
        <h1 class="title">Run Comparator (No JavaScript)</h1>
        <p class="subtitle">Pick a question on the left. Choose the two runs to compare on the top bar (Left=red, Right=blue).</p>

        {q_radios}
        {left_radios}
        {right_radios}

        <div class="card">
          <div class="topbar">
            <div class="chip"><strong>Runs:</strong> {len(runs)} &nbsp; <strong>Questions:</strong> {len(all_qids)}</div>

            <div class="toggles">
              <div class="toggleGroup left">
                <span class="groupLabel">Left</span>
                {left_tabs}
              </div>
              <div class="toggleGroup right">
                <span class="groupLabel">Right</span>
                {right_tabs}
              </div>
            </div>
          </div>

          <div class="layout">
            <aside class="sidebar">
              <div class="sidebarHeader">
                <div class="h2">Questions</div>
                <div class="chip"><strong>QIDs</strong></div>
              </div>
              <div class="qList">
                {''.join(q_items)}
              </div>
            </aside>

            <main class="main">
              {''.join(qviews)}
            </main>
          </div>
        </div>
      </div>
    </body>
    </html>
    """.strip()

    return html_doc


def main(input_dir: Path, output_html: Path) -> None:
    run_dirs = sorted([p for p in input_dir.iterdir() if p.is_dir()])

    runs: list[RunData] = []
    for rd in run_dirs:
        r = read_run(rd)
        if r is not None:
            runs.append(r)

    if len(runs) < 2:
        raise SystemExit(f"Need at least 2 runs under {input_dir} (found {len(runs)}).")

    output_html.parent.mkdir(parents=True, exist_ok=True)
    output_html.write_text(build_html(runs), encoding="utf-8")
    print(f"Wrote report: {output_html.resolve()}")


if __name__ == "__main__":
    main(Path("sample_runs"), Path("out/report.html"))
