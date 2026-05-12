"""Phase 5 사전 자료 — 실 지출결의서 round-trip 통합 테스트 스켈레톤.

ADR-006 §"통합 테스트 스켈레톤" — TemplateAnalyzer 가 추출한 AnalyzedTemplate 이
실 양식의 형태/위치/수식과 일치하는지 검증할 fixture 사전 작성.

현재는 ``@pytest.mark.skip`` — Phase 5 TemplateAnalyzer 구현 후 활성화.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_REAL_TEMPLATES_DIR = (
    Path(__file__).resolve().parents[1] / "smoke" / "real_templates"
)


@pytest.mark.skip(reason="Phase 5 TemplateAnalyzer 구현 후 활성화 — ADR-006")
def test_real_xlsx_round_trip_via_template_analyzer() -> None:
    """3 장 실 양식 → TemplateAnalyzer → AnalyzedTemplate 결과가 ADR-006 §명세 일치.

    검증:
    - sheet_kind 자동 분류 (법인/개인/차량).
    - column_map 의 모든 카테고리 → 컬럼 letter 일치.
    - sum_row 위치 (A 컬럼 "합" 셀 위치 + 1).
    - formula_cols 가 E, F, G, H, I, J, K, L, M, N 포함.
    - formula_cells 가 sum_row 의 모든 SUM 수식 + 행별 E열 SUM 수식 포함.
    """
    fixture_files = [
        _REAL_TEMPLATES_DIR / "expense_2025_12_a.xlsx",
        _REAL_TEMPLATES_DIR / "expense_2026_03_a.xlsx",
        _REAL_TEMPLATES_DIR / "expense_2026_03_b.xlsx",
    ]
    for fp in fixture_files:
        if not fp.exists():
            pytest.skip(f"{fp.name} 미존재 (gitignore) — ADR-003 매핑 참고")
