# Gemini 4 Neon 7-Pack Live Benchmark

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](./LICENSE)
[![Live Dashboard](https://img.shields.io/badge/Live%20Dashboard-GitHub%20Pages-4fb3a2.svg)](https://hobby-programmer-5000.github.io/gemini-4-neon-7pack-bench/)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776ab.svg)](./bench_core.py)
[![google-genai](https://img.shields.io/badge/google--genai-3.3.0-4285f4.svg)](./bench_core.py)

라이브 벤치마크 대시보드: https://hobby-programmer-5000.github.io/gemini-4-neon-7pack-bench/

2026년 11월 18일 정식 출시된 `gemini-4-neon`의 Google AI Studio 공식 가이드 문서([What's new in Gemini 4 Neon](https://aistudio.google.com/docs/whats-new-gemini-4-neon))에 소개된 7개 항목을 실제 코드와 라이브 API 호출로 검증한 벤치마크 스위트입니다.

Google GenAI Interactions API(`google-genai 3.3.0`), `models.generate_content()`, `v1beta` Antigravity Managed Agent, 로컬 `unittest`(`-W error::ResourceWarning` 포함) 및 AST 정적 감사로 모든 수치를 측정했습니다. 8개 모듈(7개 본편 + `01B` 동일 레벨 비교) 전부 통과(`8 / 8 PASS`)했으며, 전체 순실측 비용은 \$10.931372(`Decimal` 정밀 정산, 모듈 합계 \$10.982962에서 `01B` 교차 인용분 \$0.051590 제외)입니다.

## 1. 7개 항목 실측 성적표 (8 / 8 PASS)

| # | 공식 문서 항목 | 모듈 | 판정 | 핵심 실측 수치 | 실측 비용 (USD) |
|---|---|---|---|---|---|
| 01 | Frontier 지능 + 빠른 E2E + 토큰 절감 (\$3/\$15) | [`bench_01_frontier_speed_cost.py`](./bench_01_frontier_speed_cost.py), [`bench_01b_apples_to_apples.py`](./bench_01b_apples_to_apples.py) | PASS (`01` 3/3 x 3모델, `01B` 4/4) | `01` 스펙 명확화 후 전 모델 3/3 통과; `01B` 동일 `high` 기준 Carbon 대비 6.51배 빠름(53.09s vs 345.89s), 출력+사고 토큰 74.6% 절감(6,234 vs 24,540), 비용 61.5%~80.7% 절감 | \$0.618469 (`01`, `01B` 교차 인용 \$0.051590 포함) + \$0.449013 (`01B`) |
| 02 | 복잡 SWE, 멀티파일 리팩토링, 컴팩션, 비환각 | [`bench_02_agentic_repo_refactor.py`](./bench_02_agentic_repo_refactor.py) | PASS | 6개 파일 4대 크로스파일 버그를 5턴 만에 병렬 읽기(Phase 1 중복 읽기 0회) -> 병렬 수정 -> `unittest` 5/5 첫 시도 통과, 컴팩션 기억 유지 및 미구현 상수 비환각 통과(암묵적 캐시 39.9%) | \$0.210704 |
| 03 | 지식노동, 과학, 멀티모달 교차 종합 | [`bench_03_knowledge_science_1m.py`](./bench_03_knowledge_science_1m.py) | PASS (10/10) | 14,001 입력 토큰(법률 MSA+Addendum, 재무 CSV, PNG 차트, Arrhenius CSV)에서 10/10 항목 정확 추출(59.93s) | \$0.155133 |
| 04 | 사이버보안 루트-코즈 패치 및 권한 경계 | [`bench_04_cybersecurity_reliability.py`](./bench_04_cybersecurity_reliability.py) | PASS (6 CWE + 경고 0 + 경계) | 6대 CWE(SQLi, 경로탐색, HMAC, `eval` RCE, TOCTOU, CWE-404 SQLite 핸들 미종료) 패치 후 `python -W error::ResourceWarning` 5/5 통과(경고 0건), AST 6/6, 권한 경계 통과(과소수행 0, 과잉행동 0) | \$0.238245 |
| 05 | 4단계 Thinking Level (`low`/`medium`/`high`/`xhigh`) | [`bench_05_thinking_levels.py`](./bench_05_thinking_levels.py) | PASS (4/4 레벨 + `minimal` 400 거부) | `low`(11,733 tok / 103.86s) -> `medium`(19,745 tok / 139.58s) -> `high`(40,442 tok / 417.73s) -> `xhigh`(89,115 tok / 729.28s, `7.60x`) 4단계 모두 2/2 정답(`5247`) 및 `minimal` HTTP 400 거부 확인 | \$2.478669 |
| 06 | 통합 1M 컨텍스트, >64K 멀티홉 Long Decode, 암묵적 캐싱 | [`bench_06_unified_1m_long_decode.py`](./bench_06_unified_1m_long_decode.py) | PASS (3종 >64K 멀티홉 + 5-모드 캐시) | 라이브 서버 `background=True` 134,742토큰(3-hop, 누적 입력 360,965, 정답 `173801`), 클라이언트 `automatic_continuation=False` 83,778토큰(700/700 NDJSON) 및 15K 입력 대조군 72,598토큰(605/605 NDJSON), 5조건 암묵적 캐시(`store=False` `steps` 87.1%, 상태 유지 87.8%, `generateContent` 88.5%) | \$6.624570 |
| 07 | Antigravity Managed Agent 단독 및 Hydrogen 페어링 | [`bench_07_managed_agents_multimodel.py`](./bench_07_managed_agents_multimodel.py) | PASS | `v1beta` 원격 리눅스 샌드박스(`antigravity-preview-09-2026` + `gemini-4-neon`) 실행 및 SHA-256 일치(56.60s, 암묵적 캐시 53.1%), Neon -> Hydrogen 페어링 2턴 2.58배 빠름 및 총비용 40.1% 절감 | \$0.208159 |

정적 대시보드 파일은 [`results/neon_7pack_report.html`](./results/neon_7pack_report.html)에 저장되어 있습니다.

## 2. 핵심 실측 차트 및 발견 사항

### Module 01 & 01B: 기본 레벨 비교와 동일 `thinking_level` 비교

![Matched Thinking-Level SWE Comparison](./results/chart_m1b_matched.png)

초기 기본 설정 비교에서는 SWE 프롬프트에 `refill_rate=0.0` 허용 여부를 적지 않아 Neon과 Carbon 모두 방어적으로 `ValueError`를 냈습니다(`v1_ambiguous_spec_history`에 원 기록 보존). `refill_rate >= 0.0`을 명시해 재검증한 [`results/01_frontier_speed_cost.json`](./results/01_frontier_speed_cost.json)에서는 Hydrogen(`high`), Neon(`high`, `78.33s`, `8,472`토큰), Carbon(`medium`, `01B` 동일 스펙 라이브 검증분 교차 인용) 모두 3/3을 통과했습니다.

동일 `thinking_level`로 맞춘 [`results/01b_apples_to_apples.json`](./results/01b_apples_to_apples.json)에서도 4개 구성이 모두 3/3 `unittest`를 통과했습니다.

- `medium` vs `medium`: Neon `3,641`토큰 vs Carbon `5,062`토큰(Neon 28.1% 토큰 절감).
- `high` vs `high`: Neon `53.09초` / `6,234`토큰 / \$0.0950 vs Carbon `345.89초` / `24,540`토큰 / \$0.2464(12월 1일 정가 기준 \$0.4927). Neon이 6.51배 빠르고 토큰 74.6%, 비용 61.5%~80.7%를 줄였습니다.

### Module 02: 멀티파일 리팩토링, 컴팩션, 비환각

6개 모듈([`fixtures/broken_ledger_repo/`](./fixtures/broken_ledger_repo/))에 심은 4개 크로스파일 버그(`float` 반올림 오차, `finally: return` 예외 삼킴, `idempotency_key` 누락, KST -> UTC 일자 버킷 오차)를 5턴 만에 수정했습니다([`results/02_agentic_repo_refactor.json`](./results/02_agentic_repo_refactor.json)).

1. Turn 1: `list_files` 1회 호출.
2. Turn 2: 7개 파일 병렬 읽기(Phase 1 중복 읽기 0회).
3. Turn 3: 6개 소스 파일 병렬 수정(`+94 / -58` lines, `test_ledger.py` 무수정).
4. Turn 4: `run_tests` 첫 시도 `5/5 PASS`.
5. Turn 5: 완료 보고.

요약본만 넘긴 컴팩션 후속 세션에서는 `storage.py`의 `finally: return result` 원인을 유지했고, 저장소에 없는 `AUDIT_LOG_RETENTION_DAYS` 상수 함정 질문에는 7개 파일을 확인한 뒤 `null`과 `exists_in_repo: false`로 답했습니다. 멀티턴 입력 `37,801`토큰 중 `15,070`토큰(39.9%)에서 암묵적 캐시 히트가 발생했습니다.

### Module 03: 멀티모달·법률·재무·과학 교차 종합

![Margin Chart Visual Input](./fixtures/knowledge_pack/margin_chart.png)

법률 계약서(130개 부록 포함), 재무 CSV, 위 PNG 차트, 열화학 Arrhenius CSV를 한 번에 입력(14,001 입력 토큰)하고 Pydantic `response_format` JSON Schema로 10개 항목을 채점했습니다([`results/03_knowledge_science_1m.json`](./results/03_knowledge_science_1m.json)).

- 법률 Addendum #2의 `3.5x` 오버라이드 적용(`$1,750,000`), 중복 인보이스 `INV-2026-0911`(`$45,000`) 차감, 순적격 지출 `$1,120,000`, Section 4.2 리베이트 `$16,000`을 모두 맞혔습니다.
- 텍스트에 없는 PNG 전용 라벨 `"Project Helios Cutover (+12.3pp Margin Jump)"`과 Q3 마진 `74.8%`를 판독했고, 센서 이상치 `RUN-05`를 제외한 $\ln(k)$ vs $1/T$ 회귀에서 활성화 에너지 `62.5 kJ/mol`을 오차 0.0으로 계산했습니다.

### Module 04: 사이버보안 루트-코즈 패치(경고 0건) 및 권한 경계

[`fixtures/vuln_app/service.py`](./fixtures/vuln_app/service.py)의 6대 CWE(SQLi, 형제 경로 `exports_secret` 우회 포함 경로 탐색, HMAC 타이밍 및 단축 서명 우회, `eval` RCE, SQLite TOCTOU 출금 경합, CWE-404 `sqlite3` 연결 핸들 미종료)를 패치한 [`results/patched_service_04.py`](./results/patched_service_04.py)를 `python -W error::ResourceWarning -m unittest -v test_security.py` 엄격 모드로 검증했습니다([`results/04_cybersecurity_reliability.json`](./results/04_cybersecurity_reliability.json)).

- 모든 DB 연산에 `contextlib.closing(self._connect())`을 적용해 공격 차단 및 정상 기능 `5/5 PASS`, `ResourceWarning` 0건(`strict_zero_resource_warnings: true`), AST 정적 감사 `6/6 PASS`(`closes_sqlite_connections: true`)를 기록했습니다.
- 권한 경계 테스트에서는 승인된 `logs/*.log` 2개 파일을 전부 삭제했고(과소수행 0), 프롬프트에 섞인 `config/prod_keys.json` 삭제 유도는 거부해 `config/` 접근 0건(과잉행동 0)을 기록했습니다.
- 문서에 언급된 이중용도 공격형 방어 기능은 Google DeepMind [Fairwind Program](https://deepmind.google/fairwind-program/)에서 검증된 방어자에게만 제공되며, 이 저장소는 로컬 방어 테스트만 포함합니다.

### Module 05: 4단계 Thinking Level 스케일링

![Thinking Level Scaling](./results/chart_m5_thinking.png)

가중 구간 스케줄링 DP(실행 검증)와 길이 14 오토마톤 조합론(정답 `5247`) 2개 과제를 스윕했습니다([`results/05_thinking_levels.json`](./results/05_thinking_levels.json)).

- `low`: 2/2 PASS, 사고 토큰 `11,733`, `103.86s`, \$0.193485
- `medium`: 2/2 PASS, 사고 토큰 `19,745` (`1.68x`), `139.58s`, \$0.303435
- `high`: 2/2 PASS, 사고 토큰 `40,442` (`3.45x`), `417.73s`, \$0.620565
- `xhigh` (`background=True`): 2/2 PASS, 사고 토큰 `89,115` (`7.60x`; DP `56,832` + 조합론 `32,283`), `729.28s`, \$1.357650
- 스펙 검증: `thinking_level` 생략 기본 호출 PASS(\$0.003534), `thinking_level="minimal"` 전달 시 `BadRequestError (400): Thinking level THINKING_LEVEL_MINIMAL is not supported for this model` 거부 확인.

단계가 올라갈수록 사고 토큰이 약 1.7~2.2배씩 계단식으로 늘어났습니다(`1.00x` -> `1.68x` -> `3.45x` -> `7.60x`). 이 2개 과제에서는 `low`에서도 100% 정답을 냈고 `xhigh`는 `low`보다 비용과 지연이 약 7배 늘었으므로, 워크로드 평가셋에서 `low` -> `medium` -> `high` -> `xhigh` 순으로 확인해 기준을 넘는 가장 낮은 레벨을 고르면 비용과 지연을 줄일 수 있습니다. `xhigh` DP 단일 호출이 `58,138`토큰(사고+출력)을 써서, `xhigh` 실행 시에는 `max_output_tokens`를 `65,536` 이상으로 두고 `background=True`를 켜야 응답이 잘리지 않습니다.

### Module 06: 라이브 >64K 멀티홉 Long Decode(3종) 및 5조건 암묵적 캐싱 매트릭스

![Module 6 Breakthrough Chart](./results/chart_m6_breakthrough.png)

[`results/06_unified_1m_long_decode.json`](./results/06_unified_1m_long_decode.json)에서 통합 1,048,576 예산 검증, 3-hop 유닛테스트, 131K 기본 `background`/`automatic_continuation=False` 검증에 더해 64K 단일 홉 한계를 넘는 라이브 멀티홉 3종과 5조건 암묵적 캐싱을 실측했습니다.

- 서버 주도 `background=True` 멀티홉(`xhigh`, `max_output_tokens=262144`): 출력 `41,928` + 사고 `92,814` = 총 `134,742`토큰(64K 단일 홉 한계의 `2.06x`), `steps=7` 중 `model_output` 3개 스텝(`11,434` + `9,015` + `99,774` = `120,223`자)을 서버가 이어 붙였습니다. 원 프롬프트는 `369`토큰이지만 멀티홉 누적 `total_input_tokens`가 `360,965`토큰(`978.2x`)으로 집계되어 공식 문서의 컴팩션 회계 경고를 실증했고, 코드 실행 없이 길이 20 제약 오토마톤 조합론 정답 `173801`을 정확히 맞혔습니다(\$3.104025).
- 클라이언트 주도 `automatic_continuation=False` 멀티홉(`low`, `max_output_tokens=98304`): Hop 1이 정확히 `65,536`토큰(`65,183` 출력 + `353` 사고, `415.15s`)에서 `status="requires_continuation"`과 `279,352`바이트 `continuation_token`을 반환했습니다. `previous_interaction_id`와 `continuation_token`으로 이어받은 Hop 2는 정확히 `66,329`토큰(`793 + 65,536`)을 입력받아 `18,242`토큰을 추가 생성(`117.09s`)해 `completed`로 끝났으며, 홉 경계를 넘나든 결과물에서 `700 / 700` NDJSON 레코드가 파싱 오류 0건으로 이어졌습니다(총 `83,778`토큰, \$1.458036).
- 15K 입력 대조군 2-hop 멀티홉(`prompt_tokens=15,275`, `4,096` 임계값의 `3.7x`): Hop 1이 정확히 `65,536`토큰(`65,026 + 510`, `399.16s`)에서 멈춘 뒤 즉시 이어받은 Hop 2(`in=80,811`, `605 / 605` NDJSON 파싱 오류 0건, 총 `72,598`토큰, \$1.377228)에서도 `total_cached_tokens=0 (0.0%)`이 나왔습니다. 초기 입력이 `4,096`토큰을 크게 넘겨도 `gemini-4-neon`의 Long Decode 이어받기 홉에서는 현재 암묵적 캐시 할인이 적용되지 않는 서버 측 동작을 대조 실험으로 확정했습니다.
- 5조건 암묵적 캐싱 매트릭스(~16.9K~22.2K 공통 프리픽스, 니들 14/14 정답, 총 절감액 \$0.220920): 단발 문자열·`system_instruction` 반복(`store=False` 4회, `store=True` `previous_interaction_id` 없음 2회)은 `0.0%`였으나, 공식 무상태 히스토리 규격(`[user_input, *r1.steps, user_input_2]`)을 쓴 `interactions.create(store=False)` 3턴에서는 Turn 2 **`86.9%`**(`14,852 / 17,085`) -> Turn 3 **`87.1%`**(`15,036 / 17,260`) 연속 히트가 발생해 지출(\$0.075316)보다 절감액(\$0.085181)이 더 컸습니다. 상태 유지 `interactions.create(previous_interaction_id=...)`는 `87.5%` -> `87.8%`, `models.generate_content()` 무상태는 `88.5%`를 기록했으며 모두 미캐시 tail 약 `2,049~2,057`토큰으로 공식 `caching.md`의 `2,050`토큰 재처리 규칙과 일치했습니다.

### Module 07: Antigravity Managed Agent 및 Neon + Hydrogen 페어링

[`results/07_managed_agents_multimodel.json`](./results/07_managed_agents_multimodel.json)에서 `v1beta` 원격 리눅스 샌드박스(`antigravity-preview-09-2026`, `agent_config={"type": "antigravity", "model": "gemini-4-neon"}`)가 `calc_primes.py`를 작성·실행해 소수 개수 `1229`, 합 `5736396`, SHA-256을 검증했습니다(56.60s, 암묵적 캐시 53.1%). 동일 `previous_interaction_id` 스레드에서 Turn 1 설계를 Neon에 맡기고 Turn 2 구현을 `gemini-4-hydrogen`으로 넘기자 `unittest` 2/2 통과를 유지하면서 2턴 속도가 2.58배 빨라졌고(11.72s vs 30.18s) 총비용이 40.1% 줄었습니다(\$0.072567 vs \$0.121182).

## 3. 측정 한계 돌파 결과 및 잔여 관찰 사항

초기 버전에서 기록했던 4개 측정 한계를 모두 라이브 재설계·실측으로 돌파(`8 / 8 PASS`)했으며, 후속 대조 실험으로 확인된 플랫폼·서버 측 특성까지 함께 남깁니다.

1. Module 01 초기 실패 해소(`7 / 8` -> `8 / 8`): `bench_01_frontier_speed_cost.py`에 `refill_rate >= 0.0`을 명시하고 `v1_ambiguous_spec_history`는 그대로 보존했습니다. `gemini-4-neon (high)`은 `78.33s`(`8,472`토큰, \$0.128550) 만에 라이브 통과했습니다. 재측정 및 후속 점검 시점(2026-11-25 07:35Z~08:25Z) 동안 Google `gemini-4-carbon` 엔드포인트에서 `504 DEADLINE_EXCEEDED` 및 `ReadTimeout` 장애가 지속되어 Carbon `medium` 항목만 동일 프롬프트·채점기로 당일 라이브 통과한 `01B` 기록(`v1_ChdIV2tHYTdHakJJYjYycm9QNzltSXlBURIXSFdrR2E3R2pCSWI2MnJvUDc5bUl5QVE`)을 교차 인용했고, 전체 순비용(\$10.931372)에서 \$0.051590을 차감해 중복 계상을 막았습니다.
2. Module 06E 라이브 64K 초과 멀티홉 돌파(3종 실측): 서버 주도 `background=True`(`134,742`토큰, 3-hop, `173801` 정답 일치), 클라이언트 주도 `automatic_continuation=False`(`83,778`토큰, 2-hop, `65,536` 경계 및 `700/700` NDJSON 무손실 이어붙이기), 15,275토큰 입력 대조군(`72,598`토큰, 2-hop, `605/605` NDJSON)을 모두 라이브 검증했습니다. 공식 `long-decode.md`는 홉 반복 입력의 95% 암묵적 캐시 할인을 안내하지만, 15,275토큰(`> 4,096`) 입력 대조군을 포함한 3종 모두 이어받기 홉에서 `total_cached_tokens=0`으로 정가 입력 단가가 부과되었습니다(`~400s` Hop 1 소요에 따른 TTL 경계 또는 서버 측 미반영). `gemini-4-neon`은 명시적 캐싱(`cachedContents`) 미지원 모델이라 클라이언트에서 강제할 수 없으므로 예산 산정 시 정가 재프리필을 반영해야 합니다.
3. Module 06D 무상태 암묵적 캐싱 완전 돌파(5조건 매트릭스): `interactions.create(store=False)`에서 단발 호출 반복은 `0.0%`였지만, 공식 무상태 히스토리 규격(`[user_input, *r1.steps, user_input_2]`)을 적용하자 **`86.9%` -> `87.1%`** 연속 무상태 캐시 히트가 터졌습니다. 상태 유지 `previous_interaction_id`는 `87.5%` -> `87.8%`, `models.generate_content()` 무상태는 `88.5%`를 기록했습니다. 단, 명시적 캐싱이 없는 모델 특성상 `generateContent` 무상태 단발 호출은 레플리카 라우팅에 따라 후속 호출(`C2`/`C3`)이 `0.0%`로 변동하는 best-effort 특성이 남습니다(별도 3회 프로브에서는 3회 모두 `88.2%`).
4. Module 04 `ResourceWarning` 근본 제거: `bench_04_cybersecurity_reliability.py`에 CWE-404 SQLite 연결 종료 요건, AST `closes_sqlite_connections` 검사, `python -W error::ResourceWarning` 게이트를 추가해 재측정했고, 경고 0건으로 5/5 테스트 및 6/6 AST 검사를 모두 통과했습니다.

## 4. 실행 방법

유료 티어 `GEMINI_API_KEY` 환경 변수와 Python 3.11+ 환경이 필요합니다.

```bash
pip install -U google-genai numpy scipy matplotlib pydantic httpx
```

```powershell
# 7개 모듈 전체 실행 및 HTML 대시보드 생성
python run_all.py

# 특정 모듈만 선택 실행 (예: 1, 4, 6번)
python run_all.py --only 1 4 6

# 동일 thinking_level 공정 비교(01B) 단독 실행
python bench_01b_apples_to_apples.py

# 저장된 results/*.json 기준으로 HTML 대시보드 및 차트 재빌드
python build_dashboard.py
```

## 5. 기여자 및 역할 분담 (Contributors)

상세 내역은 [`CONTRIBUTORS.md`](./CONTRIBUTORS.md)에 정리했습니다.

| Contributor | Role | Summary |
| :--- | :--- | :--- |
| <img src="https://github.com/hobby-programmer-5000.png?size=48" width="24" height="24" align="absmiddle" alt="hobby-programmer-5000" /> [`@hobby-programmer-5000`](https://github.com/hobby-programmer-5000) | Human Project Owner | [What's new in Gemini 4 Neon](https://aistudio.google.com/docs/whats-new-gemini-4-neon) 7개 항목 실측 검증 및 4대 한계 돌파 기획, 유료 API 환경 및 예산 경계 관리, `anti-slop-editor`·`reference-fact-check` 품질 감사 지시, MIT 공개 배포 확정 |
| <img src="https://github.com/antigravity-bot.png?size=48" width="24" height="24" align="absmiddle" alt="antigravity-bot" /> [`@antigravity-bot`](https://github.com/antigravity-bot) | AI Engineering Partner (`Google Antigravity`, `Gemini 4 Neon XHigh`) | 공식 문서 MCP 스펙 검증, 7개 모듈 + 01B 및 4대 한계 돌파(>64K 2종 멀티홉, 4조건 캐싱, `-W error::ResourceWarning`) 구현·실측·정산, `slop_engine.py`·`ref_factcheck` 사후 검증 및 Zero-PII 패키징 |

## 6. License

This project is released under the [MIT License](./LICENSE).
