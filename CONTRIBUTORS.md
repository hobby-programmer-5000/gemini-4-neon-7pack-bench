# Contributors (기여자 및 역할 분담)

| Contributor | Role | Key Contributions |
| :--- | :--- | :--- |
| <img src="https://github.com/hobby-programmer-5000.png?size=48" width="24" height="24" align="absmiddle" alt="hobby-programmer-5000" /> [`@hobby-programmer-5000`](https://github.com/hobby-programmer-5000) | Human Project Owner & Verification Director | Google AI Studio [What's new in Gemini 4 Neon](https://aistudio.google.com/docs/whats-new-gemini-4-neon) 7개 항목 전수 실측 검증 기획, 유료 티어 API 환경 제공, `anti-slop-editor` 전체 파일 품질 점검 및 `reference-fact-check` 감사 지시, MIT 라이선스 및 공개 저장소 배포 거버넌스 확정 |
| <img src="https://github.com/antigravity-bot.png?size=48" width="24" height="24" align="absmiddle" alt="antigravity-bot" /> [`@antigravity-bot`](https://github.com/antigravity-bot) | AI Engineering & Verification Partner (`Google Antigravity`, `Gemini 4 Neon XHigh`) | Gemini Docs MCP 1차 스펙 대조, 7개 실전 벤치마크 모듈 및 공정 비교 추가 모듈(`01B`) 구현, 픽스처(6개 파일 원장 저장소, 법률·재무·차트·Arrhenius 팩, 5대 CWE 취약 앱) 및 `unittest`/AST 하네스 작성, 라이브 API 실행 및 정밀 `Decimal` 비용 정산, HTML 대시보드 생성, `slop_engine.py` 및 `ref_factcheck` 사후 검증, Zero-PII 공개 패키징 |

## 역할 분담 상세

### 1. Human Project Owner (`@hobby-programmer-5000`)

연락처: `hobbyprogrammer5000@gmail.com`

1. 실험 목표와 범위 설정: Google AI Studio 공식 문서([What's new in Gemini 4 Neon](https://aistudio.google.com/docs/whats-new-gemini-4-neon))에 소개된 7개 항목을 하나도 빠뜨리지 않고 실제 동작하는 코드와 라이브 API로 검증하도록 지시했습니다.
2. 실행 환경 및 예산 관리: 유료 티어 Gemini API 실행 환경을 제공하고, Module 5 `xhigh` 1차 시도에서 프로젝트 월간 지출 한도(`HTTP 429`)에 도달하자 AI Studio Spend 페이지에서 한도를 상향해 4단계 전체(`low` -> `xhigh` + `minimal` 400 거부) 재측정을 승인했습니다.
3. 품질 감사 및 공개 배포 지시: 생성된 전 파일에 `anti-slop-editor`와 `reference-fact-check`를 적용하도록 지시했고, MIT 라이선스 및 인간-AI 공동 기여 표기 원칙을 정했습니다.

### 2. AI Engineering & Verification Partner (`@antigravity-bot`)

플랫폼: Google Antigravity (`Gemini 4 Neon XHigh`)

1. 공식 스펙 검증: 코드 작성 전 Gemini Docs MCP(`whats-new-gemini-4-neon.md`, `long-decode.md`, `pricing.md`, `antigravity-agent.md`, `choosing-a-model.md`, `function-calling.md`)에서 가격, `thinking_level`, Long Decode, `agent_config` 스키마를 확인했습니다.
2. 벤치마크 하네스 및 픽스처 구현: `bench_core.py`, `bench_01`부터 `bench_07`, 동일 레벨 공정 비교 `bench_01b_apples_to_apples.py`, 마스터 실행기 `run_all.py`, 다크모드 HTML 대시보드 `build_dashboard.py`를 작성했습니다.
3. 실측 및 디버깅: 7개 모듈과 1B 추가 모듈을 라이브 실행해 총 \$4.374928 구간의 실측 데이터를 수집했습니다. Module 1의 `refill_rate=0.0` 스펙 모호성, Module 4의 Windows `sqlite3` 임시 디렉터리 잠금(`[WinError 32]`), Module 5 `xhigh`의 `background=True` 재실측을 처리했습니다.
4. 사후 검증 및 공개 패키징: 전 파일에 `slop_engine.py`(scan/verify), `ref_factcheck`(Tier 0-1), `py_compile`, `unittest` 회귀 검사를 실행했고, 로컬 절대 경로와 개인 사용자명을 제거해 공개 저장소로 정리했습니다.

## 책임 및 기여 표기 원칙

저장소의 기획 방향, 검증 범위 승인, MIT 라이선스 및 공개 배포의 최종 책임은 프로젝트 소유자([`@hobby-programmer-5000`](https://github.com/hobby-programmer-5000))에게 있습니다. AI 에이전트([`@antigravity-bot`](https://github.com/antigravity-bot))의 코드 작성, 실행, 문서 정리 기여는 Git 커밋 메타데이터(`Author` / `Co-authored-by`)와 본 문서에 기록합니다.
