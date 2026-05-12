"""GeneratedArtifact repository — POST /generate 결과 영속.

ADR-010 D-4: Session 1:N artifacts (xlsx + pdf + zip). user_id 강제 (IDOR).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ForbiddenError, NotFoundError
from app.db.models import GeneratedArtifact


async def replace_for_session(
    db: AsyncSession,
    *,
    user_id: int,
    session_id: int,
    artifacts: list[GeneratedArtifact],
) -> None:
    """기존 artifacts 삭제 + 신규 적재 — generate 재호출 시 멱등.

    각 row 의 user_id 가 일치해야 add (호출자 실수 차단).
    """
    for a in artifacts:
        if a.user_id != user_id:
            raise ValueError(f"artifact.user_id={a.user_id} != current={user_id}")
        if a.session_id != session_id:
            raise ValueError(f"artifact.session_id={a.session_id} != current={session_id}")

    # 기존 row 제거.
    stmt = select(GeneratedArtifact).where(
        GeneratedArtifact.session_id == session_id,
        GeneratedArtifact.user_id == user_id,
    )
    result = await db.execute(stmt)
    for existing in result.scalars().all():
        await db.delete(existing)

    db.add_all(artifacts)
    await db.flush()


async def list_for_session(
    db: AsyncSession, *, user_id: int, session_id: int,
) -> list[GeneratedArtifact]:
    stmt = (
        select(GeneratedArtifact)
        .where(GeneratedArtifact.session_id == session_id)
        .where(GeneratedArtifact.user_id == user_id)
        .order_by(GeneratedArtifact.id.asc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_by_kind(
    db: AsyncSession, *, user_id: int, session_id: int, artifact_type: str,
) -> GeneratedArtifact:
    """IDOR + 404 — kind 일치 + user 일치."""
    stmt = (
        select(GeneratedArtifact)
        .where(GeneratedArtifact.session_id == session_id)
        .where(GeneratedArtifact.artifact_type == artifact_type)
    )
    result = await db.execute(stmt)
    obj = result.scalar_one_or_none()
    if obj is None:
        raise NotFoundError(f"artifact kind={artifact_type} not found")
    if obj.user_id != user_id:
        raise ForbiddenError("not your resource")
    return obj
