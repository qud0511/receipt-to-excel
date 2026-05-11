# Phase 4 — Parsers + Resolvers — DONE (Smoke Gate 사용자 액션 대기)

- 완료일: 2026-05-11
- 브랜치: 로컬 `main` → `origin/v4`
- Phase 4 commit 범위: `b0f3ace` (Phase 3 종료) ~ Task 4.8 (smoke suite + done)

## 산출 모듈

| 영역 | 파일 | 책임 |
|---|---|---|
| ParseError 계층 | `app/services/parsers/base.py` | `ProviderNotDetectedError` / `ParserNotImplementedError` / `RequiredFieldMissingError` / `FormatMismatchError` / `LLMDisabledError` 5종 |
| 룰 기반 — 완전 구현 | `rule_based/shinhan.py` | pdfplumber + AD-2 canonical + 정규식 8종 |
| 룰 기반 — 완전 구현 | `rule_based/samsung.py` | 합계금액 vs 이용금액 구분 + 거래일자 분리 |
| 룰 기반 — 완전 구현 | `rule_based/kbank.py` | `[\d,]+ 원` 공백 + 공급가액/부가세 None |
| 룰 기반 — stub | `rule_based/{hana,woori,lotte}.py` | `ParserNotImplementedError` → OCR Hybrid fallback |
| OCR Hybrid | `ocr_hybrid/docling_service.py` | 한글 EasyOCR (`lang=["ko","en"]`) + 무거운 분석 비활성 |
| OCR Hybrid | `ocr_hybrid/ollama_vision_client.py` | `temperature=0.0` + `format="json"` + PIL Image base64 |
| OCR Hybrid | `ocr_hybrid/prompt.py` | `<<<OCR_HINT_BEGIN>>>...<<<END>>>` injection 방어 |
| OCR Hybrid | `ocr_hybrid/parser.py` | Hallucination 방어 2단 체인 (JSON parse + Pydantic strict) |
| OCR 후처리 | `ocr_hybrid/postprocessors/kakaobank.py` | 국내매입/해외매입 prefix 제거, 점(.) 구분자 거래일, 유효기간 suffix 제거 |
| LLM-only | `llm/llm_parser.py` | `enabled=False` 인스턴스화 차단 (defence-in-depth) |
| LLM-only | `llm/prompt.py` | OCR Hybrid system prompt 재사용 |
| Resolver | `resolvers/card_type.py` | 3-tier deterministic + AD-2 silent fail 방어 |
| Resolver | `resolvers/category_classifier.py` | `config/category_rules.json` substring 매핑 |
| Resolver | `resolvers/note_generator.py` | R6 + meal_type boundary inclusive |
| Resolver | `resolvers/vendor_matcher.py` | autocomplete `DEFAULT_LIMIT=8` (vendor_repo wrapper) |
| config | `config/category_rules.json` | 19 키 + `__default__: 기타비용` |
| config | `config/meal_type_rules.json` | 조식 [6,10] / 중식 [11,14] / 석식 [17,21] |
| Router | `parsers/router.py` | `pick_parser()` (Phase 3) + `parse()` (Phase 4: rule→OCR→LLM fallback + tier_skipped 구조화 로그) |

## 테스트 카운트

총 **120 단위 통과** + **39 smoke 수집** (`-m real_pdf` 명시 시만 실행):

| Phase | 파일 | 케이스 |
|---|---|---|
| 1~3 회귀 | (전 phase 동일) | 62 |
| 4.1 | `test_other_rule_based_stubs.py` | 6 (stubs + router fallback + 구조화 로그) |
| 4.2 | `test_shinhan_parser.py` | 7 (AD-1/AD-2/AD-4 + 필수/optional/raise) |
| 4.3 | `test_samsung_parser.py` + `test_kbank_parser.py` | 12 |
| 4.4 | `test_ocr_hybrid_parser.py` | 9 (Docling config + Ollama payload + prompt + PII) |
| 4.5 | `test_kakaobank_postprocessor.py` | 4 |
| 4.6 | `test_llm_parser.py` | 3 |
| 4.7 | `test_card_type_resolver.py` + `test_category_classifier.py` + `test_note_generator.py` + `test_vendor_matcher.py` | 17 |
| 4.8 | `tests/smoke/test_real_pdfs.py` | 39 (parametrize, real_pdf marker) |
| **합계** | — | **120 단위** + **39 smoke** |

분류: 단위 118 / 통합 2 / e2e 0 / smoke 39.

## Phase 4 DoD 게이트

