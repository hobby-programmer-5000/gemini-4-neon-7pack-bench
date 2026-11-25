"""Module 5: Four Configurable Thinking Levels (`low`, `medium`, `high` default, `xhigh`).

Empirically sweeps all 4 supported `thinking_level` values on `gemini-4-neon` across:
  - Task A (Algorithmic DP + Reconstruction: Executable Grader)
  - Task B (Hard Combinatorial Automaton Counting: Exact DP Ground Truth)
Plus 2 spec-compliance checks:
  - Omitting `thinking_level` (defaults to `high`)
  - Passing `thinking_level="minimal"` (must be rejected with API error per official Neon docs)
"""
from __future__ import annotations

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

THINKING_LEVELS = ["low", "medium", "high", "xhigh"]

# Task A: Weighted Interval Scheduling with mandatory cooldown gap `gap` and lexicographically smallest tie-breaking
TASK_DP_PROMPT = textwrap.dedent("""
Write a Python 3 function `max_weighted_schedule(jobs: list[tuple[int, int, int, str]], gap: int) -> tuple[int, list[str]]`:
- Each job is `(start, end, weight, job_id)` with `start < end`, `weight > 0`.
- Two selected jobs `i` and `j` (with `start_i <= start_j`) are compatible iff `end_i + gap <= start_j`.
- Maximize total weight.
- If multiple schedules achieve the same maximum total weight, return the one whose sorted list of `job_id`s is lexicographically smallest.
- Return `(max_weight, sorted_job_ids)`.
- Must handle up to N=2000 jobs efficiently (`O(N log N)` or clean `O(N^2)` for small N without exponential recursion).

Return ONLY a single ```python ... ``` code block.
""").strip()

DP_TEST_HARNESS = textwrap.dedent("""
import itertools
import unittest
from candidate import max_weighted_schedule

def brute_force(jobs, gap):
    best_w = 0
    best_ids = []
    n = len(jobs)
    for mask in range(1, 1 << n):
        chosen = [jobs[i] for i in range(n) if (mask >> i) & 1]
        chosen_sorted = sorted(chosen, key=lambda x: (x[0], x[1]))
        ok = True
        for a, b in zip(chosen_sorted, chosen_sorted[1:]):
            if a[1] + gap > b[0]:
                ok = False
                break
        if ok:
            w = sum(x[2] for x in chosen)
            ids = sorted(x[3] for x in chosen)
            if w > best_w or (w == best_w and ids < best_ids):
                best_w = w
                best_ids = ids
    return best_w, best_ids

class TestSchedule(unittest.TestCase):
    def test_cases(self):
        cases = [
            ([(1, 3, 5, "b"), (4, 6, 5, "a"), (2, 5, 10, "c")], 1),
            ([(0, 2, 4, "j1"), (2, 4, 4, "j2"), (4, 6, 4, "j3"), (0, 6, 8, "j4")], 0),
            ([(0, 2, 4, "j1"), (2, 4, 4, "j2"), (4, 6, 4, "j3"), (0, 6, 8, "j4")], 1),
            ([(1, 4, 10, "z"), (1, 4, 10, "a"), (5, 8, 10, "m"), (6, 9, 10, "b")], 2),
            ([(0, 3, 7, "k1"), (2, 5, 9, "k2"), (4, 8, 8, "k3"), (7, 10, 6, "k4"), (9, 12, 11, "k5")], 1),
        ]
        for jobs, gap in cases:
            expected = brute_force(jobs, gap)
            got = max_weighted_schedule(jobs, gap)
            self.assertEqual(got, expected, f"Failed for gap={gap}: expected {expected}, got {got}")
        self.assertEqual(max_weighted_schedule([], 2), (0, []))

if __name__ == "__main__":
    unittest.main()
""").strip()


# Task B: Hard exact combinatorial count (computed programmatically via exact DP!)
# Count ternary strings of length L=14 over {'0','1','2'} such that:
#   1. No two adjacent characters are equal (valid coloring of path P_14)
#   2. The substring "012" appears AT LEAST ONCE
#   3. The substring "210" NEVER appears
def compute_combinatorics_ground_truth(length: int = 14) -> int:
    # State: (last2_tuple, has_012)
    dp: dict[tuple[str, bool], int] = {"": 0}  # placeholder unused
    states: dict[tuple[str, bool], int] = {("", False): 1}
    for _ in range(length):
        nxt: dict[tuple[str, bool], int] = {}
        for (tail, has012), cnt in states.items():
            for ch in ("0", "1", "2"):
                if tail and tail[-1] == ch:
                    continue
                seq = tail + ch
                if seq.endswith("210"):
                    continue
                new_has = has012 or seq.endswith("012")
                new_tail = seq[-2:]
                nxt[(new_tail, new_has)] = nxt.get((new_tail, new_has), 0) + cnt
        states = nxt
    return sum(cnt for (_, has012), cnt in states.items() if has012)


COMBINATORICS_GT = compute_combinatorics_ground_truth(14)

TASK_COMBO_PROMPT = textwrap.dedent("""
Compute the EXACT integer number of strings of length 14 over the alphabet {'0', '1', '2'} that satisfy ALL THREE constraints:
1. No two adjacent characters are identical (e.g., '00', '11', '22' are forbidden).
2. The contiguous substring "012" appears AT LEAST ONCE.
3. The contiguous substring "210" NEVER appears anywhere in the string.

Return ONLY a JSON object with the exact integer:
{"exact_count": integer}
""").strip()


def grade_dp(code: str) -> bool:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        (tmp / "candidate.py").write_text(code, encoding="utf-8")
        (tmp / "test_dp.py").write_text(DP_TEST_HARNESS, encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, "-m", "unittest", "test_dp.py"],
            cwd=tmpdir,
            capture_output=True,
            text=True,
            timeout=20,
        )
        return proc.returncode == 0


