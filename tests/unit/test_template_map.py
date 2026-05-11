"""Phase 3 — TemplateConfig / SheetConfig 의 직렬화 + sum_row 보호 + 3-mode 판별."""

from __future__ import annotations

import json

from app.domain.template_map import SheetConfig


def _sheet(**overrides: object) -> SheetConfig:
    """기본 정상 값 + override 패턴 — 각 테스트가 일부 필드만 바꿔 검증."""
    base: dict[str, object] = {
        "sheet_name": "법인",
        "date_col": "C",
        "merchant_col": "D",
        "project_col": "E",
        "total_col": "K",
        "note_col": "L",
        "category_cols": {"식대": "F", "통신비": "G"},
        "formula_cols": {"K", "L"},
        "data_start_row": 5,
        "data_end_row": 100,
        "sum_row": 101,
        "header_row": 4,
        "merged_cells_template": [],
    }
    base.update(overrides)
    return SheetConfig(**base)  # type: ignore[arg-type]


# ── 1) formula_cols set → JSON 호환 list (정렬) ───────────────────────────────
def test_template_config_serializes_formula_cols_to_list() -> None:
    sc = _sheet(formula_cols={"K", "M", "A"})
    dumped = sc.model_dump()
    assert isinstance(dumped["formula_cols"], list)
    assert dumped["formula_cols"] == ["A", "K", "M"]  # 정렬 보장
    # JSON 직렬화 가능 — set 은 그대로면 TypeError.
    json.dumps(dumped, ensure_ascii=False)


# ── 2) effective_data_end_row — sum_row 행 보호 ───────────────────────────────
def test_template_config_effective_data_end_row_with_sum_row() -> None:
    # sum_row 가 data_end_row 보다 1 클 때 — data_end_row 그대로.
    sc_safe = _sheet(data_end_row=100, sum_row=101)
    assert sc_safe.effective_data_end_row == 100

    # 충돌 (data_end_row 가 sum_row 와 동등하거나 큼) — sum_row - 1 로 클램프.
    sc_clamped = _sheet(data_end_row=101, sum_row=101)
    assert sc_clamped.effective_data_end_row == 100

    # sum_row 없음 — data_end_row 그대로.
    sc_no_sum = _sheet(data_end_row=100, sum_row=None)
    assert sc_no_sum.effective_data_end_row == 100


# ── 3) 3 modes — field-only / category-only / hybrid ────────────────────────
def test_template_config_3_modes_field_category_hybrid() -> None:
    field_only = _sheet(
        date_col="C",
        merchant_col="D",
        category_cols={},
    )
    assert field_only.mode == "field"

    category_only = _sheet(
        date_col=None,
        merchant_col=None,
        project_col=None,
        total_col=None,
        note_col=None,
        category_cols={"식대": "F"},
    )
    assert category_only.mode == "category"

    hybrid = _sheet(
        date_col="C",
        merchant_col="D",
        category_cols={"식대": "F"},
    )
    assert hybrid.mode == "hybrid"
