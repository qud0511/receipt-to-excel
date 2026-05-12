# Phase 5 — Templates + XLSX Writer (R13) + PDF Generators

> 임시 워크어라운드: JPG hana/kakaobank 5건은 vendor_name 수동 입력 — ADR-009 별도 트랙
> (`docs/limitations/ocr_qwen_vendor_name.md` 참조, 본 Phase 와 직교).

- 시작일: 2026-05-12
- 의존: Phase 3 (`domain/template_map.py` TemplateConfig/SheetConfig), Phase 2 (`db/repositories/template_repo.py`)
- 참조: ADR-006 (실 양식 분석), `synthesis/05 §Phase 5`, `synthesis/04 §3.1 TemplateConfig`
- 범위 외: 차량 시트 (Phase 6+), 차량운행일지 (별도 양식)

## 목표

- 사용자 .xlsx 등록 → 자동 분석 → `TemplateConfig` 영속 → 추출된 거래를 행 단위로 XLSX 에 기입.
- v3 R13 (동적 행 삽입 + 스타일/병합/수식 보존), v1 Bug 1·2 회귀 차단.
- 거래의 영수증 원본 PDF 병합 + layout-fit PDF 두 양식 생성.

## ADR-006 핵심 결정 → 본 Phase 매핑

| ADR-006 결정 | Phase 5 구현 |
| --- | --- |
| 시트 명명 `{YY.MM}_{법인\|개인}` | `TemplateAnalyzer` 가 `sheet.title.split("_")[-1]` 로 sheet_kind 결정 |
| 헤더 row 2/4/6/7/8 고정 + 데이터 row 9 시작 | `data_start_row=9` 상수, header_row=7 |
| A 컬럼 일자 형식 (text vs datetime) 진화 | `XlsxWriter.write_date()` 가 cell.data_type 검사 후 양쪽 출력 |
| B/C/D 거래처 분리 변형 | `column_map["거래처"]` 가 단일 letter 또는 (B,C,D) tuple — `SheetConfig.merchant_col` 단일, project_col 분리 |
| G 헤더 sub-label 변동 ("버스,택시" vs "버스,택시,대리") | `TemplateAnalyzer` 가 substring 매칭 |
| sum_row gap 0/1/2 | A 컬럼 "합" 포함 셀 스캔 — gap 자동 흡수 |
| E 컬럼 `=SUM(F:N)` 또는 `=SUM(F:O)` | `formula_cells` 영속 — writer 가 가져다 씀 |
| 차량 시트 | Phase 5 범위 외 — analyzer 가 sheet_kind="차량" 시 skip |

## 분리된 산출물

### Phase 5.1 — Template Analyzer + Injector

`app/services/templates/analyzer.py` (신규):
- `analyze_workbook(path: Path) -> AnalyzedTemplate` — openpyxl `data_only=True` (수식 값 무시, 수식 텍스트만)
- ADR-006 휴리스틱 7 단계 그대로 — `sheet_kind` 결정 → 헤더 매핑 → sum_row 탐지 → `formula_cells` 수집.
- 3 modes (`field` / `category` / `hybrid`) 자동 분류 — `TemplateConfig.mode` 와 일치.

`app/services/templates/injector.py` (신규):
- `inject_named_ranges(path: Path, sheet: str, fields: dict[str, str]) -> None`
- `=FIELD`, `=DATA_START` 등 named range 를 등록 후 writer 가 사용.
- 시트명에 공백 시 single-quote (openpyxl 명세).

### Phase 5.2 — XLSX Writer (R13 핵심)

`app/services/generators/xlsx_writer.py` (신규):
- `clear_data_rows(sheet, sheet_config)` — 기존 더미 행 제거 (v1 Bug 1).
- `write_receipt(sheet, row_idx, transaction, sheet_config)` — 1 거래 1 행 기입.
  - `formula_cols` 셀은 절대 덮어쓰지 않음 (v1 Bug 2).
  - 카테고리 → column letter 매핑은 `sheet_config.category_cols`.
  - 카테고리 미매칭 시 `기타비용` 컬럼으로 fallback.
- `insert_row_with_style(sheet, src_row, dst_row)` — R13 동적 행 삽입.
  - openpyxl 의 `insert_rows()` 직접 사용 시 스타일/병합/수식 모두 깨짐.
  - **수동 복제**: cell.font / fill / border / alignment / number_format 명시 복사 + merged_cells_template 재적용 + sum_row 수식 참조 `+1` shift.
- 시트 라우팅: `transaction.카드사 in ("법인",)` → 법인 시트, 아니면 개인 시트 (R2).
- 파일명: `R12_{YYYY}_{MM}_지출결의서.xlsx` 패턴.

### Phase 5.3 — PDF Generators

`app/services/generators/merged_pdf.py` (신규):
- 거래일 ASC 정렬 → 각 원본 PDF/JPG 페이지 연결.
- pypdf 또는 PIL 기반 (Pillow `PdfMerger`).

`app/services/generators/layout_pdf.py` (신규):
- 2 또는 3 / A4 layout — scale-to-fit + aspect ratio 보존 (R11).
- reportlab `Canvas.drawImage()` + 비례 계산.
- 파일명: R12 패턴.

### Phase 5.4 — Templates API Routes

`app/api/routes/templates.py` (신규):
- `POST /templates/analyze` — 업로드 .xlsx → AnalyzedTemplate 미리보기 (영속 X).
- `POST /templates` — 등록 (TemplateConfig 영속, FS 저장).
- `GET /templates` — 사용자별 list.
- `GET /templates/{id}/grid` — 미리보기 grid (셀 텍스트 + 좌표).
- `PUT /templates/{id}` — 메타 수정 (시트 매핑).
- `DELETE /templates/{id}` — IDOR 차단 (다른 사용자 → 403).

