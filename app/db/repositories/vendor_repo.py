"""Vendor repository — autocomplete + create_or_get."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Vendor


async def autocomplete(
    db: AsyncSession,
    *,
    user_id: int,
    prefix: str = "",
    limit: int = 10,
) -> list[Vendor]:
    """최근 사용 우선 정렬 + usage_count tiebreak (CLAUDE.md §"성능": vendor 인덱스)."""
    stmt = select(Vendor).where(Vendor.user_id == user_id)
    if prefix:
        stmt = stmt.where(Vendor.name.startswith(prefix))
    stmt = stmt.order_by(
        Vendor.last_used_at.desc().nulls_last(),
        Vendor.usage_count.desc(),
        Vendor.name.asc(),
    ).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def create_or_get(db: AsyncSession, *, user_id: int, name: str) -> Vendor:
    stmt = select(Vendor).where(Vendor.user_id == user_id).where(Vendor.name == name)
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing is not None:
        return existing
    obj = Vendor(user_id=user_id, name=name)
    db.add(obj)
    await db.flush()
    return obj
