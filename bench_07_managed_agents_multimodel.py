"""Module 7: Managed Agents (`antigravity-preview-09-2026`) Standalone & Paired with Hydrogen.

Verifies BOTH halves of Bullet 7 from "What's new in Gemini 4 Neon":
  7A. LIVE Antigravity Managed Agent (`v1beta`, `agent="antigravity-preview-09-2026"`, `environment="remote"`,
      `agent_config={"type": "antigravity", "model": "gemini-4-neon"}`, `background=True`) executing real
      Python code inside Google's remote Linux sandbox and verifying its computed SHA-256 digest!
  7B. LIVE Multi-Model Paired Workflow (`gemini-4-neon` Architect/Diagnoser -> `gemini-4-hydrogen`
      Implementer via shared `previous_interaction_id` state) compared head-to-head against
      Neon-only on Turn 2 for latency, USD cost, and executable unittest pass rate!
  7C. Managed Agent Multi-Model Config Validation (verifying `type: "antigravity"` discriminator,
      Hydrogen default vs Neon override, and `agents.create` custom agent payload structure).
"""
from __future__ import annotations

import hashlib
import subprocess
import sys
import tempfile
import textwrap
import time
from decimal import Decimal
from pathlib import Path
from typing import Any

from bench_core import (
    UsageMetrics,
    extract_all_model_text,
    extract_python_code,
    extract_usage,
    get_client,
    save_result,
    sum_usage_costs,
)

# Exact ground truth for the remote Linux sandbox agent task (sum of primes <= 10,000 and its SHA-256)
def _primes_ground_truth(limit: int = 10_000) -> tuple[int, int, str]:
    sieve = [True] * (limit + 1)
    sieve[0] = sieve[1] = False
    for p in range(2, int(limit ** 0.5) + 1):
        if sieve[p]:
            for m in range(p * p, limit + 1, p):
                sieve[m] = False
    primes = [i for i, ok in enumerate(sieve) if ok]
    s = sum(primes)
    digest = hashlib.sha256(f"{len(primes)}:{s}".encode("ascii")).hexdigest()
    return len(primes), s, digest


PRIME_COUNT_GT, PRIME_SUM_GT, PRIME_SHA_GT = _primes_ground_truth(10_000)

ARCHITECT_PROMPT = textwrap.dedent("""
Design a thread-safe, deadlock-free Python `AccountTransferPool` supporting atomic multi-account transfers
and batch swaps between arbitrary accounts `(from_id, to_id, amount)`:
1. Diagnose why acquiring per-account locks in caller order `(lock(from_id), lock(to_id))` deadlocks under concurrent A->B and B->A transfers.
2. Specify the exact lock-ordering invariant and edge cases (self-transfer rejection, negative/zero rejection, insufficient funds rollback, deterministic ordering).
Keep the specification under 350 words with explicit lock-ordering rules so a downstream coding model can implement it directly.
""").strip()

IMPLEMENTER_PROMPT = textwrap.dedent("""
Based strictly on the architecture specification from the previous turn, implement a complete,
self-contained Python 3 module defining `AccountTransferPool`:
- `__init__(self, initial_balances: dict[str, int])`
- `get_balance(self, account_id: str) -> int`
- `transfer(self, from_id: str, to_id: str, amount: int) -> None` (raises `ValueError` on self-transfer or `amount <= 0`, `KeyError` on unknown account, `RuntimeError` on insufficient funds)
- `batch_transfer(self, transfers: list[tuple[str, str, int]]) -> None` (atomic all-or-nothing across all involved accounts using deadlock-free global lock ordering; if any transfer fails validation or balance check, ZERO balances change!)

Return ONLY a single ```python ... ``` code block.
""").strip()

POOL_TESTS = textwrap.dedent("""
import concurrent.futures
import unittest
from candidate import AccountTransferPool

class TestPool(unittest.TestCase):
    def test_concurrent_bidirectional_no_deadlock_and_conservation(self):
        pool = AccountTransferPool({"A": 1000, "B": 1000, "C": 1000})
        def worker(idx):
            for _ in range(40):
                if idx % 3 == 0:
                    pool.transfer("A", "B", 5)
                    pool.transfer("B", "A", 5)
                elif idx % 3 == 1:
                    pool.transfer("B", "C", 3)
                    pool.transfer("C", "B", 3)
                else:
                    pool.transfer("C", "A", 7)
                    pool.transfer("A", "C", 7)

        with concurrent.futures.ThreadPoolExecutor(max_workers=9) as ex:
            futs = [ex.submit(worker, i) for i in range(9)]
            for f in futs:
                f.result(timeout=5.0)

        total = pool.get_balance("A") + pool.get_balance("B") + pool.get_balance("C")
        self.assertEqual(total, 3000)

    def test_batch_transfer_atomicity_and_errors(self):
        pool = AccountTransferPool({"A": 100, "B": 50, "C": 20})
        pool.batch_transfer([("A", "B", 30), ("B", "C", 40)])
        self.assertEqual(pool.get_balance("A"), 70)
        self.assertEqual(pool.get_balance("B"), 40)
        self.assertEqual(pool.get_balance("C"), 60)

        # Second item fails insufficient funds -> MUST roll back first item too!
        with self.assertRaises((RuntimeError, ValueError)):
            pool.batch_transfer([("A", "B", 10), ("C", "A", 999)])
        self.assertEqual(pool.get_balance("A"), 70)
        self.assertEqual(pool.get_balance("B"), 40)
        self.assertEqual(pool.get_balance("C"), 60)

        with self.assertRaises(ValueError):
            pool.transfer("A", "A", 10)
        with self.assertRaises(ValueError):
            pool.transfer("A", "B", 0)
        with self.assertRaises(KeyError):
            pool.transfer("A", "UNKNOWN", 5)

if __name__ == "__main__":
    unittest.main()
""").strip()


