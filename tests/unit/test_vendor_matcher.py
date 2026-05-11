"""Phase 4.7 — VendorMatcher 3 케이스 (autocomplete top-8 정렬)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest_asyncio
from app.db.models import Base, User, Vendor
from app.db.session import make_engine, make_session_maker
from app.services.resolvers.vendor_matcher import DEFAULT_LIMIT, autocomplete
from sqlalchemy.ext.asyncio import AsyncSession


@pytest_asyncio.fixture
async def db_session(tmp_path: Path) -> AsyncIterator[AsyncSession]:
    engine = make_engine(f"sqlite+aiosqlite:///{tmp_path}/vendor.db")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sm = make_session_maker(engine)
    async with sm() as s:
        yield s
    await engine.dispose()


async def _make_user(s: AsyncSession) -> User:
    u = User(oid="u", email="u@e.com", name="u")
    s.add(u)
    await s.flush()
    return u


# ── 1) last_used_at DESC NULLS LAST ─────────────────────────────────────────
async def test_autocomplete_orders_by_last_used_desc(db_session: AsyncSession) -> None:
    u = await _make_user(db_session)
    now = datetime(2026, 5, 11, 12, 0, tzinfo=UTC)

    db_session.add_all(
        [
            Vendor(user_id=u.id, name="가장오래전", last_used_at=now - timedelta(days=30)),
            Vendor(user_id=u.id, name="최근", last_used_at=now),
            Vendor(user_id=u.id, name="중간", last_used_at=now - timedelta(days=5)),
        ]
    )
    await db_session.flush()

    items = await autocomplete(db_session, user_id=u.id)
    names = [v.name for v in items]
    assert names == ["최근", "중간", "가장오래전"]


# ── 2) last_used_at 동일 시 usage_count DESC tiebreak ──────────────────────
async def test_autocomplete_ties_broken_by_usage_count_desc(
    db_session: AsyncSession,
) -> None:
    u = await _make_user(db_session)
    same_time = datetime(2026, 5, 11, 12, 0, tzinfo=UTC)

    db_session.add_all(
        [
            Vendor(user_id=u.id, name="저빈도", usage_count=3, last_used_at=same_time),
            Vendor(user_id=u.id, name="고빈도", usage_count=15, last_used_at=same_time),
            Vendor(user_id=u.id, name="중빈도", usage_count=8, last_used_at=same_time),
        ]
    )
    await db_session.flush()

    items = await autocomplete(db_session, user_id=u.id)
    names = [v.name for v in items]
    assert names == ["고빈도", "중빈도", "저빈도"]


# ── 3) 기본 limit=8 — 10개 입력 → 8개 반환 ──────────────────────────────────
async def test_autocomplete_returns_top_8_by_default(db_session: AsyncSession) -> None:
    u = await _make_user(db_session)
    now = datetime(2026, 5, 11, 12, 0, tzinfo=UTC)

    # 10개 vendor — 다른 last_used_at 으로 정렬 결정성 확보.
    db_session.add_all(
        [
            Vendor(user_id=u.id, name=f"v{i:02d}", last_used_at=now - timedelta(days=i))
            for i in range(10)
        ]
    )
    await db_session.flush()

    items = await autocomplete(db_session, user_id=u.id)
    assert len(items) == DEFAULT_LIMIT == 8
    # 가장 최근 8개 (v00..v07).
    assert {v.name for v in items} == {f"v{i:02d}" for i in range(8)}
