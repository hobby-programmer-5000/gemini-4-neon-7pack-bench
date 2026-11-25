"""Module 3: Knowledge work, science, and analytical reasoning (Multimodal + Multi-Doc + Structured Output).

Generates real source artifacts inside `fixtures/knowledge_pack/`:
  1. Dense legal contract (`msa_contract.md`) with cross-referenced rebate, cap, and addendum override
  2. Financial spreadsheet (`q1_q4_financials.csv`) with duplicate invoice & unapplied rebate anomaly
  3. Rendered matplotlib chart PNG (`margin_chart.png`) containing a visual-only inflection annotation
  4. Quantitative scientific dataset (`thermal_experiment.csv`) following Arrhenius kinetics with 1 sensor outlier

Sends all 4 artifacts (including inline base64 PNG image + dense appendices exceeding 6K tokens to exercise
long-context cross-referencing AND implicit caching) to `gemini-4-neon` with strict Pydantic `response_format`
JSON Schema, then grades every extracted legal/financial/visual/scientific quantity deterministically.
"""
from __future__ import annotations

import base64
import csv
import math
import time
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from pydantic import BaseModel, Field

from bench_core import (
    FIXTURES_DIR,
    extract_all_model_text,
    extract_usage,
    get_client,
    save_result,
)

PACK_DIR = FIXTURES_DIR / "knowledge_pack"
PACK_DIR.mkdir(parents=True, exist_ok=True)


class ExecutiveSynthesis(BaseModel):
    effective_data_breach_liability_cap_usd: float = Field(
        description="Effective data-breach indemnification liability cap in USD after applying Addendum #2 override."
    )
    duplicate_invoice_id: str = Field(
        description="Exact invoice ID that appears duplicated in q1_q4_financials.csv."
    )
    duplicate_overcharge_usd: float = Field(
        description="Dollar amount of the duplicate invoice overcharge."
    )
    net_eligible_annual_spend_usd: float = Field(
        description="Total Q1-Q4 spend after removing the single duplicate invoice."
    )
    missing_volume_rebate_usd: float = Field(
        description="Exact volume rebate owed under Section 4.2 based on net eligible annual spend."
    )
    chart_inflection_event_label: str = Field(
        description="Exact annotated event label visible ONLY inside margin_chart.png at the Q3 margin jump."
    )
    chart_q3_gross_margin_pct: float = Field(
        description="Q3 Gross Margin percentage annotated on margin_chart.png."
    )
    arrhenius_outlier_run_id: str = Field(
        description="Run ID of the faulty sensor outlier in thermal_experiment.csv."
    )
    activation_energy_kj_per_mol: float = Field(
        description="Activation energy Ea (kJ/mol) computed from linear regression of ln(k) vs 1/T excluding the outlier."
    )
    action_items: list[str] = Field(
        description="3 concrete, cited executive remediation steps referencing exact clauses, invoices, and runs."
    )