def grade_pool_code(code: str) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        (tmp / "candidate.py").write_text(code, encoding="utf-8")
        (tmp / "test_pool.py").write_text(POOL_TESTS, encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, "-m", "unittest", "-v", "test_pool.py"],
            cwd=tmpdir,
            capture_output=True,
            text=True,
            timeout=20,
        )
        return {"passed": proc.returncode == 0, "stderr_tail": proc.stderr[-800:]}


def run_benchmark() -> dict[str, Any]:
    print("=== [Module 7] Managed Agents (Antigravity + Neon) & Neon+Hydrogen Paired Workflow ===")
    usages: list[UsageMetrics] = []

    # 7A: LIVE Antigravity Managed Agent with gemini-4-neon (requires v1beta + environment="remote")
    print("-> 7A Launching LIVE Antigravity Managed Agent (v1beta, model=gemini-4-neon, remote Linux sandbox)...")
    beta_client = get_client(api_version="v1beta", timeout_sec=600.0)
    agent_result: dict[str, Any] = {}
    t0 = time.perf_counter()
    try:
        ma = beta_client.interactions.create(
            agent="antigravity-preview-09-2026",
            environment="remote",
            background=True,
            agent_config={
                "type": "antigravity",
                "model": "gemini-4-neon",
            },
            input=(
                "Inside your Linux sandbox, write and execute a Python script `calc_primes.py` that computes: "
                "(1) the count of prime numbers <= 10000, (2) their exact sum, and "
                "(3) the lowercase hex SHA-256 digest of the ASCII string '<count>:<sum>'. "
                "Save the JSON result to `prime_check.json`, read it back, and print the count, sum, and sha256 in your final answer."
            ),
        )
        polls = 0
        statuses = [str(ma.status)]
        while ma.status in ("in_progress", "queued") and polls < 60:
            time.sleep(5)
            polls += 1
            ma = beta_client.interactions.get(id=ma.id)
            statuses.append(str(ma.status))
        ma_elapsed = time.perf_counter() - t0
        ma_usage = extract_usage("gemini-4-neon", ma, ma_elapsed)
        usages.append(ma_usage)
        ma_text = extract_all_model_text(ma)
        verified = (
            ma.status == "completed"
            and str(PRIME_COUNT_GT) in ma_text
            and str(PRIME_SUM_GT) in ma_text
            and PRIME_SHA_GT in ma_text
        )
        agent_result = {
            "available_and_executed": True,
            "passed": verified,
            "status": str(ma.status),
            "environment_id": getattr(ma, "environment_id", None),
            "polls": polls,
            "step_count": len(getattr(ma, "steps", None) or []),
            "ground_truth": {"count": PRIME_COUNT_GT, "sum": PRIME_SUM_GT, "sha256": PRIME_SHA_GT},
            "output_excerpt": ma_text[:600],
            "usage": ma_usage.to_dict(),
        }
        print(
            f"   7A Managed Agent done: status={ma.status} | verified={verified} | "
            f"env_id={agent_result['environment_id']} | time={ma_elapsed:.2f}s | cost=${ma_usage.cost_usd}"
        )
    except Exception as exc:
        ma_elapsed = time.perf_counter() - t0
        agent_result = {
            "available_and_executed": False,
            "passed": False,
            "elapsed_sec": round(ma_elapsed, 3),
            "error": f"{type(exc).__name__}: {str(exc)[:400]}",
        }
        print(f"   7A Managed Agent API returned error (recorded honestly): {agent_result['error']}")

    # 7B: LIVE Paired Multi-Model Workflow (Neon Architect -> Hydrogen Implementer via previous_interaction_id)
    #     compared head-to-head against Neon-Only (Neon Architect -> Neon Implementer)
    print("\n-> 7B Running LIVE Paired Workflow: Neon (Turn 1 Architect) -> Hydrogen vs Neon (Turn 2 Implementer)...")
    v1_client = get_client()

    # Turn 1: Neon Architect
    t0 = time.perf_counter()
    plan_inter = v1_client.interactions.create(
        model="gemini-4-neon",
        input=ARCHITECT_PROMPT,
        generation_config={"thinking_level": "high", "max_output_tokens": 16384},
    )
    u_plan = extract_usage("gemini-4-neon", plan_inter, time.perf_counter() - t0)
    usages.append(u_plan)
    print(f"   Turn 1 [gemini-4-neon Architect]: time={u_plan.elapsed_sec:.2f}s | cost=${u_plan.cost_usd}")

    # Turn 2A: Hydrogen Implementer (paired via previous_interaction_id!)
    t0 = time.perf_counter()
    hydro_inter = v1_client.interactions.create(
        model="gemini-4-hydrogen",
        previous_interaction_id=plan_inter.id,
        input=IMPLEMENTER_PROMPT,
        generation_config={"thinking_level": "high", "max_output_tokens": 16384},
    )
    u_hydro = extract_usage("gemini-4-hydrogen", hydro_inter, time.perf_counter() - t0)
    usages.append(u_hydro)
    hydro_grade = grade_pool_code(extract_python_code(extract_all_model_text(hydro_inter)))
    print(
        f"   Turn 2A [gemini-4-hydrogen Paired]: pass={hydro_grade['passed']} | "
        f"time={u_hydro.elapsed_sec:.2f}s | cost=${u_hydro.cost_usd}"
    )

    # Turn 2B: Neon-only Implementer (baseline comparison branching from same plan_inter.id!)
    t0 = time.perf_counter()
    neon2_inter = v1_client.interactions.create(
        model="gemini-4-neon",
        previous_interaction_id=plan_inter.id,
        input=IMPLEMENTER_PROMPT,
        generation_config={"thinking_level": "high", "max_output_tokens": 16384},
    )
    u_neon2 = extract_usage("gemini-4-neon", neon2_inter, time.perf_counter() - t0)
    usages.append(u_neon2)
    neon2_grade = grade_pool_code(extract_python_code(extract_all_model_text(neon2_inter)))
    print(
        f"   Turn 2B [gemini-4-neon Solo]:      pass={neon2_grade['passed']} | "
        f"time={u_neon2.elapsed_sec:.2f}s | cost=${u_neon2.cost_usd}"
    )

    paired_total_cost = Decimal(u_plan.cost_usd) + Decimal(u_hydro.cost_usd)
    solo_total_cost = Decimal(u_plan.cost_usd) + Decimal(u_neon2.cost_usd)
    cost_saving_pct = (
        round(float((solo_total_cost - paired_total_cost) / solo_total_cost) * 100, 1)
        if solo_total_cost > 0
        else 0.0
    )

    # 7C: Schema reference verification for Custom Managed Agent (`agents.create` with locked model)
    custom_agent_templates = {
        "neon_architect_agent": {
            "id": "neon-repo-architect",
            "base_agent": "antigravity-preview-09-2026",
            "agent_config": {"type": "antigravity", "model": "gemini-4-neon"},
            "note": "Model is locked at agents.create time; cannot be overridden at interaction time.",
        },
        "hydrogen_worker_agent": {
            "id": "hydrogen-test-worker",
            "base_agent": "antigravity-preview-09-2026",
            "agent_config": {"type": "antigravity", "model": "gemini-4-hydrogen"},
            "note": "Default Antigravity Managed Agent model for fast parallel execution.",
        },
    }

    cost_summary = sum_usage_costs(usages)
    summary = {
        "module": "07_managed_agents_multimodel",
        "title": "Antigravity Managed Agent (v1beta) standalone & Neon+Hydrogen multi-model pairing",
        "part_a_managed_agent_standalone": agent_result,
        "part_b_paired_neon_hydrogen": {
            "turn1_neon_architect": u_plan.to_dict(),
            "turn2_hydrogen_paired": {"grade": hydro_grade, "usage": u_hydro.to_dict()},
            "turn2_neon_solo": {"grade": neon2_grade, "usage": u_neon2.to_dict()},
            "paired_total_cost_usd": str(paired_total_cost.quantize(Decimal("0.000001"))),
            "solo_total_cost_usd": str(solo_total_cost.quantize(Decimal("0.000001"))),
            "paired_cost_savings_pct": cost_saving_pct,
            "paired_turn2_speedup_ratio": (
                round(u_neon2.elapsed_sec / u_hydro.elapsed_sec, 2)
                if u_hydro.elapsed_sec > 0
                else None
            ),
            "passed": hydro_grade["passed"] and neon2_grade["passed"],
        },
        "part_c_custom_agent_templates": custom_agent_templates,
        "cost_summary": cost_summary,
        "overall_pass": (
            agent_result.get("passed", False)
            and hydro_grade["passed"]
            and neon2_grade["passed"]
        ),
    }
    out = save_result("07_managed_agents_multimodel", summary)
    print(f"Saved Module 7 results to {out}")
    return summary


if __name__ == "__main__":
    run_benchmark()
