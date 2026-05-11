"""Card (card_meta) repository — AD-2 canonical masked-number lookup."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Card


async def get_by_masked(db: AsyncSession, *, user_id: int, card_number_masked: str) -> Card | None:
    """AD-2 canonical NNNN-****-****-NNNN exact match.

    형식 미일치 → None. 호출자(CardTypeResolver) 는 그 시점에 형식 검증을 마쳐야 한다.
    silent 시트 라우팅 실패 방지 (CLAUDE.md §"특이사항").
    """
    stmt = (
        select(Card)
        .where(Card.user_id == user_id)
        .where(Card.card_number_masked == card_number_masked)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_for_user(db: AsyncSession, *, user_id: int) -> list[Card]:
    stmt = select(Card).where(Card.user_id == user_id).order_by(Card.created_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())
