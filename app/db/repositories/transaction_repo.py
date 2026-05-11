"""Transaction repository — bulk_create / list_for_session."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Transaction


async def list_for_session(db: AsyncSession, *, user_id: int, session_id: int) -> list[Transaction]:
    """session_id + user_id 동시 필터 — IDOR 차단의 단일 지점."""
    stmt = (
        select(Transaction)
        .where(Transaction.session_id == session_id)
        .where(Transaction.user_id == user_id)
        .order_by(Transaction.transaction_date.asc(), Transaction.id.asc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def bulk_create(db: AsyncSession, *, user_id: int, transactions: list[Transaction]) -> None:
    """파서 출력의 일괄 적재. 각 row 가 user_id 일치해야 add."""
    for t in transactions:
        if t.user_id != user_id:
            # 호출자 실수 — 다른 사용자 row 가 섞이면 즉시 에러.
            raise ValueError(f"transaction.user_id={t.user_id} != current={user_id}")
    db.add_all(transactions)
    await db.flush()
