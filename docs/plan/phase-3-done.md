# Phase 3 — Domain Models + Confidence Policy + Parser Base — DONE

- 완료일: 2026-05-11
- 브랜치: 로컬 `main` → `origin/v4`
- Phase 3 commit 범위: `b8338c8` (Task 3.1) → `ffe980f` (Task 3.2) → `7abf0ff` (Task 3.3) → Task 3.4 마무리

## 산출 모듈

| 영역 | 파일 | 책임 |
|---|---|---|
| 도메인 | `app/domain/__init__.py` | 패키지 헤더 — db/services/api 의존 금지 표명 |
| 도메인 | `app/domain/confidence.py` | `ConfidenceLabel = Literal["high","medium","low","none"]` |
| 도메인 | `app/domain/parsed_transaction.py` | `ParsedTransaction` (한글 필드 + AD-1/AD-2/AD-4 강제) + `CardProvider`/`ParserUsed` Literal |
| 도메인 | `app/domain/expense_record.py` | 사용자 검수 결과 + 자동 결정 필드 (도메인 layer) |
| 도메인 | `app/domain/card.py` | 카드 (`카드번호_마스킹` AD-2 pattern) |
| 도메인 | `app/domain/{vendor,project,user,attendee}.py` | 도메인 엔티티 4종 |
| 도메인 | `app/domain/template_map.py` | `SheetConfig` + `TemplateConfig` (3 modes / sum_row 보호 / formula_cols set→list) |
| 서비스 | `app/services/extraction/confidence_labeler.py` | 4-label 매핑 (rule/OCR/LLM/user) — UI 색상 코딩 단일 진실의 출처 |
| 서비스 | `app/services/parsers/base.py` | `BaseParser` ABC + `ParseError` (field/reason/tier_attempted) + `FieldNotFoundError`/`FormatMismatchError` |
| 서비스 | `app/services/parsers/pdf_text_probe.py` | byte-level `BT` 토큰 검사 (스캔 vs 텍스트 PDF) |
| 서비스 | `app/services/parsers/router.py` | provider 감지 + tier 라우팅 (Rule > OCR > LLM) |

## 테스트 카운트

총 **62 케이스 통과** (`pytest -q` 62 dots):

| 파일 | 케이스 | 갯수 |
|---|---|---|
| Phase 1 회귀 (scaffold/auth/logging/errors) | — | 18 |
| Phase 2 회귀 (db_models/repositories/migrations) | — | 16 |
| `tests/unit/test_domain_parsed_transaction.py` | canonical / non-canonical / amount gt 0 / 4-label / merchant immutable | 5 |
| `tests/unit/test_confidence_labeler.py` | rule 3 + OCR 4 + LLM 1 + user 1 | 9 |
| `tests/unit/test_template_map.py` | formula_cols 직렬화 / sum_row 보호 / 3 modes | 3 |
| `tests/unit/test_parser_router.py` | shinhan/hana/unknown 감지 / text_embedded probe / rule/ocr/llm 선택 / ParseError raise / **ParseError 필드 보유 (DoD)** | 10 |
| `tests/unit/test_domain_isolation.py` | **도메인 모듈 격리 (DoD)** — AST walk 으로 db/services/api import 검출 | 1 |

분류: 단위 60 / 통합 2 / e2e 0 / smoke 0.

## Phase 3 DoD 게이트

- [x] **도메인 모듈은 db/services/api 어떤 것도 import 하지 않음**
  - `test_domain_isolation.py` 가 AST walk 으로 정적 검증 — 7 도메인 모듈 0건 위반
  - import-linter 도입은 향후 ADR 로 검토 (현재 AST 검사로 충분)
- [x] **`ParsedTransaction` 검증: canonical 카드번호 + 양수 금액 + 4-label confidence**
  - AD-2 pattern `^\d{4}-\*{4}-\*{4}-\d{4}$`, `금액: Field(gt=0)`, `field_confidence: dict[str, ConfidenceLabel]`
- [x] **confidence labeler 9 케이스 통과**
- [x] **ParserRouter 9 케이스 통과 (모의 PDF bytes 픽스처)**
- [x] **`ParseError` 가 `field`, `reason`, `tier_attempted` 필드 보유**
  - `test_parse_error_has_field_reason_tier_attempted` 직접 검증
- [x] `pytest`, `mypy --strict`, `ruff` 통과
- [x] `pip-audit --strict` clean

## 인프라 결정사항 (Phase 3)

1. **도메인은 pydantic BaseModel** (synthesis 의 `@dataclass` 표기는 추상적 의미로 해석): JSON 직렬화 + computed_field + field_serializer 활용. `SheetConfig.formula_cols (set[str])` → JSON 호환 `sorted(list[str])` 직렬화는 `@field_serializer` 가 처리.
2. **provider signature 매칭**: UTF-8 raw bytes (`"신한카드".encode()`) — PDF 텍스트 추출 없이 byte search 만으로 1차 라우팅. 정확도 향상은 후속 phase 의 `pdfplumber` 도입 시점에 본 모듈 신호 + 추출 텍스트 동시 사용으로 발전.
3. **`pdf_text_probe` byte-level heuristic**: `BT` 토큰 in `content` — Phase 3 외부 의존성 0개 원칙. 후속에서 `pdfplumber.PDF(io.BytesIO(c)).pages[0].extract_text()` 등으로 교체해도 시그니처 유지.
4. **`ParserRouter.pick_parser` 우선순위**: RuleBased (provider known + text embedded) > OCR Hybrid > LLM (명시적 활성화 시) — CLAUDE.md §"특이사항: 추출 우선순위" 정확 일치.
5. **`@computed_field` + `@property`** 조합: pydantic v2 의 `[prop-decorator]` mypy 이슈는 `# type: ignore[prop-decorator]` 한 줄로 한정 (사유 주석 함께).

## Phase 4 진입 의존성

- Phase 3 산출: `BaseParser` ABC + `ParseError` 계층 + `ParserRouter` + `ParsedTransaction` 계약 + `ConfidenceLabeler` + `TemplateConfig`
- Phase 4 작업:
  - `services/parsers/rule_based/{shinhan,samsung,kbank}.py` (3 파서)
  - `services/parsers/rule_based/postprocess_kakaobank.py` (OCR 후처리)
  - `services/parsers/ocr_hybrid/{...}.py` — EasyOCR + 정규식 후처리
  - `services/parsers/llm/{...}.py` — Ollama gemma4 (선택)
  - `services/extraction/{card_type_resolver,vendor_resolver,project_resolver,note_generator}.py`
- 확장 포인트: 새 카드사 = `rule_based/{provider}.py` 1 파일 + Router signature 1 줄 (CLAUDE.md §"코드 구조")
