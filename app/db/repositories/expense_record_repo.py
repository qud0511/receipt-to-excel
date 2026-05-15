"""ExpenseRecord repository — Phase 6 PATCH (last-write-wins) 진입점."""

from __future__ import annotations

from typing import Any  # 'patch: dict[str, Any]' 시그니처용.

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ForbiddenError
from app.db.models import ExpenseRecord, Transaction


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


async def upsert_user_input(
    db: AsyncSession,
    *,
    user_id: int,
    transaction_id: int,
    patch: dict[str, Any],
) -> ExpenseRecord:
    """PATCH 본문의 변경 필드만 적용 — last-write-wins (ADR-010 D-2).

    ExpenseRecord 가 없으면 생성, 있으면 patch 필드만 update. IDOR 차단 —
    Transaction.user_id 검증 (다른 사용자 transaction 참조 시 ForbiddenError).
    """
    tx = await db.get(Transaction, transaction_id)
    if tx is None or tx.user_id != user_id:
        raise ForbiddenError("not your transaction")

    existing = await get_by_transaction(db, user_id=user_id, transaction_id=transaction_id)
    if existing is None:
        # 신규 — 최소 필드. vendor_id / xlsx_sheet 등은 Phase 6.9 resolver 가 갱신.
        attendees = patch.get("attendees")
        new = ExpenseRecord(
            transaction_id=transaction_id,
            user_id=user_id,
            vendor_id=0,  # placeholder — Phase 6.9 자동완성 시 실 vendor_id.
            project_id=None,
            purpose=_str_or_none(patch.get("purpose")),
            attendees_json=list(attendees) if isinstance(attendees, list) else [],
            headcount=_int_or_none(patch.get("headcount")),
            xlsx_sheet=tx.card_type or "개인",
            expense_column="기타비용",  # Phase 6.10 generate 시 category resolver.
            auto_note=str(patch.get("note") or ""),
        )
        db.add(new)
        await db.flush()
        return new

    # 갱신 — patch 의 not-None 필드만 적용 (None = "변경 없음").
    if patch.get("purpose") is not None:
        existing.purpose = str(patch["purpose"])
    if patch.get("headcount") is not None:
        existing.headcount = int(patch["headcount"])
    if patch.get("attendees") is not None:
        existing.attendees_json = list(patch["attendees"])
    if patch.get("note") is not None:
        existing.auto_note = str(patch["note"])
    await db.flush()
    return existing


def _str_or_none(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _int_or_none(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value)
    raise TypeError(f"int 변환 불가: {type(value).__name__}")
