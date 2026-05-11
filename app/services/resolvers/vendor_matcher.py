"""VendorMatcher — autocomplete 의 서비스 진입점. 기본 top-8.

vendor_repo.autocomplete 의 wrapper — 라우터가 본 모듈을 의존성으로 받는다
(repository 직접 호출 시 service layer 추상화 누락).
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Vendor
from app.db.repositories import vendor_repo

DEFAULT_LIMIT = 8


async def autocomplete(
    db: AsyncSession,
    *,
    user_id: int,
    prefix: str = "",
    limit: int = DEFAULT_LIMIT,
) -> list[Vendor]:
    """vendor_repo.autocomplete 동일 시그니처 + 기본 limit=8 (UI 자동완성 표시 한계)."""
    return await vendor_repo.autocomplete(db, user_id=user_id, prefix=prefix, limit=limit)
