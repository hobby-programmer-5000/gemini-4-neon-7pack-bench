"""Module 1: Frontier-level intelligence with fast end-to-end task completion ($3/$15).

Compares `gemini-4-neon` head-to-head against `gemini-4-hydrogen` and `gemini-4-carbon`
across 3 domains (Complex Software Engineering, Quantitative Finance/Knowledge Work,
and Scientific/Mathematical Computation) using deterministic automated graders.
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
import tempfile
import textwrap
import time
from decimal import Decimal
from pathlib import Path
from typing import Any

from bench_core import (
    extract_all_model_text,
    extract_json_object,
    extract_python_code,
    extract_usage,
    get_client,
    save_result,
)

MODELS_TO_COMPARE = [
    ("gemini-4-hydrogen", "high"),
    ("gemini-4-neon", "high"),
    ("gemini-4-carbon", "medium"),  # official default for Carbon
]

# Task 1A: Complex SWE - Thread-safe SingleFlight + Sliding-Window Token Bucket Rate Limiter
TASK_SWE_PROMPT = textwrap.dedent("""
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
   - Thread-safe method `allow(self, tokens: float = 1.0) -> bool`:
     - Refills tokens smoothly based on elapsed time from `clock()`, capped at `capacity`.
     - Raises `ValueError` if `tokens <= 0` or `tokens > capacity`.
     - Atomically consumes `tokens` and returns `True` if available, else consumes 0 and returns `False`.
   - Method `time_until_available(self, tokens: float = 1.0) -> float`:
     - Returns `0.0` if `tokens` can be granted immediately, else exact seconds needed until available (non-negative).

Return ONLY a single ```python ... ``` code block using the Python standard library.
""").strip()

SWE_VERIFICATION_TESTS = textwrap.dedent("""
import concurrent.futures
import threading
import time
import unittest

from candidate import SingleFlight, TokenBucketLimiter

class TestSWE(unittest.TestCase):
    def test_singleflight_dedup_and_shared_flag(self):
        sf = SingleFlight()
        calls = 0
        calls_lock = threading.Lock()
        gate = threading.Event()
        started = threading.Event()

        def work():
            nonlocal calls
            with calls_lock:
                calls += 1
            started.set()
            gate.wait(timeout=2.0)
            return "PAYLOAD_42"

        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
            futs = [ex.submit(sf.do, "k1", work) for _ in range(5)]
            self.assertTrue(started.wait(timeout=1.5))
            time.sleep(0.08)
            gate.set()
            results = [f.result(timeout=2.0) for f in futs]

        self.assertEqual(calls, 1)
        self.assertTrue(all(val == "PAYLOAD_42" for val, _ in results))
        self.assertTrue(all(shared is True for _, shared in results))

        # Single unshared call after completion
        val2, shared2 = sf.do("k1", lambda: "SOLO")
        self.assertEqual(val2, "SOLO")
        self.assertFalse(shared2)

    def test_singleflight_exception_cleanup_and_parallel_keys(self):
        sf = SingleFlight()
        b = threading.Barrier(2, timeout=1.5)
        def slow(tag):
            b.wait()
            return tag
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
            f1 = ex.submit(sf.do, "keyA", lambda: slow("A"))
            f2 = ex.submit(sf.do, "keyB", lambda: slow("B"))
            self.assertEqual(f1.result(timeout=2.0)[0], "A")
            self.assertEqual(f2.result(timeout=2.0)[0], "B")

        def boom():
            time.sleep(0.05)
            raise RuntimeError("boom!")
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
            futs = [ex.submit(sf.do, "errk", boom) for _ in range(3)]
            for f in futs:
                with self.assertRaises(RuntimeError):
                    f.result(timeout=2.0)
        # Key must be cleaned up so retry succeeds
        self.assertEqual(sf.do("errk", lambda: "RECOVERED")[0], "RECOVERED")

    def test_token_bucket_deterministic_clock_and_threads(self):
        now = [100.0]
        limiter = TokenBucketLimiter(capacity=5.0, refill_rate=2.0, clock=lambda: now[0])
        self.assertTrue(limiter.allow(3.0))
        self.assertTrue(limiter.allow(2.0))
        self.assertFalse(limiter.allow(1.0))
        self.assertAlmostEqual(limiter.time_until_available(1.0), 0.5, places=6)
        now[0] += 0.5
        self.assertAlmostEqual(limiter.time_until_available(1.0), 0.0, places=6)
        self.assertTrue(limiter.allow(1.0))
        now[0] += 100.0  # must cap at capacity=5.0
        self.assertTrue(limiter.allow(5.0))
        self.assertFalse(limiter.allow(0.1))
        with self.assertRaises(ValueError):
            limiter.allow(0.0)
        with self.assertRaises(ValueError):
            limiter.allow(5.5)

        # Concurrent contention check: capacity=10, refill=0 -> exactly 10 of 25 succeed
        fixed_limiter = TokenBucketLimiter(capacity=10.0, refill_rate=0.0, clock=lambda: 0.0)
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
            res = list(ex.map(lambda _: fixed_limiter.allow(1.0), range(25)))
        self.assertEqual(res.count(True), 10)

