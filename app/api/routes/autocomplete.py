"""Phase 6.9 — 자동완성 endpoint 4 종.

ADR-010 D-5: Cache-Control: max-age=300 (클라이언트 캐시 5분).
ADR-010 추천 6: 참석자 hybrid (autocomplete + team_group chip).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.models import TeamMember
from app.db.repositories import (
    project_repo,
    team_group_repo,
    user_repo,
    vendor_repo,
)
from app.schemas.auth import UserInfo
from app.schemas.autocomplete import (
    AttendeeView,
    ProjectView,
    TeamGroupView,
    TeamMemberView,
    VendorView,
)

router = APIRouter(tags=["autocomplete"])

_CACHE_HEADER = {"Cache-Control": "max-age=300"}


async def _get_db(request: Request) -> AsyncIterator[AsyncSession]:
    sessionmaker = request.app.state.db_sessionmaker
    async with sessionmaker() as session:
        yield session


@router.get("/vendors", response_model=list[VendorView])
async def autocomplete_vendors(
    response: Response,
    user: Annotated[UserInfo, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(_get_db)],
    q: Annotated[str, Query()] = "",
    limit: Annotated[int, Query(ge=1, le=50)] = 8,
) -> list[VendorView]:
    """Vendor autocomplete — 최근 사용 우선 + prefix 매칭."""
    db_user = await user_repo.get_or_create_by_oid(db, oid=user.oid, name=user.name)
    vendors = await vendor_repo.autocomplete(
        db,
        user_id=db_user.id,
        prefix=q,
        limit=limit,
    )
    response.headers.update(_CACHE_HEADER)
    return [
        VendorView(
            id=v.id,
            name=v.name,
            last_used_at=v.last_used_at,
            usage_count=v.usage_count,
        )
        for v in vendors
    ]


@router.get("/projects", response_model=list[ProjectView])
async def autocomplete_projects(
    response: Response,
    user: Annotated[UserInfo, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(_get_db)],
    vendor_id: Annotated[int, Query(ge=0)] = 0,
    q: Annotated[str, Query()] = "",
    limit: Annotated[int, Query(ge=1, le=50)] = 8,
) -> list[ProjectView]:
    """Project autocomplete — vendor scope 강제 (IDOR + 2-tier UI)."""
    db_user = await user_repo.get_or_create_by_oid(db, oid=user.oid, name=user.name)
    projects = await project_repo.autocomplete(
        db,
        user_id=db_user.id,
        vendor_id=vendor_id,
        prefix=q,
        limit=limit,
    )
    response.headers.update(_CACHE_HEADER)
    return [
        ProjectView(
            id=p.id,
            vendor_id=p.vendor_id,
            name=p.name,
            last_used_at=p.last_used_at,
            usage_count=p.usage_count,
        )
        for p in projects
    ]


@router.get("/team-groups", response_model=list[TeamGroupView])
async def list_team_groups(
    response: Response,
    user: Annotated[UserInfo, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(_get_db)],
) -> list[TeamGroupView]:
    """팀 → 멤버 nested. UI Verify 의 team chip 선택 (ADR-010 추천 6 hybrid)."""
    db_user = await user_repo.get_or_create_by_oid(db, oid=user.oid, name=user.name)
    groups = await team_group_repo.list_for_user(db, user_id=db_user.id)
    result: list[TeamGroupView] = []
    for g in groups:
        # Lazy load 회피 — 명시적 query.
        stmt = select(TeamMember).where(TeamMember.team_group_id == g.id)
        members = list((await db.execute(stmt)).scalars().all())
        result.append(
            TeamGroupView(
                id=g.id,
                name=g.name,
                members=[TeamMemberView(id=m.id, name=m.name) for m in members],
            ),
        )
    response.headers.update(_CACHE_HEADER)
    return result


@router.get("/attendees", response_model=list[AttendeeView])
async def autocomplete_attendees(
    response: Response,
    user: Annotated[UserInfo, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(_get_db)],
    q: Annotated[str, Query()] = "",
) -> list[AttendeeView]:
    """모든 팀 멤버 평탄화 + name 부분 일치 검색 (free text autocomplete)."""
    db_user = await user_repo.get_or_create_by_oid(db, oid=user.oid, name=user.name)
    groups = await team_group_repo.list_for_user(db, user_id=db_user.id)
    out: list[AttendeeView] = []
    for g in groups:
        stmt = select(TeamMember).where(TeamMember.team_group_id == g.id)
        for m in (await db.execute(stmt)).scalars().all():
            if q and q not in m.name:
                continue
            out.append(AttendeeView(name=m.name, team=g.name))
    response.headers.update(_CACHE_HEADER)
    return out
