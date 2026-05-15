"""Templates API schema — request/response.

ADR-006/011 휴리스틱 결과 + ADR-010 추천 3 (Phase 6.8 셀 값 + 매핑 chips PATCH 만).
한↔영 매핑은 schemas/_mappers.py 한 곳 (CLAUDE.md §"가독성").
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class TemplateSummary(BaseModel):
    """GET /templates 응답 row — Templates sidebar 의 list 항목."""

    model_config = ConfigDict(extra="forbid")

    id: int
    name: str
    is_default: bool
    mapping_status: str  # "mapped" / "needs_mapping"
    created_at: datetime
    updated_at: datetime


class SheetConfigView(BaseModel):
    """SheetConfig (도메인) 의 API 표현 — JSON 직렬화."""

    model_config = ConfigDict(extra="forbid")

    sheet_name: str
    sheet_kind: str | None = None  # "법인" / "개인" / null (Field mode)
    mode: str  # field / category / hybrid
    analyzable: bool
    date_col: str | None = None
    merchant_col: str | None = None
    project_col: str | None = None
    total_col: str | None = None
    note_col: str | None = None
    category_cols: dict[str, str] = {}
    formula_cols: list[str] = []
    data_start_row: int
    data_end_row: int
    sum_row: int | None = None
    header_row: int


class AnalyzedTemplateResponse(BaseModel):
    """POST /templates/analyze 응답 — 영속 X, 미리보기."""

    model_config = ConfigDict(extra="forbid")

    sheets: dict[str, SheetConfigView]
    mapping_status: str  # 한 시트라도 analyzable=False → needs_mapping


class TemplateCreatedResponse(BaseModel):
    """POST /templates 응답."""

    model_config = ConfigDict(extra="forbid")

    template_id: int
    name: str
    mapping_status: str


class GridCell(BaseModel):
    """셀 1 개 — Templates editor 의 grid 표시."""

    model_config = ConfigDict(extra="forbid")

    row: int
    col: int  # 1-based.
    value: str | int | float | None = None
    is_formula: bool = False  # value 가 "=" 시작 시 True


class GridSheetView(BaseModel):
    """시트 1 개의 cell 모음 — Phase 6.8b GET /templates/{id}/grid 응답."""

    model_config = ConfigDict(extra="forbid")

    sheet_name: str
    cells: list[GridCell]
    max_row: int
    max_col: int


class GridResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sheets: dict[str, GridSheetView]


class CellPatchItem(BaseModel):
    """PATCH /templates/{id}/cells body 의 1 셀 변경."""

    model_config = ConfigDict(extra="forbid")

    sheet: str
    row: int
    col: int
    value: str | int | float | None = None


class CellsPatchRequest(BaseModel):
    """다중 셀 일괄 수정. style/병합/줌 deferred (ADR-010 추천 3)."""

    model_config = ConfigDict(extra="forbid")

    cells: list[CellPatchItem]


class MappingPatchRequest(BaseModel):
    """매핑 chip override — sheet 별 column_map 갱신."""

    model_config = ConfigDict(extra="forbid")

    sheet: str
    date_col: str | None = None
    merchant_col: str | None = None
    project_col: str | None = None
    total_col: str | None = None
    note_col: str | None = None
    category_cols: dict[str, str] | None = None  # 식대→L 등.


class MetaPatchRequest(BaseModel):
    """이름 / 기본 양식 토글."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = None


def sheet_config_to_view(sheet_name: str, cfg: Any) -> SheetConfigView:  # noqa: ANN401
    """app.domain.template_map.SheetConfig → SheetConfigView 변환."""
    return SheetConfigView(
        sheet_name=sheet_name,
        sheet_kind=cfg.sheet_kind,
        mode=cfg.mode,
        analyzable=cfg.analyzable,
        date_col=cfg.date_col,
        merchant_col=cfg.merchant_col,
        project_col=cfg.project_col,
        total_col=cfg.total_col,
        note_col=cfg.note_col,
        category_cols=dict(cfg.category_cols),
        formula_cols=sorted(cfg.formula_cols),
        data_start_row=cfg.data_start_row,
        data_end_row=cfg.data_end_row,
        sum_row=cfg.sum_row,
        header_row=cfg.header_row,
    )