if __name__ == "__main__":
    unittest.main()
""").strip()


# Task 1B: Knowledge Work (Finance / SaaS Accounting Exact Calculation)
# Ground truth verified via Python Decimal:
# Contract value: 3-year Enterprise SaaS deal:
#   Year 1: $180,000 subscription + $24,000 non-distinct onboarding (bundled over 36 months)
#   Year 2: 5% CPI uplift on subscription ($189,000)
#   Year 3: 5% CPI uplift on Year 2 ($198,450)
#   Total transaction price = 180,000 + 189,000 + 198,450 + 24,000 = $591,450.00
#   ASC 606 straight-line monthly revenue = 591,450 / 36 = $16,429.166666... -> $16,429.17
#   Year 1 recognized revenue (12 months) = 591,450 / 3 = $197,150.00
#   Year 1 cash billed upfront = $180,000 + $24,000 = $204,000.00
#   End of Year 1 Deferred Revenue (Contract Liability) = 204,000 - 197,150 = $6,850.00
#   Sales commission = 8% of Year 1 ACV ($180,000) = $14,400.00, capitalized under ASC 340-40 over 5-year expected customer life = $2,880.00/yr amortization.
TASK_FINANCE_PROMPT = textwrap.dedent("""
Solve this ASC 606 / ASC 340-40 SaaS revenue recognition problem with exact arithmetic:

A software vendor signs a non-cancellable 3-year (36-month) enterprise SaaS contract starting Jan 1, 2026:
- Year 1 annual subscription fee: $180,000 (billed upfront Jan 1, 2026)
- Mandatory non-distinct implementation/onboarding fee: $24,000 (billed upfront Jan 1, 2026; NOT a separate performance obligation, so bundled into the single stand-ready SaaS obligation over 36 months)
- Year 2 annual subscription fee: 5% escalation over Year 1 subscription
- Year 3 annual subscription fee: 5% escalation compounded over Year 2 subscription
- Sales commission paid at signing: 8% of Year 1 subscription ($180,000 only, excluding onboarding), capitalized under ASC 340-40 and amortized straight-line over the 5-year expected customer benefit period (including anticipated renewals).

