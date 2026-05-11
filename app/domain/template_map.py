"""TemplateConfig / SheetConfig — 엑셀 양식 매핑 도메인.

v1 의 TemplateConfig 자산 + v3 R13 확장. synthesis/04 §3.1.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_serializer

SheetMode = Literal["field", "category", "hybrid"]


class SheetConfig(BaseModel):
    """단일 시트 (법인/개인 중 하나) 의 컬럼 매핑."""

    model_config = ConfigDict(extra="forbid")

    sheet_name: str  # "법인" / "개인"
    date_col: str | None = None
    merchant_col: str | None = None
    project_col: str | None = None
    total_col: str | None = None  # 합계 수식 열 — 보통 formula_cols 에도 포함.
    note_col: str | None = None
    category_cols: dict[str, str] = Field(default_factory=dict)
    # 절대 덮어쓰기 금지 — XLSX writer 가 본 집합 외에만 값을 씀 (CLAUDE.md §"특이사항: SUM").
    formula_cols: set[str] = Field(default_factory=set)
    data_start_row: int
    data_end_row: int
    sum_row: int | None = None
    header_row: int
    merged_cells_template: list[str] = Field(default_factory=list)

    @field_serializer("formula_cols")
    def _serialize_formula_cols(self, value: set[str]) -> list[str]:
        # set 은 JSON 직렬화 불가 — 정렬된 list 로 deterministic 출력.
        return sorted(value)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def effective_data_end_row(self) -> int:
        """sum_row 행 보호 — 데이터는 sum_row 한 행 위까지만 허용."""
        if self.sum_row is None:
            return self.data_end_row
        return min(self.data_end_row, self.sum_row - 1)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def mode(self) -> SheetMode:
        """3 modes — field-only / category-only / hybrid.

        - field: date/merchant/project/total/note 등 고정 슬롯만 사용.
        - category: expense_column → column letter 매핑 (`category_cols`) 만.
        - hybrid: 양쪽 동시 — v3 R13 의 주류 케이스.
        """
        has_field = any(
            [
                self.date_col,
                self.merchant_col,
                self.project_col,
                self.total_col,
                self.note_col,
            ]
        )
        has_category = bool(self.category_cols)
        if has_field and has_category:
            return "hybrid"
        if has_category:
            return "category"
        return "field"


class TemplateConfig(BaseModel):
    """양식 1개 (= 1 사용자가 등록한 .xlsx) 의 전체 매핑.

    `sheets` 에 "법인"/"개인" 키로 SheetConfig 등록. 추후 다른 시트 분류도 같은 dict 확장.
    """

    model_config = ConfigDict(extra="forbid")

    sheet_name: str  # 기본 시트 (대시보드 진입 시 default selection).
    sheets: dict[str, SheetConfig]
    template_id: str
    template_path: str
