---
id: ADR-007
title: Provider 감지 text-aware 전환 — PDF font encoding 우회
date: 2026-05-12
status: accepted
supersedes:
  - ADR-004 §"이중 게이트" — byte fingerprint 가정 (PDF font encoding 으로 무효 판명)
refs:
  - tests/smoke/results/20260512.md (1차 smoke 26% 통과율 진단)
  - synthesis/04-design.md §"Provider 식별"
---

# 결정

`router.detect_provider()` 시그니처를 다음으로 확장:

```python
def detect_provider(
    content: bytes,
    filename: str = "",
    *,
    extracted_text: str | None = None,
) -> CardProvider
```

탐지 단계 (early-return on first match):
1. **byte ASCII 시그니처** — URL 등 raw bytes 에 직접 존재하는 것 (`shinhancard.com`, `hyundaicard.com`, `Hyundai Card`, `kbank.com`, `kakaobank` 등).
2. **추출 텍스트 한글 시그니처** — `extracted_text` 가 주어진 경우 한글 카드사명 매칭 (`신한카드`, `삼성카드`, `우리카드`, `현대카드`, `케이뱅크`, `롯데카드`, `하나카드`, `카드매출 온라인전표`).
3. **우리카드 N-up dual gate** (text-based) — 추출 텍스트에 `"국내전용카드"` + 9500-BIN 패턴(`9500-\*{4}-\*{4}-\d{4}`) 모두 매칭 시.
4. **현대카드 파일명 hint** — 이미지 PDF 의 텍스트 추출 None 시 fallback.

`ParserRouter.parse()` 가 텍스트 임베디드 PDF 에 한해 `extract_pdf_text()` 1 회 호출 후 결과 캐시 → `detect_provider()` 와 `rule_based_parser.parse()` 양쪽이 동일 텍스트 가용성 가짐.

# 컨텍스트 — 결함 진단 (1차 smoke 11/42 = 26%)

PDF 의 한글 텍스트는 raw bytes 에 UTF-8 로 존재하지 않음. pdfplumber 의 ToUnicode mapping 으로 추출 시점에만 한글 가시화. 결과:

| PDF | `"카드사".encode() in raw_bytes` | extracted text 한글 |
| --- | --- | --- |
| `woori_nup_01.pdf` | ❌ False | ✅ "국내전용카드" |
| `shinhan_01.pdf` | ❌ False | ✅ "신한카드" |
| `samsung_01.pdf` | ❌ False | ✅ "삼성카드" |

영향: `_PROVIDER_SIGNATURES` 의 `"한글카드사명".encode()` 항목 모두 무용. ASCII URL 없는 카드사 (우리 N-up·삼성 일부) 는 provider="unknown" → OCR Hybrid 강제. 결과적으로 ADR-004 의 우리 N-up RuleBased 가 진입조차 못함 (unit 테스트는 parser 직접 호출이라 통과했음).

# 보안 분석

- 텍스트 추출은 pdfplumber 내부 처리 — 외부 입력 신뢰 없음 (CLAUDE.md §"외부 입력 신뢰 금지" 무관).
- 파일명 hint 는 hyundai 이미지 PDF 만 — 라우팅 hint 일 뿐, 권한·인증과 무관.
- 우리 dual gate 의 두 게이트 (마커 + BIN) 모두 텍스트 내용에서 검증되므로 단일 텍스트만으로 위변조 불가 (PDF 생성 시 두 패턴 동시 위조 필요).

# 보안 — 텍스트 추출 비용 분석

- `extract_pdf_text()` 는 동기 IO → `asyncio.to_thread()` 로 wrap.
- 비용 ~50-200ms/PDF. text-embedded PDF 만 실행 (스캔본 None).
- rule_based parser 가 다시 텍스트 추출하는 중복 작업 — Phase 5 에서 cache 공유 리팩토링 검토 (현재는 단순성 우선).

# 영향

- woori_nup_*.pdf 의 RuleBased 가 즉시 활성화 (텍스트에 "국내전용카드" + 9500 BIN 매칭).
- shinhan/samsung/kbank 의 한글 시그니처 매칭 활성화 (다만 rule_based regex 가 별개 결함 ADR-008 으로 분리).
- hyundai 이미지 PDF 는 파일명 hint fallback 으로 정상 (텍스트 추출 None).
- 모든 호출자 — `router.parse()` 가 텍스트 캐싱하므로 변경 없음.

# 대안 폐기

| 대안 | 폐기 사유 |
| --- | --- |
| **byte ASCII 시그니처만 유지 + 한글 시그니처 제거** | URL 없는 카드사 (우리 N-up, 삼성 일부) provider=unknown → OCR 강제. ADR-004 우리 N-up 전체 무효화. |
| **filename hint 만으로 provider 결정** | CLAUDE.md §"외부 입력 신뢰 금지" 위반. 위·변조 파일명으로 라우팅 우회 가능. |
| **detect_provider 내부에서 lazy 텍스트 추출** | `detect_provider` 가 pdfplumber 의존 → 단위 테스트 시 mock 부담 증가. caller 가 cache 결정하는 편이 명확. |
| **현 byte-only 유지, 후속 phase 에 이전** | 1차 smoke 26% 결과 그대로 → Phase 5 진입 불가. 우선 처리 정당. |

# 후속

- **ADR-008** (rule_based regex 보강) — 실 PDF layout 기반 정규식 보강. 본 ADR 가 provider 식별을 해결해도 parser 자체 정확도는 별개.
- **Phase 5+ 텍스트 cache 공유** — router 가 추출한 텍스트를 rule_based parser 에 전달해 중복 작업 제거.