def build_knowledge_fixtures() -> dict[str, Any]:
    """Generate deterministic legal, finance, chart PNG, and science fixtures + exact ground truth."""
    # 1. Financial CSV: 16 invoices + 1 deliberate duplicate (INV-2026-0911 for $45,000)
    rows = [
        ("INV-2026-0101", "Q1", "NA", "CorePlatform", 120000),
        ("INV-2026-0102", "Q1", "EMEA", "CorePlatform", 85000),
        ("INV-2026-0103", "Q1", "APAC", "AnalyticsAddOn", 45000),
        ("INV-2026-0401", "Q2", "NA", "CorePlatform", 130000),
        ("INV-2026-0402", "Q2", "EMEA", "CorePlatform", 90000),
        ("INV-2026-0403", "Q2", "APAC", "AnalyticsAddOn", 50000),
        ("INV-2026-0701", "Q3", "NA", "CorePlatform", 140000),
        ("INV-2026-0702", "Q3", "EMEA", "CorePlatform", 95000),
        ("INV-2026-0911", "Q3", "APAC", "AnalyticsAddOn", 45000),
        ("INV-2026-0911", "Q3", "APAC", "AnalyticsAddOn", 45000),  # DUPLICATE!
        ("INV-2026-1001", "Q4", "NA", "CorePlatform", 150000),
        ("INV-2026-1002", "Q4", "EMEA", "CorePlatform", 105000),
        ("INV-2026-1003", "Q4", "APAC", "AnalyticsAddOn", 65000),
    ]
    csv_path = PACK_DIR / "q1_q4_financials.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["invoice_id", "quarter", "region", "product", "amount_usd"])
        w.writerows(rows)

    # Net eligible spend = sum of unique rows = 1,120,000
    unique_spend = sum(r[4] for r in rows) - 45000  # 1,120,000
    assert unique_spend == 1_120_000
    # Section 4.2 rebate: 5% on spend strictly above $800,000 -> 0.05 * 320,000 = $16,000
    rebate_owed = Decimal("0.05") * Decimal(str(unique_spend - 800_000))  # 16,000.00
    assert rebate_owed == Decimal("16000.00")

    # 2. Dense Legal MSA + Long Technical Appendices (~5,500 tokens so implicit caching >=4096 triggers too!)
    filler_clauses = "\n".join(
        f"### Appendix B.{i} Standard Operational Telemetry Control\n"
        f"Provider shall maintain log integrity digest SHA-256 verification across region shard {i:03d}, "
        f"retaining read-only metrics for diagnostic verification under ISO/IEC 27001 control family A.12.{i % 7 + 1}. "
        f"Scheduled maintenance windows occur Sundays 02:00-04:00 UTC with 72-hour advance notice.\n"
        for i in range(1, 130)
    )
    msa_text = f"""# MASTER SERVICES AGREEMENT (MSA-2026-APEX)
Between Apex Cloud Systems Inc. ("Provider") and Horizon BioLabs Corp. ("Customer").

## Section 4.2: Annual Volume Rebate
If Customer's Net Eligible Annual Spend across all non-duplicated invoices in a calendar year exceeds USD 800,000, Provider shall issue a retroactive Volume Rebate equal to **5.0% of the incremental Net Eligible Annual Spend strictly exceeding USD 800,000** (zero rebate on the first USD 800,000). Duplicate billings must be deducted prior to threshold computation.

## Section 9.4: General Limitation of Liability
Except as expressly modified by signed written Addendum, Provider's aggregate liability under this Agreement shall not exceed **USD 500,000** (the "Base Liability Cap").

## Technical & Compliance Appendices (A through B)
{filler_clauses}

## ADDENDUM #2 (EXECUTED OCT 14, 2026): SUPERSEDING DATA BREACH INDEMNITY CAP
Notwithstanding Section 9.4 (General Limitation of Liability), solely with respect to Provider's indemnification obligations arising from a confirmed Unauthorized Personal Data Disclosure ("Data Breach"), the aggregate liability cap is hereby increased to **3.5x the Base Liability Cap** (i.e., **USD 1,750,000**), superseding Section 9.4 for Data Breach claims only.
"""
    msa_path = PACK_DIR / "msa_contract.md"
    msa_path.write_text(msa_text, encoding="utf-8")

    # 3. Real Rendered Chart PNG containing a visual-only inflection annotation
    chart_path = PACK_DIR / "margin_chart.png"
    quarters = ["Q1-26", "Q2-26", "Q3-26", "Q4-26"]
    margins = [61.2, 62.5, 74.8, 76.1]
    latency_ms = [210, 198, 92, 85]

    fig, ax1 = plt.subplots(figsize=(9, 5), dpi=150)
    ax1.plot(quarters, margins, marker="o", linewidth=2.8, color="#1f77b4", label="Gross Margin (%)")
    ax1.set_ylabel("Gross Margin (%)", color="#1f77b4", fontsize=11, fontweight="bold")
    ax1.set_ylim(50, 85)
    for q, m in zip(quarters, margins):
        ax1.annotate(f"{m:.1f}%", (q, m), textcoords="offset points", xytext=(0, 10), ha="center", fontweight="bold", color="#1f77b4")

    # Visual-only annotation (NOT written anywhere in text/CSV!)
    ax1.annotate(
        "Project Helios Cutover\n(+12.3pp Margin Jump)",
        xy=("Q3-26", 74.8),
        xytext=("Q1-26", 78.5),
        fontsize=10,
        fontweight="bold",
        color="#b22222",
        bbox=dict(boxstyle="round,pad=0.4", facecolor="#fff4e6", edgecolor="#b22222", lw=1.5),
        arrowprops=dict(arrowstyle="->", color="#b22222", lw=2.0),
    )

    ax2 = ax1.twinx()
    ax2.bar(quarters, latency_ms, alpha=0.25, width=0.35, color="#2ca02c", label="P95 Latency (ms)")
    ax2.set_ylabel("P95 Latency (ms)", color="#2ca02c", fontsize=11, fontweight="bold")
    ax2.set_ylim(0, 260)

    plt.title("Horizon BioLabs: Quarterly Gross Margin & P95 Latency (FY2026)", fontsize=13, fontweight="bold")
    fig.tight_layout()
    fig.savefig(chart_path)
    plt.close(fig)

    # 4. Scientific Arrhenius dataset: k(T) = A * exp(-Ea / (R*T))
    # True parameters: Ea = 62.50 kJ/mol, A = 1.20e9 s^-1, R = 8.314462618 J/(mol*K)
    R = 8.314462618
    Ea_true = 62500.0
    A_true = 1.2e9
    temps_k = [300.0, 310.0, 320.0, 330.0, 340.0, 350.0, 360.0]
    exp_rows = []
    clean_inv_t = []
    clean_lnk = []
    for idx, T in enumerate(temps_k, start=1):
        run_id = f"RUN-{idx:02d}"
        if run_id == "RUN-05":
            # Corrupt sensor outlier (100x off)
            k_val = 0.000150
            note = "thermocouple_drift_alert"
        else:
            k_val = A_true * math.exp(-Ea_true / (R * T))
            clean_inv_t.append(1.0 / T)
            clean_lnk.append(math.log(k_val))
            note = "nominal"
        exp_rows.append((run_id, f"{T:.1f}", f"{k_val:.8e}", note))

    exp_path = PACK_DIR / "thermal_experiment.csv"
    with exp_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["run_id", "temp_kelvin", "rate_constant_k_s_inv", "sensor_status"])
        w.writerows(exp_rows)

    slope, intercept = np.polyfit(clean_inv_t, clean_lnk, 1)
    ea_kj = (-slope * R) / 1000.0

    return {
        "msa_path": msa_path,
        "csv_path": csv_path,
        "chart_path": chart_path,
        "exp_path": exp_path,
        "ground_truth": {
            "effective_data_breach_liability_cap_usd": 1_750_000.0,
            "duplicate_invoice_id": "INV-2026-0911",
            "duplicate_overcharge_usd": 45_000.0,
            "net_eligible_annual_spend_usd": 1_120_000.0,
            "missing_volume_rebate_usd": 16_000.0,
            "chart_inflection_event_label_keyword": "Helios",
            "chart_q3_gross_margin_pct": 74.8,
            "arrhenius_outlier_run_id": "RUN-05",
            "activation_energy_kj_per_mol": round(float(ea_kj), 4),
        },
    }


