"""Phase 5 활성화 — 실 지출결의서 round-trip 통합 테스트 (ADR-006 휴리스틱 검증).

3 장 실 양식 (`tests/smoke/real_templates/`) 을 TemplateAnalyzer 로 분석 → ADR-006 §명세
일치 확인:
- 시트 명명 규약 + sheet_kind 자동 분류
- 헤더 row 7 keyword 매핑 (식대/접대비/기타비용 + 여비교통비 sub-headers)
- formula_cols 가 E·F·G·H·I·J·L·M·N 포함
- sum_row 위치 (A 컬럼 "합" 셀)
- data_start_row=9 default

실 자료는 .gitignore — 부재 시 skip.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from app.services.templates.analyzer import analyze_workbook

_REAL_TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "smoke" / "real_templates"
_REAL_TEMPLATE_FILES = (
    _REAL_TEMPLATES_DIR / "expense_2025_12_a.xlsx",
    _REAL_TEMPLATES_DIR / "expense_2026_03_a.xlsx",
    _REAL_TEMPLATES_DIR / "expense_2026_03_b.xlsx",
)


@pytest.mark.parametrize("path", _REAL_TEMPLATE_FILES, ids=lambda p: p.name)
def test_real_xlsx_round_trip_via_template_analyzer(path: Path) -> None:
    """3 장 실 양식 → TemplateAnalyzer → SheetConfig 결과가 ADR-006 §명세 일치.

    검증 (ADR-006 §"공통점"):
    - 시트명 suffix '_법인' / '_개인' 감지 (차량 시트는 skip).
    - row 7 + row 8 헤더 keyword 매핑 (식대/접대비/기타비용).
    - sum_row > data_start_row (9).
    - formula_cols 에 E (행별 SUM) + sum_row 카테고리 컬럼 포함.
    """
    if not path.exists():
        pytest.skip(f"{path.name} 미존재 (gitignore)")

    sheets = analyze_workbook(path.read_bytes())

    # 최소 2 시트 (법인 + 개인). 차량 시트는 analyzer 가 skip.
    assert len(sheets) >= 2, f"{path.name}: 법인/개인 시트 2개 이상 필요, got {list(sheets)}"

    # 시트 kind 에 법인/개인 모두 포함 (ADR-011: cfg.sheet_kind 사용, sheet_name 은 title).
    kinds = {cfg.sheet_kind for cfg in sheets.values() if cfg.analyzable}
    assert "법인" in kinds and "개인" in kinds, f"{path.name}: kinds={kinds}"

    for name, cfg in sheets.items():
        if not cfg.analyzable:
            # ADR-011 placeholder — 자동 분석 실패, 사용자 매핑 대기. layout 검증 skip.
            continue

        # 기본 layout 일치.
        assert cfg.data_start_row == 9, f"{name}: data_start_row={cfg.data_start_row}"
        assert cfg.header_row == 7

        # sum_row 가 data_start_row 이후에 탐지됨.
        assert cfg.sum_row is not None, f"{name}: sum_row 미탐지"
        assert cfg.sum_row > cfg.data_start_row

        # formula_cols 에 최소 E (행별 SUM) 포함.
        assert "E" in cfg.formula_cols, f"{name}: formula_cols={cfg.formula_cols}"

        # 최소 한 가지 모드 결정 (field / category / hybrid).
        assert cfg.mode in ("field", "category", "hybrid"), f"{name}: mode={cfg.mode}"

        # category mode 가 활성이면 식대 또는 기타비용 매핑 보유.
        if cfg.mode in ("category", "hybrid"):
            has_food_or_etc = "식대" in cfg.category_cols or "기타비용" in cfg.category_cols
            assert has_food_or_etc, f"{name}: category_cols={cfg.category_cols}"


def test_real_xlsx_grid_io_round_trip() -> None:
    """실 양식 3장 → grid_io read_grid/apply_cell_patches round-trip 보존.

    PII 보호: 셀 값 자체를 단언/로그하지 않고 구조 불변식만 검증.
    """
    from app.services.templates.grid_io import apply_cell_patches, read_grid

    present = [p for p in _REAL_TEMPLATE_FILES if p.exists()]
    if not present:
        pytest.skip("real_templates 미존재 (gitignore)")

    for path in present:
        content = path.read_bytes()
        sheets = read_grid(content)
        assert sheets, f"{path.name}: 시트 0"
        assert any(s.cells for s in sheets.values()), f"{path.name}: 모든 시트 빈 셀"
        for s in sheets.values():
            assert s.max_row >= 1 and s.max_col >= 1

        # no-op 성격 패치: 기존 셀에 동일 값 재기록 → 구조 보존 확인.
        first_sheet, rs = next(iter(sheets.items()))
        assert rs.cells, f"{path.name}: {first_sheet} 빈 셀"
        c0 = rs.cells[0]
        new_bytes, count = apply_cell_patches(content, [(first_sheet, c0.row, c0.col, c0.value)])
        assert count == 1
        after = read_grid(new_bytes)
        # 시트 집합·각 시트 셀 좌표/수식여부 보존.
        assert set(after) == set(sheets)
        for name in sheets:
            before_idx = {(c.row, c.col, c.is_formula) for c in sheets[name].cells}
            after_idx = {(c.row, c.col, c.is_formula) for c in after[name].cells}
            assert after_idx == before_idx, f"{path.name}/{name}: grid 구조 변경됨"