Return ONLY a JSON object with exact numbers rounded to 2 decimal places (HALF_UP):
{
  "total_transaction_price": number,
  "year1_recognized_revenue": number,
  "year1_ending_deferred_revenue": number,
  "year1_commission_amortization": number
}
""").strip()

FINANCE_GROUND_TRUTH = {
    "total_transaction_price": Decimal("591450.00"),
    "year1_recognized_revenue": Decimal("197150.00"),
    "year1_ending_deferred_revenue": Decimal("6850.00"),
    "year1_commission_amortization": Decimal("2880.00"),
}


# Task 1C: Science / Quantitative (Consecutive First-Order Chemical Kinetics A -> B -> C)
# Exact analytic solution:
#   [B](t) = [A]_0 * (k1 / (k2 - k1)) * (exp(-k1*t) - exp(-k2*t))
#   t_max = ln(k2 / k1) / (k2 - k1)
#   [B]_max = [A]_0 * (k1 / k2)**(k2 / (k2 - k1))
# Given: [A]_0 = 2.50 mol/L, k1 = 0.18 s^-1, k2 = 0.45 s^-1
# Exact:
#   t_max = ln(0.45 / 0.18) / (0.45 - 0.18) = ln(2.5) / 0.27 = 3.393669374837... s
#   b_max = 2.50 * (0.4)**(0.45/0.27) = 2.50 * (0.4)**(5/3) = 0.5428835233189... mol/L
#   c_at_tmax = 2.50 - [A](t_max) - [B]_max = 2.50 - 2.50*exp(-0.18*t_max) - b_max
#             = 2.50 - 2.50*(0.4)**(2/3) - b_max = 2.50 - 1.35720880829745... - 0.54288352331898... = 0.59990766838356...
TASK_SCIENCE_PROMPT = textwrap.dedent("""
Consider a consecutive irreversible first-order chemical reaction in an isothermal batch reactor:
    A --(k1)--> B --(k2)--> C

Initial concentrations at t = 0:
    [A]_0 = 2.50 mol/L, [B]_0 = 0, [C]_0 = 0
Rate constants:
    k1 = 0.18 s^-1
    k2 = 0.45 s^-1

Compute to at least 6 decimal places:
1. `t_max`: the exact time (in seconds) at which intermediate concentration [B](t) reaches its maximum.
2. `b_max`: the maximum concentration [B](t_max) in mol/L.
3. `c_at_tmax`: the product concentration [C](t_max) in mol/L at t = t_max.

