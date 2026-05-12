---
id: ADR-004
title: 우리카드 N-up 매출전표 RuleBasedParser 설계 — 라벨 없는 위치 기반 layout + 이중 게이트
date: 2026-05-12
status: accepted
supersedes:
  - synthesis/05 §"우리카드 stub" (raw layout 가정 부재 시 ParserNotImplementedError 만 발생)
refs:
  - synthesis/04-design.md §ParserBase / §Provider 식별
  - ADR-003 (실 fixture 정규화)
  - tests/smoke/results/20260512.md (Phase 4 1차 smoke 결과)
note:
  - "Task 3 의 원 ADR-004(parser-returns-list)은 본 ADR 와 충돌하여 ADR-005 로 재번호.
     Task 5 의 expense-template-analysis 는 ADR-006 로 시프트."
---

# 결정

우리카드 N-up 매출전표를 위한 RuleBasedParser 는 다음 3 원칙으로 구현한다.

1. **라벨 없는 위치 기반 line block 추출** — 발행본에 필드 라벨이 없으므로 정규식 라벨 매칭 불가.
   `국내전용카드` 마커 line 이후 14~16 개 line 을 순서 고정 인덱스로 매핑.
2. **4-line 금액 위치 추정** — 순서 `① 거래금액 ② 봉사료 ③ 부가세 ④ 자원순환보증금`.
   부가세 비율(`vat ≈ 거래금액 x 10/110, ±1`)로 검증 가드 작동.
3. **provider 식별은 이중 게이트** — 파일명 hint + 텍스트 fingerprint 두 조건 모두 매칭 시
   `provider=woori` 로 라우팅. 단일 hint 만으로는 라우팅 금지.

# 컨텍스트

## 실 자료 분석 (`tests/smoke/real_pdfs/woori_nup_0{1,2}.pdf`)

- pdfplumber 텍스트 추출 결과, 한 페이지에 2x2 또는 2x1 grid 로 매출전표가 N-up 배치.
- 브랜드명(`우리카드`/`wooricard.com`) 이 본문에 부재 — Phase 4 의 byte 시그니처 매칭 실패.
- 각 거래 블록은 13~15 line, 라벨 없이 값만 출력. 좌·우 열의 같은 행은 공백으로 join.
- 금액 4 line 의 의미 추정 근거: `woori_nup_01.pdf` 거래 1 — `거래금액=70,000, vat 추정 line=6,364`.
  `70,000 x 10/110 ≈ 6,364` → line 3 = 부가세 확정. 1/2/4 는 다른 N-up 케이스 검증 시 모두 0 원이라
  완전 검증 불가. **추정의 한계는 본 ADR 의 명시 한계**.

## 보안 — 파일명 신뢰 분석 (CLAUDE.md §"외부 입력 신뢰 금지")

- 파일명은 사용자 업로드 origin 이라 변조 가능. 단독 사용 금지.
- 그러나 본 결정에서 파일명은 **provider routing hint** 일 뿐 인증/권한/사용자 식별과 무관.
- 동시에 텍스트 fingerprint (`국내전용카드` byte 시그니처) 가 매칭되어야 woori RuleBased 로 진입.
- 두 게이트가 동시 매칭되지 않으면 OCR Hybrid 폴백 — RuleBased 가 잘못 선택돼도 OCR 이 catch.
- 위·변조된 파일명만으로는 절대 woori RuleBased 진입 불가 → 이중 게이트로 신뢰 위험 차단.

# 적용

## Parser 구현

| 영역                | 결정                                                                              |
| ------------------- | --------------------------------------------------------------------------------- |
| 블록 마커           | line 단독 또는 N-up 반복(`국내전용카드 국내전용카드`) 모두 매칭                   |
| 페이지 timestamp    | `^\d{4}\.\d{2}\.\d{2}\s*\d{2}:\d{2}:\d{2}$` line 은 skip                          |
| 카드번호            | raw `NNNN-NN**-****-NNNN` 또는 이미 canonical 둘 다 매칭 → AD-2 canonical 출력    |
| 거래일+시각         | `(\d{4})/(\d{2})/(\d{2})\s*(\d{2}):(\d{2}):(\d{2})` (공백 옵션)                   |
| 금액 4-line         | block[3..6] 순서 고정: 거래금액 / 봉사료 / 부가세 / 자원순환보증금                |
| 가맹점명            | block[8] (마커+카드+일시+할부+4금액+승인=8 line 이후 첫 line)                     |
| 주소 + 가맹점번호    | block[9..k] 가 주소(1~2 line), block[k] = 9 자리 단독 line = 가맹점번호           |
| 공급가액 계산        | `거래금액 - 봉사료 - 부가세 - 자원순환보증금` (음수/0 시 None)                    |
| 비율 가드            | `vat == 0` 또는 `\|vat - round(total x 10/110)\| <= 1` → 실패 시 경고 + confidence 강등 |

