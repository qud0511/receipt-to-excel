"""Phase 6.9 — Dashboard API.

UI Dashboard 진입 시 한 번 호출. ADR-010 자료 검증의 4 KPI + 최근 결의서 list.
ADR-010 추천 5: baseline 15 분/거래 (Phase 6 하드코드).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.models import Template, Transaction, UploadSession
from app.db.repositories import user_repo
from app.schemas.auth import UserInfo
from app.schemas.autocomplete import (
    DashboardSummaryResponse,
    RecentExpenseReport,
    ThisMonthMetric,
    ThisYearMetric,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

_BASELINE_MIN_PER_TRANSACTION = 15  # ADR-010 추천 5.


async def _get_db(request: Request) -> AsyncIterator[AsyncSession]:
    sessionmaker = request.app.state.db_sessionmaker
    async with sessionmaker() as session:
        yield session


@router.get("/summary", response_model=DashboardSummaryResponse)
async def get_dashboard_summary(
    user: Annotated[UserInfo, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(_get_db)],
) -> DashboardSummaryResponse:
    """Dashboard 진입 — 4 KPI + 최근 결의서 N 개."""
    db_user = await user_repo.get_or_create_by_oid(db, oid=user.oid, name=user.name)

    # 이번 달 / 전월 — UTC 기준 (timezone aware 운영 환경).
    now = datetime.now(UTC)
    this_ym = f"{now.year:04d}-{now.month:02d}"
    prev_year, prev_month = (now.year - 1, 12) if now.month == 1 else (now.year, now.month - 1)
    prev_ym = f"{prev_year:04d}-{prev_month:02d}"

    # 이번 달 metric.
    this_month_total = await _sum_amount_by_year_month(db, db_user.id, this_ym)
    this_month_count = await _count_transactions_by_year_month(db, db_user.id, this_ym)
    this_month_pending = await _count_pending_transactions_by_year_month(
        db,
        db_user.id,
        this_ym,
    )
    prev_month_total = await _sum_amount_by_year_month(db, db_user.id, prev_ym)
    prev_diff_pct = _calc_diff_pct(this_month_total, prev_month_total)

    # 이번 년도 metric.
    completed_count = await _count_completed_sessions_this_year(db, db_user.id, now.year)
    this_year_tx_count = await _count_transactions_this_year(db, db_user.id, now.year)
    time_saved_hours = (this_year_tx_count * _BASELINE_MIN_PER_TRANSACTION) // 60

    # 최근 결의서 list (5).
    recent = await _list_recent_expense_reports(db, db_user.id, limit=5)

    return DashboardSummaryResponse(
        user_name=db_user.name or "",
        this_month=ThisMonthMetric(
            total_amount=this_month_total,
            transaction_count=this_month_count,
            pending_count=this_month_pending,
            prev_month_diff_pct=prev_diff_pct,
        ),
        this_year=ThisYearMetric(
            completed_count=completed_count,
            time_saved_hours=time_saved_hours,
        ),
        recent_expense_reports=recent,
    )


async def _sum_amount_by_year_month(
    db: AsyncSession,
    user_id: int,
    year_month: str,
) -> int:
    """해당 month 의 모든 transaction 금액 합."""
    stmt = (
        select(func.coalesce(func.sum(Transaction.amount), 0))
        .join(UploadSession, Transaction.session_id == UploadSession.id)
        .where(Transaction.user_id == user_id)
        .where(UploadSession.year_month == year_month)
    )
    result = await db.execute(stmt)
    return int(result.scalar() or 0)


async def _count_transactions_by_year_month(
    db: AsyncSession,
    user_id: int,
    year_month: str,
) -> int:
    stmt = (
        select(func.count(Transaction.id))
        .join(UploadSession, Transaction.session_id == UploadSession.id)
        .where(Transaction.user_id == user_id)
        .where(UploadSession.year_month == year_month)
    )
    return int((await db.execute(stmt)).scalar() or 0)


async def _count_pending_transactions_by_year_month(
    db: AsyncSession,
    user_id: int,
    year_month: str,
) -> int:
    """미입력 = ExpenseRecord 부재 거래 수.

    Phase 6.9 단순화: ExpenseRecord 가 없는 transaction 카운트.
    """
    from app.db.models import ExpenseRecord

    sub = select(ExpenseRecord.transaction_id).where(
        ExpenseRecord.user_id == user_id,
    )
    stmt = (
        select(func.count(Transaction.id))
        .join(UploadSession, Transaction.session_id == UploadSession.id)
        .where(Transaction.user_id == user_id)
        .where(UploadSession.year_month == year_month)
        .where(Transaction.id.not_in(sub))
    )
    return int((await db.execute(stmt)).scalar() or 0)


async def _count_completed_sessions_this_year(
    db: AsyncSession,
    user_id: int,
    year: int,
) -> int:
    """이번 년도 'generated' 또는 submitted_at NOT NULL Session 카운트."""
    year_prefix = f"{year:04d}-"
    stmt = (
        select(func.count(UploadSession.id))
        .where(UploadSession.user_id == user_id)
        .where(UploadSession.year_month.startswith(year_prefix))
        .where(
            (UploadSession.status == "generated") | (UploadSession.submitted_at.is_not(None)),
        )
    )
    return int((await db.execute(stmt)).scalar() or 0)


async def _count_transactions_this_year(
    db: AsyncSession,
    user_id: int,
    year: int,
) -> int:
    year_prefix = f"{year:04d}-"
    stmt = (
        select(func.count(Transaction.id))
        .join(UploadSession, Transaction.session_id == UploadSession.id)
        .where(Transaction.user_id == user_id)
        .where(UploadSession.year_month.startswith(year_prefix))
    )
    return int((await db.execute(stmt)).scalar() or 0)


def _calc_diff_pct(current: int, previous: int) -> float:
    """전월 대비 % 변화. 전월 0 이면 0 반환 (분모 보호)."""
    if previous == 0:
        return 0.0
    return round((current - previous) * 100.0 / previous, 1)


async def _list_recent_expense_reports(
    db: AsyncSession,
    user_id: int,
    *,
    limit: int,
) -> list[RecentExpenseReport]:
    """최근 N 개 — updated_at desc."""
    stmt = (
        select(UploadSession, Template.name)
        .outerjoin(Template, UploadSession.template_id == Template.id)
        .where(UploadSession.user_id == user_id)
        .order_by(UploadSession.updated_at.desc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).all()
    out: list[RecentExpenseReport] = []
    for upload_session, template_name in rows:
        # 거래 수 + 합계 — 별도 query (작은 N이라 OK).
        receipt_count = await _count_transactions_by_session(
            db,
            user_id,
            upload_session.id,
        )
        total_amount = await _sum_amount_by_session(db, user_id, upload_session.id)
        out.append(
            RecentExpenseReport(
                session_id=upload_session.id,
                year_month=upload_session.year_month,
                template_name=template_name,
                receipt_count=receipt_count,
                total_amount=total_amount,
                status=upload_session.status,
                is_submitted=upload_session.submitted_at is not None,
                updated_at=upload_session.updated_at,
            ),
        )
    return out


async def _count_transactions_by_session(
    db: AsyncSession,
    user_id: int,
    session_id: int,
) -> int:
    stmt = (
        select(func.count(Transaction.id))
        .where(Transaction.user_id == user_id)
        .where(Transaction.session_id == session_id)
    )
    return int((await db.execute(stmt)).scalar() or 0)


async def _sum_amount_by_session(
    db: AsyncSession,
    user_id: int,
    session_id: int,
) -> int:
    stmt = (
        select(func.coalesce(func.sum(Transaction.amount), 0))
        .where(Transaction.user_id == user_id)
        .where(Transaction.session_id == session_id)
    )
    return int((await db.execute(stmt)).scalar() or 0)