Return ONLY a JSON object:
{
  "t_max": number,
  "b_max": number,
  "c_at_tmax": number
}
""").strip()


def _science_ground_truth() -> dict[str, float]:
    a0, k1, k2 = 2.50, 0.18, 0.45
    t_max = math.log(k2 / k1) / (k2 - k1)
    a_t = a0 * math.exp(-k1 * t_max)
    b_max = a0 * (k1 / (k2 - k1)) * (math.exp(-k1 * t_max) - math.exp(-k2 * t_max))
    c_t = a0 - a_t - b_max
    return {"t_max": t_max, "b_max": b_max, "c_at_tmax": c_t}


def grade_swe(code: str) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        (tmp / "candidate.py").write_text(code, encoding="utf-8")
        (tmp / "test_swe.py").write_text(SWE_VERIFICATION_TESTS, encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, "-m", "unittest", "-v", "test_swe.py"],
            cwd=tmpdir,
            capture_output=True,
            text=True,
            timeout=25,
        )
        return {
            "passed": proc.returncode == 0,
            "returncode": proc.returncode,
            "stderr_tail": proc.stderr[-800:],
        }


def grade_finance(text: str) -> dict[str, Any]:
    try:
        parsed = extract_json_object(text)
    except Exception as exc:
        return {"passed": False, "error": f"JSON parse error: {exc}"}
    checks = {}
    all_ok = True
    for key, expected in FINANCE_GROUND_TRUTH.items():
        if key not in parsed:
            checks[key] = {"ok": False, "expected": str(expected), "got": None}
            all_ok = False
        else:
            got = Decimal(str(parsed[key])).quantize(Decimal("0.01"))
            ok = abs(got - expected) <= Decimal("0.01")
            checks[key] = {"ok": ok, "expected": str(expected), "got": str(got)}
            if not ok:
                all_ok = False
    return {"passed": all_ok, "checks": checks}


def grade_science(text: str) -> dict[str, Any]:
    try:
        parsed = extract_json_object(text)
    except Exception as exc:
        return {"passed": False, "error": f"JSON parse error: {exc}"}
    gt = _science_ground_truth()
    checks = {}
    all_ok = True
    for key, expected in gt.items():
        if key not in parsed:
            checks[key] = {"ok": False, "expected": round(expected, 6), "got": None}
            all_ok = False
        else:
            got = float(parsed[key])
            err = abs(got - expected)
            ok = err <= 1e-4
            checks[key] = {"ok": ok, "expected": round(expected, 6), "got": round(got, 6), "abs_err": err}
            if not ok:
                all_ok = False
    return {"passed": all_ok, "checks": checks}


def run_benchmark() -> dict[str, Any]:
    print("=== [Module 1] Frontier Intelligence, Fast E2E & Cost Efficiency ($3/$15) ===")
    client = get_client()
    tasks = [
        ("swe_singleflight_ratelimiter", TASK_SWE_PROMPT, grade_swe, True),
        ("finance_asc606", TASK_FINANCE_PROMPT, grade_finance, False),
        ("science_kinetics", TASK_SCIENCE_PROMPT, grade_science, False),
    ]

    results_by_model: dict[str, Any] = {}
    for model, thinking_level in MODELS_TO_COMPARE:
        print(f"\n-> Testing {model} (thinking_level={thinking_level})...")
        model_tasks = []
        passed_count = 0
        total_elapsed = 0.0
        total_out_and_thought = 0
        total_cost = Decimal("0")
        total_cost_post_promo = Decimal("0")

        for task_name, prompt, grader, is_code in tasks:
            t0 = time.perf_counter()
            try:
                interaction = client.interactions.create(
                    model=model,
                    input=prompt,
                    generation_config={
                        "thinking_level": thinking_level,
                        "max_output_tokens": 32768,
                    },
                )
                elapsed = time.perf_counter() - t0
                usage = extract_usage(model, interaction, elapsed)
                text = extract_all_model_text(interaction)
                grade = grader(extract_python_code(text) if is_code else text)
            except Exception as exc:
                elapsed = time.perf_counter() - t0
                usage = None
                grade = {"passed": False, "error": f"{type(exc).__name__}: {exc}"}

            ok = bool(grade.get("passed"))
            if ok:
                passed_count += 1
            total_elapsed += elapsed
            if usage:
                total_out_and_thought += usage.total_output_tokens + usage.total_thought_tokens
                total_cost += Decimal(usage.cost_usd)
                if usage.cost_usd_carbon_post_promo:
                    total_cost_post_promo += Decimal(usage.cost_usd_carbon_post_promo)

            print(
                f"   [{task_name}] pass={ok} | time={elapsed:.2f}s | "
                f"out+thought={(usage.total_output_tokens + usage.total_thought_tokens) if usage else 0} | "
                f"cost=${usage.cost_usd if usage else 'N/A'}"
            )
            model_tasks.append({
                "task": task_name,
                "grade": grade,
                "usage": usage.to_dict() if usage else None,
            })

        results_by_model[model] = {
            "thinking_level": thinking_level,
            "passed": passed_count,
            "total": len(tasks),
            "pass_rate": round(passed_count / len(tasks), 4),
            "total_elapsed_sec": round(total_elapsed, 3),
            "total_output_plus_thought_tokens": total_out_and_thought,
            "total_cost_usd": str(total_cost.quantize(Decimal("0.000001"))),
            "total_cost_usd_carbon_post_promo": (
                str(total_cost_post_promo.quantize(Decimal("0.000001")))
                if model == "gemini-4-carbon"
                else None
            ),
            "tasks": model_tasks,
        }

    neon = results_by_model["gemini-4-neon"]
    carbon = results_by_model["gemini-4-carbon"]
    summary = {
        "module": "01_frontier_speed_cost",
        "title": "Frontier-level intelligence with fast E2E completion ($3/$15)",
        "models": results_by_model,
        "comparisons": {
            "neon_vs_carbon_speedup_ratio": (
                round(carbon["total_elapsed_sec"] / neon["total_elapsed_sec"], 2)
                if neon["total_elapsed_sec"] > 0
                else None
            ),
            "neon_vs_carbon_token_ratio": (
                round(neon["total_output_plus_thought_tokens"] / carbon["total_output_plus_thought_tokens"], 2)
                if carbon["total_output_plus_thought_tokens"] > 0
                else None
            ),
        },
        "overall_pass": neon["passed"] == len(tasks),
    }
    path = save_result("01_frontier_speed_cost", summary)
    print(f"\nSaved Module 1 results to {path}")
    return summary


if __name__ == "__main__":
    run_benchmark()
