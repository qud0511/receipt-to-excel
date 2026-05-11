"""Phase 2 — 11 SQLAlchemy 모델의 유니크/cascade/JSON 라운드트립/accessor 검증."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import date
from pathlib import Path

import pytest
import pytest_asyncio
from app.db.models import (
    Base,
    Card,
    ExpenseRecord,
    Project,
    TeamGroup,
    TeamMember,
    Transaction,
    UploadSession,
    User,
    Vendor,
)
from app.db.session import make_engine, make_session_maker
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


@pytest_asyncio.fixture
async def session(tmp_path: Path) -> AsyncIterator[AsyncSession]:
    engine = make_engine(f"sqlite+aiosqlite:///{tmp_path}/models.db")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sm = make_session_maker(engine)
    async with sm() as s:
        yield s
    await engine.dispose()


async def _make_user(s: AsyncSession, oid: str, email: str) -> User:
    u = User(oid=oid, email=email, name="tester")
    s.add(u)
    await s.flush()
    return u


# ── 1) User.oid unique ────────────────────────────────────────────────────────
async def test_user_unique_oid(session: AsyncSession) -> None:
    session.add(User(oid="oid-1", email="a@e.com", name="a"))
    await session.flush()
    session.add(User(oid="oid-1", email="b@e.com", name="b"))
    with pytest.raises(IntegrityError):
        await session.flush()


# ── 2) Card.card_number_masked unique per user ────────────────────────────────
async def test_card_unique_number_per_user(session: AsyncSession) -> None:
    u1 = await _make_user(session, "u1", "u1@e.com")
    u2 = await _make_user(session, "u2", "u2@e.com")

    masked = "1234-****-****-9999"
    session.add(
        Card(
            user_id=u1.id,
            card_number_masked=masked,
            card_type="개인",
            card_provider="신한",
        )
    )
    await session.flush()

    # 다른 사용자에게 같은 마스킹 번호는 허용 (시나리오: 가족 카드 분리).
    session.add(
        Card(
            user_id=u2.id,
            card_number_masked=masked,
            card_type="개인",
            card_provider="신한",
        )
    )
    await session.flush()

    # 같은 사용자에게는 중복 거부.
    session.add(
        Card(
            user_id=u1.id,
            card_number_masked=masked,
            card_type="개인",
            card_provider="신한",
        )
    )
    with pytest.raises(IntegrityError):
        await session.flush()


# ── 3) Vendor.name unique per user ───────────────────────────────────────────
async def test_vendor_unique_name_per_user(session: AsyncSession) -> None:
    u1 = await _make_user(session, "u1", "u1@e.com")
    u2 = await _make_user(session, "u2", "u2@e.com")

    session.add(Vendor(user_id=u1.id, name="스타벅스코리아"))
    await session.flush()

    # 다른 사용자는 같은 이름 OK
    session.add(Vendor(user_id=u2.id, name="스타벅스코리아"))
    await session.flush()

    session.add(Vendor(user_id=u1.id, name="스타벅스코리아"))
    with pytest.raises(IntegrityError):
        await session.flush()


# ── 4) Project.name unique per vendor ────────────────────────────────────────
async def test_project_unique_name_per_vendor(session: AsyncSession) -> None:
    u = await _make_user(session, "u", "u@e.com")
    v1 = Vendor(user_id=u.id, name="벤더A")
    v2 = Vendor(user_id=u.id, name="벤더B")
    session.add_all([v1, v2])
    await session.flush()

    session.add(Project(user_id=u.id, vendor_id=v1.id, name="프로젝트1"))
    await session.flush()

    # 다른 vendor 는 같은 이름 OK
    session.add(Project(user_id=u.id, vendor_id=v2.id, name="프로젝트1"))
    await session.flush()

    session.add(Project(user_id=u.id, vendor_id=v1.id, name="프로젝트1"))
    with pytest.raises(IntegrityError):
        await session.flush()


# ── 5) TeamMember cascade on TeamGroup delete ────────────────────────────────
async def test_team_group_member_cascade_on_delete(session: AsyncSession) -> None:
    u = await _make_user(session, "u", "u@e.com")
    tg = TeamGroup(user_id=u.id, name="개발1팀")
    session.add(tg)
    await session.flush()

    tm = TeamMember(team_group_id=tg.id, name="홍길동")
    session.add(tm)
    await session.flush()
    tm_id = tm.id

    await session.delete(tg)
    await session.flush()
    session.expire_all()

    result = await session.execute(select(TeamMember).where(TeamMember.id == tm_id))
    assert result.scalar_one_or_none() is None


# ── 6) UploadSession.get_year_month accessor (R12) ───────────────────────────
async def test_upload_session_get_year_month_accessor(session: AsyncSession) -> None:
    u = await _make_user(session, "u", "u@e.com")
    upload = UploadSession(
        user_id=u.id,
        year_month="2026-05",
        source_filenames=["receipt_001.pdf", "receipt_002.pdf"],
        status="parsing",
    )
    session.add(upload)
    await session.flush()
    assert upload.get_year_month() == "2026-05"


# ── 7) Transaction.field_confidence JSON round-trip ──────────────────────────
async def test_transaction_field_confidence_json_round_trip(
    session: AsyncSession,
) -> None:
    u = await _make_user(session, "u", "u@e.com")
    upload = UploadSession(
        user_id=u.id,
        year_month="2026-05",
        source_filenames=["r.pdf"],
        status="parsing",
    )
    session.add(upload)
    await session.flush()

    confidence = {
        "merchant_name": "high",
        "transaction_date": "high",
        "amount": "medium",
        "approval_number": "low",
    }
    tx = Transaction(
        session_id=upload.id,
        user_id=u.id,
        merchant_name="스타벅스",
        transaction_date=date(2026, 5, 10),
        amount=4500,
        card_provider="신한",
        parser_used="rule_based",
        field_confidence=confidence,
        source_filename="r.pdf",
        source_file_path="storage/users/u/uploads/1/r.pdf",
    )
    session.add(tx)
    await session.flush()
    tx_id = tx.id
    session.expire_all()

    fetched = await session.get(Transaction, tx_id)
    assert fetched is not None
    assert fetched.field_confidence == confidence


# ── 8) ExpenseRecord.attendees_json round-trip ───────────────────────────────
async def test_expense_record_attendees_json_round_trip(
    session: AsyncSession,
) -> None:
    u = await _make_user(session, "u", "u@e.com")
    v = Vendor(user_id=u.id, name="갈비집")
    session.add(v)
    await session.flush()
    upload = UploadSession(
        user_id=u.id,
        year_month="2026-05",
        source_filenames=["r.pdf"],
        status="review",
    )
    session.add(upload)
    await session.flush()

    tx = Transaction(
        session_id=upload.id,
        user_id=u.id,
        merchant_name="갈비집",
        transaction_date=date(2026, 5, 9),
        amount=150_000,
        card_provider="신한",
        parser_used="rule_based",
        field_confidence={"merchant_name": "high"},
        source_filename="r.pdf",
        source_file_path="storage/users/u/uploads/1/r.pdf",
    )
    session.add(tx)
    await session.flush()

    attendees = ["김철수", "이영희", "박민수"]
    er = ExpenseRecord(
        transaction_id=tx.id,
        user_id=u.id,
        vendor_id=v.id,
        attendees_json=attendees,
        headcount=3,
        xlsx_sheet="법인",
        expense_column="식대",
        auto_note="회식",
    )
    session.add(er)
    await session.flush()
    er_id = er.id
    session.expire_all()

    fetched = await session.get(ExpenseRecord, er_id)
    assert fetched is not None
    assert fetched.attendees_json == attendees
