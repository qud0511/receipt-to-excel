"""Phase 2 — Repository 9종의 user_id scoping + autocomplete 정렬 + IDOR 차단."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
import pytest_asyncio
from app.core.errors import ForbiddenError
from app.db.models import Base, Card, Project, Transaction, User, Vendor
from app.db.repositories import (
    card_meta_repo,
    project_repo,
    session_repo,
    transaction_repo,
    vendor_repo,
)
from app.db.session import make_engine, make_session_maker
from sqlalchemy.ext.asyncio import AsyncSession


@pytest_asyncio.fixture
async def db_session(tmp_path: Path) -> AsyncIterator[AsyncSession]:
    engine = make_engine(f"sqlite+aiosqlite:///{tmp_path}/repo.db")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sm = make_session_maker(engine)
    async with sm() as s:
        yield s
    await engine.dispose()


async def _make_user(s: AsyncSession, oid: str, email: str) -> User:
    u = User(oid=oid, email=email, name=oid)
    s.add(u)
    await s.flush()
    return u


# ── 1) session_repo.create 가 user_id 를 스코프로 박는다 ──────────────────────
async def test_session_repo_create_scopes_user_id(db_session: AsyncSession) -> None:
    u = await _make_user(db_session, "u", "u@e.com")
    s = await session_repo.create(
        db_session,
        user_id=u.id,
        year_month="2026-05",
        source_filenames=["receipt_001.pdf"],
    )
    assert s.user_id == u.id
    assert s.year_month == "2026-05"
    assert s.status == "parsing"


# ── 2) transaction_repo.list_for_session 은 session_id + user_id 양쪽 필터 ───
async def test_transaction_repo_list_filters_by_session_and_user(
    db_session: AsyncSession,
) -> None:
    u1 = await _make_user(db_session, "u1", "u1@e.com")
    u2 = await _make_user(db_session, "u2", "u2@e.com")

    s1 = await session_repo.create(
        db_session, user_id=u1.id, year_month="2026-05", source_filenames=["a.pdf"]
    )
    s2 = await session_repo.create(
        db_session, user_id=u2.id, year_month="2026-05", source_filenames=["b.pdf"]
    )

    db_session.add_all(
        [
            Transaction(
                session_id=s1.id,
                user_id=u1.id,
                merchant_name="M1",
                transaction_date=date(2026, 5, 1),
                amount=1000,
                card_provider="신한",
                parser_used="rule_based",
                field_confidence={"merchant_name": "high"},
                source_filename="a.pdf",
                source_file_path="x/a.pdf",
            ),
            Transaction(
                session_id=s2.id,
                user_id=u2.id,
                merchant_name="M2",
                transaction_date=date(2026, 5, 2),
                amount=2000,
                card_provider="신한",
                parser_used="rule_based",
                field_confidence={"merchant_name": "high"},
                source_filename="b.pdf",
                source_file_path="x/b.pdf",
            ),
        ]
    )
    await db_session.flush()

    # u1 자기 세션 — 1건
    items = await transaction_repo.list_for_session(db_session, user_id=u1.id, session_id=s1.id)
    assert len(items) == 1
    assert items[0].merchant_name == "M1"

    # u1 이 u2 세션으로 조회 — IDOR 차단으로 0건
    items = await transaction_repo.list_for_session(db_session, user_id=u1.id, session_id=s2.id)
    assert items == []


# ── 3) vendor_repo.autocomplete — last_used_at DESC NULLS LAST → usage_count DESC ─
async def test_vendor_repo_autocomplete_orders_by_last_used_then_usage(
    db_session: AsyncSession,
) -> None:
    u = await _make_user(db_session, "u", "u@e.com")
    now = datetime(2026, 5, 11, 12, 0, tzinfo=UTC)

    db_session.add_all(
        [
            Vendor(user_id=u.id, name="A", usage_count=10, last_used_at=now - timedelta(days=5)),
            Vendor(user_id=u.id, name="B", usage_count=5, last_used_at=now),
            # C: last_used_at None — NULLS LAST 로 마지막.
            Vendor(user_id=u.id, name="C", usage_count=20, last_used_at=None),
        ]
    )
    await db_session.flush()

    items = await vendor_repo.autocomplete(db_session, user_id=u.id)
    names = [v.name for v in items]
    # B (가장 최근) → A (5일 전) → C (NULL).
    assert names == ["B", "A", "C"]


# ── 4) project_repo.autocomplete 는 vendor_id 로도 스코프 ─────────────────────
async def test_project_repo_autocomplete_scopes_to_vendor(
    db_session: AsyncSession,
) -> None:
    u = await _make_user(db_session, "u", "u@e.com")
    v1 = Vendor(user_id=u.id, name="V1")
    v2 = Vendor(user_id=u.id, name="V2")
    db_session.add_all([v1, v2])
    await db_session.flush()

    db_session.add_all(
        [
            Project(user_id=u.id, vendor_id=v1.id, name="P-V1-A"),
            Project(user_id=u.id, vendor_id=v1.id, name="P-V1-B"),
            Project(user_id=u.id, vendor_id=v2.id, name="P-V2-A"),
        ]
    )
    await db_session.flush()

    items = await project_repo.autocomplete(db_session, user_id=u.id, vendor_id=v1.id)
    names = {p.name for p in items}
    assert names == {"P-V1-A", "P-V1-B"}


# ── 5) card_meta_repo.get_by_masked — AD-2 canonical exact match ─────────────
async def test_card_meta_repo_lookup_by_masked_number_canonical(
    db_session: AsyncSession,
) -> None:
    u = await _make_user(db_session, "u", "u@e.com")
    masked = "1234-****-****-9999"
    c = Card(
        user_id=u.id,
        card_number_masked=masked,
        card_type="개인",
        card_provider="신한",
    )
    db_session.add(c)
    await db_session.flush()

    found = await card_meta_repo.get_by_masked(db_session, user_id=u.id, card_number_masked=masked)
    assert found is not None
    assert found.id == c.id

    # AD-2 canonical 미준수 형식 — 매치 안 됨 (silent 시트 라우팅 실패 방지).
    not_found = await card_meta_repo.get_by_masked(
        db_session, user_id=u.id, card_number_masked="1234999999999999"
    )
    assert not_found is None


# ── 6) IDOR 차단 회귀 — 다른 사용자 리소스 접근 시 ForbiddenError ──────────────
async def test_repository_raises_permission_denied_on_other_user_id(
    db_session: AsyncSession,
) -> None:
    u1 = await _make_user(db_session, "u1", "u1@e.com")
    u2 = await _make_user(db_session, "u2", "u2@e.com")

    s = await session_repo.create(
        db_session, user_id=u1.id, year_month="2026-05", source_filenames=["a.pdf"]
    )

    # 정상 — u1 자신.
    fetched = await session_repo.get(db_session, user_id=u1.id, session_id=s.id)
    assert fetched.id == s.id

    # IDOR — u2 가 u1 의 session 으로 get.
    with pytest.raises(ForbiddenError):
        await session_repo.get(db_session, user_id=u2.id, session_id=s.id)
