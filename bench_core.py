"""Shared benchmark core for the Gemini 4 Neon 7-Feature Live Verification Suite.

Uses the official Google GenAI Interactions API (`google-genai >= 3.2.0`),
exact `Decimal(str(...))` billing math matching official pricing docs,
and clean JSON result persistence.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field, asdict
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any

from google import genai

ROOT_DIR = Path(__file__).resolve().parent
FIXTURES_DIR = ROOT_DIR / "fixtures"
RESULTS_DIR = ROOT_DIR / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# Verified official pricing per 1M tokens (USD) from Gemini API pricing docs
# Note: Carbon promo ($2/$10/$0.10) applies through 2026-11-30; standard ($4/$20/$0.20) from 2026-12-01.
PRICING_PER_1M: dict[str, dict[str, Decimal]] = {
    "gemini-4-neon": {
        "input": Decimal("3.00"),
        "cached_input": Decimal("0.15"),
        "output": Decimal("15.00"),
    },
    "gemini-4-hydrogen": {
        "input": Decimal("1.50"),
        "cached_input": Decimal("0.075"),
        "output": Decimal("7.50"),
    },
    "gemini-4-carbon": {
        "input": Decimal("2.00") if date.today() <= date(2026, 11, 30) else Decimal("4.00"),
        "cached_input": Decimal("0.10") if date.today() <= date(2026, 11, 30) else Decimal("0.20"),
        "output": Decimal("10.00") if date.today() <= date(2026, 11, 30) else Decimal("20.00"),
    },
    "gemini-4-carbon-standard": {
        "input": Decimal("4.00"),
        "cached_input": Decimal("0.20"),
        "output": Decimal("20.00"),
    },
}

ONE_MILLION = Decimal("1000000")
UNIFIED_CONTEXT_WINDOW = 1_048_576
DEFAULT_SYNC_OUTPUT_CAP = 65_536


@dataclass
class UsageMetrics:
    model: str
    elapsed_sec: float
    initial_input_tokens: int = 0
    total_input_tokens: int = 0
    total_cached_tokens: int = 0
    total_output_tokens: int = 0
    total_thought_tokens: int = 0
    total_tokens: int = 0
    cost_usd: str = "0.000000"
    cost_usd_carbon_post_promo: str | None = None
    status: str = "unknown"
    interaction_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def get_client(api_version: str | None = None, timeout_sec: float = 900.0) -> genai.Client:
    """Create a Google GenAI client (v1 default; v1beta when requested for Managed Agents)."""
    http_opts: dict[str, Any] = {"timeout": int(timeout_sec * 1000)}
    if api_version:
        http_opts["api_version"] = api_version
    return genai.Client(http_options=http_opts)


def extract_all_model_text(interaction: Any) -> str:
    """Join text across all `model_output` steps (required for Long Decode multi-hop)."""
    steps = getattr(interaction, "steps", None) or []
    chunks: list[str] = []
    for step in steps:
        if getattr(step, "type", None) == "model_output":
            for content in getattr(step, "content", None) or []:
                if getattr(content, "type", None) == "text" and getattr(content, "text", None):
                    chunks.append(content.text)
    if chunks:
        return "".join(chunks)
    return getattr(interaction, "output_text", None) or ""


def compute_cost_usd(
    model: str,
    total_input_tokens: int,
    total_cached_tokens: int,
    total_output_tokens: int,
    total_thought_tokens: int,
    pricing_override_key: str | None = None,
) -> Decimal:
    """Exact Decimal billing calculation: non-cached input + cached input + (output + thinking)."""
    key = pricing_override_key or model
    rates = PRICING_PER_1M.get(key, PRICING_PER_1M["gemini-4-neon"])
    non_cached_input = max(0, total_input_tokens - total_cached_tokens)
    billable_output = total_output_tokens + total_thought_tokens

    cost = (
        (Decimal(str(non_cached_input)) / ONE_MILLION) * rates["input"]
        + (Decimal(str(total_cached_tokens)) / ONE_MILLION) * rates["cached_input"]
        + (Decimal(str(billable_output)) / ONE_MILLION) * rates["output"]
    )
    return cost.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


def extract_usage(model: str, interaction: Any, elapsed_sec: float) -> UsageMetrics:
    usage = getattr(interaction, "usage", None)
    initial_in = int(getattr(usage, "initial_input_tokens", 0) or 0)
    total_in = int(getattr(usage, "total_input_tokens", 0) or 0)
    cached = int(getattr(usage, "total_cached_tokens", 0) or 0)
    total_out = int(getattr(usage, "total_output_tokens", 0) or 0)
    thought = int(getattr(usage, "total_thought_tokens", 0) or 0)
    total_tok = int(getattr(usage, "total_tokens", 0) or 0)

    cost = compute_cost_usd(model, total_in, cached, total_out, thought)
    carbon_post_promo = None
    if model == "gemini-4-carbon":
        carbon_post_promo = str(
            compute_cost_usd(
                model,
                total_in,
                cached,
                total_out,
                thought,
                pricing_override_key="gemini-4-carbon-standard",
            )
        )

    return UsageMetrics(
        model=model,
        elapsed_sec=round(elapsed_sec, 3),
        initial_input_tokens=initial_in,
        total_input_tokens=total_in,
        total_cached_tokens=cached,
        total_output_tokens=total_out,
        total_thought_tokens=thought,
        total_tokens=total_tok,
        cost_usd=str(cost),
        cost_usd_carbon_post_promo=carbon_post_promo,
        status=str(getattr(interaction, "status", "unknown")),
        interaction_id=getattr(interaction, "id", None),
    )


def extract_python_code(text: str) -> str:
    """Extract the largest ```python ... ``` code block from a model response."""
    blocks = re.findall(r"```(?:python|py)\s*\n(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    if blocks:
        return max(blocks, key=len).strip()
    blocks_any = re.findall(r"```\s*\n(.*?)```", text, flags=re.DOTALL)
    if blocks_any:
        return max(blocks_any, key=len).strip()
    return text.strip()


def extract_json_object(text: str) -> dict[str, Any]:
    """Parse JSON from plain or fenced response."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```\s*$", "", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise


def save_result(module_id: str, payload: dict[str, Any]) -> Path:
    payload["recorded_at_utc"] = datetime.now(timezone.utc).isoformat()
    out_path = RESULTS_DIR / f"{module_id}.json"
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return out_path


def sum_usage_costs(metrics_list: list[UsageMetrics]) -> dict[str, Any]:
    total_cost = sum((Decimal(m.cost_usd) for m in metrics_list), Decimal("0"))
    return {
        "calls": len(metrics_list),
        "total_elapsed_sec": round(sum(m.elapsed_sec for m in metrics_list), 3),
        "total_input_tokens": sum(m.total_input_tokens for m in metrics_list),
        "total_cached_tokens": sum(m.total_cached_tokens for m in metrics_list),
        "total_output_tokens": sum(m.total_output_tokens for m in metrics_list),
        "total_thought_tokens": sum(m.total_thought_tokens for m in metrics_list),
        "total_cost_usd": str(total_cost.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)),
    }
