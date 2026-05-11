"""DB 엔진/세션 팩토리 + FastAPI ``get_db`` dependency.

CLAUDE.md §"성능": async def 기본 + 블로킹 작업은 to_thread.
CLAUDE.md §"보안": 모든 변경 쿼리에 ``WHERE user_id = :current`` (Repository 책임).
"""

from __future__ import annotations

import re
from collections.abc import AsyncIterator
from pathlib import Path

from fastapi import Request
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# 로컬 SQLite URL 에서 디렉토리 경로 추출 — 부팅 시 mkdir 보장.
_SQLITE_FILE_RE = re.compile(r"^sqlite\+aiosqlite:///(?P<path>[^?]+)")


def _ensure_sqlite_dir(database_url: str) -> None:
    """``sqlite+aiosqlite:///storage/app.db`` 같은 URL 의 부모 디렉토리 보장."""
    m = _SQLITE_FILE_RE.match(database_url)
    if not m:
        return
    raw_path = m.group("path")
    if raw_path == ":memory:":
        return
    Path(raw_path).parent.mkdir(parents=True, exist_ok=True)


def make_engine(database_url: str, *, echo: bool = False) -> AsyncEngine:
    _ensure_sqlite_dir(database_url)
    return create_async_engine(database_url, echo=echo, future=True)


def make_session_maker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    """모든 변경 라우터의 단일 DB 세션 진입점."""
    sm: async_sessionmaker[AsyncSession] = request.app.state.db_sessionmaker
    async with sm() as session:
        yield session
