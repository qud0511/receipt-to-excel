"""Template repository — Phase 6.8 CRUD 확장."""

from __future__ import annotations

from typing import Any

from sqlalchemy import delete, select
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


async def create(
    db: AsyncSession,
    *,
    user_id: int,
    name: str,
    file_path: str,
    sheets_json: dict[str, Any],
    mapping_status: str = "mapped",
    is_default: bool = False,
) -> Template:
    obj = Template(
        user_id=user_id,
        name=name,
        file_path=file_path,
        sheets_json=sheets_json,
        mapping_status=mapping_status,
        is_default=is_default,
    )
    db.add(obj)
    await db.flush()
    return obj


async def update_meta(
    db: AsyncSession,
    *,
    user_id: int,
    template_id: int,
    name: str | None = None,
) -> Template:
    """메타 (name) 갱신. Phase 6.8b 의 PATCH cells/mapping 과 분리."""
    template = await get(db, user_id=user_id, template_id=template_id)
    if name is not None:
        template.name = name
    await db.flush()
    return template


async def delete_by_id(db: AsyncSession, *, user_id: int, template_id: int) -> None:
    """IDOR 차단 — get() 통과 후 삭제."""
    template = await get(db, user_id=user_id, template_id=template_id)
    stmt = delete(Template).where(Template.id == template.id)
    await db.execute(stmt)
    await db.flush()
