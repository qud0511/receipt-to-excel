"""UploadSession repository — create / get / list_for_user."""

from __future__ import annotations

from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ForbiddenError, NotFoundError
from app.db.models import UploadSession


async def create(
    db: AsyncSession,
    *,
    user_id: int,
    year_month: str,
    source_filenames: list[str],
    status: Literal["parsing", "review", "generated", "failed"] = "parsing",
    template_id: int | None = None,
    batch_card_type: Literal["법인", "개인"] | None = None,
) -> UploadSession:
    obj = UploadSession(
        user_id=user_id,
        year_month=year_month,
        source_filenames=source_filenames,
        status=status,
        template_id=template_id,
        batch_card_type=batch_card_type,
    )
    db.add(obj)
    await db.flush()
    return obj


async def get(db: AsyncSession, *, user_id: int, session_id: int) -> UploadSession:
    """user_id 와 session_id 가 모두 매치돼야만 반환 — 그 외에는 ForbiddenError.

    IDOR 차단의 게이트키퍼. 존재 자체를 노출하지 않으려면 NotFoundError 가 더 안전하지만
    감사 추적 위해 'Forbidden' 시그널을 유지한다 (사양 따름).
    """
    obj = await db.get(UploadSession, session_id)
    if obj is None:
        raise NotFoundError(f"UploadSession {session_id} not found")
    if obj.user_id != user_id:
        raise ForbiddenError("not your resource")
    return obj


async def list_for_user(db: AsyncSession, *, user_id: int) -> list[UploadSession]:
    stmt = (
        select(UploadSession)
        .where(UploadSession.user_id == user_id)
        .order_by(UploadSession.created_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())
