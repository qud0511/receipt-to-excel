---
id: ADR-008
title: Shinhan / KBank rule_based 정규식 실 PDF layout 보강
date: 2026-05-12
status: accepted
refs:
  - tests/smoke/results/20260512.md (2차 smoke 17/42 → 보강 후 재검증)
  - ADR-007 (provider 감지는 text-aware 로 해결)
  - synthesis/05 §"Phase 4 Smoke Gate"
---

# 결정

shinhan / kbank rule_based parser 의 정규식을 실 PDF layout 에 맞게 보강.
합성 fixture (`make_shinhan_receipt` / `make_kbank_receipt`) 와 실 자료 양쪽 모두
동작 강제 (한 정규식이 양쪽 layout 흡수).

## Shinhan — 4 정규식 갱신

| 필드 | 합성 layout | 실 PDF layout (shinhan_01..12, taxi_01..06) | 보강 정규식 |
| --- | --- | --- | --- |
| 거래일 | `거래일시: 2026-05-10 14:23:11` (대시, 공백, 초) | `거래일 2025.12.05\x0115:15` (점, \x01, 초 없음) — 헤더 `2026.1.2\x0111:21:53` 와 구별 필수 | `r"거래일[시]?[:\s]*(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})[\s\x01]+(\d{2}):(\d{2})(?::(\d{2}))?"` — **라벨 강제** + 구분자 OR + 초 옵셔널 |
| 금액 | `거래금액: ₩8,900` (라벨 + ₩) | `10,300` \n `원` (라벨 없는 두 줄) | `_AMOUNT_LABELED` → `_AMOUNT_BARE = r"^([\d,]+)\s*\n\s*원\s*$"` (MULTILINE) fallback |
| 가맹점명 | `가맹점명: 테스트가맹점` (라벨) | `가맹점\x01정보\n에슬로우\x01대치1호점(ESLOW)` (라벨 없는 블록) | `_MERCHANT_LABELED` → `_MERCHANT_INFO_BLOCK = r"가맹점.정보\s*\n([^\n]+)"` fallback. AD-1 raw 보존 (\x01 포함). |
| 카드번호 | canonical `9999-99**-****-9999` 형식 | 부재 (`이용카드 본인\x01178*` partial) → optional, None graceful | 변경 없음 |

**페이지 헤더 오인식 차단**: 실 PDF 의 `2026.1.2\x0111:21:53` 는 페이지 출력 시각 (TX 아님).
라벨 `거래일[시]?` 강제로 이 라인 매칭 차단 — silent wrong date 회귀 방지.

## KBank — 2 정규식 완화 (`\s+` → `\s*`)

| 필드 | 합성 | 실 PDF (kbank_03, kbank_04) | 보강 |
| --- | --- | --- | --- |
| 거래일시 | `2026/05/10 14:23:11` (공백) | `2026/04/0612:52:53` (공백 없음) | `(\d{4})/(\d{2})/(\d{2})\s*(\d{2}):(\d{2}):(\d{2})` |
| 거래금액 | `4,700 원` (공백) | `4,700원` (공백 없음) | `거래금액[:\s]*([\d,]+)\s*원` |

# 컨텍스트 — v1 회귀 패턴 진단

2차 smoke (text-aware router + is_text_embedded 보강 후, 17/42 = 40.5%) 의 25 실패 분류:

- **rule_based `field=거래일` (20 건)**: shinhan 18 + kbank 2. 합성 fixture 와 실 PDF
  layout 불일치. 본 ADR 의 작업 범위.
- **OCR `가맹점명` empty (5 건)**: hana 2 + kakaobank 3. LLM 일관성 — 별도 (out of scope, §ADR-009 후속).

실 자료 dump 핵심 증거:

```
shinhan_01.pdf:
  '2026.1.2\x0111:21:53'         ← 페이지 헤더 (오인식 차단 대상)
  '에슬로우\x01대치1호점(ESLOW)'  ← 가맹점명 (라벨 없음)
  '10,300' / '원'                 ← 금액 (두 줄)
  '거래일 2025.12.05\x0115:15'   ← 거래일 (점 + \x01 + 초 없음)

kbank_03.pdf:
  '거래일시 2026/04/0612:52:53'  ← 일·시각 공백 없음
  '거래금액 4,700원'              ← 숫자·원 공백 없음
```

# 보안 분석

- 정규식 보강만 — 외부 입력 신뢰 변경 없음 (CLAUDE.md §보안 무영향).
- `_AMOUNT_BARE` (MULTILINE) 의 `^([\d,]+)` 가 다른 숫자 라인 오매치 가능성 검토:
  실 shinhan PDF 에 라인 단독 숫자는 금액 1 곳만. 다른 숫자는 텍스트 라인 내 (`공급가액 9,364원` 등). False positive 0건 확인.
- `_MERCHANT_INFO_BLOCK` 의 `([^\n]+)` 가 가맹점 정보 다음 줄 임의 캡처 가능 — 실 PDF
  layout 상 가맹점 정보 직후 = 가맹점명 라인. AD-1 raw 보존 (\x01 미정규화) 의도.

# 영향

- 잠재 통과율 갱신: 17/42 → **37/42 ≈ 88%** (20 건 rule_based 정규식 복구).
- shinhan 18 (일반 12 + 택시 6) → 거래일/금액/가맹점/공급가액/부가세 모두 추출.
- kbank 2 (03, 04) → 거래일/금액/가맹점 추출. 거래금액 confidence high 유지.
- 합성 fixture 통과 보장 — 18/18 unit pass (실 PDF 4 + 합성 14, dot 변형 회귀 신규 1).
- mypy --strict + ruff clean.

# 단위 테스트 (TDD RED → GREEN)

| 케이스 | 마커 | 의도 |
| --- | --- | --- |
| `test_real_shinhan_01_extracts_date_amount_merchant` | `real_pdf` | 실 자료 dot + \x01 layout 회귀 |
| `test_real_shinhan_taxi_01_extracts_fields` | `real_pdf` | 택시 variant |
| `test_synthetic_shinhan_with_dot_separator_still_parses` | (default) | dash 합성 fixture 회귀 |
| `test_real_kbank_03_extracts_date_amount_merchant` | `real_pdf` | 일·시각 공백 없음 |
| `test_real_kbank_04_extracts_fields` | `real_pdf` | 동일 layout 확인 |

# 대안 폐기

| 대안 | 폐기 사유 |
| --- | --- |
| **합성 fixture 자체 수정 (dot 변형 생성)** | 실 PDF 의 layout 다양성 (라벨 없음 + 멀티라인) 을 합성에 완전 재현 어려움. 정규식 유연화가 직접적. |
| **shinhan/kbank 전용 layout-aware tokenizer** | 50줄 함수 규칙 (CLAUDE.md §가독성) 위반. 정규식 fallback 체인이 50줄 이내. |
| **라벨 강제 없이 첫 날짜 패턴 매칭** | 페이지 헤더 `2026.1.2\x0111:21:53` 가 거래일로 오인식 — silent wrong date 회귀. AD-1 회계 추적성 위반. |

# 후속 작업

- **결함 3 (OCR LLM 가맹점명 empty)** → ADR-009 (qwen2.5vl prompt 강화 + 빈 응답 retry).
- **samsung/woori 추가 변형** — 2차 smoke 에서 모두 통과한 상태. 추가 변형 발견 시 본 ADR 패턴 따라 fallback 추가.
- **합성 fixture 의 실 PDF 변형 옵션** — 필요 시 `make_shinhan_receipt(datetime_format="dot_x01")` 매개변수 추가 (현재는 정규식 유연화로 충분).
