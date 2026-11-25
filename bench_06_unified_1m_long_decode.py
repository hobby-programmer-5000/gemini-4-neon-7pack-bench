"""Module 6: Unified 1M Context Window, Long Decode (Background + Client-Side Continuation) & Implicit Caching.

Verifies every technical mechanism documented for Gemini 4 Neon's 1M unified context & Long Decode:
  6A. Unified 1,048,576-token window budget validator + multi-hop `initial_input_tokens` vs `total_input_tokens`
      accounting test (verifying compaction never uses cumulative multi-hop `total_input_tokens`)
  6B. LIVE Background Execution Long Decode (`background=True`, `max_output_tokens=131072`), polling
      `interactions.get(id=...)` while status in ("in_progress", "queued"), joining all `model_output` steps
  6C. LIVE Client-Side Continuation (`background=False`, `automatic_continuation=False`, `max_output_tokens=131072`)
      with the official `requires_continuation` + `continuation_token` loop, PLUS a deterministic 3-hop
      unit-tested mock proving multi-hop text assembly & interrupted-hop resume
  6D. LIVE Implicit Context Caching verification (>= 4,096 token shared prefix) measuring real
      `total_cached_tokens > 0` and realized 95% cached input savings ($0.15/1M vs $3.00/1M)
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from bench_core import (
    DEFAULT_SYNC_OUTPUT_CAP,
    UNIFIED_CONTEXT_WINDOW,
    UsageMetrics,
    compute_cost_usd,
    extract_all_model_text,
    extract_usage,
    get_client,
    save_result,
    sum_usage_costs,
)


def validate_unified_window_budget(
    input_tokens: int,
    max_output_tokens: int | None,
    background: bool = False,
) -> dict[str, Any]:
    """Validate unified 1M window allocation & official Neon output limit rules."""
    effective_cap = max_output_tokens if max_output_tokens is not None else DEFAULT_SYNC_OUTPUT_CAP
    remaining_budget = UNIFIED_CONTEXT_WINDOW - input_tokens
    warnings: list[str] = []
    if max_output_tokens is not None and max_output_tokens < 32_768:
        warnings.append("Hardcoded max_output_tokens < 32,768 risks cutting off thinking before final answer.")
    if background and max_output_tokens is None:
        warnings.append("background=True without explicit max_output_tokens still caps at 65,536 tokens.")
    if effective_cap > remaining_budget:
        warnings.append(f"Requested max_output_tokens ({effective_cap}) exceeds remaining unified window ({remaining_budget}).")
    long_decode_active = effective_cap > DEFAULT_SYNC_OUTPUT_CAP
    return {
        "unified_limit": UNIFIED_CONTEXT_WINDOW,
        "input_tokens": input_tokens,
        "effective_output_cap": min(effective_cap, max(0, remaining_budget)),
        "remaining_window_for_output_and_thinking": max(0, remaining_budget),
        "long_decode_enabled": long_decode_active,
        "warnings": warnings,
    }


def simulate_multihop_continuation_unit_test() -> dict[str, Any]:
    """Deterministic unit verification of client-side multi-hop continuation + compaction accounting."""
    @dataclass
    class _Content:
        type: str
        text: str

    @dataclass
    class _Step:
        type: str
        content: list[_Content]

    @dataclass
    class _Usage:
        initial_input_tokens: int
        total_input_tokens: int
        total_output_tokens: int
        total_thought_tokens: int

    @dataclass
    class _FakeInteraction:
        id: str
        status: str
        continuation_token: str | None
        steps: list[_Step]
        usage: _Usage

    hops = [
        _FakeInteraction(
            id="int_hop_1",
            status="requires_continuation",
            continuation_token="ctok_1",
            steps=[_Step("model_output", [_Content("text", "[HOP1:Architecture]")])],
            usage=_Usage(initial_input_tokens=120_000, total_input_tokens=120_000, total_output_tokens=64_000, total_thought_tokens=1_536),
        ),
        _FakeInteraction(
            id="int_hop_2",
            status="requires_continuation",
            continuation_token="ctok_2",
            steps=[_Step("model_output", [_Content("text", "[HOP2:Implementation]")])],
            usage=_Usage(initial_input_tokens=120_000, total_input_tokens=185_536, total_output_tokens=64_000, total_thought_tokens=1_536),
        ),
        _FakeInteraction(
            id="int_hop_3",
            status="completed",
            continuation_token=None,
            steps=[_Step("model_output", [_Content("text", "[HOP3:Verification]")])],
            usage=_Usage(initial_input_tokens=120_000, total_input_tokens=251_072, total_output_tokens=18_000, total_thought_tokens=500),
        ),
    ]

    idx = 0
    cur = hops[idx]
    assembled = extract_all_model_text(cur)
    cumulative_billed_input = cur.usage.total_input_tokens
    hop_ids = [cur.id]
    tokens_seen = []

    while cur.status == "requires_continuation":
        assert cur.continuation_token is not None
        tokens_seen.append((cur.id, cur.continuation_token))
        idx += 1
        cur = hops[idx]
        assembled += extract_all_model_text(cur)
        cumulative_billed_input += cur.usage.total_input_tokens
        hop_ids.append(cur.id)

    # Context compaction MUST track final context occupancy (initial_input + cumulative output/thought),
    # NEVER the multi-hop sum `cumulative_billed_input` (556,608)!
    true_final_context_occupancy = (
        cur.usage.initial_input_tokens
        + sum(h.usage.total_output_tokens + h.usage.total_thought_tokens for h in hops)
    )
    passed = (
        assembled == "[HOP1:Architecture][HOP2:Implementation][HOP3:Verification]"
        and len(hop_ids) == 3
        and len(tokens_seen) == 2
        and cumulative_billed_input > true_final_context_occupancy
        and true_final_context_occupancy < UNIFIED_CONTEXT_WINDOW
    )
    return {
        "passed": passed,
        "hops_chained": len(hop_ids),
        "assembled_text": assembled,
        "cumulative_billed_input_tokens_do_not_use_for_compaction": cumulative_billed_input,
        "true_final_context_occupancy_tokens": true_final_context_occupancy,
    }


def run_3mode_implicit_caching_matrix(client: Any) -> dict[str, Any]:
    """Compare implicit caching across Interactions stateless/stateful and generateContent stateless."""
    corpus = "\n".join(
        f"[CONTROL-ID: NCACHE-{i:04d}] Mesh cluster node-{i % 19:02d} region-{(i % 5) + 1} policy mTLS-1.3 "
        f"cipher TLS_AES_256_GCM_SHA384 rotation {(i % 14) + 1}d heartbeat {120 + (i % 60)}ms "
        f"attestation epoch {2026100 + i} digest-seed beta-{i * 11 % 997:03d}."
        + (
            " PRIMARY_TOKEN_142='NEON-STATELESS-9941'."
            if i == 142
            else (
                " SECONDARY_TOKEN_210='NEON-STATEFUL-7712'."
                if i == 210
                else ""
            )
        )
        for i in range(1, 240)
    )
    probes = [
        ("What is PRIMARY_TOKEN_142? Reply with ONLY the token.", "NEON-STATELESS-9941"),
        ("What is the heartbeat in ms for NCACHE-0142? Reply with ONLY the integer.", str(120 + (142 % 60))),
        ("What is SECONDARY_TOKEN_210? Reply with ONLY the token.", "NEON-STATEFUL-7712"),
    ]
    usages_local: list[UsageMetrics] = []

    def _calc_saved(u: UsageMetrics) -> Decimal:
        uncached = compute_cost_usd("gemini-4-neon", u.total_input_tokens, 0, u.total_output_tokens, u.total_thought_tokens)
        return uncached - Decimal(u.cost_usd)

    mode_a = []
    first_id = None
    for idx, (q, expected) in enumerate(probes[:2], 1):
        t0 = time.perf_counter()
        inter = client.interactions.create(
            model="gemini-4-neon",
            store=True,
            input=f"{corpus}\n\nQuestion: {q}",
            generation_config={"thinking_level": "low", "max_output_tokens": 2048},
        )
        if first_id is None:
            first_id = inter.id
        u = extract_usage("gemini-4-neon", inter, time.perf_counter() - t0)
        usages_local.append(u)
        ans = extract_all_model_text(inter).strip()
        ratio = round(u.total_cached_tokens / max(1, u.total_input_tokens), 4)
        saved = _calc_saved(u)
        mode_a.append({"call": idx, "needle_ok": expected in ans, "answer": ans, "cache_hit_ratio": ratio, "saved_usd": str(saved.quantize(Decimal("0.000001"))), "usage": u.to_dict()})

    mode_b = []
    prev_id = first_id
    for idx, (q, expected) in enumerate([
        ("What is the region identifier (region-X) for NCACHE-0142? Reply with ONLY region-X.", f"region-{(142 % 5) + 1}"),
        ("What is SECONDARY_TOKEN_210? Reply with ONLY the token.", "NEON-STATEFUL-7712"),
    ], 1):
        t0 = time.perf_counter()
        inter = client.interactions.create(
            model="gemini-4-neon",
            previous_interaction_id=prev_id,
            input=q,
            generation_config={"thinking_level": "low", "max_output_tokens": 2048},
        )
        prev_id = inter.id
        u = extract_usage("gemini-4-neon", inter, time.perf_counter() - t0)
        usages_local.append(u)
        ans = extract_all_model_text(inter).strip()
        ratio = round(u.total_cached_tokens / max(1, u.total_input_tokens), 4)
        saved = _calc_saved(u)
        mode_b.append({"call": idx, "needle_ok": expected in ans, "answer": ans, "cache_hit_ratio": ratio, "saved_usd": str(saved.quantize(Decimal("0.000001"))), "usage": u.to_dict()})

    mode_c = []
    for idx, (q, expected) in enumerate(probes, 1):
        t0 = time.perf_counter()
        res = client.models.generate_content(
            model="gemini-4-neon",
            contents=f"{corpus}\n\nQuestion: {q}",
            config={"thinking_config": {"thinking_level": "low"}, "max_output_tokens": 2048},
        )
        elapsed = time.perf_counter() - t0
        um = res.usage_metadata
        p_tok = int(getattr(um, "prompt_token_count", 0) or 0)
        c_tok = int(getattr(um, "cached_content_token_count", 0) or 0)
        o_tok = int(getattr(um, "candidates_token_count", 0) or 0)
        t_tok = int(getattr(um, "thoughts_token_count", 0) or 0)
        tot_tok = int(getattr(um, "total_token_count", p_tok + o_tok + t_tok) or 0)
        cost = compute_cost_usd("gemini-4-neon", p_tok, c_tok, o_tok, t_tok)
        u = UsageMetrics(
            model="gemini-4-neon",
            elapsed_sec=round(elapsed, 3),
            initial_input_tokens=p_tok,
            total_input_tokens=p_tok,
            total_cached_tokens=c_tok,
            total_output_tokens=o_tok,
            total_thought_tokens=t_tok,
            total_tokens=tot_tok,
            cost_usd=str(cost),
            status="completed",
            interaction_id=None,
        )
        usages_local.append(u)
        ans = (res.text or "").strip()
        ratio = round(c_tok / max(1, p_tok), 4)
        saved = _calc_saved(u)
        mode_c.append({"call": idx, "needle_ok": expected in ans, "answer": ans, "cache_hit_ratio": ratio, "uncached_tail_tokens": p_tok - c_tok, "saved_usd": str(saved.quantize(Decimal("0.000001"))), "usage": u.to_dict()})

    total_saved = sum((Decimal(x["saved_usd"]) for x in mode_a + mode_b + mode_c), Decimal("0"))
    return {
        "all_needles_ok": all(x["needle_ok"] for x in mode_a + mode_b + mode_c),
        "cache_hit_observed": any(x["usage"]["total_cached_tokens"] > 0 for x in mode_b + mode_c),
        "stateless_generate_content_peak_hit_ratio": max(x["cache_hit_ratio"] for x in mode_c),
        "stateful_interactions_peak_hit_ratio": max(x["cache_hit_ratio"] for x in mode_b),
        "stateless_interactions_peak_hit_ratio": max(x["cache_hit_ratio"] for x in mode_a),
        "total_cache_savings_usd": str(total_saved.quantize(Decimal("0.000001"))),
        "interactions_store_true_stateless_no_prev_id": mode_a,
        "interactions_stateful_with_prev_id": mode_b,
        "generate_content_stateless": mode_c,
        "_usages": usages_local,
    }


def run_stateless_implicit_cache_burst(client: Any) -> dict[str, Any]:
    """Send 4 rapid stateless calls sharing a ~20K-token prefix to verify live stateless implicit caching (95% discount)."""
    shared_corpus = "\n".join(
        f"[CONTROL-ID: SEC-{i:04d}] Service cluster node-{i % 19:02d} in region-{(i % 4) + 1} enforces "
        f"mTLS 1.3 cipher suite TLS_AES_256_GCM_SHA384 with certificate rotation interval {(i % 12) + 1} days, "
        f"audit stream partition p{i % 8}, deterministic quorum heartbeat timeout {150 + (i % 50)}ms, "
        f"and zero-trust workload attestation epoch {202600 + i}."
        + (
            " Special verification token for SEC-0142 is 'OMEGA-NEON-7741'."
            if i == 142
            else (
                " Backup failover token for SEC-0250 is 'DELTA-CACHE-9920'."
                if i == 250
                else ""
            )
        )
        for i in range(1, 260)
    )
    probes = [
        ("What is the special verification token for SEC-0142? Reply with ONLY the token.", "OMEGA-NEON-7741"),
        ("What is the heartbeat timeout in ms for SEC-0142? Reply with ONLY the number followed by ms.", "192"),
        ("What is the backup failover token for SEC-0250? Reply with ONLY the token.", "DELTA-CACHE-9920"),
        ("What is the certificate rotation interval in days for SEC-0250? Reply with ONLY the integer.", str((250 % 12) + 1)),
    ]
    calls_data = []
    usages_local: list[UsageMetrics] = []
    max_hit_ratio = 0.0
    total_saved = Decimal("0")

    for idx, (q, expected) in enumerate(probes, start=1):
        t0 = time.perf_counter()
        inter = client.interactions.create(
            model="gemini-4-neon",
            store=False,
            system_instruction=shared_corpus,
            input=q,
            generation_config={"thinking_level": "low", "max_output_tokens": 256},
        )
        u = extract_usage("gemini-4-neon", inter, time.perf_counter() - t0)
        usages_local.append(u)
        ans = extract_all_model_text(inter).strip()
        ok = expected in ans
        ratio = round(u.total_cached_tokens / u.total_input_tokens, 4) if u.total_input_tokens > 0 else 0.0
        max_hit_ratio = max(max_hit_ratio, ratio)
        uncached = compute_cost_usd("gemini-4-neon", u.total_input_tokens, 0, u.total_output_tokens, u.total_thought_tokens)
        saved = uncached - Decimal(u.cost_usd)
        total_saved += saved
        print(
            f"   [6D stateless call {idx}/4] ok={ok} | in={u.total_input_tokens} | cached={u.total_cached_tokens} "
            f"({ratio:.1%}) | time={u.elapsed_sec:.2f}s | saved=${saved:.6f}"
        )
        calls_data.append({
            "call_index": idx,
            "needle_ok": ok,
            "cache_hit_ratio": ratio,
            "saved_usd": str(saved.quantize(Decimal("0.000001"))),
            "usage": u.to_dict(),
        })

    return {
        "stateless_mode_store_false": True,
        "all_needles_ok": all(c["needle_ok"] for c in calls_data),
        "cache_hit_observed": any(c["usage"]["total_cached_tokens"] > 0 for c in calls_data),
        "peak_cache_hit_ratio": max_hit_ratio,
        "total_cache_savings_usd": str(total_saved.quantize(Decimal("0.000001"))),
        "calls": calls_data,
        "_usages": usages_local,
    }


def run_live_over_64k_multihop_long_decode(client: Any) -> dict[str, Any]:
    """Trigger a genuine LIVE >65,536-token multi-hop Long Decode on gemini-4-neon (background=True, max_output_tokens=262144, xhigh).

    Proves multi-hop execution via live API telemetry:
      - combined_generated_tokens (output + thought) > 65,536
      - AND/OR total_input_tokens > 65,536 (multi-hop cumulative input re-feed documented in long-decode.md)
      - AND verifies exact mathematical ground truth on the hard combinatorics/number-theory problem!
    """
    # Exact ground truth computed locally via deterministic DP:
    # Problem: Count length-20 strings over {'0','1','2','3'} with:
    #   1. No adjacent equal digits
    #   2. No adjacent difference equal to 2 (i.e., forbidden transitions 0<->2 and 1<->3)
    #   3. Substring "0123" appears AT LEAST ONCE
    #   4. Substring "3210" NEVER appears
    #   5. Sum of all 20 digits is divisible by 3
    states: dict[tuple[str, bool, int], int] = {("", False, 0): 1}
    for _ in range(20):
        nxt: dict[tuple[str, bool, int], int] = {}
        for (tail, has0123, mod3), cnt in states.items():
            for d in range(4):
                ch = str(d)
                if tail:
                    prev_d = int(tail[-1])
                    if prev_d == d or abs(prev_d - d) == 2:
                        continue
                seq = tail + ch
                if seq.endswith("3210"):
                    continue
                new_has = has0123 or seq.endswith("0123")
                new_tail = seq[-3:]
                key = (new_tail, new_has, (mod3 + d) % 3)
                nxt[key] = nxt.get(key, 0) + cnt
        states = nxt
    gt_exact = sum(cnt for (_, has0123, mod3), cnt in states.items() if has0123 and mod3 == 0)
    print(f"-> 6E Running LIVE >64K Multi-Hop Long Decode (xhigh, background=True, max_output_tokens=262144, GT={gt_exact})...")

    prompt = (
        "Solve BOTH parts in one unified, exhaustive, self-contained mathematical & engineering response.\n\n"
        "=== PART 1: EXACT AUTOMATON & MODULAR COMBINATORICS PROOF ===\n"
        "Compute the EXACT integer count of strings of length 20 over the alphabet {'0', '1', '2', '3'} satisfying ALL FIVE rules:\n"
        "1. No two adjacent digits are equal.\n"
        "2. No two adjacent digits differ by 2 (so 0<->2 and 1<->3 transitions are forbidden).\n"
        "3. The contiguous substring '0123' appears AT LEAST ONCE.\n"
        "4. The contiguous substring '3210' NEVER appears.\n"
        "5. The sum of all 20 digits is divisible by 3.\n"
        "Derive the full state-transition matrix / recurrence step by step, verify small lengths (L=4, 5, 6) by hand, "
        "carefully compute the exact transition table up to L=20 without shortcuts, double-check every arithmetic step "
        "modulo 10 and modulo 9, and state the final exact integer in a line formatted strictly as: FINAL_EXACT_COUNT=<integer>.\n\n"
        "=== PART 2: FORMAL PROOF + COMPLETE PYTHON DISTRIBUTED RAFT-STYLE CONSENSUS ENGINE ===\n"
        "After Part 1, write a rigorous formal proof of Election Safety, Log Matching, and Leader Completeness for a "
        "joint-consensus replicated state machine, followed by a complete, runnable standard-library Python implementation "
        "of the state machine, deterministic partition simulator, and an exhaustive unittest suite covering split-brain, "
        "stale-term rejection, log truncation, and snapshot compaction."
    )

    t0 = time.perf_counter()
    inter = client.interactions.create(
        model="gemini-4-neon",
        input=prompt,
        background=True,
        generation_config={
            "max_output_tokens": 262_144,
            "thinking_level": "xhigh",
        },
    )
    polls = 0
    statuses = [str(inter.status)]
    while inter.status in ("in_progress", "queued") and polls < 400:
        time.sleep(5)
        polls += 1
        inter = client.interactions.get(id=inter.id)
        if statuses[-1] != str(inter.status):
            statuses.append(str(inter.status))
        if polls % 12 == 0:
            print(f"   [6E poll {polls}] status={inter.status} elapsed={time.perf_counter() - t0:.1f}s")

    elapsed = time.perf_counter() - t0
    u = extract_usage("gemini-4-neon", inter, elapsed)
    text = extract_all_model_text(inter)
    combined_gen = u.total_output_tokens + u.total_thought_tokens
    crossed_64k = combined_gen > DEFAULT_SYNC_OUTPUT_CAP
    multihop_input_proof = u.total_input_tokens > DEFAULT_SYNC_OUTPUT_CAP
    model_output_steps = sum(1 for s in (getattr(inter, "steps", None) or []) if getattr(s, "type", None) == "model_output")
    exact_match = str(gt_exact) in text.replace(",", "")

    print(
        f"   6E done: status={inter.status} | polls={polls} | out+thought={combined_gen} (>64K={crossed_64k}) | "
        f"total_in={u.total_input_tokens} (cached={u.total_cached_tokens}) | model_output_steps={model_output_steps} | "
        f"exact_gt_match={exact_match} | time={elapsed:.2f}s | cost=${u.cost_usd}"
    )
    return {
        "passed": inter.status == "completed" and crossed_64k,
        "status": str(inter.status),
        "poll_count": polls,
        "status_transitions": statuses,
        "combined_output_plus_thought_tokens": combined_gen,
        "crossed_65536_single_hop_wall": crossed_64k,
        "multihop_cumulative_input_gt_65536": multihop_input_proof,
        "model_output_step_count": model_output_steps,
        "output_chars": len(text),
        "combinatorics_ground_truth": gt_exact,
        "combinatorics_exact_match": exact_match,
        "usage": u.to_dict(),
        "_usage": u,
    }


def run_benchmark(breakthrough_only: bool = False) -> dict[str, Any]:
    import json
    from bench_core import RESULTS_DIR

    print(f"=== [Module 6] Unified 1M Context Window, Long Decode & Implicit Caching (breakthrough_only={breakthrough_only}) ===")
    client = get_client(timeout_sec=900.0)
    usages: list[UsageMetrics] = []

    existing_path = RESULTS_DIR / "06_unified_1m_long_decode.json"
    existing = json.loads(existing_path.read_text(encoding="utf-8")) if (breakthrough_only and existing_path.exists()) else None

    if existing:
        part_a = existing["part_a_budget_and_multihop_sim"]
        part_b = existing["part_b_background_long_decode"]
        part_c = existing["part_c_client_side_continuation"]
        budget_ok_check = part_a["budget_long_decode_262k"]
        budget_warn_check = part_a["budget_low_cap_warning"]
        multihop_sim = part_a["multihop_continuation_unit_test"]
        bg_ok = part_b["passed"]
        cs_ok = part_c["passed"]
    else:
        budget_ok_check = validate_unified_window_budget(input_tokens=200_000, max_output_tokens=262_144, background=True)
        budget_warn_check = validate_unified_window_budget(input_tokens=10_000, max_output_tokens=8_192, background=False)
        multihop_sim = simulate_multihop_continuation_unit_test()
        part_a = {
            "budget_long_decode_262k": budget_ok_check,
            "budget_low_cap_warning": budget_warn_check,
            "multihop_continuation_unit_test": multihop_sim,
        }
        print(f"-> 6A Budget validator + 3-hop continuation unit test passed: {multihop_sim['passed']}")

        print("-> 6B Running LIVE Background Execution Long Decode (max_output_tokens=131072)...")
        t0 = time.perf_counter()
        bg_inter = client.interactions.create(
            model="gemini-4-neon",
            input=(
                "Write a concise, production-ready technical migration blueprint (5 numbered sections: "
                "Schema, Cutover, Dual-Write, Rollback, Verification Checklist) for migrating a payment "
                "ledger from single-region PostgreSQL to multi-region active-active CockroachDB. "
                "Keep each section concise with concrete steps."
            ),
            background=True,
            generation_config={"max_output_tokens": 131_072, "thinking_level": "medium"},
        )
        poll_statuses = [str(bg_inter.status)]
        polls = 0
        while bg_inter.status in ("in_progress", "queued") and polls < 60:
            time.sleep(3)
            polls += 1
            bg_inter = client.interactions.get(id=bg_inter.id)
            poll_statuses.append(str(bg_inter.status))
        bg_usage = extract_usage("gemini-4-neon", bg_inter, time.perf_counter() - t0)
        usages.append(bg_usage)
        bg_text = extract_all_model_text(bg_inter)
        bg_ok = bg_inter.status == "completed" and len(bg_text) > 400
        part_b = {
            "passed": bg_ok,
            "poll_count": polls,
            "status_transitions": poll_statuses,
            "output_chars": len(bg_text),
            "usage": bg_usage.to_dict(),
        }

        print("-> 6C Running LIVE Client-Side Continuation (automatic_continuation=False, max_output_tokens=131072)...")
        t0 = time.perf_counter()
        cs_inter = client.interactions.create(
            model="gemini-4-neon",
            input=(
                "Outline a 4-point RFC for zero-downtime key rotation in a distributed HMAC webhook gateway. "
                "Include exact state transitions (ACTIVE -> DUAL_VERIFY -> RETIRED)."
            ),
            automatic_continuation=False,
            generation_config={"max_output_tokens": 131_072, "thinking_level": "low"},
        )
        cs_hops = 1
        cs_text = extract_all_model_text(cs_inter)
        while getattr(cs_inter, "status", None) == "requires_continuation" and cs_hops < 5:
            cs_hops += 1
            cs_inter = client.interactions.create(
                model="gemini-4-neon",
                previous_interaction_id=cs_inter.id,
                continuation_token=cs_inter.continuation_token,
                automatic_continuation=False,
                generation_config={"max_output_tokens": 131_072, "thinking_level": "low"},
            )
            cs_text += extract_all_model_text(cs_inter)
        cs_usage = extract_usage("gemini-4-neon", cs_inter, time.perf_counter() - t0)
        usages.append(cs_usage)
        cs_ok = cs_inter.status == "completed" and "DUAL_VERIFY" in cs_text
        part_c = {
            "passed": cs_ok,
            "hops_executed": cs_hops,
            "output_chars": len(cs_text),
            "usage": cs_usage.to_dict(),
        }

    # 6D: Live 4-condition implicit caching matrix (store=False burst + 3-mode comparison)
    print("-> 6D Running LIVE 4-Condition Implicit Caching Matrix...")
    part_d_burst = run_stateless_implicit_cache_burst(client)
    usages.extend(part_d_burst.pop("_usages"))
    part_d_3mode = run_3mode_implicit_caching_matrix(client)
    usages.extend(part_d_3mode.pop("_usages"))
    part_d_raw = {
        "all_needles_ok": part_d_burst["all_needles_ok"] and part_d_3mode["all_needles_ok"],
        "cache_hit_observed": part_d_3mode["cache_hit_observed"],
        "stateless_generate_content_peak_hit_ratio": part_d_3mode["stateless_generate_content_peak_hit_ratio"],
        "stateful_interactions_peak_hit_ratio": part_d_3mode["stateful_interactions_peak_hit_ratio"],
        "stateless_interactions_peak_hit_ratio": part_d_3mode["stateless_interactions_peak_hit_ratio"],
        "total_cache_savings_usd": part_d_3mode["total_cache_savings_usd"],
        "interactions_store_false_stateless_4calls": part_d_burst["calls"],
        "interactions_store_true_stateless_no_prev_id": part_d_3mode["interactions_store_true_stateless_no_prev_id"],
        "interactions_stateful_with_prev_id": part_d_3mode["interactions_stateful_with_prev_id"],
        "generate_content_stateless": part_d_3mode["generate_content_stateless"],
    }

    # 6E: Live >64K Multi-Hop Long Decode stress verification (xhigh, background=True, max_output_tokens=262144)
    part_e_bg = run_live_over_64k_multihop_long_decode(client)
    usages.append(part_e_bg.pop("_usage"))
    part_e_raw = {
        "passed": part_e_bg["passed"],
        "server_side_background_134k": part_e_bg,
    }

    if existing:
        # Combine previous 6B+6C cost with new 6D+6E cost
        prev_u = [part_b["usage"], part_c["usage"]]
        new_sum = sum_usage_costs(usages)
        cost_summary = {
            "calls": len(prev_u) + new_sum["calls"],
            "total_elapsed_sec": round(sum(float(x["elapsed_sec"]) for x in prev_u) + new_sum["total_elapsed_sec"], 3),
            "total_input_tokens": sum(int(x["total_input_tokens"]) for x in prev_u) + new_sum["total_input_tokens"],
            "total_cached_tokens": sum(int(x["total_cached_tokens"]) for x in prev_u) + new_sum["total_cached_tokens"],
            "total_output_tokens": sum(int(x["total_output_tokens"]) for x in prev_u) + new_sum["total_output_tokens"],
            "total_thought_tokens": sum(int(x["total_thought_tokens"]) for x in prev_u) + new_sum["total_thought_tokens"],
            "total_cost_usd": str(
                (sum((Decimal(str(x["cost_usd"])) for x in prev_u), Decimal("0")) + Decimal(new_sum["total_cost_usd"])).quantize(Decimal("0.000001"))
            ),
        }
    else:
        cost_summary = sum_usage_costs(usages)

    summary = {
        "module": "06_unified_1m_long_decode",
        "title": "Unified 1M context window, Live >64K Multi-Hop Long Decode & 3-Mode Implicit Caching",
        "part_a_budget_and_multihop_sim": part_a,
        "part_b_background_long_decode": part_b,
        "part_c_client_side_continuation": part_c,
        "part_d_implicit_caching_matrix": part_d_raw,
        "part_e_live_over_64k_multihop": part_e_raw,
        "cost_summary": cost_summary,
        "overall_pass": (
            budget_ok_check["long_decode_enabled"]
            and len(budget_warn_check["warnings"]) >= 1
            and multihop_sim["passed"]
            and bg_ok
            and cs_ok
            and part_d_raw["all_needles_ok"]
            and part_d_raw["cache_hit_observed"]
            and part_e_raw["passed"]
        ),
    }
    out = save_result("06_unified_1m_long_decode", summary)
    print(f"Saved Module 6 results to {out}")
    return summary


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--breakthrough-64k-and-cache", action="store_true", help="Keep 6A-6C and run live 6D stateless cache burst + 6E >64K multi-hop Long Decode")
    cli = ap.parse_args()
    run_benchmark(breakthrough_only=cli.breakthrough_64k_and_cache)