`app/schemas/template.py` (신규): 요청/응답 Pydantic (snake_case → 한글 매핑은 `_mappers.py` 한 곳).

## 작성 테스트 명세 (TDD RED→GREEN)

### `tests/unit/test_template_analyzer.py` — 7 케이스

- `test_analyze_returns_field_mode_for_named_ranges()`
- `test_analyze_returns_category_mode_for_keyword_headers()`
- `test_analyze_returns_hybrid_mode_when_both_present()`
- `test_detect_formula_cols_from_sum_formulas()`
- `test_data_start_row_fallback_to_max_FIELD_row_plus_1()`
- `test_no_FIELD_no_category_keywords_raises_validation_error()`
- `test_analyze_real_template_round_trip()` *(integration, real_xlsx marker)*

### `tests/unit/test_template_injector.py` — 3 케이스

- `test_inject_named_ranges_creates_FIELD_and_DATA_START()`
- `test_inject_named_ranges_overwrites_existing()`
- `test_inject_named_ranges_quotes_sheet_names_with_spaces()`

### `tests/unit/test_xlsx_writer.py` — 11 케이스 (v1 회귀 차단 핵심)

- `test_clear_data_rows_removes_existing_dummy()` — v1 Bug 1
- `test_write_receipt_does_not_overwrite_formula_col()` — **v1 Bug 2**
- `test_write_receipt_routes_to_correct_category_col()`
- `test_write_receipt_regenerates_sum_formula()`
- `test_write_receipt_falls_back_to_기타비용_col_when_category_missing()`
- `test_sheet_routing_법인_card_goes_to_법인_sheet()` — R2
- `test_sheet_routing_개인_card_goes_to_개인_sheet()`
- `test_dynamic_row_insertion_preserves_style()` — R13
- `test_dynamic_row_insertion_preserves_merged_cells()`
- `test_dynamic_row_insertion_adjusts_formula_references()`
- `test_filename_follows_R12_pattern_YYYY_MM_지출결의서_xlsx()`

### `tests/unit/test_pdf_generators.py` — 6 케이스

- `test_merged_pdf_orders_by_transaction_date_asc()`
- `test_merged_pdf_concatenates_original_pages()`
- `test_layout_pdf_fits_2_or_3_per_A4()`
- `test_layout_pdf_preserves_aspect_ratio()` — R11
- `test_layout_pdf_filename_follows_R12()`
- `test_merged_pdf_empty_input_returns_no_file()`

### `tests/integration/test_templates_api.py` — 6 케이스 (라우터 4종 의무)

- `test_analyze_then_register_then_get_then_delete()`  # 정상 round-trip
- `test_register_requires_auth()`                       # 401
- `test_register_validates_xlsx_magic_bytes()`          # 422
- `test_get_template_filters_by_user()`                 # IDOR — 다른 사용자 403
- `test_grid_returns_cell_text_with_coordinates()`
- `test_delete_template_removes_file_and_db_row()`

## 의존성

- `openpyxl>=3.1` (XLSX 읽기/쓰기, 수식 보존)
- `pypdf>=4.0` 또는 PIL `PdfMerger` (병합)
- `reportlab` (layout PDF — 이미 사용 중)
- `python-multipart` (업로드 form, 이미 fastapi 의존성)

## Phase 5 DoD (CLAUDE.md §"TDD" + synthesis/05)

- [ ] Analyzer 7 / 3 / 11 / 6 단위 통과 → 27 단위
- [ ] Templates API 통합 6 케이스 통과 (auth/IDOR/422/round-trip)
- [ ] R12 파일명 패턴 정확 + R13 스타일·병합·수식 보존
- [ ] v1 Bug 1 (dummy row 잔존) + Bug 2 (formula 덮어쓰기) 회귀 0
- [ ] 합성 fixture (`tests/fixtures/synthetic_xlsx.py` 신규) 만으로 작동 — 실 영수증 사용 금지
- [ ] mypy --strict + ruff + pip-audit 통과
- [ ] 실 자료 round-trip 1 케이스 (`tests/smoke/real_templates/` 의 1 장으로) integration

## 자율 진행 / 멈춤 조건

자율 진행: Phase 5.1 → 5.2 → 5.3 → 5.4 순차. 각 단계 RED→GREEN→Refactor 후 commit.

멈춤 조건:
- 합성 xlsx fixture 로 analyzer 가 ADR-006 휴리스틱 구현 불가 시 (양식 진화 흔적 추가 발견)
- R13 스타일/병합/수식 동시 보존이 openpyxl 한계로 불가 시 (P5 우려사항 — synthesis/05 §맨끝)
- v1 Bug 2 (formula 덮어쓰기) 회귀 발견 시
- IDOR 통합 테스트가 403 미반환 시
- mypy/ruff/pip-audit 실패 시

Phase 5 완료 시 `phase-5-done.md` 작성 + Phase 6 진입 사용자 승인 대기.

## ADR-009 격리 메모

본 Phase 와 ADR-009 (qwen2.5vl 가맹점명 빈 응답) 는 완전 직교:
- ADR-009 영향 입력: JPG hana/kakaobank 5 건.
- Phase 5 처리 대상: ParsedTransaction → XLSX 행. 가맹점명이 채워져 있다면 본 Phase 정상 동작.
- 운영 시 5건은 수동 가맹점명 입력 (Phase 7 UI 에서 처리 예정) — 본 Phase 코드 변경 0.
