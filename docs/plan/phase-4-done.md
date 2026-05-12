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
| 룰 기반 — stub | `rule_based/{hana,hyundai,lotte}.py` | `ParserNotImplementedError` → OCR Hybrid fallback |
| 룰 기반 — 완전 구현 | `rule_based/woori.py` | N-up 위치 기반 layout (ADR-004) + splitter (ADR-005) — 1 파일 → N 거래 |
| 전처리 | `parsers/preprocessor/nup_splitter.py` | 마커 기반 단일 컬럼 텍스트 분할 (ADR-005) |
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
| `woori_legacy_*.jpg` | 2 | `ocr_hybrid` (stub 없음 — 텍스트 미임베디드 이미지) |
| `woori_nup_*.pdf` | 2 | `rule_based` (N-up 4·5 거래, ADR-004) |
| `hyundai_01.pdf` | 1 | `ocr_hybrid` (stub fallback — 이미지 PDF) |
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
  - `services/templates/` — TemplateConfig 등록 + 분석 (XLSX 매핑) — **ADR-006 명세 따름**
  - `services/xlsx_writer/` — R13 행 복제 + formula_cols 보호 + SUM 수식
  - `services/pdf_generator/` — evidence PDF 병합 (PIL 기반)
  - 신규 의존성: `openpyxl`, `python-multipart` (업로드)

---

## Phase 4 최종 종료 — 보완 작업 (2026-05-12)

Phase 4 1차 smoke 결과 후 발견된 미해결 사항 5건 일괄 처리:

### 산출

| 영역 | 결정 | ADR |
| --- | --- | --- |
| 실 fixture 정규화 | PII 한글명 → ASCII-safe 영문명 매핑 + `real_templates/` 추가 (.gitignore) | ADR-003 |
| 우리카드 RuleBased 완전 구현 | 라벨 없는 위치 기반 N-up layout 분석 + 이중 게이트 (filename hint + 텍스트 fingerprint) | ADR-004 |
| Parser 인터페이스 | `list[ParsedTransaction]` 반환 + N-up splitter generic utility | ADR-005 |
| 현대카드 라우팅 | `hyundai` stub + 파일명 hint 보조 → OCR Hybrid 폴백 | ADR-005 §note |
| 지출결의서 양식 분석 | 3 장 실 양식 분석 + Phase 5 TemplateAnalyzer 명세 | ADR-006 |

### 확장 포인트 검증 (재확인) ✅

- **새 카드사 = 1 파일 추가**: hyundai stub 도입으로 6 → 7 rule_based, Router 변경 1 줄로 완료.
- **N-up 발행본 대응**: parser interface 가 list 반환이라 향후 다른 카드사 N-up 도입 시 분기 0.
- **양식 진화 대응**: ADR-006 의 휴리스틱 추출 → 사용자 양식 변경마다 코드 변경 0.

### 테스트 카운트 (Phase 4 최종)

| 영역 | Phase 4.1~4.8 | Phase 4 보완 (Task 1~5) | 합계 |
| --- | --- | --- | --- |
| 단위 | 118 | +18 (woori 11 + splitter 7 + hyundai 2 + router dual-gate 3 - woori stub 1) | **146** |
| 통합 | 2 | +1 (real_template_round_trip skip) | **3 (skip 1)** |
| smoke | 39 | +3 (woori_nup_01, woori_nup_02, hyundai_01) | **42** |
| **e2e/총합** | 159 | +22 | **181** |

mypy --strict + ruff + pip-audit 모두 통과.

### Smoke Gate 최종 결과 (2026-05-12, 30 분 42 파일 실행)

`tests/smoke/results/20260512.md` (PII 마스킹, 각 거래 row 별 기록).

| 지표 | 값 |
| --- | --- |
| PASSED | **11 / 42 = 26 %** |
| FAILED | 31 / 42 (모두 `가맹점명=''` — OCR 빈 문자열) |
| 사용자 임계값 | 70 % 미만 → **멈춤 + 분석 보고** (현재 26 % → 임계 위반) |
| 단위/통합 회귀 | 146 / 3 (skip 1) — 0 건 회귀, mypy --strict + ruff 통과 |

#### PASSED 목록 (모두 OCR Hybrid 경로)

`hyundai_01.pdf` (신규) · `kbank_{01,02,05}.pdf` · `lotte_01.pdf` · `samsung_{02,06,07,08}.pdf` · `woori_legacy_{01,02}.jpg`.

#### FAILED 분류

- 신한 18 (택시 6 포함) — 전부 OCR 폴백 후 빈 가맹점명
- 삼성 4 (samsung_{01,03,04,05}) — 동일 패턴
- 케이뱅크 2 (kbank_{03,04}) — LLM 일관성 부족
- 카카오뱅크 3 — OCR 후처리 후 빈 가맹점명
- 하나 2 (JPG) — 빈 가맹점명
- 우리 N-up 2 (woori_nup_{01,02}.pdf) — RuleBased 미적용 (근본 원인 §아래)

