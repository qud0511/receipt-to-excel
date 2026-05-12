"""Sessions API 요청/응답 schema — 한↔영 매핑은 _mappers.py 에 위임 (CLAUDE.md)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SessionCreatedResponse(BaseModel):
    """POST /sessions 응답 — 잡 큐 등록 직후."""

    model_config = ConfigDict(extra="forbid")

    session_id: int
    status: Literal["parsing"]


class SessionSummary(BaseModel):
    """GET /sessions 응답 row."""

    model_config = ConfigDict(extra="forbid")

    session_id: int
    year_month: str
    status: Literal["parsing", "awaiting_user", "generated", "failed"]
    submitted_at: datetime | None = None
    created_at: datetime
    transaction_count: int = 0
    total_amount: int = 0


class TransactionView(BaseModel):
    """Verify 그리드 1 행. ADR-010 자료 검증 B-5 (9 컬럼) 매핑.

    한글 필드는 도메인 표기 유지 — UI 가 그대로 표시.
    """

    model_config = ConfigDict(extra="forbid")

    id: int
    가맹점명: str
    거래일: str  # ISO YYYY-MM-DD.
    거래시각: str | None = None  # HH:MM:SS.
    금액: int
    업종: str | None = None
    카드사: str
    카드번호_마스킹: str | None = None
    parser_used: str
    field_confidence: dict[str, str]
    confidence_score: float = Field(
        default=0.0,
        description="row-level 종합 신뢰도 (0.0~1.0). high=1.0, medium=0.66, low=0.33, none=0.",
    )
    # ExpenseRecord (사용자 입력) — 미입력 시 None.
    vendor: str | None = None
    project: str | None = None
    purpose: str | None = None
    headcount: int | None = None
    attendees: list[str] = Field(default_factory=list)


class TransactionListResponse(BaseModel):
    """GET /sessions/{id}/transactions 응답."""

    model_config = ConfigDict(extra="forbid")

    transactions: list[TransactionView]
    counts: dict[str, int]  # all / missing / review / complete.
