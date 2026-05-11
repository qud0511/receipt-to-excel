"""Project repository — autocomplete (vendor scoped) + create_or_get."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Project


async def autocomplete(
    db: AsyncSession,
    *,
    user_id: int,
    vendor_id: int,
    prefix: str = "",
    limit: int = 10,
) -> list[Project]:
    """vendor_id 와 user_id 양쪽으로 스코프 — IDOR 차단 + 2-tier UI 의 2차."""
    stmt = select(Project).where(Project.user_id == user_id).where(Project.vendor_id == vendor_id)
    if prefix:
        stmt = stmt.where(Project.name.startswith(prefix))
    stmt = stmt.order_by(
        Project.last_used_at.desc().nulls_last(),
        Project.usage_count.desc(),
        Project.name.asc(),
    ).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def create_or_get(db: AsyncSession, *, user_id: int, vendor_id: int, name: str) -> Project:
    stmt = (
        select(Project)
        .where(Project.user_id == user_id)
        .where(Project.vendor_id == vendor_id)
        .where(Project.name == name)
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing is not None:
        return existing
    obj = Project(user_id=user_id, vendor_id=vendor_id, name=name)
    db.add(obj)
    await db.flush()
    return obj
