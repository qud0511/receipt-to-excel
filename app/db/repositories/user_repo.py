"""User repository — Azure AD oid → DB User row 매핑.

ADR-010 D-3 후속: 모든 API 라우터의 ``Depends(get_current_user)`` 가 ``UserInfo.oid``
반환 → DB user_id (int) 가 필요한 모든 작업에서 본 helper 통과.

stub 모드 (REQUIRE_AUTH=false) 에서는 oid="default" 가 자동 생성 — 로컬 개발 / e2e 테스트.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User


async def get_or_create_by_oid(
    db: AsyncSession,
    *,
    oid: str,
    name: str = "",
    email: str = "",
) -> User:
    """oid 매칭 User 반환, 없으면 생성. email 충돌 시 갱신 없이 기존 row 반환.

    호출자 (Sessions / Templates API) 는 본 helper 의 ``User.id`` 를 ``user_id``
    parameter 로 모든 다른 repository 에 전달.
    """
    stmt = select(User).where(User.oid == oid)
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()
    if existing is not None:
        return existing

    # 신규 사용자 — email 가 unique 라 충돌 회피 위해 oid 기반 placeholder.
    safe_email = email or f"{oid}@local.invalid"
    obj = User(oid=oid, name=name, email=safe_email)
    db.add(obj)
    await db.flush()
    return obj


async def get_by_id(db: AsyncSession, *, user_id: int) -> User:
    """PK 로 User 조회. 잡 컨텍스트(user_id 만 보유)에서 baseline 갱신용."""
    user = await db.get(User, user_id)
    if user is None:
        raise ValueError(f"user {user_id} not found")
    return user
