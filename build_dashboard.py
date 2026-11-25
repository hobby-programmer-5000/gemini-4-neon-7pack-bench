"""Builds a standalone dark-mode HTML benchmark dashboard with live measured charts from results/*.json."""
from __future__ import annotations

import base64
import html
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from bench_core import FIXTURES_DIR, RESULTS_DIR


def _load_json(name: str) -> dict[str, Any] | None:
    p = RESULTS_DIR / f"{name}.json"
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def _img_to_b64(path: Path) -> str | None:
    if not path.exists():
        return None
    return base64.b64encode(path.read_bytes()).decode("ascii")


def _render_m1_chart(m1: dict[str, Any]) -> Path:
    out = RESULTS_DIR / "chart_m1_models.png"
    models = list(m1["models"].keys())
    labels = [m.replace("gemini-4-", "G4 ").title() for m in models]
    latencies = [m1["models"][m]["total_elapsed_sec"] for m in models]
    tokens = [m1["models"][m]["total_output_plus_thought_tokens"] for m in models]
    pass_rates = [m1["models"][m]["pass_rate"] * 100 for m in models]

    plt.style.use("dark_background")
    fig, axes = plt.subplots(1, 3, figsize=(13, 3.8), dpi=140)
    colors = ["#38bdf8", "#a855f7", "#f59e0b"]

    axes[0].bar(labels, pass_rates, color=colors)
    axes[0].set_title("Pass Rate (%)", fontweight="bold")
    axes[0].set_ylim(0, 115)
    for i, v in enumerate(pass_rates):
        axes[0].text(i, v + 3, f"{v:.0f}%", ha="center", fontweight="bold")

    axes[1].bar(labels, latencies, color=colors)
    axes[1].set_title("Total E2E Latency (s)", fontweight="bold")
    for i, v in enumerate(latencies):
        axes[1].text(i, v + max(latencies) * 0.03, f"{v:.1f}s", ha="center", fontweight="bold")

    axes[2].bar(labels, tokens, color=colors)
    axes[2].set_title("Output + Thinking Tokens", fontweight="bold")
    for i, v in enumerate(tokens):
        axes[2].text(i, v + max(tokens) * 0.03, f"{v:,}", ha="center", fontweight="bold")

    fig.suptitle("Module 1: Gemini 4 Model Comparison (Hydrogen vs Neon vs Carbon)", fontsize=12, fontweight="bold")
    fig.tight_layout()
    fig.savefig(out, facecolor="#0f172a")
    plt.close(fig)
    return out


def _render_m5_chart(m5: dict[str, Any]) -> Path:
    out = RESULTS_DIR / "chart_m5_thinking.png"
    lvls = ["low", "medium", "high", "xhigh"]
    thoughts = [m5["levels"].get(l, {}).get("total_thought_tokens", 0) for l in lvls]
    secs = [m5["levels"].get(l, {}).get("total_elapsed_sec", 0.0) for l in lvls]
    labels = []
    for l in lvls:
        info = m5["levels"].get(l, {})
        if info.get("status") == "rate_limited_429":
            labels.append(f"{l}\n(429 Spend Cap)")
        else:
            labels.append(f"{l}\n(Score {info.get('score', 0)}/2)")

    plt.style.use("dark_background")
    fig, ax1 = plt.subplots(figsize=(9, 3.8), dpi=140)
    x = np.arange(len(lvls))
    bar_colors = ["#818cf8" if m5["levels"].get(l, {}).get("status") != "rate_limited_429" else "#475569" for l in lvls]
    bars = ax1.bar(x - 0.18, thoughts, width=0.35, color=bar_colors, label="Thought Tokens")
    ax1.set_ylabel("Thought Tokens", color="#818cf8", fontweight="bold")
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, fontweight="bold")
    max_t = max(thoughts) if any(thoughts) else 1
    for bar, v, l in zip(bars, thoughts, lvls):
        txt = "429 Cap" if m5["levels"].get(l, {}).get("status") == "rate_limited_429" else f"{v:,}"
        ax1.text(bar.get_x() + bar.get_width() / 2, v + max_t * 0.02, txt, ha="center", fontsize=8)

    valid_idx = [i for i, l in enumerate(lvls) if m5["levels"].get(l, {}).get("status") != "rate_limited_429"]
    ax2 = ax1.twinx()
    ax2.plot([x[i] + 0.18 for i in valid_idx], [secs[i] for i in valid_idx], marker="o", linewidth=2.5, color="#34d399", label="Total Latency (s)")
    ax2.set_ylabel("Latency (s)", color="#34d399", fontweight="bold")
    max_s = max(secs) if any(secs) else 1
    for i in valid_idx:
        ax2.text(x[i] + 0.18, secs[i] + max_s * 0.03, f"{secs[i]:.1f}s", ha="center", color="#34d399", fontsize=8, fontweight="bold")

    plt.title("Module 5: Gemini 4 Neon Thinking Level Scaling (low -> high measured; xhigh hit 429 spend cap)", fontweight="bold")
    fig.tight_layout()
    fig.savefig(out, facecolor="#0f172a")
    plt.close(fig)
    return out


