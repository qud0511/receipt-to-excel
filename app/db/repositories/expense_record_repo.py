"""ExpenseRecord repository — minimal stub. Phase 7 에서 확장."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ExpenseRecord


async def get_by_transaction(
    db: AsyncSession, *, user_id: int, transaction_id: int
) -> ExpenseRecord | None:
    stmt = (
        select(ExpenseRecord)
        .where(ExpenseRecord.user_id == user_id)
        .where(ExpenseRecord.transaction_id == transaction_id)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()
