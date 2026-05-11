"""ExpenseRecord — 사용자 검수 결과 + 자동 결정 필드 (도메인 계층)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ExpenseRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transaction_id: int

    # 사용자 입력.
    vendor_id: int
    project_id: int | None = None
    purpose: str | None = None
    attendees: list[str] = Field(default_factory=list)
    headcount: int | None = Field(default=None, gt=0)
    receipt_attachment_url: str | None = None

    # 자동 결정.
    xlsx_sheet: Literal["법인", "개인"]
    expense_column: str
    auto_note: str

    # 메타.
    created_at: datetime
    updated_at: datetime
