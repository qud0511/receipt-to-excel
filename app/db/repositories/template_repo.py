"""Template repository — minimal stub. Phase 5 에서 확장."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ForbiddenError, NotFoundError
from app.db.models import Template


async def list_for_user(db: AsyncSession, *, user_id: int) -> list[Template]:
    stmt = (
        select(Template)
        .where(Template.user_id == user_id)
        .order_by(Template.is_default.desc(), Template.created_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get(db: AsyncSession, *, user_id: int, template_id: int) -> Template:
    obj = await db.get(Template, template_id)
    if obj is None:
        raise NotFoundError(f"Template {template_id} not found")
    if obj.user_id != user_id:
        raise ForbiddenError("not your resource")
    return obj