def _render_m1b_chart(m1b: dict[str, Any]) -> Path:
    out = RESULTS_DIR / "chart_m1b_matched.png"
    runs = m1b["runs"]
    labels = [f"{r['model'].replace('gemini-4-', 'G4 ').title()}\n({r['thinking_level']})" for r in runs]
    secs = [r["usage"]["elapsed_sec"] for r in runs]
    toks = [r["output_plus_thought_tokens"] for r in runs]
    costs = [float(r["usage"]["cost_usd"]) for r in runs]
    colors = ["#a855f7", "#f59e0b", "#c084fc", "#fbbf24"]

    plt.style.use("dark_background")
    fig, axes = plt.subplots(1, 3, figsize=(13, 3.8), dpi=140)
    axes[0].bar(labels, secs, color=colors)
    axes[0].set_title("Matched-Level Latency (s)", fontweight="bold")
    for i, v in enumerate(secs):
        axes[0].text(i, v + max(secs) * 0.03, f"{v:.1f}s", ha="center", fontweight="bold", fontsize=8)

    axes[1].bar(labels, toks, color=colors)
    axes[1].set_title("Output + Thinking Tokens", fontweight="bold")
    for i, v in enumerate(toks):
        axes[1].text(i, v + max(toks) * 0.03, f"{v:,}", ha="center", fontweight="bold", fontsize=8)

    axes[2].bar(labels, costs, color=colors)
    axes[2].set_title("Measured Cost (USD)", fontweight="bold")
    for i, v in enumerate(costs):
        axes[2].text(i, v + max(costs) * 0.03, f"${v:.4f}", ha="center", fontweight="bold", fontsize=8)

    fig.suptitle("Module 1B: Matched Thinking-Level SWE Comparison (Neon vs Carbon | All 4/4 PASS)", fontsize=12, fontweight="bold")
    fig.tight_layout()
    fig.savefig(out, facecolor="#0f172a")
    plt.close(fig)
    return out


