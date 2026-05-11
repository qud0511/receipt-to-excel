"""Merchant repository — minimal stub. Phase 5 에서 확장."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Merchant


async def get_by_name(db: AsyncSession, *, user_id: int, name: str) -> Merchant | None:
    stmt = select(Merchant).where(Merchant.user_id == user_id).where(Merchant.name == name)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()
