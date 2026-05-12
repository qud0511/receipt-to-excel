---
id: ADR-005
title: Parser 시그니처를 list[ParsedTransaction] 반환으로 변경
date: 2026-05-12
status: accepted
supersedes:
  - synthesis/04-design.md §"BaseParser.parse" 단일 반환 정의 (마이그레이션 1회)
refs:
  - ADR-004 (우리카드 N-up layout — list 반환 동기)
  - synthesis/04-design.md §"BaseParser ABC"
note:
  - "원 사용자 명세의 'ADR-004-parser-returns-list' 는 ADR-004 가 우리카드 N-up 분석으로
     이미 점유되어 본 ADR-005 로 시프트. Task 5 의 ADR 은 ADR-006 으로 시프트."
---

# 결정

`BaseParser.parse()` 와 `ParserRouter.parse()` 의 반환 타입을 단일 `ParsedTransaction` 에서
**list[ParsedTransaction]** 으로 변경한다. 단일 거래 PDF/JPG 도 길이 1 list 로 반환.

```python
# 변경 전
async def parse(self, content: bytes, *, filename: str) -> ParsedTransaction: ...

# 변경 후
async def parse(self, content: bytes, *, filename: str) -> list[ParsedTransaction]:
    """빈 list 금지 — 실패는 ParseError. 단일 거래도 [tx] 형태."""
```

# 이유

1. **우리카드 N-up 발행** (ADR-004) — 한 PDF 에 4~5 거래가 grid 로 배치됨.
   단일 반환 가정 시 N-1 거래 데이터 손실.
2. **확장성** — 다른 카드사 향후 N-up 발행 가능성. parser interface 가 단일 거래로
   고정되면 매번 라우터 분기 + 호출자 처리 부담.
3. **호출자 단순화** — 일관 list 계약. `for tx in await parser.parse(...)` 가 단일·다중 동일 코드.

# 적용 — 마이그레이션 변경 영역

## App 영역 (6 파일)

| 파일                                              | 변경                                              |
| ------------------------------------------------- | ------------------------------------------------- |
| `app/services/parsers/base.py`                    | abstract sig → `list[ParsedTransaction]` + docstring 갱신 |
| `app/services/parsers/rule_based/shinhan.py`      | `return [self._parse_from_text(text)]`            |
| `app/services/parsers/rule_based/samsung.py`      | `return [self._parse_from_text(text)]`            |
| `app/services/parsers/rule_based/kbank.py`        | `return [self._parse_from_text(text)]`            |
| `app/services/parsers/rule_based/woori.py`        | **N-up column 추출 + splitter → list 반환** (실 다중-tx 지원) |
| `app/services/parsers/rule_based/hana.py`         | sig 변경만 (stub raise — 반환 없음)               |
| `app/services/parsers/rule_based/lotte.py`        | sig 변경만 (stub raise)                           |
| `app/services/parsers/ocr_hybrid/parser.py`       | 단일 결과 list 1 래핑                             |
| `app/services/parsers/llm/llm_parser.py`          | 단일 결과 list 1 래핑                             |
| `app/services/parsers/router.py`                  | `parse()` return type → `list[ParsedTransaction]` (구현 변경 無 — passthrough) |
| `app/services/parsers/preprocessor/nup_splitter.py` | **신규** — `split_by_marker(text, marker) -> list[str]` |

## 테스트 영역 (9 파일)

- 모든 `result = await parser.parse(...)` → `[result] = await parser.parse(...)` 패턴으로 변경
  (단일 결과 length 1 list 를 unpack — 길이 위반 시 ValueError 즉시).
- StubParser 클래스 `parse()` 도 `return [tx]` 로 갱신.
- 신규 테스트:
  - `tests/unit/test_nup_splitter.py` — splitter 단위 (7 케이스)
  - `tests/unit/test_woori_parser.py` 추가 — 실 PDF 다중-tx 검증
    (`test_extracts_4_transactions_from_nup_01`, `test_extracts_5_transactions_from_nup_02` —
    `@pytest.mark.real_pdf` + `@pytest.mark.skipif(not Path.exists())`).

# 영향

- **breaking change** — 외부 호출자(api layer 후속 Phase 5) 가 list 처리 필요. Phase 5 시작 전이라
  이번 마이그레이션 1회로 충분.
- **CLI 단일 호출 시나리오 (Phase 5+ extraction service)**: list 의 모든 거래를 별도 row 로
  TX 테이블에 저장 (1 file → N row).
- **smoke 결과 보고서**: 1 파일당 1 row 가 아니라 N row 기록 (woori_nup_01.pdf → 4 row). 다만 본
  마이그레이션 시점에 smoke runner 는 `[result] = await router.parse(...)` 단일 unpack 사용 — 
  N-up 파일은 ValueError 로 명시 실패. Task 6 에서 smoke runner 가 list iterate 형태로 갱신
  후 woori_nup 도 통과 가능.

# 대안 폐기

| 대안                                            | 폐기 사유                                                                       |
| ----------------------------------------------- | ------------------------------------------------------------------------------- |
| `parse_single() → ParsedTransaction` + `parse_all() → list` 별도 메서드 유지 | 호출자가 분기 부담. 회귀 위험 (호출자 실수로 single 호출 시 N-1 거래 손실). |
| 우리카드 전용 `parse_nup()` 만 추가              | 다른 N-up 카드사 추가 시 또 같은 분기. 인터페이스 일관성 손실.                    |
| `Generator[ParsedTransaction]` (yield)           | async + generator 조합 복잡도 증가. list 가 충분히 간결.                          |

# 후속

- Phase 5 extraction service 가 list 처리 시 SSE 진행 보고 단위를 "거래 1건당" 으로 세분화 가능.
- smoke 결과 보고서 row 수 = 실제 거래 수 (파일 수 ≠ 거래 수). Phase 4 종료 보고서 갱신 필요.
