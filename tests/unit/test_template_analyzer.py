"""Phase 5.1 — Template Analyzer 합성 양식 7 케이스 (TDD RED→GREEN).

ADR-006 휴리스틱:
- 시트 명명 `{YY.MM}_{법인|개인}` 만 분석 대상 (차량 시트는 Phase 5 범위 외).
- field mode: named range (`FIELD_DATE_*`, `DATA_START_*`) 만.
- category mode: row 7 keyword 헤더 (여비교통비/식대/접대비/기타비용) 만.
- hybrid mode: 양쪽 동시.
- formula_cols: row 9 ~ sum_row 의 `=` 시작 셀의 column letter 집합.
"""

from __future__ import annotations

import pytest
from app.domain.template_map import SheetConfig
from app.services.templates.analyzer import (
    TemplateAnalysisError,
    analyze_workbook,
)

from tests.fixtures.synthetic_xlsx import make_empty_template, make_template


# ── 1) field mode — named range 만 보유 ──────────────────────────────────────
def test_analyze_returns_field_mode_for_named_ranges() -> None:
    xlsx = make_template(mode="field")
    sheets = analyze_workbook(xlsx)

    # 시트 명은 "26.05_법인" / "26.05_개인" — 분석 결과 키.
    assert set(sheets.keys()) == {"26.05_법인", "26.05_개인"}
    for cfg in sheets.values():
        assert isinstance(cfg, SheetConfig)
        assert cfg.mode == "field"
        # field mode 시 named range 로 슬롯 채움.
        assert cfg.date_col == "A"
        assert cfg.merchant_col == "B"
        assert cfg.total_col == "E"
        # category mode 시그니처 부재.
        assert cfg.category_cols == {}


# ── 2) category mode — row 7 keyword 헤더 만 ─────────────────────────────────
def test_analyze_returns_category_mode_for_keyword_headers() -> None:
    xlsx = make_template(mode="category")
    sheets = analyze_workbook(xlsx)

    for cfg in sheets.values():
        assert cfg.mode == "category"
        # row 7 헤더 keyword → category_cols 매핑.
        assert cfg.category_cols.get("식대") == "L"
        assert cfg.category_cols.get("접대비") == "M"
        assert cfg.category_cols.get("기타비용") == "N"
        # 여비교통비 그룹 — row 7 의 'F' 컬럼 또는 row 8 의 sub-headers.
        assert "여비교통비" in cfg.category_cols or "항공료" in cfg.category_cols
        # field mode 슬롯 부재.
        assert cfg.date_col is None
        assert cfg.merchant_col is None


# ── 3) hybrid mode — 양쪽 동시 ───────────────────────────────────────────────
def test_analyze_returns_hybrid_mode_when_both_present() -> None:
    xlsx = make_template(mode="hybrid")
    sheets = analyze_workbook(xlsx)

    for cfg in sheets.values():
        assert cfg.mode == "hybrid"
        assert cfg.date_col == "A"
        assert cfg.category_cols.get("식대") == "L"


# ── 4) formula_cols — row 9 ~ sum_row 의 `=` 시작 셀에서 추출 ─────────────────
def test_detect_formula_cols_from_sum_formulas() -> None:
    xlsx = make_template(mode="hybrid", data_rows=2)
    sheets = analyze_workbook(xlsx)

    for cfg in sheets.values():
        # 합성 양식의 행별 SUM (E열) + sum_row 의 SUM (E,F,G,H,I,J,L,M,N).
        # 본 영역의 column letter 모두 formula_cols 에 포함.
        assert "E" in cfg.formula_cols
        assert "F" in cfg.formula_cols
        assert "N" in cfg.formula_cols
        # 데이터 컬럼 (A, B) 는 formula_cols 부재.
        assert "A" not in cfg.formula_cols
        assert "B" not in cfg.formula_cols


# ── 5) data_start_row — named range DATA_START 우선, 부재 시 row 9 default ──
def test_data_start_row_from_named_range_or_default() -> None:
    xlsx = make_template(mode="field")
    sheets = analyze_workbook(xlsx)
    for cfg in sheets.values():
        # DATA_START_법인 = 'sheet'!$A$9 → row 9.
        assert cfg.data_start_row == 9

    # category mode (named range 없음) → ADR-006 fallback: row 9 (헤더 row 8 + 1).
    xlsx_cat = make_template(mode="category")
    sheets_cat = analyze_workbook(xlsx_cat)
    for cfg in sheets_cat.values():
        assert cfg.data_start_row == 9


# ── 6) sum_row 자동 탐지 — A 컬럼 "합" 포함 셀 ───────────────────────────────
def test_sum_row_detected_by_label() -> None:
    # gap 0 → sum_row = data_end + 1
    xlsx_g0 = make_template(mode="hybrid", data_rows=2, sum_row_gap=0)
    for cfg in analyze_workbook(xlsx_g0).values():
        # data_start=9, data_rows=2 → data_end=10, sum_row=11.
        assert cfg.sum_row == 11
        assert cfg.data_end_row == 10

    # gap 1 → sum_row = data_end + 2
    xlsx_g1 = make_template(mode="hybrid", data_rows=2, sum_row_gap=1)
    for cfg in analyze_workbook(xlsx_g1).values():
        assert cfg.sum_row == 12


# ── 7) 빈 양식 — 헤더·named range 둘 다 부재 → TemplateAnalysisError ──────────
def test_no_field_no_category_keywords_raises_error() -> None:
    xlsx = make_empty_template()
    with pytest.raises(TemplateAnalysisError):
        analyze_workbook(xlsx)
