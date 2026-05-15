"""Phase 6.9 — 자동완성 + Dashboard 통합 테스트."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from app.db.models import Base
from app.main import create_app
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncEngine


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path / "storage"))
    app = create_app()

    async def _init_db(engine: AsyncEngine) -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_init_db(app.state.db_engine))
    return TestClient(app)


# ── Vendors autocomplete ──────────────────────────────────────────────────────
def test_vendors_autocomplete_returns_empty_for_new_user(client: TestClient) -> None:
    response = client.get("/vendors")
    assert response.status_code == 200
    assert response.json() == []
    assert response.headers.get("cache-control") == "max-age=300"


def test_vendors_autocomplete_with_data(client: TestClient) -> None:
    """Vendor 직접 DB 삽입 후 autocomplete 검증."""
    from app.db.models import User, Vendor

    async def _seed() -> None:
        sm = client.app.state.db_sessionmaker  # type: ignore[attr-defined]
        async with sm() as db:
            user = User(oid="default", name="t", email="t@x")
            db.add(user)
            await db.flush()
            db.add_all([
                Vendor(user_id=user.id, name="신용정보원"),
                Vendor(user_id=user.id, name="신한은행"),
                Vendor(user_id=user.id, name="한국은행"),
            ])
            await db.commit()

    asyncio.run(_seed())

    # prefix '신' → 2 건.
    response = client.get("/vendors?q=신&limit=8")
    assert response.status_code == 200
    names = {v["name"] for v in response.json()}
    assert names == {"신용정보원", "신한은행"}


# ── Projects autocomplete (vendor scope) ──────────────────────────────────────
def test_projects_autocomplete_filters_by_vendor_id(client: TestClient) -> None:
    from app.db.models import Project, User, Vendor

    async def _seed() -> int:
        sm = client.app.state.db_sessionmaker  # type: ignore[attr-defined]
        async with sm() as db:
            user = User(oid="default", name="t", email="t@x")
            db.add(user)
            await db.flush()
            vendor = Vendor(user_id=user.id, name="신용정보원")
            db.add(vendor)
            await db.flush()
            db.add(Project(user_id=user.id, vendor_id=vendor.id, name="차세대 IT"))
            await db.commit()
            return vendor.id  # type: ignore[no-any-return]

    vendor_id = asyncio.run(_seed())
    response = client.get(f"/projects?vendor_id={vendor_id}")
    assert response.status_code == 200
    names = {p["name"] for p in response.json()}
    assert names == {"차세대 IT"}


# ── Team groups + attendees ───────────────────────────────────────────────────
def test_team_groups_returns_nested_members(client: TestClient) -> None:
    from app.db.models import TeamGroup, TeamMember, User

    async def _seed() -> None:
        sm = client.app.state.db_sessionmaker  # type: ignore[attr-defined]
        async with sm() as db:
            user = User(oid="default", name="t", email="t@x")
            db.add(user)
            await db.flush()
            tg = TeamGroup(user_id=user.id, name="개발1팀")
            db.add(tg)
            await db.flush()
            db.add_all([
                TeamMember(team_group_id=tg.id, name="홍길동"),
                TeamMember(team_group_id=tg.id, name="김지호"),
            ])
            await db.commit()

    asyncio.run(_seed())
    response = client.get("/team-groups")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["name"] == "개발1팀"
    member_names = {m["name"] for m in body[0]["members"]}
    assert member_names == {"홍길동", "김지호"}


def test_attendees_filter_by_q(client: TestClient) -> None:
    from app.db.models import TeamGroup, TeamMember, User

    async def _seed() -> None:
        sm = client.app.state.db_sessionmaker  # type: ignore[attr-defined]
        async with sm() as db:
            user = User(oid="default", name="t", email="t@x")
            db.add(user)
            await db.flush()
            tg = TeamGroup(user_id=user.id, name="개발1팀")
            db.add(tg)
            await db.flush()
            db.add_all([
                TeamMember(team_group_id=tg.id, name="홍길동"),
                TeamMember(team_group_id=tg.id, name="김지호"),
                TeamMember(team_group_id=tg.id, name="박서연"),
            ])
            await db.commit()

    asyncio.run(_seed())
    response = client.get("/attendees?q=홍")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["name"] == "홍길동"
    assert body[0]["team"] == "개발1팀"


# ── Dashboard summary ─────────────────────────────────────────────────────────
def test_dashboard_summary_empty_user(client: TestClient) -> None:
    """신규 사용자 — 모든 metric 0 + recent list 빈."""
    response = client.get("/dashboard/summary")
    assert response.status_code == 200
    body = response.json()
    assert body["this_month"]["total_amount"] == 0
    assert body["this_month"]["transaction_count"] == 0
    assert body["this_year"]["completed_count"] == 0
    assert body["recent_expense_reports"] == []