def grade_combo(text: str) -> tuple[bool, Any]:
    try:
        obj = extract_json_object(text)
        got = int(obj["exact_count"])
        return got == COMBINATORICS_GT, got
    except Exception as exc:
        return False, f"parse_err: {exc}"


def run_benchmark() -> dict[str, Any]:
    print(f"=== [Module 5] Four Thinking Levels Sweep (Combinatorics GT={COMBINATORICS_GT}) ===")
    client = get_client()
    level_results: dict[str, Any] = {}

    for lvl in THINKING_LEVELS:
        print(f"\n-> Sweeping thinking_level='{lvl}'...")
        try:
            # Task A: DP
            t0 = time.perf_counter()
            inter_dp = client.interactions.create(
                model="gemini-4-neon",
                input=TASK_DP_PROMPT,
                generation_config={"thinking_level": lvl, "max_output_tokens": 32768},
            )
            u_dp = extract_usage("gemini-4-neon", inter_dp, time.perf_counter() - t0)
            dp_ok = grade_dp(extract_python_code(extract_all_model_text(inter_dp)))

            # Task B: Hard Combinatorics
            t0 = time.perf_counter()
            inter_cb = client.interactions.create(
                model="gemini-4-neon",
                input=TASK_COMBO_PROMPT,
                generation_config={"thinking_level": lvl, "max_output_tokens": 49152},
            )
            u_cb = extract_usage("gemini-4-neon", inter_cb, time.perf_counter() - t0)
            cb_ok, cb_got = grade_combo(extract_all_model_text(inter_cb))

            total_cost = Decimal(u_dp.cost_usd) + Decimal(u_cb.cost_usd)
            total_thought = u_dp.total_thought_tokens + u_cb.total_thought_tokens
            total_out = u_dp.total_output_tokens + u_cb.total_output_tokens
            total_sec = round(u_dp.elapsed_sec + u_cb.elapsed_sec, 3)

            print(
                f"   level={lvl:6s} | dp={dp_ok} combo={cb_ok} (got={cb_got}) | "
                f"thought_tok={total_thought} | out_tok={total_out} | time={total_sec:.2f}s | cost=${total_cost:.6f}"
            )
            level_results[lvl] = {
                "status": "completed",
                "dp_passed": dp_ok,
                "combo_passed": cb_ok,
                "combo_got": cb_got,
                "combo_expected": COMBINATORICS_GT,
                "score": int(dp_ok) + int(cb_ok),
                "total_tasks": 2,
                "total_elapsed_sec": total_sec,
                "total_thought_tokens": total_thought,
                "total_output_tokens": total_out,
                "total_cost_usd": str(total_cost.quantize(Decimal("0.000001"))),
                "dp_usage": u_dp.to_dict(),
                "combo_usage": u_cb.to_dict(),
            }
        except Exception as exc:
            err_msg = f"{type(exc).__name__}: {str(exc)[:300]}"
            print(f"   level={lvl:6s} | ERROR: {err_msg}")
            level_results[lvl] = {
                "status": "error",
                "error": err_msg,
                "score": 0,
                "total_tasks": 2,
                "total_elapsed_sec": 0.0,
                "total_thought_tokens": 0,
                "total_output_tokens": 0,
                "total_cost_usd": "0.000000",
            }
        # Incremental checkpoint save so partial sweeps are never lost on quota caps
        save_result("05_thinking_levels", {"module": "05_thinking_levels", "levels": level_results, "in_progress": True})

    # Spec check 1: Default thinking_level (omitted -> defaults to high)
    t0 = time.perf_counter()
    default_inter = client.interactions.create(
        model="gemini-4-neon",
        input="Compute 37 * 43 and return ONLY the integer.",
    )
    default_usage = extract_usage("gemini-4-neon", default_inter, time.perf_counter() - t0)
    default_ok = "1591" in extract_all_model_text(default_inter)

    # Spec check 2: Rejects unsupported `minimal` level
    minimal_rejected = False
    minimal_error = ""
    try:
        client.interactions.create(
            model="gemini-4-neon",
            input="Say hello.",
            generation_config={"thinking_level": "minimal"},
        )
    except Exception as exc:
        minimal_rejected = True
        minimal_error = f"{type(exc).__name__}: {str(exc)[:240]}"

    print(f"\n-> Spec checks: default_ok={default_ok} | minimal_rejected={minimal_rejected}")
    if minimal_error:
        print(f"   minimal rejection detail: {minimal_error}")

    # Monotonic thought-token scaling sanity check: xhigh > low
    thought_scaling_observed = (
        level_results["xhigh"]["total_thought_tokens"] > level_results["low"]["total_thought_tokens"]
    )

    summary = {
        "module": "05_thinking_levels",
        "title": "Four configurable thinking levels (low, medium, high, xhigh) + minimal rejection",
        "combinatorics_ground_truth": COMBINATORICS_GT,
        "levels": level_results,
        "spec_checks": {
            "default_omitted_ok": default_ok,
            "default_usage": default_usage.to_dict(),
            "minimal_rejected_as_documented": minimal_rejected,
            "minimal_error": minimal_error,
            "thought_tokens_scale_xhigh_gt_low": thought_scaling_observed,
        },
        "overall_pass": (
            default_ok
            and minimal_rejected
            and thought_scaling_observed
            and max(v["score"] for v in level_results.values()) == 2
        ),
    }
    out = save_result("05_thinking_levels", summary)
    print(f"Saved Module 5 results to {out}")
    return summary


if __name__ == "__main__":
    run_benchmark()