- [x] **Shinhan rule parser** 합성 픽스처 7 케이스 통과
- [x] **Samsung rule parser** 합성 픽스처 6 케이스 통과 (격상)
- [x] **KBank rule parser** 합성 픽스처 6 케이스 통과 (신규)
- [x] **Kakaobank OCR postprocessor** 4 케이스 통과
- [x] **하나/우리/롯데 stub** `ParserNotImplementedError` → Router OCR fallback (6 케이스)
- [x] **`ParseError` 4 subclass** 로그에 사유별 구분 기록 (`tier_skipped="rule_based:stub"` 등)
- [x] **OCR Hybrid** 합성 mock 으로 동일 schema 반환 + `temperature=0.0` + `format=json` + 디리미터 + Pydantic strict
- [x] **LLM parser** `enabled=False` 기본 — 인스턴스화 자체 차단
- [x] **4 Resolver** 각각 5/5/4/3 = 17 케이스 통과
- [x] **`category_rules.json` 변경만으로 새 카테고리** 추가됨 입증
- [x] **모든 prompt** 가 OCR 텍스트를 `<<<OCR_HINT_BEGIN>>>...<<<END>>>` 로 감쌈
- [x] `pytest`, `mypy --strict`, `ruff`, `pip-audit` 통과

## Phase 5 진입 게이트 — **사용자 액션 대기**

CLAUDE.md §"특이사항: Smoke Gate" — Phase 5 진입 전 실 카드사 자료 11+ 파일 검증 필수.

### 진입 조건

1. **OCR 의존성 설치**:
   ```bash
   cd /bj-dev/v4 && uv sync --extra ocr
   ```
2. **Ollama 인스턴스 가동** — `gemma4` 모델 `http://localhost:11434` 로딩.
3. **Smoke 실행**:
   ```bash
   uv run pytest tests/smoke/ -m real_pdf --no-header -q
   ```
4. **결과 기록 확인** — `tests/smoke/results/YYYYMMDD.md` 생성 + 39 파일 행.
5. **실패 케이스 해소**:
   - parser/postprocessor 보강 (정규식 추가), 또는
   - 합성 fixture 보강 + 알려진 한계 `docs/limitations/` 문서화.

### 보유 실 자료 (`tests/smoke/real_pdfs/` — 39 파일)

| provider | 갯수 | 기대 `parser_used` |
|---|---|---|
| `shinhan_*.pdf` (택시 포함) | 12 + 6 = 18 | `rule_based` |
| `samsung_*.pdf` | 8 | `rule_based` |
| `kbank_*.pdf` | 5 | `rule_based` |
| `kakaobank_*.jpg` | 3 | `ocr_hybrid` + postprocessor |
| `hana_*.jpg` | 2 | `ocr_hybrid` (stub fallback + 로그) |
| `woori_*.jpg` | 2 | `ocr_hybrid` (stub fallback + 로그) |
| `lotte_*.pdf` | 1 | `ocr_hybrid` (stub fallback + 로그) |

## 인프라 결정사항 (Phase 4)

1. **`[project.optional-dependencies].ocr`**: easyocr + docling 분리. CI 기본 제외 → 빌드 시간 단축. smoke 실행 시만 `uv sync --extra ocr`.
2. **`pillow>=12.2` production**: pdfplumber transitive 가 가져옴 + CVE-2026-42309/10/11 패치.
3. **`tests/**` per-file-ignore N802/N806**: 한글 함수명/변수명 허용 (도메인 사양 명시).
4. **pytest `addopts -m "not real_pdf"`**: 기본 실행 시 smoke 자동 제외. `-m real_pdf` 명시 시만 실행.
5. **smoke fixture 분리**: `tests/smoke/real_pdfs/` (.gitignore) + `tests/smoke/results/` (.gitignore). PII 자료 git 누출 0건 보장.
6. **`_OllamaLike` Protocol image: `PILImage | None`**: `OllamaVisionClient.generate` 와 정확 매칭 — mypy strict Protocol covariance 호환.

## 확장 포인트 검증 ✅

- 새 카드사 = `rule_based/{provider}.py` 1 파일 + Router signature 1 줄. Samsung/KBank/Hana/Woori/Lotte 모두 이 패턴.
- 새 카테고리 = `config/category_rules.json` 키 추가 + `test_new_category_added_via_config_file_without_code_change` 입증.
- 새 meal_type = `config/meal_type_rules.json` 동일 패턴.
- 새 OCR 후처리기 = `ocr_hybrid/postprocessors/{name}.py` + 라우팅 시그니처 등록.

## Phase 5 의존성

- Phase 4 산출: Router + 6 rule_based + OCR Hybrid + LLM + 4 Resolver + 2 config JSON
- Phase 5 작업:
  - `services/templates/` — TemplateConfig 등록 + 분석 (XLSX 매핑)
  - `services/xlsx_writer/` — R13 행 복제 + formula_cols 보호 + SUM 수식
  - `services/pdf_generator/` — evidence PDF 병합 (PIL 기반)
  - 신규 의존성: `openpyxl`, `python-multipart` (업로드)
