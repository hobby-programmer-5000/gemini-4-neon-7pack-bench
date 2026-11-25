"""Module 1B Addendum: Apples-to-Apples Speed/Token Comparison on Clarified SWE Spec.

Addresses two findings from Module 1:
  1. Explicitly specifies `refill_rate >= 0.0` (0.0 means fixed bucket with no refill,
     `time_until_available` returns `math.inf` if deficit > 0).
  2. Compares `gemini-4-neon` vs `gemini-4-carbon` at MATCHED thinking levels (`medium` vs `medium`,
     and `high` vs `high`) to verify the release note's "leaner token usage and faster E2E completion"
     claim without default-level mismatch (Neon defaults to `high`, Carbon defaults to `medium`).
"""
from __future__ import annotations

import textwrap
import time
from typing import Any

from bench_01_frontier_speed_cost import SWE_VERIFICATION_TESTS, grade_swe
from bench_core import (
    extract_all_model_text,
    extract_python_code,
    extract_usage,
    get_client,
    save_result,
)

CLARIFIED_SWE_PROMPT = textwrap.dedent("""
Write a self-contained Python 3 module (standard library only) implementing TWO classes:

1. `SingleFlight`:
   - Method `do(self, key: str, fn: Callable[[], T]) -> tuple[T, bool]`:
     - Deduplicates concurrent in-flight calls for the same `key` across threads.
     - Only ONE thread executes `fn()` while concurrent callers for the same `key` wait and receive the same result.
     - Returns `(value, shared)` where `shared` is `True` if more than one caller shared that execution, else `False`.
     - If `fn()` raises an exception, ALL waiting callers for that in-flight call must receive that exception, and the key must be cleaned up immediately so subsequent calls retry cleanly.
     - Calls for DIFFERENT keys must execute concurrently (never hold a global lock while running `fn()`).

2. `TokenBucketLimiter`:
   - `__init__(self, capacity: float, refill_rate: float, clock: Callable[[], float] = time.monotonic)`
     - `capacity` must be `> 0`; `refill_rate` must be `>= 0.0` (`0.0` is valid and represents a fixed non-refilling quota).
   - Thread-safe method `allow(self, tokens: float = 1.0) -> bool`:
     - Refills tokens smoothly based on elapsed time from `clock()`, capped at `capacity`.
     - Raises `ValueError` if `tokens <= 0` or `tokens > capacity`.
     - Atomically consumes `tokens` and returns `True` if available, else consumes 0 and returns `False`.
   - Method `time_until_available(self, tokens: float = 1.0) -> float`:
     - Returns `0.0` if `tokens` can be granted immediately, `math.inf` if `refill_rate == 0.0` and tokens are insufficient, else exact seconds needed until available.

Return ONLY a single ```python ... ``` code block using the Python standard library.
""").strip()


def run_addendum() -> dict[str, Any]:
    print("=== [Module 1B] Apples-to-Apples SWE Comparison (Matched Thinking Levels) ===")
    client = get_client()
    configs = [
        ("gemini-4-neon", "medium"),
        ("gemini-4-carbon", "medium"),
        ("gemini-4-neon", "high"),
        ("gemini-4-carbon", "high"),
    ]
    rows: list[dict[str, Any]] = []
    for model, lvl in configs:
        t0 = time.perf_counter()
        inter = client.interactions.create(
            model=model,
            input=CLARIFIED_SWE_PROMPT,
            generation_config={"thinking_level": lvl, "max_output_tokens": 32768},
        )
        u = extract_usage(model, inter, time.perf_counter() - t0)
        grade = grade_swe(extract_python_code(extract_all_model_text(inter)))
        out_thought = u.total_output_tokens + u.total_thought_tokens
        print(
            f"   {model:17s} ({lvl:6s}) | pass={grade['passed']} | time={u.elapsed_sec:6.2f}s | "
            f"thought={u.total_thought_tokens:5d} | out+thought={out_thought:5d} | cost=${u.cost_usd}"
        )
        rows.append({
            "model": model,
            "thinking_level": lvl,
            "passed": grade["passed"],
            "grade": grade,
            "usage": u.to_dict(),
            "output_plus_thought_tokens": out_thought,
        })

    by_key = {(r["model"], r["thinking_level"]): r for r in rows}
    med_speedup = round(by_key[("gemini-4-carbon", "medium")]["usage"]["elapsed_sec"] / by_key[("gemini-4-neon", "medium")]["usage"]["elapsed_sec"], 2)
    high_speedup = round(by_key[("gemini-4-carbon", "high")]["usage"]["elapsed_sec"] / by_key[("gemini-4-neon", "high")]["usage"]["elapsed_sec"], 2)
    med_tok_ratio = round(by_key[("gemini-4-neon", "medium")]["output_plus_thought_tokens"] / by_key[("gemini-4-carbon", "medium")]["output_plus_thought_tokens"], 2)
    high_tok_ratio = round(by_key[("gemini-4-neon", "high")]["output_plus_thought_tokens"] / by_key[("gemini-4-carbon", "high")]["output_plus_thought_tokens"], 2)

    result = {
        "module": "01b_apples_to_apples",
        "title": "Clarified SWE Spec: Matched Thinking-Level Comparison (Neon vs Carbon)",
        "runs": rows,
        "matched_comparisons": {
            "medium_neon_vs_carbon_speedup": med_speedup,
            "medium_neon_vs_carbon_token_ratio": med_tok_ratio,
            "high_neon_vs_carbon_speedup": high_speedup,
            "high_neon_vs_carbon_token_ratio": high_tok_ratio,
        },
        "overall_pass": all(r["passed"] for r in rows),
    }
    p = save_result("01b_apples_to_apples", result)
    print(f"Saved Module 1B addendum to {p}")
    return result


if __name__ == "__main__":
    run_addendum()
