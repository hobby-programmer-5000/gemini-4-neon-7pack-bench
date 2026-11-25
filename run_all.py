"""Master CLI runner for the Gemini 4 Neon 7-Feature Live Verification Suite."""
from __future__ import annotations

import argparse
import importlib
import json
import sys
import time
from decimal import Decimal
from typing import Any

from bench_core import RESULTS_DIR, save_result

MODULE_REGISTRY = {
    1: ("01_frontier_speed_cost", "bench_01_frontier_speed_cost"),
    2: ("02_agentic_repo_refactor", "bench_02_agentic_repo_refactor"),
    3: ("03_knowledge_science_1m", "bench_03_knowledge_science_1m"),
    4: ("04_cybersecurity_reliability", "bench_04_cybersecurity_reliability"),
    5: ("05_thinking_levels", "bench_05_thinking_levels"),
    6: ("06_unified_1m_long_decode", "bench_06_unified_1m_long_decode"),
    7: ("07_managed_agents_multimodel", "bench_07_managed_agents_multimodel"),
}


def extract_module_cost(data: dict[str, Any]) -> Decimal:
    if "cost_summary" in data and "total_cost_usd" in data["cost_summary"]:
        return Decimal(str(data["cost_summary"]["total_cost_usd"]))
    if "usage" in data and isinstance(data["usage"], dict) and "cost_usd" in data["usage"]:
        return Decimal(str(data["usage"]["cost_usd"]))
    if "models" in data:
        return sum((Decimal(str(v.get("total_cost_usd", "0"))) for v in data["models"].values()), Decimal("0"))
    if "levels" in data:
        total = sum((Decimal(str(v.get("total_cost_usd", "0"))) for v in data["levels"].values()), Decimal("0"))
        spec_u = data.get("spec_checks", {}).get("default_usage", {})
        if spec_u and "cost_usd" in spec_u:
            total += Decimal(str(spec_u["cost_usd"]))
        return total
    return Decimal("0")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Gemini 4 Neon 7-Feature Live Benchmarks")
    parser.add_argument(
        "--only",
        nargs="+",
        type=int,
        choices=list(MODULE_REGISTRY.keys()),
        help="Run only specific module numbers (1..7). Defaults to all 7.",
    )
    parser.add_argument("--no-dashboard", action="store_true", help="Skip HTML dashboard build")
    args = parser.parse_args()

    selected = args.only or list(MODULE_REGISTRY.keys())
    summary: dict[str, Any] = {"modules": {}, "grand_total_cost_usd": "0.000000"}
    t_start = time.perf_counter()

    for num in selected:
        key, mod_name = MODULE_REGISTRY[num]
        print(f"\n{'=' * 78}\nRUNNING BENCHMARK #{num}: {mod_name}\n{'=' * 78}")
        mod = importlib.import_module(mod_name)
        try:
            res = mod.run_benchmark()
            summary["modules"][key] = {
                "overall_pass": bool(res.get("overall_pass")),
                "cost_usd": str(extract_module_cost(res).quantize(Decimal("0.000001"))),
                "title": res.get("title", key),
            }
        except Exception as exc:
            print(f"ERROR in {mod_name}: {type(exc).__name__}: {exc}")
            summary["modules"][key] = {
                "overall_pass": False,
                "error": f"{type(exc).__name__}: {exc}",
                "cost_usd": "0.000000",
            }

    # Merge any previously saved module results into master summary
    grand_cost = Decimal("0")
    all_modules_summary: dict[str, Any] = {}
    for num, (key, _) in MODULE_REGISTRY.items():
        p = RESULTS_DIR / f"{key}.json"
        if p.exists():
            data = json.loads(p.read_text(encoding="utf-8"))
            c = extract_module_cost(data)
            grand_cost += c
            all_modules_summary[key] = {
                "overall_pass": bool(data.get("overall_pass")),
                "cost_usd": str(c.quantize(Decimal("0.000001"))),
                "title": data.get("title", key),
            }

    summary["all_recorded_modules"] = all_modules_summary
    summary["grand_total_cost_usd"] = str(grand_cost.quantize(Decimal("0.000001")))
    summary["total_wall_sec"] = round(time.perf_counter() - t_start, 2)
    summary_path = save_result("master_summary", summary)

    print(f"\n{'=' * 78}\nMASTER BENCHMARK SUMMARY ({summary['total_wall_sec']}s)\n{'=' * 78}")
    for k, v in all_modules_summary.items():
        badge = "PASS" if v["overall_pass"] else "FAIL"
        print(f"  [{badge}] {k:32s} | cost=${v['cost_usd']} | {v['title']}")
    print(f"  Grand Total Measured API Spend: ${summary['grand_total_cost_usd']}")
    print(f"  Saved master summary: {summary_path}")

    if not args.no_dashboard:
        import build_dashboard
        html_path = build_dashboard.generate_dashboard()
        print(f"  Generated interactive dashboard: {html_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