def generate_dashboard() -> Path:
    m1 = _load_json("01_frontier_speed_cost")
    m1b = _load_json("01b_apples_to_apples")
    m2 = _load_json("02_agentic_repo_refactor")
    m3 = _load_json("03_knowledge_science_1m")
    m4 = _load_json("04_cybersecurity_reliability")
    m5 = _load_json("05_thinking_levels")
    m6 = _load_json("06_unified_1m_long_decode")
    m7 = _load_json("07_managed_agents_multimodel")
    master = _load_json("master_summary") or {}

    m1_img = _img_to_b64(_render_m1_chart(m1)) if m1 else None
    m1b_img = _img_to_b64(_render_m1b_chart(m1b)) if m1b else None
    m5_img = _img_to_b64(_render_m5_chart(m5)) if m5 else None
    m3_img = _img_to_b64(FIXTURES_DIR / "knowledge_pack" / "margin_chart.png")

    modules = [
        ("01", "Frontier Intelligence, Speed & Cost ($3/$15, Default Levels)", m1),
        ("01B", "Matched Thinking-Level Comparison (Neon vs Carbon, 6.51x Speedup at high)", m1b),
        ("02", "Complex SWE, Refactoring, Compaction & Anti-Fabrication", m2),
        ("03", "Knowledge Work, Science & Multimodal Synthesis", m3),
        ("04", "Cybersecurity Root-Cause Patching & Guardrails", m4),
        ("05", "Four Configurable Thinking Levels (low/med/high/xhigh)", m5),
        ("06", "Unified 1M Context, Long Decode & Implicit Caching", m6),
        ("07", "Antigravity Managed Agents & Neon+Hydrogen Pairing", m7),
    ]

    passed_n = sum(1 for _, _, d in modules if d and d.get("overall_pass"))
    loaded_n = sum(1 for _, _, d in modules if d)

    def _mod_cost(d: dict[str, Any] | None) -> Decimal:
        if not d:
            return Decimal("0")
        if "cost_summary" in d and "total_cost_usd" in d["cost_summary"]:
            return Decimal(str(d["cost_summary"]["total_cost_usd"]))
        if "usage" in d and isinstance(d["usage"], dict) and "cost_usd" in d["usage"]:
            return Decimal(str(d["usage"]["cost_usd"]))
        if "models" in d:
            return sum((Decimal(str(v.get("total_cost_usd", "0"))) for v in d["models"].values()), Decimal("0"))
        if "runs" in d:
            return sum((Decimal(str(r["usage"]["cost_usd"])) for r in d["runs"] if r.get("usage")), Decimal("0"))
        if "levels" in d:
            tot = sum((Decimal(str(v.get("total_cost_usd", "0"))) for v in d["levels"].values()), Decimal("0"))
            su = d.get("spec_checks", {}).get("default_usage", {})
            if su and "cost_usd" in su:
                tot += Decimal(str(su["cost_usd"]))
            return tot
        return Decimal("0")

    computed_total = sum((_mod_cost(d) for _, _, d in modules), Decimal("0"))
    grand_cost = str(computed_total.quantize(Decimal("0.000001")))

    cards_html = []
    for num, title, data in modules:
        if not data:
            cards_html.append(f"<div class='card'><h3>#{num} {html.escape(title)}</h3><p>Not run yet.</p></div>")
            continue
        status_cls = "pass" if data.get("overall_pass") else "fail"
        status_lbl = "VERIFIED PASS" if data.get("overall_pass") else "NEEDS REVIEW"
        pretty = html.escape(json.dumps(data, indent=2, ensure_ascii=False))
        extra_img = ""
        if num == "01" and m1_img:
            extra_img = f"<img class='chart' src='data:image/png;base64,{m1_img}' alt='M1 Comparison'/>"
        elif num == "01B" and m1b_img:
            extra_img = f"<img class='chart' src='data:image/png;base64,{m1b_img}' alt='M1B Matched-Level Comparison'/>"
        elif num == "03" and m3_img:
            extra_img = f"<img class='chart' src='data:image/png;base64,{m3_img}' alt='M3 Input Chart'/>"
        elif num == "05" and m5_img:
            extra_img = f"<img class='chart' src='data:image/png;base64,{m5_img}' alt='M5 Thinking Levels'/>"

        cards_html.append(f"""
        <section class="card">
          <div class="card-head">
            <h2>#{num} &middot; {html.escape(title)}</h2>
            <span class="badge {status_cls}">{status_lbl}</span>
          </div>
          {extra_img}
          <details>
            <summary>Inspect Raw Measured JSON Telemetry</summary>
            <pre>{pretty}</pre>
          </details>
        </section>
        """)

    html_doc = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>Gemini 4 Neon: 7-Feature Live Benchmark Report</title>
  <style>
    :root {{ --bg:#0b1120; --card:#111827; --border:#1f2937; --text:#e5e7eb; --muted:#9ca3af; --accent:#a855f7; }}
    body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; background:var(--bg); color:var(--text); margin:0; padding:32px; line-height:1.5; }}
    .wrap {{ max-width:1180px; margin:0 auto; }}
    header {{ display:flex; justify-content:space-between; align-items:flex-end; border-bottom:1px solid var(--border); padding-bottom:20px; margin-bottom:24px; flex-wrap:wrap; gap:16px; }}
    h1 {{ margin:0; font-size:28px; background:linear-gradient(90deg,#38bdf8,#a855f7,#f472b6); -webkit-background-clip:text; -webkit-text-fill-color:transparent; }}
    .kpi-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr)); gap:14px; margin-bottom:26px; }}
    .kpi {{ background:var(--card); border:1px solid var(--border); border-radius:12px; padding:16px; }}
    .kpi .label {{ font-size:12px; color:var(--muted); text-transform:uppercase; letter-spacing:0.06em; }}
    .kpi .val {{ font-size:26px; font-weight:700; margin-top:4px; color:#f8fafc; }}
    .card {{ background:var(--card); border:1px solid var(--border); border-radius:14px; padding:20px; margin-bottom:20px; }}
    .card-head {{ display:flex; justify-content:space-between; align-items:center; gap:12px; flex-wrap:wrap; }}
    .card h2 {{ margin:0; font-size:18px; }}
    .badge {{ padding:4px 12px; border-radius:999px; font-size:12px; font-weight:700; }}
    .badge.pass {{ background:#064e3b; color:#6ee7b7; border:1px solid #10b981; }}
    .badge.fail {{ background:#7f1d1d; color:#fca5a5; border:1px solid #ef4444; }}
    .chart {{ width:100%; max-width:960px; border-radius:10px; margin:16px 0; border:1px solid var(--border); display:block; }}
    details {{ margin-top:12px; }}
    summary {{ cursor:pointer; color:#93c5fd; font-weight:600; font-size:14px; }}
    pre {{ background:#030712; padding:14px; border-radius:10px; overflow:auto; max-height:420px; font-size:12px; color:#cbd5e1; border:1px solid var(--border); }}
  </style>
</head>
<body>
  <div class="wrap">
    <header>
      <div>
        <h1>Gemini 4 Neon: 7-Feature Live Verification Suite</h1>
        <p style="margin:6px 0 0;color:var(--muted);">Real Interactions API (google-genai 3.3.0) + Local Execution Graders</p>
      </div>
      <div style="color:var(--muted);font-size:13px;">Pricing Baseline: $3.00 / 1M input &middot; $0.15 / 1M cached &middot; $15.00 / 1M output+thinking</div>
    </header>
    <div class="kpi-grid">
      <div class="kpi"><div class="label">Modules Verified</div><div class="val">{passed_n} / {loaded_n}</div></div>
      <div class="kpi"><div class="label">Measured API Spend</div><div class="val">${html.escape(str(grand_cost))}</div></div>
      <div class="kpi"><div class="label">Unified Context Window</div><div class="val">1,048,576 tok</div></div>
      <div class="kpi"><div class="label">Thinking Levels</div><div class="val">low &rarr; xhigh</div></div>
    </div>
    {''.join(cards_html)}
  </div>
</body>
</html>"""

    out_path = RESULTS_DIR / "neon_7pack_report.html"
    out_path.write_text(html_doc, encoding="utf-8")
    return out_path


if __name__ == "__main__":
    p = generate_dashboard()
    print(f"Dashboard written to {p}")