### 근본 원인 — provider 감지 + parser layout 양쪽 모두 사전 결함

#### 결함 1: PDF 한글 시그니처 byte 매칭 불가 (모든 카드사 영향)

PDF 내 한글 텍스트는 raw bytes 에 UTF-8 로 존재하지 않음. font ToUnicode mapping 으로 pdfplumber 추출 시점에만 한글 가시화.

| PDF | `"카드사".encode() in raw_bytes` | extracted text 한글 |
| --- | --- | --- |
| `woori_nup_01.pdf` | ❌ False | ✅ "국내전용카드" |
| `shinhan_01.pdf` | ❌ False | ✅ "신한카드" |
| `samsung_01.pdf` | ❌ False | ✅ "삼성카드" |

영향: `router.detect_provider()` 의 byte 매칭이 ASCII URL (`shinhancard.com` 등) 에만 의존. URL 없는 카드사 (우리 N-up · 삼성/케뱅크 일부) 는 provider="unknown" → OCR Hybrid 강제.

본 세션 Task 2 의 우리카드 N-up 이중 게이트 (filename + `"국내전용카드"` fingerprint) 도 동일 이유로 raw bytes 매칭 실패 → RuleBased 미적용 (unit 테스트는 parser 직접 호출이라 통과했음).

#### 결함 2: rule_based 정규식 vs 실 자료 layout 불일치 (provider 식별돼도 실패)

`shinhan_01.pdf` 추출 텍스트 일부:
```
26. 1. 2. 오전 11:21 카드매출전표 < 신한카드
2026.1.2\x0111:21:53           ← 점 구분자 + \x01 컨트롤 문자
```

shinhan parser 정규식 `(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2}):(\d{2})` (대시 + 공백) 미일치 → `RequiredFieldMissingError` → OCR 폴백. 합성 fixture (`make_shinhan_receipt`) 의 layout 이 실 자료와 다른 **v1 회귀 패턴**.

samsung / kbank 도 유사 layout 차이 의심.

#### 결함 3: OCR Hybrid LLM 의 가맹점명 빈 문자열 응답

OCR 폴백 후에도 31 / 42 에서 가맹점명 ''. ParsedTransaction 의 `가맹점명: str` 이 empty string 을 허용해 Pydantic strict 미차단. smoke assertion `assert result.가맹점명` 만 차단.

LLM (qwen2.5vl:7b) 의 응답 일관성 부족 — prompt 재설계 또는 빈 값 검증 후 retry 필요.

### 본 세션 5 작업의 실제 효과

| Task | 산출 | smoke 효과 |
| --- | --- | --- |
| 1: fixture 정규화 (ADR-003) | ✅ PII 마스킹 정상 | smoke 결과에 한글명 노출 0 — 정상 |
| 2: 우리카드 RuleBased (ADR-004) | ✅ unit 11/11 + real PDF 2/2 통과 | ❌ router 진입 실패 (결함 1) — 미적용 |
| 3: N-up splitter (ADR-005) | ✅ unit 7/7 + 마이그레이션 완료 | ❌ Task 2 와 동반 — 미적용 |
| 4: hyundai stub + OCR 라우팅 | ✅ filename hint 동작 | ✅ `hyundai_01.pdf` 통과 (신규 1 건) |
| 5: 지출결의서 분석 (ADR-006) | ✅ Phase 5 자료 + skip 통합 테스트 | N/A (Phase 5 범위) |

### Phase 5 진입 게이트 — **미충족**

진입 조건 (사용자 정의 70 % 통과) 미달. 4 결함 해소 필요:

1. **결함 1 (provider 감지)**: `detect_provider()` 를 text-aware 로 변경 — `is_text_embedded()` 가 이미 추출하는 텍스트 결과 캐시 사용. router 한 곳 + 호출자 1 줄. → Task 2 의 woori RuleBased 즉시 활성화 예상.
2. **결함 2 (rule_based layout)**: shinhan / samsung / kbank 정규식 보강 + 실 PDF 기반 unit 테스트 추가 (4 카드사 × 5 케이스 ~ 20 테스트). v1 회귀 차단 핵심 작업.
3. **결함 3 (OCR LLM 빈 응답)**: prompt 강화 또는 빈 응답 시 retry 로직.
4. **rule_based 가 도달 가능해진 후 재smoke** → 90 % 이상 통과 시 Phase 5 진입.

본 세션 외 추가 작업 요청 사항. ADR-007/008/009 (각 결함별) 필요 예상.

---

> ⚠️ Phase 4 는 **DoD 1차 항목 (단위 테스트) 충족** 이나, **Smoke Gate 미통과** 로 인해 Phase 5 진입 차단 상태. 본 세션 산출 (ADR-003~006 + woori N-up parser + N-up splitter + hyundai routing) 은 Phase 5 시작 가능 시점까지 보존.
