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

from tests.fixtures.synthetic_xlsx import (
    make_field_mode_template,
    make_template,
    make_unrecognized_marker_template,
)


# ── 1) field mode — named range 만 보유 ──────────────────────────────────────
def test_analyze_returns_field_mode_for_named_ranges() -> None:
    xlsx = make_template(mode="field")
    sheets = analyze_workbook(xlsx)

    # 시트 명은 "26.05_법인" / "26.05_개인" — 분석 결과 키 (ADR-011: title 그대로).
    assert set(sheets.keys()) == {"26.05_법인", "26.05_개인"}
    for cfg in sheets.values():
        assert isinstance(cfg, SheetConfig)
        # sheet_kind 가 suffix 에서 추출 (ADR-011).
        assert cfg.sheet_kind in ("법인", "개인")
        assert cfg.mode == "field"
        # field mode 시 named range 로 슬롯 채움.
        assert cfg.date_col == "A"
        assert cfg.merchant_col == "B"
        assert cfg.total_col == "E"
        # category mode 시그니처 부재.
        assert cfg.category_cols == {}
        assert cfg.analyzable is True


# ── 2) category mode — row 7 keyword 헤더 만 ─────────────────────────────────
def test_analyze_returns_category_mode_for_keyword_headers() -> None:
    xlsx = make_template(mode="category")
    sheets = analyze_workbook(xlsx)

    for cfg in sheets.values():
        # ADR-011: row 7 의 "일자"/"거래처 / 프로젝트명"/"합계"/"식대" 등이 Field mode 슬롯에도
        # 매칭되므로 mode 가 hybrid 또는 category. Field slot 부재만 보장 못 함.
        # 핵심 contract — category_cols 가 채워졌는지.
        assert cfg.mode in ("category", "hybrid")
        # row 7 헤더 keyword → category_cols 매핑.
        assert cfg.category_cols.get("식대") == "L"
        assert cfg.category_cols.get("접대비") == "M"
        assert cfg.category_cols.get("기타비용") == "N"
        # 여비교통비 그룹 — row 7 의 'F' 컬럼 또는 row 8 의 sub-headers.
        assert "여비교통비" in cfg.category_cols or "항공료" in cfg.category_cols


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


# ── 7) 빈 양식 — A2 마커도 없으면 TemplateAnalysisError ───────────────────────
def test_no_field_no_category_keywords_raises_error() -> None:
    """ADR-011: A2 마커 있으면 placeholder (analyzable=False) 로 회수, 아예 없어야 error."""
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    if ws is not None:
        ws.title = "Sheet1"
        # A2 마커 부재 — 분석 대상조차 아님.
    import io as _io

    buf = _io.BytesIO()
    wb.save(buf)
    with pytest.raises(TemplateAnalysisError):
        analyze_workbook(buf.getvalue())


# ── 8) ADR-011: Field mode 양식 (suffix 부재) → analyzable=True ───────────────
def test_field_mode_sheet_without_suffix_analyzable() -> None:
    """UI A사 파견용 양식 (시트명 '지출결의서') → 분석 가능."""
    xlsx = make_field_mode_template()
    sheets = analyze_workbook(xlsx)

    # 분석 대상 시트 — "지출결의서" 하나 (다른 시트는 A2 마커 부재로 skip).
    assert "지출결의서" in sheets
    cfg = sheets["지출결의서"]
    assert cfg.analyzable is True
    assert cfg.sheet_kind is None  # suffix 부재.
    # row 7 의 "거래일" → DATE 슬롯, "거래처명" → MERCHANT 슬롯 매핑.
    assert cfg.date_col == "B"
    assert cfg.merchant_col == "C"
    assert cfg.project_col == "D"
    assert cfg.total_col == "G"


# ── 9) ADR-011: A2 마커 있으나 row 7 헤더 부족 → analyzable=False placeholder ─
def test_unrecognized_sheet_marked_needs_mapping() -> None:
    xlsx = make_unrecognized_marker_template()
    sheets = analyze_workbook(xlsx)
    assert "낯선양식" in sheets
    cfg = sheets["낯선양식"]
    assert cfg.analyzable is False


# ── 10) ADR-011: stop word 시트 (차량/운행일지) → 완전 skip ────────────────────
def test_stop_word_sheet_skipped() -> None:
    xlsx = make_field_mode_template(include_stop_sheet=True)
    sheets = analyze_workbook(xlsx)
    # "차량운행일지" 는 stop word 로 skip — 결과 dict 에 없음.
    assert "차량운행일지" not in sheets


# ── 11) ADR-011: mapping_status 집계 — 한 시트 placeholder 면 needs_mapping ──
def test_mapping_status_aggregates_to_needs_mapping() -> None:
    """SheetConfig.analyzable False 시트가 한 개라도 있으면 Template.mapping_status = needs_mapping.

    aggregator 로직 검증: dict[str, SheetConfig] 의 analyzable False 카운트.
    """
    xlsx = make_unrecognized_marker_template()
    sheets = analyze_workbook(xlsx)
    has_unanalyzable = any(not cfg.analyzable for cfg in sheets.values())
    assert has_unanalyzable
    # mapping_status 집계 — 본 helper 는 service layer 의 책임 (단위 contract 만 검증).
    mapping_status = (
        "needs_mapping" if any(not cfg.analyzable for cfg in sheets.values()) else "mapped"
    )
    assert mapping_status == "needs_mapping"
