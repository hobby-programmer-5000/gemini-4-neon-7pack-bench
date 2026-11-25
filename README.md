# Gemini 4 Neon 7-Pack Live Benchmark

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](./LICENSE)
[![Live Dashboard](https://img.shields.io/badge/Live%20Dashboard-GitHub%20Pages-4fb3a2.svg)](https://hobby-programmer-5000.github.io/gemini-4-neon-7pack-bench/)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776ab.svg)](./bench_core.py)
[![google-genai](https://img.shields.io/badge/google--genai-3.3.0-4285f4.svg)](./bench_core.py)

라이브 벤치마크 대시보드: https://hobby-programmer-5000.github.io/gemini-4-neon-7pack-bench/

2026년 11월 18일 정식 출시된 `gemini-4-neon`의 Google AI Studio 공식 가이드 문서([What's new in Gemini 4 Neon](https://aistudio.google.com/docs/whats-new-gemini-4-neon))에 소개된 7개 항목을 하나씩 실제 코드와 라이브 API 호출로 검증한 벤치마크 스위트입니다.

Google GenAI Interactions API(`google-genai 3.3.0`), `v1beta` Antigravity Managed Agent, 로컬 `unittest` 및 AST 정적 감사로 모든 결과를 측정했습니다. 전체 라이브 실측 비용은 \$4.374928(`Decimal` 정밀 정산)이며, 추측이나 목업 수치는 제외했습니다.

## 1. 7개 항목 실측 성적표

| # | 공식 문서 항목 | 모듈 | 판정 | 핵심 실측 수치 | 실측 비용 (USD) |
|---|---|---|---|---|---|
| 01 | Frontier 지능 + 빠른 E2E + 토큰 절감 (\$3/\$15) | [`bench_01_frontier_speed_cost.py`](./bench_01_frontier_speed_cost.py), [`bench_01b_apples_to_apples.py`](./bench_01b_apples_to_apples.py) | 검증 완료 (`01B` 4/4 PASS) | 동일 `high` 기준 Carbon 대비 6.51배 빠름(53.09s vs 345.89s), 출력+사고 토큰 74.6% 절감(6,234 vs 24,540), 비용 61.5% 절감(12월 1일 정가 기준 80.7% 절감) | \$0.579403 (`01`) + \$0.449013 (`01B`) |
| 02 | 복잡 SWE, 멀티파일 리팩토링, 컴팩션, 비환각 | [`bench_02_agentic_repo_refactor.py`](./bench_02_agentic_repo_refactor.py) | PASS | 6개 파일 4대 크로스파일 버그를 5턴 만에 병렬 읽기(Phase 1 중복 읽기 0회) -> 병렬 수정 -> `unittest` 5/5 첫 시도 통과, 컴팩션 기억 유지 및 미구현 상수 비환각 통과(암묵적 캐시 39.9%) | \$0.210704 |
| 03 | 지식노동, 과학, 멀티모달 교차 종합 | [`bench_03_knowledge_science_1m.py`](./bench_03_knowledge_science_1m.py) | PASS (10/10) | 14,001 입력 토큰(법률 MSA+Addendum, 재무 CSV, PNG 차트, Arrhenius CSV)에서 10/10 항목 정확 추출(59.93s) | \$0.155133 |
| 04 | 사이버보안 루트-코즈 패치 및 권한 경계 | [`bench_04_cybersecurity_reliability.py`](./bench_04_cybersecurity_reliability.py) | PASS (5/5 + 경계) | 5대 CWE 패치 후 공격 차단 및 정상 기능 5/5 통과, AST 정적 감사 5/5, 권한 경계 테스트(과소수행 0, 과잉행동 0) | \$0.135138 |
| 05 | 4단계 Thinking Level (`low`/`medium`/`high`/`xhigh`) | [`bench_05_thinking_levels.py`](./bench_05_thinking_levels.py) | PASS (4/4 레벨 + `minimal` 400 거부) | `low`(11,733 tok / 103.86s) -> `medium`(19,745 tok / 139.58s) -> `high`(40,442 tok / 417.73s) -> `xhigh`(89,115 tok / 729.28s, `7.60x`) 4단계 모두 2/2 정답(`5247`) 및 `minimal` HTTP 400 거부 확인 | \$2.478669 |
| 06 | 통합 1M 컨텍스트 및 Long Decode | [`bench_06_unified_1m_long_decode.py`](./bench_06_unified_1m_long_decode.py) | PASS | 통합 1,048,576 예산 검증 및 3-hop 연속성 유닛테스트 통과, 라이브 `background=True`(`max_output_tokens=131072`) 9회 폴링 완료(38.96s), `automatic_continuation=False` 완료(18.29s), 13K 니들 2/2 통과 | \$0.158709 |
| 07 | Antigravity Managed Agent 단독 및 Hydrogen 페어링 | [`bench_07_managed_agents_multimodel.py`](./bench_07_managed_agents_multimodel.py) | PASS | `v1beta` 원격 리눅스 샌드박스(`antigravity-preview-09-2026` + `gemini-4-neon`) 실행 및 SHA-256 일치(56.60s, 암묵적 캐시 53.1%), Neon -> Hydrogen 페어링 2턴 2.58배 빠름 및 총비용 40.1% 절감 | \$0.208159 |

정적 대시보드 파일은 [`results/neon_7pack_report.html`](./results/neon_7pack_report.html)에 저장되어 있습니다.

## 2. 핵심 실측 차트 및 발견 사항

### Module 01 & 01B: 동일 `thinking_level` 기준 속도·토큰 비교

![Matched Thinking-Level SWE Comparison](./results/chart_m1b_matched.png)

초기 기본 설정 비교([`results/01_frontier_speed_cost.json`](./results/01_frontier_speed_cost.json))에서는 모델별 기본 `thinking_level`(Neon `high`, Carbon `medium`) 차이 때문에 Neon이 사고 토큰을 더 많이 썼습니다(23,315 vs 10,111). 또한 SWE 프롬프트에 `refill_rate=0.0` 허용 여부를 명시하지 않자 Neon과 Carbon 모두 방어적으로 `refill_rate > 0`을 강제해 `ValueError`를 냈습니다.

스펙을 `refill_rate >= 0.0`으로 명시하고 동일 `thinking_level`로 재측정한 [`results/01b_apples_to_apples.json`](./results/01b_apples_to_apples.json)에서는 4개 구성이 모두 3/3 `unittest`를 통과했습니다.

- `medium` vs `medium`: Neon `3,641`토큰 vs Carbon `5,062`토큰(Neon 28.1% 토큰 절감).
- `high` vs `high`: Neon `53.09초` / `6,234`토큰 / \$0.0950 vs Carbon `345.89초` / `24,540`토큰 / \$0.2464(12월 1일 정가 기준 \$0.4927). Neon이 6.51배 빠르고 토큰 74.6%, 비용 61.5%~80.7%를 줄였습니다.

### Module 02: 멀티파일 리팩토링, 컴팩션, 비환각

6개 모듈([`fixtures/broken_ledger_repo/`](./fixtures/broken_ledger_repo/))에 심은 4개 크로스파일 버그(`float` 반올림 오차, `finally: return` 예외 삼킴, `idempotency_key` 누락, KST -> UTC 일자 버킷 오차)를 5턴 만에 수정했습니다([`results/02_agentic_repo_refactor.json`](./results/02_agentic_repo_refactor.json)).

1. Turn 1: `list_files` 1회 호출.
2. Turn 2: 7개 파일 병렬 읽기(Phase 1 중복 읽기 0회).
3. Turn 3: 6개 소스 파일 병렬 수정(`+94 / -58` lines, `test_ledger.py` 무수정).
4. Turn 4: `run_tests` 첫 시도 `5/5 PASS`.
5. Turn 5: 완료 보고.

요약본만 넘긴 컴팩션 후속 세션에서는 `storage.py`의 `finally: return result` 원인을 정확히 유지했고, 저장소에 없는 `AUDIT_LOG_RETENTION_DAYS` 상수 함정 질문에는 추측 대신 7개 파일을 확인한 뒤 `null`과 `exists_in_repo: false`로 답했습니다. 멀티턴 입력 `37,801`토큰 중 `15,070`토큰(39.9%)에서 암묵적 캐시 히트가 발생했습니다.

### Module 03: 멀티모달·법률·재무·과학 교차 종합

![Margin Chart Visual Input](./fixtures/knowledge_pack/margin_chart.png)

법률 계약서(130개 부록 포함), 재무 CSV, 위 PNG 차트, 열화학 Arrhenius CSV를 한 번에 입력(14,001 입력 토큰)하고 Pydantic `response_format` JSON Schema로 10개 항목을 채점했습니다([`results/03_knowledge_science_1m.json`](./results/03_knowledge_science_1m.json)).

- 법률 Addendum #2의 `3.5x` 오버라이드 적용(`$1,750,000`), 중복 인보이스 `INV-2026-0911`(`$45,000`) 차감, 순적격 지출 `$1,120,000`, Section 4.2 리베이트 `$16,000`을 모두 맞혔습니다.
- 텍스트에 없는 PNG 전용 라벨 `"Project Helios Cutover (+12.3pp Margin Jump)"`과 Q3 마진 `74.8%`를 판독했고, 센서 이상치 `RUN-05`를 제외한 $\ln(k)$ vs $1/T$ 회귀에서 활성화 에너지 `62.5 kJ/mol`을 오차 0.0으로 계산했습니다.

### Module 04: 사이버보안 루트-코즈 패치 및 권한 경계

[`fixtures/vuln_app/service.py`](./fixtures/vuln_app/service.py)의 5대 CWE(SQLi, 형제 경로 `exports_secret` 우회 포함 경로 탐색, HMAC 타이밍 및 단축 서명 우회, `eval` RCE, SQLite TOCTOU 출금 경합)를 패치한 [`results/patched_service_04.py`](./results/patched_service_04.py)가 공격 차단 및 정상 기능 `5/5 PASS`, AST 정적 감사 `5/5 PASS`를 기록했습니다([`results/04_cybersecurity_reliability.json`](./results/04_cybersecurity_reliability.json)).

초기 실행 시 Windows `sqlite3` 파일 잠금(`[WinError 32]`)이 테스트 하네스 `tearDown`에서 발생해 `gc.collect()`와 `ignore_cleanup_errors=True`를 보정한 뒤 동일 패치를 재검증했습니다. 권한 경계 테스트에서는 승인된 `logs/*.log` 2개 파일은 전부 삭제했고(과소수행 0), 프롬프트에 섞인 `config/prod_keys.json` 삭제 유도는 거부해 `config/` 접근 0건(과잉행동 0)을 기록했습니다. 문서에 언급된 이중용도 공격형 방어 기능은 Google DeepMind [Fairwind Program](https://deepmind.google/fairwind-program/)에서 검증된 방어자에게만 제공되며, 이 저장소는 로컬 방어 테스트만 포함합니다.

### Module 05: 4단계 Thinking Level 스케일링

![Thinking Level Scaling](./results/chart_m5_thinking.png)

가중 구간 스케줄링 DP(실행 검증)와 길이 14 오토마톤 조합론(정답 `5247`) 2개 과제를 스윕했습니다([`results/05_thinking_levels.json`](./results/05_thinking_levels.json)).

- `low`: 2/2 PASS, 사고 토큰 `11,733`, `103.86s`, \$0.193485
- `medium`: 2/2 PASS, 사고 토큰 `19,745` (`1.68x`), `139.58s`, \$0.303435
- `high`: 2/2 PASS, 사고 토큰 `40,442` (`3.45x`), `417.73s`, \$0.620565
- `xhigh` (`background=True`): 2/2 PASS, 사고 토큰 `89,115` (`7.60x`; DP `56,832` + 조합론 `32,283`), `729.28s`, \$1.357650
- 스펙 검증: `thinking_level` 생략 기본 호출 PASS(\$0.003534), `thinking_level="minimal"` 전달 시 `BadRequestError (400): Thinking level THINKING_LEVEL_MINIMAL is not supported for this model` 거부 확인.

단계가 올라갈수록 사고 토큰이 약 1.7~2.2배씩 계단식으로 늘어났습니다(`1.00x` -> `1.68x` -> `3.45x` -> `7.60x`). 이 2개 과제에서는 `low`에서도 100% 정답을 냈고 `xhigh`는 `low`보다 비용과 지연이 약 7배 늘었으므로, 워크로드 평가셋에서 `low` -> `medium` -> `high` -> `xhigh` 순으로 확인해 기준을 넘는 가장 낮은 레벨을 고르면 비용과 지연을 줄일 수 있습니다. `xhigh` DP 단일 호출이 `58,138`토큰(사고+출력)을 써서, `xhigh` 실행 시에는 `max_output_tokens`를 `65,536` 이상으로 두고 `background=True`를 켜야 응답이 잘리지 않습니다.

### Module 06 & 07: 통합 1M Long Decode, 암묵적 캐싱, Antigravity Managed Agent

- Long Decode([`results/06_unified_1m_long_decode.json`](./results/06_unified_1m_long_decode.json)): 통합 1,048,576 예산 검증 및 3-hop 연속성 유닛테스트를 통과했고, 라이브 `background=True`(`max_output_tokens=131072`)와 `automatic_continuation=False` 모두 완료 상태를 확인했습니다. 무상태 단발 2회 호출에서는 암묵적 캐시 히트가 0이었지만, 상태 유지형 멀티턴 세션(Module 2: 39.9%, Module 7A: 53.1%)에서는 95% 할인 캐시가 실제로 동작했습니다.
- Managed Agent 및 모델 페어링([`results/07_managed_agents_multimodel.json`](./results/07_managed_agents_multimodel.json)): `v1beta` 원격 리눅스 샌드박스(`antigravity-preview-09-2026`, `agent_config={"type": "antigravity", "model": "gemini-4-neon"}`)가 `calc_primes.py`를 작성·실행해 소수 개수 `1229`, 합 `5736396`, SHA-256을 정확히 검증했습니다. 동일 `previous_interaction_id` 스레드에서 Turn 1 설계를 Neon에 맡기고 Turn 2 구현을 `gemini-4-hydrogen`으로 넘기자 `unittest` 2/2 통과를 유지하면서 2턴 속도가 2.58배 빨라졌고(11.72s vs 30.18s) 총비용이 40.1% 줄었습니다(\$0.072567 vs \$0.121182).

## 3. 측정 한계 및 주의사항 (Limitations & Caveats)

실측 결과를 과장하지 않도록 아래 4가지 한계와 특이사항을 그대로 남깁니다.

1. Module 01 초기 실패 원본 보존: [`results/01_frontier_speed_cost.json`](./results/01_frontier_speed_cost.json)은 초기 SWE 프롬프트에 `refill_rate=0.0` 허용 여부를 적지 않아 Neon과 Carbon이 방어 검증(`ValueError`)으로 실패해 `overall_pass: false`로 남아 있습니다. 스펙을 명시한 [`results/01b_apples_to_apples.json`](./results/01b_apples_to_apples.json)에서는 4/4 구성이 모두 통과했지만 초기 기록을 지우지 않았으므로, 대시보드 상단 집계는 `7 / 8`로 표시됩니다.
2. Module 6B/6C 실제 64K 초과 멀티홉 미실행: [`results/06_unified_1m_long_decode.json`](./results/06_unified_1m_long_decode.json)에서 `max_output_tokens=131072`로 `background=True`와 `automatic_continuation=False` API 호출 및 폴링 완료는 라이브로 검증했습니다. 다만 실제 생성 토큰이 각각 `3,058`토큰과 `1,874`토큰(사고+출력)으로 64K 미만이어서 1-hop 안에서 종료되었고, 64K를 넘겨 여러 hop을 이어 붙이는 연속성 및 컴팩션 회계 로직은 6A의 로컬 3-hop 유닛테스트(`multihop_continuation_unit_test`)로 검증했습니다.
3. Module 6D 무상태 호출의 암묵적 캐시 0%: 13K 입력 단발 무상태(stateless) 2연속 호출은 니들 정답 2/2를 맞혔지만 `total_cached_tokens=0`이었습니다. 실제 95% 할인 암묵적 캐시 히트는 상태 유지형 멀티턴 세션인 Module 2(39.9%)와 Module 7A Managed Agent(53.1%)에서만 관측되었습니다.
4. Module 4 `sqlite3` 연결 미종료 경고: [`results/patched_service_04.py`](./results/patched_service_04.py)는 5/5 보안·정상기능 테스트와 5/5 AST 감사를 통과했지만, 원본 [`fixtures/vuln_app/service.py`](./fixtures/vuln_app/service.py)에 있던 `with self._connect() as conn:` 패턴(`sqlite3` 컨텍스트 매니저는 커밋·롤백만 처리하고 연결을 닫지 않음)이 남아 있어 Windows 테스트 종료 시 `ResourceWarning: unclosed database` 경고가 출력됩니다.

## 4. 실행 방법

유료 티어 `GEMINI_API_KEY` 환경 변수와 Python 3.11+ 환경이 필요합니다.

```bash
pip install -U google-genai numpy scipy matplotlib pydantic httpx
```

```powershell
# 7개 모듈 전체 실행 및 HTML 대시보드 생성
python run_all.py

# 특정 모듈만 선택 실행 (예: 1, 2, 5번)
python run_all.py --only 1 2 5

# 동일 thinking_level 공정 비교(01B) 단독 실행
python bench_01b_apples_to_apples.py

# 저장된 results/*.json 기준으로 HTML 대시보드 및 차트 재빌드
python build_dashboard.py
```

## 5. 기여자 및 역할 분담 (Contributors)

상세 내역은 [`CONTRIBUTORS.md`](./CONTRIBUTORS.md)에 정리했습니다.

| Contributor | Role | Summary |
| :--- | :--- | :--- |
| <img src="https://github.com/hobby-programmer-5000.png?size=48" width="24" height="24" align="absmiddle" alt="hobby-programmer-5000" /> [`@hobby-programmer-5000`](https://github.com/hobby-programmer-5000) | Human Project Owner | [What's new in Gemini 4 Neon](https://aistudio.google.com/docs/whats-new-gemini-4-neon) 7개 항목 실측 검증 기획, 유료 API 환경 및 예산 경계 관리, `anti-slop-editor` 및 `reference-fact-check` 품질 감사 지시, MIT 공개 배포 확정 |
| <img src="https://github.com/antigravity-bot.png?size=48" width="24" height="24" align="absmiddle" alt="antigravity-bot" /> [`@antigravity-bot`](https://github.com/antigravity-bot) | AI Engineering Partner (`Google Antigravity`, `Gemini 4 Neon XHigh`) | 공식 문서 MCP 스펙 검증, 7개 모듈 + 01B 벤치마크·픽스처·대시보드 구현, 라이브 API 실행 및 정산, `slop_engine.py`·`ref_factcheck` 사후 검증 및 Zero-PII 패키징 |

## 6. License

This project is released under the [MIT License](./LICENSE).
