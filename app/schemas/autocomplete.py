"""Autocomplete + Dashboard 응답 schema."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class VendorView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    name: str
    last_used_at: datetime | None = None
    usage_count: int = 0


class ProjectView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    vendor_id: int
    name: str
    last_used_at: datetime | None = None
    usage_count: int = 0


class TeamMemberView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    name: str


class TeamGroupView(BaseModel):
    """팀 → 멤버 nested — UI Verify 의 hybrid 입력."""

    model_config = ConfigDict(extra="forbid")

    id: int
    name: str
    members: list[TeamMemberView] = []


class AttendeeView(BaseModel):
    """모든 팀 멤버 평탄화 — Verify autocomplete chip."""

    model_config = ConfigDict(extra="forbid")

    name: str
    team: str  # 소속 팀 이름.


class RecentExpenseReport(BaseModel):
    """Dashboard 최근 작성한 지출결의서 row."""

    model_config = ConfigDict(extra="forbid")

    session_id: int
    year_month: str
    template_name: str | None = None
    receipt_count: int
    total_amount: int
    status: Literal["parsing", "awaiting_user", "generated", "failed"]
    is_submitted: bool  # submitted_at IS NOT NULL.
    updated_at: datetime


class ThisMonthMetric(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_amount: int
    transaction_count: int
    pending_count: int  # 미입력 (ExpenseRecord 부재 또는 vendor_id=0).
    prev_month_diff_pct: float = 0.0  # 전월 대비.


class ThisYearMetric(BaseModel):
    model_config = ConfigDict(extra="forbid")

    completed_count: int  # status='generated' 또는 submitted_at NOT NULL.
    time_saved_hours: int  # baseline 15분/거래 누적.


class DashboardSummaryResponse(BaseModel):
    """GET /dashboard/summary — Dashboard 진입 시 한 번."""

    model_config = ConfigDict(extra="forbid")

    user_name: str
    this_month: ThisMonthMetric
    this_year: ThisYearMetric
    recent_expense_reports: list[RecentExpenseReport]
