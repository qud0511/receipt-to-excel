"""TeamGroup repository — minimal stub. Phase 7 에서 확장."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import TeamGroup


async def list_for_user(db: AsyncSession, *, user_id: int) -> list[TeamGroup]:
    stmt = select(TeamGroup).where(TeamGroup.user_id == user_id).order_by(TeamGroup.name.asc())
    result = await db.execute(stmt)
    return list(result.scalars().all())