def run_benchmark() -> dict[str, Any]:
    print("=== [Module 3] Knowledge Work, Science & Multimodal Analytical Synthesis ===")
    fx = build_knowledge_fixtures()
    gt = fx["ground_truth"]

    msa_text = fx["msa_path"].read_text(encoding="utf-8")
    csv_text = fx["csv_path"].read_text(encoding="utf-8")
    exp_text = fx["exp_path"].read_text(encoding="utf-8")
    chart_b64 = base64.b64encode(fx["chart_path"].read_bytes()).decode("ascii")

    prompt_text = (
        "You are an executive legal, financial, and quantitative research analyst.\n"
        "Synthesize ALL FOUR attached artifacts (MSA Contract, Q1-Q4 Financial CSV, "
        "Arrhenius Thermal Experiment CSV, and the attached Quarterly Margin Chart PNG).\n"
        "Compute exact values using R = 8.314462618 J/(mol*K) for the Arrhenius linear regression "
        "(ln(k) vs 1/T, excluding the corrupted sensor outlier run).\n\n"
        "=== DOCUMENT 1: MSA CONTRACT ===\n"
        f"{msa_text}\n\n"
        "=== DOCUMENT 2: Q1-Q4 FINANCIALS CSV ===\n"
        f"{csv_text}\n\n"
        "=== DOCUMENT 3: THERMAL EXPERIMENT CSV ===\n"
        f"{exp_text}\n\n"
        "=== DOCUMENT 4: ATTACHED CHART PNG ===\n"
        "Inspect the attached image `margin_chart.png` for the Q3 margin value and the red-boxed event label.\n"
        "Return your structured synthesis strictly matching the JSON schema."
    )

    client = get_client()
    t0 = time.perf_counter()
    interaction = client.interactions.create(
        model="gemini-4-neon",
        input=[
            {"type": "text", "text": prompt_text},
            {"type": "image", "data": chart_b64, "mime_type": "image/png"},
        ],
        response_format={
            "type": "text",
            "mime_type": "application/json",
            "schema": ExecutiveSynthesis.model_json_schema(),
        },
        generation_config={
            "thinking_level": "high",
            "max_output_tokens": 32768,
        },
    )
    elapsed = time.perf_counter() - t0
    usage = extract_usage("gemini-4-neon", interaction, elapsed)
    raw_text = extract_all_model_text(interaction)

    parsed = ExecutiveSynthesis.model_validate_json(raw_text)
    checks = {
        "legal_addendum_cap": abs(parsed.effective_data_breach_liability_cap_usd - gt["effective_data_breach_liability_cap_usd"]) < 1.0,
        "finance_duplicate_id": parsed.duplicate_invoice_id.strip() == gt["duplicate_invoice_id"],
        "finance_duplicate_amount": abs(parsed.duplicate_overcharge_usd - gt["duplicate_overcharge_usd"]) < 1.0,
        "finance_net_spend": abs(parsed.net_eligible_annual_spend_usd - gt["net_eligible_annual_spend_usd"]) < 1.0,
        "finance_rebate_owed": abs(parsed.missing_volume_rebate_usd - gt["missing_volume_rebate_usd"]) < 1.0,
        "chart_visual_label": gt["chart_inflection_event_label_keyword"].lower() in parsed.chart_inflection_event_label.lower(),
        "chart_q3_margin": abs(parsed.chart_q3_gross_margin_pct - gt["chart_q3_gross_margin_pct"]) <= 0.15,
        "science_outlier_id": parsed.arrhenius_outlier_run_id.strip().upper() == gt["arrhenius_outlier_run_id"],
        "science_activation_energy_kj": abs(parsed.activation_energy_kj_per_mol - gt["activation_energy_kj_per_mol"]) <= 0.25,
        "action_items_present": len(parsed.action_items) >= 3,
    }
    passed_checks = sum(1 for v in checks.values() if v)
    print(f"-> Passed {passed_checks}/{len(checks)} cross-domain checks | time={elapsed:.2f}s | cost=${usage.cost_usd}")
    for k, ok in checks.items():
        print(f"   [{ 'PASS' if ok else 'FAIL' }] {k}")

    summary = {
        "module": "03_knowledge_science_1m",
        "title": "Knowledge work, science & multimodal synthesis (Legal + Finance + Chart + Arrhenius)",
        "usage": usage.to_dict(),
        "ground_truth": gt,
        "parsed_output": parsed.model_dump(),
        "checks": checks,
        "passed_checks": passed_checks,
        "total_checks": len(checks),
        "overall_pass": passed_checks == len(checks),
        "chart_artifact": "fixtures/knowledge_pack/margin_chart.png",
    }
    out = save_result("03_knowledge_science_1m", summary)
    print(f"Saved Module 3 results to {out}")
    return summary


if __name__ == "__main__":
    run_benchmark()
