---
id: ADR-008
title: Rule_based 정규식 실 자료 보강 — 후속 세션 작업 (Q2 미해결)
date: 2026-05-12
status: deferred
refs:
  - tests/smoke/results/20260512.md (1차 + 2차 smoke 결과)
  - ADR-007 (provider 감지는 text-aware 로 해결)
  - synthesis/05 §"Phase 4 Smoke Gate"
---

# 결정 (deferred)

**Phase 4.5 또는 Phase 5 후반 별도 세션** 에서 shinhan / samsung / kbank rule_based parser 의 정규식을 실 PDF 자료 layout 에 맞게 보강. 본 ADR 는 결정·범위·테스트 전략을 사전 고정해 후속 세션이 즉시 착수 가능하게 함.

# 컨텍스트 — v1 회귀 패턴 재발 진단

1차 smoke (11/42 = 26%) 분석 결과 발견된 결함:

- **합성 fixture vs 실 PDF layout 불일치** — `make_shinhan_receipt()` 가 만든 `YYYY-MM-DD HH:MM:SS` 와 실 PDF `YYYY.MM.DD\x01HH:MM:SS` 가 다름. 정규식 `(\d{4})-(\d{2})-(\d{2})\s+...` 가 실 자료에 미일치 → `RequiredFieldMissingError` → OCR 폴백 → LLM 빈 가맹점명.

- **검증된 카드사 (samsung_02/06/07/08, kbank_01/02/05, lotte_01)** 는 OCR 폴백 + LLM 운좋은 응답으로 우연 통과 — 신뢰 못 함.

- v1 회귀 차단의 핵심 책임 (CLAUDE.md §"카드사 양식 변동성은 Smoke Gate 로 검증") 미달.

# 작업 범위

## 1. 실 PDF 기반 unit 테스트 추가 — 4 카드사 × 5+ 케이스

| Parser | 실 PDF (변형 5 종 이상) | 기대 추출 |
| --- | --- | --- |
| shinhan | `shinhan_01..12.pdf` (일반) + `shinhan_taxi_01..06.pdf` (택시) | 일자/금액/가맹점/공급가액/부가세/카드번호 |
| samsung | `samsung_01..08.pdf` | 동일 |
| kbank | `kbank_01..05.pdf` | 일자/금액/가맹점 (공급가액·부가세 None) |
| woori | 이미 ADR-004 통과 | 회귀 검증만 |

각 PDF 별 1 케이스 + 변형 패턴 (`\x01` 컨트롤 문자 케이스 등) 케이스.

## 2. 정규식 갱신 패턴

### shinhan
- 현재: `(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2}):(\d{2})`
- 실 자료: `2026.1.2\x0111:21:53` 또는 `2026/01/02 11:21:53`
- 신: `(\d{4})[./](\d{1,2})[./](\d{1,2})[\s\x00-\x1f]+(\d{2}):(\d{2}):(\d{2})`

### samsung
- 현재 헤더 라벨 기반 (`이용금액 합계`, `이용금액`, `부가세` 등)
- 실 자료 검토 후 라벨 변형 (예: `합계`, `이용 금액`, `부 가 세`) 매칭 추가.

### kbank
- 현재: `[\d,]+ 원` (공백 강제)
- 실 자료에 공백 없는 변형 발견 시 `\s*` 로 완화.

## 3. 합성 fixture 갱신

`tests/fixtures/synthetic_pdfs.py` 의 `make_shinhan_receipt`, `make_samsung_receipt`, `make_kbank_receipt` 가 **실 자료 변형도 생성** 하도록 옵션 매개변수 추가:

```python
def make_shinhan_receipt(
    *,
    datetime_format: Literal["dash", "dot", "ctrl_char"] = "dash",
    ...
)
```

기존 합성 케이스 + 신 변형 케이스 모두 통과 강제.

## 4. Smoke Gate 재실행 + 통과율 목표

- shinhan/samsung/kbank 의 rule_based 통과율 ≥ 80% 달성 시 본 ADR status → accepted + Phase 5 진입.
- 이하 시 카드사별 한계 `docs/limitations/{provider}.md` + Phase 5 부분 진입 검토.

# 본 ADR 가 다루지 않는 것 (out of scope)

- **OCR Hybrid LLM 빈 가맹점명 응답** (결함 3) — prompt 강화 또는 retry 로직. 별도 ADR-009 또는 Phase 5 작업.
- **provider 감지** — ADR-007 에서 해결됨.
- **합성 fixture 의 PII 마스킹 갱신** — 현재 ADR-003 으로 충분.

# 우선순위 / 일정 가이드

1. **즉시 (Q2 진행 세션 도입 시)**: shinhan 정규식 보강 — 1 카드사 18 파일이 가장 큰 비중.
2. **다음**: samsung 4 파일 정규식 보강.
3. **마지막**: kbank 2 파일 변형 정규식.

ADR 본문 변경 없이 본 deferred → in_progress → accepted 전환 가능.