## Confidence 정책

| 필드               | 라벨    | 근거                                                            |
| ------------------ | ------- | --------------------------------------------------------------- |
| 가맹점명/거래일/거래시각/금액 | high    | block 위치 + 정규식 exact match — 직접 검증                     |
| 카드번호_마스킹     | high    | canonical 정규식 통과 + AD-2 도메인 검증                        |
| 승인번호           | high    | 8 자리 정규식 통과 시                                           |
| 부가세             | medium  | 위치 추정 + 비율 가드 통과. 가드 실패 시 low + 경고 로그        |
| 봉사료/자원순환보증금 | low     | 위치 추정만, 비율 검증 불가 (대부분 0 원). 발행 양식 변경 조기 감지 책임 |
| 공급가액            | medium  | 4 line 계산 결과                                                |
| 업종               | none    | 우리카드 발행본에 업종 필드 부재                                |

## Provider 이중 게이트 (`router.detect_provider`)

```python
filename_hint = filename.lower().startswith("woori") or "우리카드" in filename
fingerprint = "국내전용카드".encode() in content
→ provider = "woori" iff filename_hint AND fingerprint
```

# 영향

- **Phase 4 smoke 결과 개선**: `woori_nup_*.pdf` 가 RuleBased 로 진입 → 텍스트 임베디드 PDF
  의 신뢰도·속도 모두 OCR Hybrid 대비 향상 (예상 < 1s/file vs OCR 30~40s).
- **N-up 분할은 본 ADR 외 — Task 3 ADR-005 (parser returns list) 에서 다룸**.
  본 ADR 의 Parser 는 첫 transaction block 만 반환 (단일 거래 시나리오).
- **legacy `woori_*.jpg` (스캔 이미지)** 는 텍스트 임베딩 없음 → 여전히 OCR Hybrid 경로
  (rename 후 `woori_legacy_*.jpg`, ADR-003).

# 한계 — 향후 검증 필요

1. **4-line 금액 순서 추정**: nup_01 (자연에너지 70,000) 만으로 line 3 = 부가세 확정.
   line 1 (봉사료) / line 4 (자원순환보증금) 의 위치는 0 원 데이터로 검증 불가.
   → 0 원이 아닌 봉사료/자원순환 발행 케이스 확보 시 위치 재검증 필수. 검증 실패 시 본 ADR 갱신.

2. **가맹점명 휴리스틱**: block[8] 이라는 절대 위치는 카드번호/일시/할부/4금액/승인 6 line 정확 가정.
   할부 라벨이 결손되거나 4-line 금액이 3-line 으로 줄어드는 발행 변형은 차후 발견 시 보강.

3. **dual-gate 우회 시나리오**: 사용자가 `woori_attack.pdf` 로 위장한 비-우리카드 PDF 를 업로드할 때.
   현재는 `국내전용카드` 마커가 없으므로 unknown → OCR Hybrid. 마커가 우연히 포함된 비-우리 PDF
   가 있다면 woori parser 가 실패하고 `RequiredFieldMissingError` 로 fallback. 안전.

# 대안 폐기

| 대안                                    | 폐기 사유                                                                |
| --------------------------------------- | ------------------------------------------------------------------------ |
| 합성 fixture 만으로 라벨 기반 parser 유지 | v1 회귀(`합성에만 통과`) 패턴. 실 자료 검증 부재 시 운영 즉시 실패.       |
| 우리카드를 항상 OCR Hybrid 로            | 텍스트 임베디드 PDF 를 OCR 로 처리하면 30s+ 지연 + 정확도 손실.           |
| 파일명만으로 provider 식별                | CLAUDE.md §"외부 입력 신뢰 금지" 위반. 위·변조 파일명으로 라우팅 우회 가능. |
| 텍스트 fingerprint 만으로 provider 식별   | `국내전용카드` 가 비-우리 카드사에도 사용되면 오탐. 보조 게이트 필요.     |
